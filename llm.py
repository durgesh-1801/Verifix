"""LLM comparison layer — calls Groq (llama-3.1-8b-instant) to compare Invoice vs PO.

Key fixes vs original:
  - Prompt now EXPLICITLY instructs the model to quote verbatim text from the documents.
  - Two-pass JSON extraction (regex before json.loads) eliminates markdown fencing issues.
  - Input guard: refuses to call the API if either document is empty/too short.
  - Debug: logs the raw model output so you can inspect hallucinations instantly.
  - Returns a stable schema: {"discrepancies": [...], "summary": "...", "error": "..."|None}
"""

from __future__ import annotations

import json
import logging
import os
import re

import requests

logger = logging.getLogger(__name__)

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_MODEL = "llama-3.1-8b-instant"
_TIMEOUT = 60
_MIN_TEXT_LEN = 40  # guard against passing blank / garbage text to the LLM


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You are a document auditor. "
    "You read an Invoice and a Purchase Order (PO) supplied by the user. "
    "You ONLY use information that is literally present in those two documents. "
    "You NEVER invent item names, quantities, or prices. "
    "If a value is not readable in the text, say 'unreadable'."
)

_USER_TEMPLATE = """
Compare the following Invoice and Purchase Order.

STRICT RULES:
- ONLY return mismatches
- If everything matches, return an EMPTY list []
- DO NOT return matches
- DO NOT explain correct values
- DO NOT create fields like tax, total, other

ONLY check:
1. price mismatch
2. quantity mismatch
3. missing items

Rules:
- If item exists in both -> compare price and quantity ONLY
- If item exists in PO but not in Invoice -> "missing_in_invoice"
- If item exists in Invoice but not in PO -> "missing_in_po"
- DO NOT duplicate entries
- DO NOT hallucinate fields

Invoice:
{invoice_text}

PO:
{po_text}

Return STRICT JSON:

{{
  "discrepancies": [
    {{
      "item": "",
      "field": "",
      "invoice_value": "",
      "po_value": "",
      "issue": ""
    }}
  ]
}}
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json(raw: str) -> str:
    """Strip markdown fences and return the first JSON object found."""
    # Remove ```json ... ``` or ``` ... ```
    raw = re.sub(r"```[a-z]*", "", raw).replace("```", "").strip()
    # Find the outermost { ... }
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return match.group(0)
    return raw


def _safe_parse(raw: str) -> dict:
    cleaned = _extract_json(raw)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("JSON parse failed: %s\nRaw content was:\n%s", exc, raw[:800])
        raise
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed)}")
    return parsed


def normalize_field(field):
    if not field:
        return "missing_in_invoice"

    field = field.lower().strip()

    if field in ["qty", "quantity"]:
        return "quantity"
    if field in ["price", "rate"]:
        return "price"
    if "missing" in field:
        return field

    return field


def normalize_issues(discrepancies):
    fixed = []

    for d in discrepancies:
        item = d.get("item")
        field = d.get("field", "").lower()
        inv = d.get("invoice_value")
        po = d.get("po_value")
        issue = d.get("issue", "").lower()

        # Fix wrong "missing" when both values exist
        if inv not in [None, "", "unreadable"] and po not in [None, "", "unreadable"]:
            if inv != po:
                if "qty" in field or "quantity" in field:
                    issue = "quantity mismatch"
                elif "price" in field:
                    issue = "price mismatch"

        # Fix actual missing
        elif inv in [None, "", "unreadable"] and po not in [None, "", "unreadable"]:
            issue = "missing_in_invoice"
        elif po in [None, "", "unreadable"] and inv not in [None, "", "unreadable"]:
            issue = "missing_in_po"

        d["issue"] = issue
        fixed.append(d)

    return fixed


def safe_number(value):
    try:
        value = str(value).replace(",", "").replace("₹", "").strip()
        return float(value)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compare_invoice_po(invoice_text: str, po_text: str) -> dict:
    """
    Compare extracted invoice and PO text via Groq.

    Returns:
        {
            "discrepancies": [...],
            "summary": "...",
            "error": None | "<message>"
        }
    """
    # --- Input guard ---
    if len(invoice_text.strip()) < _MIN_TEXT_LEN:
        msg = (
            f"Invoice text is too short ({len(invoice_text.strip())} chars). "
            "OCR may have failed. Check the uploaded file."
        )
        logger.error(msg)
        return {"discrepancies": [], "summary": "", "error": msg}

    if len(po_text.strip()) < _MIN_TEXT_LEN:
        msg = (
            f"PO text is too short ({len(po_text.strip())} chars). "
            "OCR may have failed. Check the uploaded file."
        )
        logger.error(msg)
        return {"discrepancies": [], "summary": "", "error": msg}

    # --- API key ---
    groq_api_key = os.getenv("GROQ_API_KEY")
    if not groq_api_key:
        return {"discrepancies": [], "summary": "", "error": "Missing GROQ_API_KEY env var."}

    # --- Build request ---
    prompt = f"""
