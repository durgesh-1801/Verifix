"""extractors/llm_structured_extractor.py

LLM-powered structured extraction of invoice / PO line items from noisy OCR text.

Pipeline
--------
OCR text  ->  LLM prompt  ->  raw JSON string  ->  validate  ->  structured dict
                                                        |
                                              (on failure) fallback
                                                        |
                                             parser.build_structured_document()

Provider selection (env var LLM_PROVIDER, default "groq"):
    groq      - Groq API  (GROQ_API_KEY, GROQ_MODEL)
    gemini    - Google Gemini  (GEMINI_API_KEY)
    openai    - OpenAI  (OPENAI_API_KEY, OPENAI_MODEL)
    anthropic - Anthropic Claude  (ANTHROPIC_API_KEY, ANTHROPIC_MODEL)

All non-default providers degrade gracefully: if the required SDK is not installed
or the API key is missing, the next provider in the fallback chain is tried.
If all LLM providers fail, the existing regex parser is used automatically.

Diagnostics
-----------
Every key stage emits a structured log line prefixed with [LLM-EXTRACT] so you
can grep for them in the Flask terminal.
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_LLM_PROVIDER   = os.getenv("LLM_PROVIDER", "groq").lower().strip()
_GROQ_API_KEY   = os.getenv("GROQ_API_KEY", "")
_GROQ_MODEL     = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
_GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
_GEMINI_MODEL   = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
_ANTHROPIC_KEY  = os.getenv("ANTHROPIC_API_KEY", "")
_ANTHROPIC_MODEL= os.getenv("ANTHROPIC_MODEL", "claude-3-haiku-20240307")

# Maximum OCR chars sent to LLM (avoids token-limit errors on giant scans)
_MAX_OCR_CHARS = int(os.getenv("LLM_MAX_OCR_CHARS", "4000"))

# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """You are a precise document parsing assistant.
Your only job is to extract structured line items from noisy invoice or purchase order OCR text.

Rules:
1. Output ONLY valid JSON — no markdown code fences, no explanation, no extra text.
2. Correct obvious OCR errors:
   - "oty", "oiy", "qty", "q ty" → quantity label
   - "prlce", "prlce", "pr1ce", "pr ice" → price label
   - merged words like "table5000" → item="table", price=5000
   - merged qty+price like "6 5003" → qty=6, price=5000 (round to nearest plausible value)
3. Infer quantity and price from numeric position when labels are missing.
   First number after item name is usually qty, next larger number is usually unit price.
4. IGNORE: header rows, page numbers, totals/subtotals, grand total, tax rows, vendor info, dates, addresses.
5. Each valid item MUST have a non-empty string "item", a positive numeric "qty", and a non-negative numeric "price".
6. Do NOT invent items that are not in the text.
7. Deduplicate: if the same item appears twice with identical qty and price, keep only one.

Output format (STRICT — no deviations):
{
  "document_type": "invoice",
  "invoice_number": "",
  "vendor": "",
  "date": "",
  "items": [
    {"item": "chair", "qty": 10, "price": 1500},
    {"item": "table", "qty": 6,  "price": 5000}
  ]
}"""

_USER_PROMPT_TEMPLATE = """Extract line items from this OCR text.

OCR TEXT:
{ocr_text}

