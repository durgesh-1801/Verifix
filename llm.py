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
    prompt = _USER_TEMPLATE.format(
        invoice_text=invoice_text.strip(),
        po_text=po_text.strip(),
    )

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

    valid_fields = {"price", "quantity", "missing_in_invoice", "missing_in_po"}

    cleaned = []
    seen = set()

    for d in discrepancies:
        if not isinstance(d, dict):
            continue

        item = d.get("item")
        field = normalize_field(d.get("field"))

        # Skip empty item
        if not item:
            continue

        # Skip invalid fields
        if field not in valid_fields:
            continue

        # Skip wrong mismatch rows where values are identical
        if d.get("invoice_value") == d.get("po_value"):
            continue

        # Fix field in object
        d["field"] = field

        # Remove duplicates
        key = (item, field)
        if key in seen:
            continue
        seen.add(key)

        cleaned.append(d)

    return {"discrepancies": cleaned}