You are an expert invoice auditor.

Compare the Invoice and Purchase Order carefully.

STRICT RULES (DO NOT VIOLATE):

1. If an item exists in BOTH documents:
   - If quantity differs → issue = "quantity mismatch"
   - If price differs → issue = "price mismatch"
   - DO NOT mark it as missing

2. If item exists ONLY in Invoice:
   → issue = "missing_in_po"

3. If item exists ONLY in PO:
   → issue = "missing_in_invoice"

4. NEVER confuse mismatch with missing

5. Use EXACT item names from text

6. If a value is not readable:
   → use "unreadable"

7. Output ONLY valid JSON
   - No explanation
   - No markdown
   - No extra text

FORMAT:
{{
  "discrepancies": [
    {{
      "item": "...",
      "field": "...",
      "invoice_value": "...",
      "po_value": "...",
      "issue": "..."
    }}
  ]
}}

---

INVOICE:
{invoice_text}

---

PO:
{po_text}
"""

    payload = {
        "model": _MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {groq_api_key}",
        "Content-Type": "application/json",
    }

    # --- Call Groq ---
    try:
        response = requests.post(_GROQ_URL, headers=headers, json=payload, timeout=_TIMEOUT)
        response.raise_for_status()
    except requests.HTTPError as exc:
        logger.error("Groq HTTP error %s: %s", exc.response.status_code, exc.response.text[:400])
        return {"discrepancies": [], "summary": "", "error": str(exc)}
    except requests.RequestException as exc:
        logger.error("Groq request failed: %s", exc)
        return {"discrepancies": [], "summary": "", "error": str(exc)}

    raw_content = response.json()["choices"][0]["message"]["content"].strip()
    logger.debug("=== RAW LLM OUTPUT ===\n%s\n=== END ===", raw_content)

    # --- Parse ---
    try:
        parsed = _safe_parse(raw_content)
    except (json.JSONDecodeError, ValueError) as exc:
        return {
            "discrepancies": [],
            "summary": "",
            "error": f"LLM returned unparseable JSON: {exc}. Raw: {raw_content[:300]}",
        }

    discrepancies = parsed.get("discrepancies", [])
    if not isinstance(discrepancies, list):
        discrepancies = []
    parsed["discrepancies"] = normalize_issues(discrepancies)

    cleaned = []
    seen = set()

    for d in parsed["discrepancies"]:
        if not isinstance(d, dict):
            continue

        item = d.get("item")
        field = str(d.get("field", "")).lower().strip()
        inv = str(d.get("invoice_value", "")).strip()
        po = str(d.get("po_value", "")).strip()
        issue = d.get("issue", "")
        issue_text = str(issue).lower().strip()
        inv_clean = str(inv).strip()
        po_clean = str(po).strip()

        # Skip empty item
        if not item:
            continue

        # Remove fake/no-issue rows
        if any(word in issue_text for word in ["no issue", "matched", "same", "identical", "correct"]):
            continue

        # Normalize fields
        if field in ["qty", "quantity"]:
            field = "quantity"
        elif field in ["price", "rate"]:
            field = "price"

        d["field"] = field

        # Normalize missing values
        if inv.lower() in ["unreadable", "", "none"]:
            d["invoice_value"] = "N/A"

        if po.lower() in ["unreadable", "", "none"]:
            d["po_value"] = "N/A"

        # Deterministic rupee difference (computed in Python, never by LLM)
        inv_num = safe_number(inv)
        po_num = safe_number(po)

        if inv_num is not None and po_num is not None:
            diff = abs(inv_num - po_num)

            # Remove decimal if whole number
            if diff.is_integer():
                diff = int(diff)

            d["difference"] = str(diff)
        else:
            d["difference"] = "N/A"

        # Remove rows where values are identical and difference is zero
        if inv_clean == po_clean and d["difference"] == "0":
            continue

        # Remove false "missing" rows when values are actually equal
        if "missing" in issue_text and inv_clean == po_clean:
            continue

        # Keep previous identical-value filter for non-missing issues
        if inv_clean == po_clean and "missing" not in issue_text:
            continue

        # Remove duplicates
        key = (item, field, d.get("invoice_value"), d.get("po_value"))
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(d)

    parsed["discrepancies"] = cleaned
    return parsed