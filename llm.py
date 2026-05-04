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

_USER_TEMPLATE = """Below are two documents. Read them carefully.

=== INVOICE (verbatim extracted text) ===
{invoice_text}

=== PURCHASE ORDER (verbatim extracted text) ===
{po_text}

Your task:
1. Identify every line item in the Invoice and the matching line item in the PO.
2. Compare: unit price, quantity, total, tax, and any terms.
3. Note items present in one document but missing in the other.
4. Use the EXACT item names/descriptions as they appear in the text above.

Respond with ONLY a JSON object — no markdown fences, no explanation:

{{
  "discrepancies": [
    {{
      "item": "<exact item name from document>",
      "field": "<price | quantity | total | tax | missing_in_invoice | missing_in_po | other>",
      "invoice_value": "<value as written in Invoice, or 'N/A'>",
      "po_value": "<value as written in PO, or 'N/A'>",
      "issue": "<one-sentence plain-English description>"
    }}
  ],
  "summary": "<2-3 sentence overall summary of match quality>"
}}

If the documents match perfectly, return:
{{ "discrepancies": [], "summary": "Invoice and PO match on all compared fields." }}
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
    user_prompt = _USER_TEMPLATE.format(
        invoice_text=invoice_text.strip(),
        po_text=po_text.strip(),
    )

    payload = {
        "model": _MODEL,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_prompt},
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

    return {
        "discrepancies": discrepancies,
        "summary": parsed.get("summary", ""),
        "error": None,
    }