Return ONLY the JSON object. No other text."""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(ocr_text: str) -> tuple[str, str]:
    """Return (system_prompt, user_prompt) ready for any chat-completion API."""
    truncated = ocr_text[:_MAX_OCR_CHARS]
    if len(ocr_text) > _MAX_OCR_CHARS:
        logger.info(
            "[LLM-EXTRACT] OCR text truncated from %d to %d chars for LLM",
            len(ocr_text), _MAX_OCR_CHARS,
        )
    user_prompt = _USER_PROMPT_TEMPLATE.format(ocr_text=truncated)
    logger.info("[LLM-EXTRACT] prompt_chars=%d (system=%d user=%d)",
                len(_SYSTEM_PROMPT) + len(user_prompt),
                len(_SYSTEM_PROMPT), len(user_prompt))
    logger.debug("[LLM-EXTRACT] full_user_prompt:\n%s", user_prompt)
    return _SYSTEM_PROMPT, user_prompt


# ---------------------------------------------------------------------------
# LLM provider calls
# ---------------------------------------------------------------------------

def _call_groq(system: str, user: str) -> str:
    """Call Groq API. Returns raw text response."""
    if not _GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set")
    try:
        from groq import Groq  # type: ignore
    except ImportError as exc:
        raise RuntimeError("groq SDK not installed: pip install groq>=0.9") from exc

    client = Groq(api_key=_GROQ_API_KEY)
    t0 = time.time()
    response = client.chat.completions.create(
        model=_GROQ_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.0,
        max_tokens=2048,
        timeout=30,
    )
    elapsed = round(time.time() - t0, 2)
    raw = response.choices[0].message.content or ""
    logger.info(
        "[LLM-EXTRACT] provider=groq model=%s elapsed_s=%.2f response_chars=%d",
        _GROQ_MODEL, elapsed, len(raw),
    )
    logger.debug("[LLM-EXTRACT] groq_raw_response:\n%s", raw)
    return raw


def _call_gemini(system: str, user: str) -> str:
    """Call Google Gemini. Returns raw text response."""
    if not _GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")
    try:
        import google.generativeai as genai  # type: ignore
    except ImportError as exc:
        raise RuntimeError("google-generativeai not installed: pip install google-generativeai") from exc

    genai.configure(api_key=_GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=_GEMINI_MODEL,
        system_instruction=system,
    )
    t0 = time.time()
    try:
        response = model.generate_content(
            user,
            request_options={"timeout": 30},
        )
    except Exception as exc:
        if time.time() - t0 > 25:
            raise TimeoutError(f"Gemini call timed out after {time.time()-t0:.1f}s") from exc
        raise
    elapsed = round(time.time() - t0, 2)
    raw = response.text or ""
    logger.info(
        "[LLM-EXTRACT] provider=gemini model=%s elapsed_s=%.2f response_chars=%d",
        _GEMINI_MODEL, elapsed, len(raw),
    )
    logger.debug("[LLM-EXTRACT] gemini_raw_response:\n%s", raw)
    return raw


def _call_openai(system: str, user: str) -> str:
    """Call OpenAI chat completion. Returns raw text response."""
    if not _OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")
    try:
        from openai import OpenAI  # type: ignore
    except ImportError as exc:
        raise RuntimeError("openai SDK not installed: pip install openai") from exc

    client = OpenAI(api_key=_OPENAI_API_KEY)
    t0 = time.time()
    response = client.chat.completions.create(
        model=_OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        temperature=0.0,
        max_tokens=2048,
        timeout=30,
    )
    elapsed = round(time.time() - t0, 2)
    raw = response.choices[0].message.content or ""
    logger.info(
        "[LLM-EXTRACT] provider=openai model=%s elapsed_s=%.2f response_chars=%d",
        _OPENAI_MODEL, elapsed, len(raw),
    )
    logger.debug("[LLM-EXTRACT] openai_raw_response:\n%s", raw)
    return raw


def _call_anthropic(system: str, user: str) -> str:
    """Call Anthropic Claude. Returns raw text response."""
    if not _ANTHROPIC_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    try:
        import anthropic  # type: ignore
    except ImportError as exc:
        raise RuntimeError("anthropic SDK not installed: pip install anthropic") from exc

    client = anthropic.Anthropic(api_key=_ANTHROPIC_KEY)
    t0 = time.time()
    message = client.messages.create(
        model=_ANTHROPIC_MODEL,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": user}],
        timeout=30,
    )
    elapsed = round(time.time() - t0, 2)
    raw = message.content[0].text if message.content else ""
    logger.info(
        "[LLM-EXTRACT] provider=anthropic model=%s elapsed_s=%.2f response_chars=%d",
        _ANTHROPIC_MODEL, elapsed, len(raw),
    )
    logger.debug("[LLM-EXTRACT] anthropic_raw_response:\n%s", raw)
    return raw


# Provider dispatch table (ordered by preference)
_PROVIDER_DISPATCH: dict[str, Any] = {
    "groq":      _call_groq,
    "gemini":    _call_gemini,
    "openai":    _call_openai,
    "anthropic": _call_anthropic,
}


_FALLBACK_ORDER = ["groq", "gemini", "openai", "anthropic"]


def _call_provider(system: str, user: str) -> str:
    """Dispatch to the configured provider with fallback chain.

    Tries the primary provider first. If it fails, tries remaining
    providers in order. Raises RuntimeError only if ALL providers fail.
    """
    primary = _LLM_PROVIDER
    order = [primary] + [p for p in _FALLBACK_ORDER if p != primary]
    errors: list[str] = []

    for provider in order:
        call_fn = _PROVIDER_DISPATCH.get(provider)
        if call_fn is None:
            continue
        try:
            logger.info("[LLM-EXTRACT] attempting provider=%s", provider)
            result = call_fn(system, user)
            if provider != primary:
                logger.warning(
                    "[LLM-EXTRACT] primary provider %s failed; succeeded with fallback %s",
                    primary, provider,
                )
            return result
        except Exception as exc:
            errors.append(f"{provider}: {type(exc).__name__}: {exc}")
            logger.warning(
                "[LLM-EXTRACT] provider %s failed: %s: %s",
                provider, type(exc).__name__, exc,
            )

    raise RuntimeError(
        f"All LLM providers failed. Errors: {'; '.join(errors)}"
    )


# ---------------------------------------------------------------------------
# JSON extraction + validation
# ---------------------------------------------------------------------------

def _strip_markdown_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers an LLM may emit."""
    text = text.strip()
    # Remove opening fence
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _safe_number(value: Any) -> float | int | None:
    """Coerce value to a Python number; return None if not possible."""
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        # Remove currency prefixes first to prevent their decimal points/abbreviations
        # from prepending to the number (e.g. "Rs. 5000" -> "5000" instead of ".5000")
        cleaned_prefix = re.sub(r"(?i)\b(?:rs|inr)\.?\s*", "", value)
        cleaned = re.sub(r"[^\d.\-]", "", cleaned_prefix.replace(",", ""))
        try:
            n = float(cleaned)
            return int(n) if n.is_integer() else round(n, 2)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# OCR Quality Gate
# ---------------------------------------------------------------------------

# Minimum quality score to accept an item name (0.0 – 1.0).
# Lower = more permissive (keeps more noisy items).
_MIN_ITEM_QUALITY = float(os.getenv("MIN_ITEM_QUALITY", "0.30"))

# If an OCR word-level confidence is available and below this threshold, reject.
_OCR_ITEM_CONFIDENCE_THRESHOLD = float(os.getenv("OCR_ITEM_CONFIDENCE_THRESHOLD", "0.45"))

# Repeated-symbol pattern: 3+ of the same non-alpha char (e.g. "...", "xxx", "---")
_REPEATED_SYMBOL_RE = re.compile(r"([^a-zA-Z\s])\1{2,}")

# Pure-punctuation / symbol token pattern (no letters at all)
_NO_ALPHA_RE = re.compile(r"^[^a-zA-Z]+$")

# Common OCR garbage tokens that are never valid item names on their own
_GARBAGE_TOKENS: frozenset[str] = frozenset({
    "i", "j", "l", "s", "o", "x", "r", "n",   # single stray letters
    "oty", "oiy", "otr", "prlce", "prlce",    # OCR label corruption
    "qty", "price", "total", "subtotal",       # header tokens — not item names
    "no", "sr", "sl", "sno", "s.no",           # serial number labels
})


def normalize_item_quality_score(item_name: str) -> tuple[float, str]:
    """Score an item name string for OCR quality (0.0 = garbage, 1.0 = perfect).

    Returns
    -------
    (score: float, reason: str)
        score  — 0.0–1.0 composite quality score
        reason — human-readable explanation of dominant penalty

    Scoring signals
    ---------------
    1. alpha_ratio        — fraction of characters that are letters
    2. punct_ratio        — fraction of characters that are punctuation/symbols
    3. vowel_sanity       — at least one vowel among alpha chars OR item is
                           a known abbreviation (< 4 chars all-consonant)
    4. repeated_symbol    — hard-fail if 3+ repeated non-alpha chars detected
    5. garbage_token      — hard-fail if whole name (stripped/lowered) is in
                           _GARBAGE_TOKENS set
    6. min_length         — penalty if fewer than 2 alpha characters total

    Accepts (does NOT reject) realistic OCR-corrupted items:
        "monltor"  (transposition)   -> high score
        "lapt0p"   (digit sub)       -> high score
        "cpu."     (trailing punct)  -> acceptable score
        "chair j"  (stray letter)    -> acceptable score
    """
    if not item_name:
        return 0.0, "empty"

    s = item_name.strip()
    lower = s.lower()

    # --- Signal 5: garbage token hard-fail (whole name) ---
    core = lower.rstrip(".").strip()
    if core in _GARBAGE_TOKENS:
        return 0.0, f"garbage_token:{core!r}"

    # --- Signal 7: per-token garbage check ---
    # Check each space-separated token from the original form.
    # A token is "bad" if:
    #   a) its alpha-stripped form is empty, 1 char, or a known garbage token, OR
    #   b) it has punctuation embedded mid-word (e.g. "lar.p") — OCR artifact pattern
    # If EVERY token is bad → hard-fail.
    _STRIP_PUNCT = re.compile(r"[^a-z0-9]")
    _MID_PUNCT   = re.compile(r"[^a-zA-Z0-9\s]")   # any non-alnum non-space

    orig_tokens = lower.split()
    if orig_tokens:
        def _token_is_bad(tok: str) -> bool:
            stripped = _STRIP_PUNCT.sub("", tok)
            if not stripped or len(stripped) <= 1 or stripped in _GARBAGE_TOKENS:
                return True
            # mid-word punctuation: punct NOT at the very start or end
            inner = tok[1:-1] if len(tok) > 2 else ""
            if inner and _MID_PUNCT.search(inner):
                return True
            return False

        bad_tokens  = [t for t in orig_tokens if _token_is_bad(t)]
        good_tokens = [t for t in orig_tokens if not _token_is_bad(t)]
        if not good_tokens:
            return 0.0, "all_tokens_garbage"

    # --- Signal 1: alpha ratio ---
    total_chars = len(s)
    alpha_chars  = sum(1 for c in s if c.isalpha())
    alpha_ratio  = alpha_chars / total_chars if total_chars else 0.0

    # --- Signal 2: punctuation ratio ---
    punct_chars = sum(1 for c in s if not c.isalnum() and not c.isspace())
    punct_ratio = punct_chars / total_chars if total_chars else 0.0

    # --- Signal 4: repeated symbol hard-fail ---
    if _REPEATED_SYMBOL_RE.search(s):
        return 0.0, "repeated_symbol"

    # --- Signal 6: minimum alpha character count ---
    if alpha_chars < 2:
        return 0.0, f"too_few_alpha:{alpha_chars}"

    # --- Signal 3: vowel/consonant sanity ---
    vowels     = sum(1 for c in lower if c in "aeiou")
    consonants = sum(1 for c in lower if c.isalpha() and c not in "aeiou")
    has_vowel  = vowels > 0
    # Short abbreviations (<=3 alpha chars) are allowed to be all-consonant (e.g. "cpu", "lcd")
    vowel_ok = has_vowel or (alpha_chars <= 3 and consonants >= 1)

    # --- Composite score ---
    # Penalise: high punct ratio, low alpha ratio, missing vowels in long words
    alpha_score   = min(alpha_ratio, 1.0)           # 0.0–1.0
    punct_penalty = min(punct_ratio * 2.0, 1.0)     # 0.0–1.0
    vowel_score   = 1.0 if vowel_ok else 0.4        # penalty for all-consonant long words

    score = round(
        alpha_score * 0.5
        - punct_penalty * 0.3
        + vowel_score * 0.2,
        4,
    )
    score = max(0.0, min(1.0, score))               # clamp to [0, 1]

    # Determine dominant failure reason for logging
    if score < _MIN_ITEM_QUALITY:
        if alpha_chars < 2:
            reason = f"too_few_alpha:{alpha_chars}"
        elif punct_ratio >= 0.5:
            reason = f"punct_heavy:{punct_ratio:.2f}"
        elif not vowel_ok:
            reason = "no_vowel_long_word"
        else:
            reason = f"low_quality_score:{score:.4f}"
    else:
        reason = "ok"

    return score, reason


def _validate_items(raw_items: Any, ocr_confidences: dict[str, float] | None = None) -> list[dict]:
    """Validate, quality-gate, and deduplicate a raw items list from LLM JSON.

    Each valid item must:
    - have a non-empty string item name that passes quality gating
    - have numeric qty > 0
    - have numeric price >= 0
    - pass optional OCR confidence threshold (if confidence provided per item)
    - not be a duplicate

    Parameters
    ----------
    raw_items        : raw list from LLM JSON payload
    ocr_confidences  : optional {item_name_lower: confidence_float} from word-level OCR.
                       When provided, items below OCR_ITEM_CONFIDENCE_THRESHOLD are rejected.

    Fallback safety
    ---------------
    If ALL items are rejected by the quality gate, the pre-gate list (numeric-valid
    items that only failed quality) is returned to prevent silent empty results.
    """
    if not isinstance(raw_items, list):
        logger.warning("[LLM-EXTRACT] items field is not a list: %r", type(raw_items).__name__)
        return []

    seen: set[tuple] = set()
    valid: list[dict] = []
    quality_rejected: list[dict] = []   # items rejected only by quality gate (safety fallback)

    for idx, entry in enumerate(raw_items):
        if not isinstance(entry, dict):
            logger.debug("[LLM-EXTRACT] item[%d] skipped: not a dict", idx)
            continue

        # --- item name ---
        item_name = str(entry.get("item") or "").strip()
        if not item_name:
            logger.debug("[LLM-EXTRACT] item[%d] skipped: empty item name", idx)
            continue

        # --- OCR confidence gate ---
        if ocr_confidences:
            conf = ocr_confidences.get(item_name.lower())
            if conf is not None and conf < _OCR_ITEM_CONFIDENCE_THRESHOLD:
                logger.info(
                    "[QUALITY] rejected item=%r reason=low_ocr_confidence:%.3f threshold=%.3f",
                    item_name, conf, _OCR_ITEM_CONFIDENCE_THRESHOLD,
                )
                continue

        # --- Item quality gate ---
        quality_score, quality_reason = normalize_item_quality_score(item_name)
        if quality_score < _MIN_ITEM_QUALITY:
            logger.info(
                "[QUALITY] rejected item=%r score=%.4f reason=%s",
                item_name, quality_score, quality_reason,
            )
            continue

        logger.info(
            "[QUALITY] accepted item=%r score=%.4f",
            item_name, quality_score,
        )

        # --- qty ---
        qty = _safe_number(entry.get("qty"))
        if qty is None or qty <= 0:
            logger.debug(
                "[LLM-EXTRACT] item[%d] (%r) skipped: invalid qty=%r",
                idx, item_name, entry.get("qty"),
            )
            continue

        # --- price ---
        price = _safe_number(entry.get("price"))
        if price is None or price < 0:
            logger.debug(
                "[LLM-EXTRACT] item[%d] (%r) skipped: invalid price=%r",
                idx, item_name, entry.get("price"),
            )
            continue

        # --- deduplicate ---
        key = (item_name.lower(), qty, price)
        if key in seen:
            logger.debug(
                "[LLM-EXTRACT] item[%d] (%r) skipped: duplicate", idx, item_name
            )
            continue
        seen.add(key)

        item_dict = {"item": item_name, "qty": qty, "price": price}
        valid.append(item_dict)
        quality_rejected.append(item_dict)   # track pre-gate survivors too
        logger.info(
            "[LLM-EXTRACT] valid_item[%d] item=%r qty=%r price=%r",
            idx, item_name, qty, price,
        )

    # --- Fallback safety: if quality gate wiped everything, revert to pre-gate set ---
    # (quality_rejected holds items that passed numeric checks, so we use that as the
    # fallback — it excludes garbage that failed name/qty/price, preserving real items)
    if not valid and quality_rejected:
        logger.warning(
            "[QUALITY] All %d items rejected by quality gate; reverting to pre-gate set (%d items)",
            len(raw_items), len(quality_rejected),
        )
        return quality_rejected

    return valid


def _parse_llm_response(raw: str) -> dict:
    """Parse raw LLM text into a validated dict.

    Returns a dict with at minimum {"items": [...]} even if partial.
    Raises ValueError if JSON cannot be decoded at all.
    """
    cleaned = _strip_markdown_fences(raw)

    # Try direct parse
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to extract a JSON object from surrounding text
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            try:
                payload = json.loads(match.group(0))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Could not decode JSON from LLM response: {exc}") from exc
        else:
            # Try JSON array fallback (some LLMs wrap items in an array)
            array_match = re.search(r"\[.*\]", cleaned, re.DOTALL)
            if array_match:
                try:
                    items = json.loads(array_match.group(0))
                    if isinstance(items, list):
                        logger.info("[LLM-EXTRACT] Recovered items from JSON array fallback")
                        return {"items": items}
                except json.JSONDecodeError:
                    pass
            raise ValueError("No JSON object found in LLM response")

    if not isinstance(payload, dict):
        raise ValueError(f"LLM returned non-dict JSON: {type(payload).__name__}")

    logger.info(
        "[LLM-EXTRACT] llm_json_response keys=%s raw_item_count=%d",
        list(payload.keys()),
        len(payload.get("items", []) if isinstance(payload.get("items"), list) else []),
    )
    logger.debug("[LLM-EXTRACT] full_llm_json:\n%s", json.dumps(payload, indent=2))

    return payload


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------

def _score_confidence(items: list[dict], raw_payload: dict, ocr_text: str) -> float:
    """Heuristic confidence score for the LLM extraction result.

    Signals used:
    - Number of valid items found (more = higher confidence)
    - Presence of invoice metadata fields (invoice_number, vendor, date)
    - Fraction of item names that appear verbatim in the OCR text
    """
    if not items:
        return 0.0

    # Base: clamp item count contribution
    item_score = min(len(items) / max(len(items), 5), 1.0)

    # Metadata presence
    meta_fields = sum(
        1 for k in ("invoice_number", "vendor", "date")
        if raw_payload.get(k, "").strip()
    )
    meta_score = meta_fields / 3.0

    # OCR grounding: how many item names appear in the OCR text?
    ocr_lower = ocr_text.lower()
    grounded = sum(
        1 for entry in items
        if entry["item"].lower() in ocr_lower or
           any(w in ocr_lower for w in entry["item"].lower().split() if len(w) > 2)
    )
    ground_score = grounded / len(items)

    confidence = round(item_score * 0.4 + meta_score * 0.2 + ground_score * 0.4, 4)
    logger.info(
        "[LLM-EXTRACT] confidence_scoring item_score=%.3f meta_score=%.3f "
        "ground_score=%.3f final=%.4f",
        item_score, meta_score, ground_score, confidence,
    )
    return confidence


# ---------------------------------------------------------------------------
# Fallback: existing regex parser
# ---------------------------------------------------------------------------

def _fallback_extract(ocr_text: str) -> dict:
    """Use the existing regex-based parser as a safety net."""
    logger.warning(
        "[LLM-EXTRACT] Falling back to regex parser. "
        "LLM extraction produced 0 valid items or raised an exception."
    )
    try:
        from parser import build_structured_document  # type: ignore
        doc = build_structured_document(ocr_text)
        items = doc.get("line_items", [])
        logger.info("[LLM-EXTRACT] fallback_parser produced %d items", len(items))
        return {
            "document_type": "unknown",
            "invoice_number": "",
            "vendor": "",
            "date": "",
            "items": items,
            "extraction_confidence": doc.get("parser_confidence_score", 0.0),
            "extraction_mode": "regex_fallback",
            "fallback_used": True,
            # Pass through full parser diagnostics for the API response
            "_parser_doc": doc,
        }
    except Exception as exc:
        logger.error("[LLM-EXTRACT] Regex fallback also failed: %s", exc)
        return {
            "document_type": "unknown",
            "invoice_number": "",
            "vendor": "",
            "date": "",
            "items": [],
            "extraction_confidence": 0.0,
            "extraction_mode": "failed",
            "fallback_used": True,
            "_parser_doc": {},
        }


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def extract_structured(ocr_text: str, doc_hint: str = "invoice") -> dict:
    """Extract structured line items from raw OCR text using an LLM.

    Parameters
    ----------
    ocr_text : str
        Raw OCR output from PaddleOCR / pdfplumber.
    doc_hint : str
        "invoice" or "po" — passed to the prompt so the LLM knows context.

    Returns
    -------
    dict with keys:
        document_type       str
        invoice_number      str
        vendor              str
        date                str
        items               list[{item, qty, price}]
        extraction_confidence  float 0-1
        extraction_mode     str   ("llm_groq" | "llm_gemini" | ... | "regex_fallback" | "failed")
        fallback_used       bool
        _parser_doc         dict  (only when fallback_used=True, for diagnostics)
    """
    logger.info(
        "[LLM-EXTRACT] === extract_structured start doc_hint=%r ocr_chars=%d ===",
        doc_hint, len(ocr_text or ""),
    )
    logger.info("[LLM-EXTRACT] raw_ocr_text_preview: %r", (ocr_text or "")[:400])

    if not (ocr_text or "").strip():
        logger.warning("[LLM-EXTRACT] Empty OCR text received; returning empty result")
        return {
            "document_type": doc_hint,
            "invoice_number": "",
            "vendor": "",
            "date": "",
            "items": [],
            "extraction_confidence": 0.0,
            "extraction_mode": "empty_input",
            "fallback_used": False,
            "_parser_doc": {},
        }

    # ------------------------------------------------------------------
    # Attempt LLM extraction
    # ------------------------------------------------------------------
    try:
        system_prompt, user_prompt = _build_prompt(ocr_text)
        raw_response = _call_provider(system_prompt, user_prompt)
        payload = _parse_llm_response(raw_response)
        items = _validate_items(payload.get("items", []))

        logger.info(
            "[LLM-EXTRACT] valid_item_count=%d after validation",
            len(items),
        )

        if not items:
            logger.warning(
                "[LLM-EXTRACT] LLM returned 0 valid items; triggering fallback. "
                "raw_payload_keys=%s",
                list(payload.keys()),
            )
            return _fallback_extract(ocr_text)

        confidence = _score_confidence(items, payload, ocr_text)
        mode = f"llm_{_LLM_PROVIDER}"

        result = {
            "document_type": str(payload.get("document_type") or doc_hint),
            "invoice_number": str(payload.get("invoice_number") or ""),
            "vendor":         str(payload.get("vendor") or ""),
            "date":           str(payload.get("date") or ""),
            "items":          items,
            "extraction_confidence": confidence,
            "extraction_mode":       mode,
            "fallback_used":         False,
            "_parser_doc": {},
        }

        logger.info(
            "[LLM-EXTRACT] === extraction complete mode=%s confidence=%.4f items=%d ===",
            mode, confidence, len(items),
        )
        logger.info("[LLM-EXTRACT] normalized_final_json: %s", json.dumps(result, default=str))
        return result

    except Exception as exc:
        logger.warning(
            "[LLM-EXTRACT] LLM extraction failed (%s: %s); triggering regex fallback.",
            type(exc).__name__, exc,
        )
        return _fallback_extract(ocr_text)
