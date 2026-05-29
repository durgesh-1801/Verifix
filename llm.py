"""Deterministic structured comparison for invoice vs PO.

Fuzzy reconciliation layer
--------------------------
Before declaring a missing-item discrepancy, every unmatched invoice item is
compared against every unmatched PO item using rapidfuzz token_set_ratio.
If similarity >= ITEM_MATCH_THRESHOLD (default 85, env-configurable) the pair
is treated as the same item and qty/price comparison is run normally.

Price tolerance
---------------
PRICE_TOLERANCE (default 0, env-configurable) allows a small absolute or
percentage difference to be ignored (e.g. rounding from different currencies).

No LLM is involved in reconciliation decisions — all matching is
deterministic text similarity + numeric comparison.
"""

from __future__ import annotations

import logging
import os
import re
import time

import parser as parser_module
from parser import normalize_currency_value, normalize_item_name, normalize_quantity

from extractors.llm_structured_extractor import extract_structured

logger = logging.getLogger(__name__)

_MIN_TEXT_LEN = 40

# ---------------------------------------------------------------------------
# Configuration (env-overridable)
# ---------------------------------------------------------------------------

_ITEM_MATCH_THRESHOLD = int(os.getenv("ITEM_MATCH_THRESHOLD", "85"))
_PRICE_TOLERANCE      = float(os.getenv("PRICE_TOLERANCE", "0"))

print("USING NEW OCR-TOLERANT PARSER + LLM EXTRACTION + FUZZY RECONCILIATION")
logger.warning(
    "Parser import verification: module=%s file=%s function_id=%s | "
    "ITEM_MATCH_THRESHOLD=%d PRICE_TOLERANCE=%g",
    parser_module.__name__,
    getattr(parser_module, "__file__", "unknown"),
    id(normalize_currency_value),
    _ITEM_MATCH_THRESHOLD,
    _PRICE_TOLERANCE,
)

# ---------------------------------------------------------------------------
# Fuzzy matching helpers
# ---------------------------------------------------------------------------

# OCR residue tokens to strip before matching (single stray chars, OCR glyph artifacts)
_OCR_RESIDUE_RE = re.compile(
    r"\b(?:j|l|i|o|0|s|oty|oiy|otr|ltem|ltems)\b",
    re.IGNORECASE,
)
_PUNCTUATION_RE = re.compile(r"[^a-z0-9\s]")
_MULTI_SPACE_RE = re.compile(r"\s+")


# OCR digit → letter substitutions applied before similarity scoring
# (handles common OCR glyph confusions: 0↔o, 1↔l/i, 3↔e, 5↔s, 8↔b)
_DIGIT_LOOKALIKE: dict[str, str] = str.maketrans("01358", "oleso")


def normalize_item_for_matching(text: str) -> str:
    """Normalize an item name for fuzzy similarity comparison.

    Steps
    -----
    1. Lowercase
    2. OCR digit→letter substitution (0→o, 1→l, 3→e, 5→s, 8→b)
    3. Remove punctuation (keep alphanumeric + spaces)
    4. Strip OCR residue tokens (stray glyphs, misread labels)
    5. Collapse multiple spaces → single space
    6. Strip leading/trailing whitespace

    Examples
    --------
    "Chair j"   -> "chair"
    "cpu."      -> "cpu"
    "lapt0p"    -> "laptop"   (0→o)
    "monltor"   -> "monltor"  (similarity engine handles transpositions)
    "LAPTOP 1"  -> "laptop l"
    """
    if not text:
        return ""
    s = str(text).lower()
    s = s.translate(_DIGIT_LOOKALIKE)          # 0→o, 1→l, 3→e, 5→s, 8→b
    s = _PUNCTUATION_RE.sub(" ", s)
    s = _OCR_RESIDUE_RE.sub(" ", s)
    s = _MULTI_SPACE_RE.sub(" ", s)
    return s.strip()


def _fuzzy_similarity(a: str, b: str) -> float:
    """Return rapidfuzz token_set_ratio (0–100) between two normalised strings."""
    try:
        from rapidfuzz.fuzz import token_set_ratio  # type: ignore
        return token_set_ratio(a, b)
    except ImportError:
        # Graceful degradation: exact match only
        logger.warning("[FUZZY] rapidfuzz not available; falling back to exact matching")
        return 100.0 if a == b else 0.0


def _build_fuzzy_match_map(
    invoice_keys: list[str],
    po_keys: list[str],
) -> dict[str, str]:
    """Build a mapping from invoice item key -> matched PO item key using fuzzy similarity.

    Algorithm
    ---------
    Greedy best-match: for each invoice item (sorted), find the highest-scoring
    unmatched PO item. If score >= threshold, record the pair and remove both
    from the candidate pool (prevents duplicate matching).

    Returns
    -------
    dict mapping each invoice key that has a fuzzy match to its PO key.
    Keys with exact matches are excluded (they are already handled upstream).
    """
    # Normalised forms for matching (keep map back to original keys)
    inv_norm = {k: normalize_item_for_matching(k) for k in invoice_keys}
    po_norm  = {k: normalize_item_for_matching(k) for k in po_keys}

    unmatched_po = set(po_keys)
    match_map: dict[str, str] = {}          # invoice_key -> po_key

    logger.info(
        "[FUZZY] Building match map: %d invoice items vs %d PO items | threshold=%d",
        len(invoice_keys), len(po_keys), _ITEM_MATCH_THRESHOLD,
    )

    for inv_key in sorted(invoice_keys):
        inv_n = inv_norm[inv_key]
        best_score = -1.0
        best_po_key: str | None = None

        for po_key in unmatched_po:
            po_n = po_norm[po_key]
            score = _fuzzy_similarity(inv_n, po_n)
            logger.debug(
                "[FUZZY] compare %r (%r) vs %r (%r) score=%.1f",
                inv_key, inv_n, po_key, po_n, score,
            )
            if score > best_score:
                best_score = score
                best_po_key = po_key

        if best_po_key is not None and best_score >= _ITEM_MATCH_THRESHOLD:
            match_map[inv_key] = best_po_key
            unmatched_po.discard(best_po_key)
            logger.info(
                "[FUZZY] MATCHED %r -> %r (score=%.1f)",
                inv_key, best_po_key, best_score,
            )
        else:
            logger.info(
                "[FUZZY] NO MATCH for %r (best_score=%.1f best_candidate=%r)",
                inv_key, best_score, best_po_key,
            )

    return match_map


# ---------------------------------------------------------------------------
# Price tolerance helper
# ---------------------------------------------------------------------------

def _prices_within_tolerance(invoice_price, po_price) -> bool:
    """Return True if the absolute difference is within PRICE_TOLERANCE."""
    if _PRICE_TOLERANCE <= 0:
        return False
    try:
        diff = abs(float(invoice_price) - float(po_price))
        within = diff <= _PRICE_TOLERANCE
        if within:
            logger.info(
                "[FUZZY] price tolerance accepted: invoice=%s po=%s diff=%.4f tolerance=%g",
                invoice_price, po_price, diff, _PRICE_TOLERANCE,
            )
        return within
    except (TypeError, ValueError):
        return False


# ---------------------------------------------------------------------------
# Existing helpers (unchanged)
# ---------------------------------------------------------------------------

def _format_number(value):
    if value is None:
        return "N/A"
    return value


def _difference(left, right):
    if left is None or right is None:
        return "N/A"
    left_num  = normalize_currency_value(left)
    right_num = normalize_currency_value(right)
    if left_num is None or right_num is None:
        return "N/A"
    diff = abs(float(left_num) - float(right_num))
    return int(diff) if diff.is_integer() else round(diff, 2)


def _group_items(line_items: list[dict]) -> dict[str, dict]:
    grouped: dict[str, dict] = {}

    for item in line_items:
        item_name = normalize_item_name(item.get("item"))
        if not item_name:
            continue

        bucket = grouped.setdefault(
            item_name,
            {
                "item": item_name,
                "entries": [],
                "qty": 0,
                "qty_values": [],
                "price_values": [],
            },
        )

        qty   = normalize_quantity(item.get("qty"))
        price = normalize_currency_value(item.get("price"))
        entry = {"item": item_name, "qty": qty, "price": price}
        bucket["entries"].append(entry)

        if qty is not None:
            old_qty = bucket["qty"]
            bucket["qty"]  += qty
            bucket["qty_values"].append(qty)
            if old_qty > 0:
                print(f"[NUMERIC_MUTATION]\nstage=grouping_aggregation\nitem={item_name}\nold_value=qty:{old_qty}\nnew_value=qty:{bucket['qty']}", flush=True)
        if price is not None:
            bucket["price_values"].append(price)

    for bucket in grouped.values():
        unique_prices = list(dict.fromkeys(bucket["price_values"]))
        bucket["price"]         = unique_prices[0] if len(unique_prices) == 1 else None
        bucket["has_duplicate"] = len(bucket["entries"]) > 1

    return grouped


def _duplicate_discrepancy(item: str, entries: list[dict], present_in: str) -> dict:
    return {
        "type": "duplicate_item",
        "item": item,
        "present_in": present_in,
        "entry_count": len(entries),
        "entries": entries,
        "field": "item",
        "invoice_value": len(entries) if present_in == "Invoice" else "N/A",
        "po_value":      len(entries) if present_in == "PO"      else "N/A",
        "invoice":       len(entries) if present_in == "Invoice" else None,
        "po":            len(entries) if present_in == "PO"      else None,
        "difference": "N/A",
        "issue": f"duplicate item in {present_in.lower()}",
    }


def _missing_discrepancy(
    item: str,
    present_in: str,
    invoice_entry: list[dict] | None,
    po_entry: list[dict] | None,
) -> dict:
    return {
        "type": "missing_item",
        "item": item,
        "present_in": present_in,
        "field": "item",
        "invoice_value": invoice_entry or "N/A",
        "po_value":      po_entry      or "N/A",
        "invoice":       invoice_entry,
        "po":            po_entry,
        "difference": "N/A",
        "issue": "missing_in_invoice" if present_in == "PO only" else "missing_in_po",
    }


def _value_mismatch(
    item: str,
    mismatch_type: str,
    invoice_value,
    po_value,
) -> dict:
    field       = "quantity" if mismatch_type == "quantity_mismatch" else "price"
    invoice_key = "invoice_qty"   if field == "quantity" else "invoice_price"
    po_key      = "po_qty"        if field == "quantity" else "po_price"
    issue       = "quantity mismatch" if field == "quantity" else "price mismatch"
    return {
        "type": mismatch_type,
        "item": item,
        invoice_key: invoice_value,
        po_key:      po_value,
        "field":     field,
        "invoice_value": _format_number(invoice_value),
        "po_value":      _format_number(po_value),
        "invoice":       invoice_value,
        "po":            po_value,
        "difference":    _difference(invoice_value, po_value),
        "issue":         issue,
    }


# ---------------------------------------------------------------------------
# Core comparison — with fuzzy reconciliation injected
# ---------------------------------------------------------------------------

def _is_suspicious_trailing_drift(val1: float, val2: float) -> bool:
    """Detect suspicious trailing digit OCR corruptions like 1500 -> 1509 or 5000 -> 5099.
    
    Checks if the difference is characteristic of a misread trailing digit (e.g. 9, 8, 99, 98),
    or if rounding both numbers to their nearest tens/hundreds makes them align perfectly.
    """
    try:
        v1 = float(val1)
        v2 = float(val2)
        diff = abs(v1 - v2)
        
        # If difference matches a single/double trailing digit noise pattern
        if diff in (1, 2, 8, 9, 18, 19, 98, 99):
            return True
            
        # Check trailing digit rounding alignability (e.g. 1500 vs 1509, 5000 vs 5099)
        for base in (10, 100):
            r1 = round(v1 / base) * base
            r2 = round(v2 / base) * base
            if r1 == r2 and (v1 % base in (0, 9, 8, 99, 98) or v2 % base in (0, 9, 8, 99, 98)):
                return True
    except (ValueError, TypeError):
        pass
    return False


def _compare_groups(
    invoice_groups: dict[str, dict],
    po_groups: dict[str, dict],
) -> list[dict]:
    """Run the full discrepancy check with fuzzy item reconciliation.

    Phase 1: Exact matches  — items whose normalised names are identical.
    Phase 2: Fuzzy matches  — unmatched items paired by rapidfuzz similarity.
    Phase 3: True missing   — items that survived both phases unmatched.

    Within each matched pair, qty and price are compared deterministically.
    """
    discrepancies: list[dict] = []

    # --- Phase 1: exact key intersection ---
    exact_inv = set(invoice_groups)
    exact_po  = set(po_groups)
    exact_both = exact_inv & exact_po

    unmatched_inv = sorted(exact_inv - exact_both)
    unmatched_po  = sorted(exact_po  - exact_both)

    logger.info(
        "[FUZZY] Phase1 exact: matched=%d | unmatched_invoice=%d unmatched_po=%d",
        len(exact_both), len(unmatched_inv), len(unmatched_po),
    )

    # --- Phase 2: fuzzy matching for unmatched items ---
    fuzzy_map: dict[str, str] = {}   # invoice_key -> po_key
    if unmatched_inv and unmatched_po:
        fuzzy_map = _build_fuzzy_match_map(unmatched_inv, unmatched_po)

    fuzzy_matched_inv = set(fuzzy_map.keys())
    fuzzy_matched_po  = set(fuzzy_map.values())

    # Collect all logical pairs to compare
    # (display_name, invoice_bucket, po_bucket)
    pairs_to_compare: list[tuple[str, dict, dict]] = []

    for item in sorted(exact_both):
        pairs_to_compare.append((item, invoice_groups[item], po_groups[item]))

    for inv_key, po_key in sorted(fuzzy_map.items()):
        # Use the invoice item name as the canonical display name
        pairs_to_compare.append((inv_key, invoice_groups[inv_key], po_groups[po_key]))

    # --- Compare each matched pair ---
    for display_name, inv_bucket, po_bucket in pairs_to_compare:
        invoice_qty = inv_bucket["qty"] if inv_bucket["qty_values"] else None
        po_qty      = po_bucket["qty"]  if po_bucket["qty_values"]  else None

        if invoice_qty is not None and po_qty is not None and invoice_qty != po_qty:
            is_noise = False
            diff = abs(invoice_qty - po_qty)
            
            # Check trailing digit drift (e.g. 1500 vs 1509)
            if _is_suspicious_trailing_drift(invoice_qty, po_qty):
                is_noise = True
                
            if is_noise:
                logger.info("[SUPPRESS-QUANTITY] Suppressing trailing digit/OCR noise discrepancy for %r: invoice=%r po=%r", display_name, invoice_qty, po_qty)
                if diff <= 1:
                    continue  # Suppress completely
                else:
                    disc = _value_mismatch(display_name, "quantity_mismatch", invoice_qty, po_qty)
                    disc["review_required"] = True
                    disc["status"] = "REVIEW_REQUIRED"
                    disc["issue"] = "quantity mismatch (probable OCR noise)"
                    discrepancies.append(disc)
            else:
                discrepancies.append(
                    _value_mismatch(display_name, "quantity_mismatch", invoice_qty, po_qty)
                )

        invoice_price = inv_bucket.get("price")
        po_price      = po_bucket.get("price")

        if invoice_price is not None and po_price is not None:
            if invoice_price != po_price:
                if not _prices_within_tolerance(invoice_price, po_price):
                    is_noise = False
                    diff = abs(invoice_price - po_price)
                    
                    if _is_suspicious_trailing_drift(invoice_price, po_price):
                        is_noise = True
                        
                    if is_noise:
                        logger.info("[SUPPRESS-PRICE] Suppressing price discrepancy for %r: invoice=%r po=%r", display_name, invoice_price, po_price)
                        if diff <= 1.0 or diff / max(invoice_price, po_price) < 0.01:
                            continue  # Suppress completely
                        else:
                            disc = _value_mismatch(display_name, "price_mismatch", invoice_price, po_price)
                            disc["review_required"] = True
                            disc["status"] = "REVIEW_REQUIRED"
                            disc["issue"] = "price mismatch (probable OCR noise)"
                            discrepancies.append(disc)
                    else:
                        discrepancies.append(
                            _value_mismatch(display_name, "price_mismatch", invoice_price, po_price)
                        )

    # --- Phase 3: true missing items ---
    truly_missing_inv = [k for k in unmatched_inv if k not in fuzzy_matched_inv]
    truly_missing_po  = [k for k in unmatched_po  if k not in fuzzy_matched_po]

    logger.info(
        "[FUZZY] Phase3 truly missing: invoice_only=%d po_only=%d",
        len(truly_missing_inv), len(truly_missing_po),
    )

    for item in sorted(truly_missing_po):
        discrepancies.append(
            _missing_discrepancy(item, "PO only", None, po_groups[item]["entries"])
        )
    for item in sorted(truly_missing_inv):
        discrepancies.append(
            _missing_discrepancy(item, "Invoice only", invoice_groups[item]["entries"], None)
        )

    return discrepancies


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def log_failure_case(invoice_text: str, po_text: str, comparison: dict):
    """Safe failure logging (categorizes failure types, stores previews securely)."""
    try:
        import json
        from uuid import uuid4
        from datetime import datetime

        discrepancies = comparison.get("discrepancies", [])
        error = comparison.get("error")
        warning = comparison.get("warning")
        
        category = "unknown_failure"
        if error:
            category = "execution_error"
        elif not comparison.get("invoice_items") and not comparison.get("po_items"):
            category = "extraction_failed"
        elif len(discrepancies) > 0:
            category = "reconciliation_mismatches"
        elif warning:
            category = "partial_extraction"
        else:
            return # Everything is completely correct; no mismatch or warning

        # Expand detailed failure modes to reusable diagnostic categories
        diagnostic_categories = []
        if error:
            diagnostic_categories.append("execution_error")
        if not comparison.get("invoice_items") and not comparison.get("po_items"):
            diagnostic_categories.append("extraction_failed")
            
        confidence_flags = comparison.get("confidence_flags", [])
        if "LOW_CONFIDENCE_OCR" in confidence_flags or "OCR_FALLBACK_TRIGGERED" in confidence_flags:
            diagnostic_categories.append("ocr_corruption_patterns")
        if "POSSIBLE_COLUMN_SHIFT" in confidence_flags:
            diagnostic_categories.append("parser_instability")
        if "MATHEMATICAL_RECONSTRUCTION_USED" in confidence_flags:
            # Check if discrepancies exist on reconstructed items
            has_recon_disc = any(
                d.get("item") in [it.get("item") for it in comparison.get("invoice_items", []) + comparison.get("po_items", []) if it.get("reconstructed")]
                for d in discrepancies
            )
            if has_recon_disc:
                diagnostic_categories.append("reconstruction_overreach")
        if "LOW_MATCH_CONFIDENCE" in confidence_flags:
            diagnostic_categories.append("fuzzy_matching_uncertainty")
            
        # Check for GST extraction failures (if item name contains CGST/SGST/IGST/VAT/tax/total)
        has_gst_item = any(
            any(k in str(item.get("item", "")).lower() for k in ("cgst", "sgst", "igst", "utgst", "vat", "gst", "tax", "total", "subtotal"))
            for item in comparison.get("invoice_items", []) + comparison.get("po_items", [])
        )
        if has_gst_item:
            diagnostic_categories.append("gst_tax_contamination")
            
        # Check for numeric drift patterns (suspicious trailing digits or tiny differences)
        has_drift = False
        for d in discrepancies:
            inv_val = d.get("invoice_qty") or d.get("invoice_price")
            po_val = d.get("po_qty") or d.get("po_price")
            if inv_val is not None and po_val is not None:
                if _is_suspicious_trailing_drift(inv_val, po_val):
                    has_drift = True
                    break
        if has_drift:
            diagnostic_categories.append("numeric_drift_patterns")

        # Ensure directory exists within workspace
        failure_dir = os.path.join("logs", "failures")
        os.makedirs(failure_dir, exist_ok=True)
        
        failure_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:8]}"
        filename = os.path.join(failure_dir, f"failure_{failure_id}.json")
        
        payload = {
            "failure_id": failure_id,
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "diagnostic_categories": diagnostic_categories,
            "error": error,
            "warning": warning,
            "invoice_text_length": len(invoice_text),
            "po_text_length": len(po_text),
            "invoice_item_count": len(comparison.get("invoice_items", [])),
            "po_item_count": len(comparison.get("po_items", [])),
            "discrepancies": discrepancies,
            "invoice_parser": comparison.get("invoice_parser", {}),
            "po_parser": comparison.get("po_parser", {}),
            "confidence_flags": confidence_flags,
            "invoice_text_preview": (invoice_text or "")[:1000],
            "po_text_preview": (po_text or "")[:1000]
        }
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
            
        logger.info("[FAILURE-ANALYTICS] Saved extraction failure log to %s | diagnostics=%s", filename, diagnostic_categories)
    except Exception as exc:
        logger.warning("[FAILURE-ANALYTICS] Failed to write failure log: %s", exc)


def compare_invoice_po(invoice_text: str, po_text: str) -> dict:
    t_start = time.perf_counter()
    logger.info("CALL CHAIN discrepancy entrypoint=compare_invoice_po")

    if len(invoice_text.strip()) < _MIN_TEXT_LEN:
        msg = (
            f"Invoice text is too short ({len(invoice_text.strip())} chars). "
            "OCR may have failed. Check the uploaded file."
        )
        logger.error(msg)
        return {"discrepancies": [], "summary": "", "error": msg, "invoice_items": [], "po_items": []}

    if len(po_text.strip()) < _MIN_TEXT_LEN:
        msg = (
            f"PO text is too short ({len(po_text.strip())} chars). "
            "OCR may have failed. Check the uploaded file."
        )
        logger.error(msg)
        return {"discrepancies": [], "summary": "", "error": msg, "invoice_items": [], "po_items": []}

    # 1. Invoice extraction timing
    t_inv_start = time.perf_counter()
    invoice_result = extract_structured(invoice_text, doc_hint="invoice")
    t_inv_end = time.perf_counter()
    inv_latency = (t_inv_end - t_inv_start) * 1000

    # 2. PO extraction timing
    t_po_start = time.perf_counter()
    po_result      = extract_structured(po_text,      doc_hint="po")
    t_po_end = time.perf_counter()
    po_latency = (t_po_end - t_po_start) * 1000

    invoice_items = invoice_result.get("items", [])
    po_items      = po_result.get("items",      [])

    # Bridge extractor output into the parser-doc shape expected by the API layer
    def _extractor_to_parser_doc(ext_result: dict, ocr_text: str) -> dict:
        inner = ext_result.get("_parser_doc") or {}
        return {
            "line_items":             ext_result.get("items", []),
            "skipped_rows":           inner.get("skipped_rows", []),
            "parser_confidence_score": ext_result.get("extraction_confidence", 0.0),
            "line_item_count":        len(ext_result.get("items", [])),
            "failure_reason":         inner.get("failure_reason"),
            "raw_ocr_preview":        (ocr_text or "")[:300],
            "parsed_item_count":      len(ext_result.get("items", [])),
            "skipped_row_count":      len(inner.get("skipped_rows", [])),
            "parser_trace":           inner.get("parser_trace", {}),
            "totals":                 inner.get("totals", {}),
            "extraction_mode":        ext_result.get("extraction_mode", "unknown"),
            "fallback_used":          ext_result.get("fallback_used", False),
            "invoice_number":         ext_result.get("invoice_number", ""),
            "vendor":                 ext_result.get("vendor", ""),
            "date":                   ext_result.get("date", ""),
        }

    invoice_doc = _extractor_to_parser_doc(invoice_result, invoice_text)
    po_doc      = _extractor_to_parser_doc(po_result,      po_text)

    invoice_parser = {
        "skipped_rows":            invoice_doc.get("skipped_rows", []),
        "parser_confidence_score": invoice_doc.get("parser_confidence_score", 0.0),
        "line_item_count":         invoice_doc.get("line_item_count", 0),
        "failure_reason":          invoice_doc.get("failure_reason"),
        "raw_ocr_preview":         invoice_doc.get("raw_ocr_preview", ""),
        "parsed_item_count":       invoice_doc.get("parsed_item_count", 0),
        "skipped_row_count":       invoice_doc.get("skipped_row_count", 0),
        "parser_trace":            invoice_doc.get("parser_trace", {}),
        "extraction_mode":         invoice_doc.get("extraction_mode", "unknown"),
        "fallback_used":           invoice_doc.get("fallback_used", False),
    }
    po_parser = {
        "skipped_rows":            po_doc.get("skipped_rows", []),
        "parser_confidence_score": po_doc.get("parser_confidence_score", 0.0),
        "line_item_count":         po_doc.get("line_item_count", 0),
        "failure_reason":          po_doc.get("failure_reason"),
        "raw_ocr_preview":         po_doc.get("raw_ocr_preview", ""),
        "parsed_item_count":       po_doc.get("parsed_item_count", 0),
        "skipped_row_count":       po_doc.get("skipped_row_count", 0),
        "parser_trace":            po_doc.get("parser_trace", {}),
        "extraction_mode":         po_doc.get("extraction_mode", "unknown"),
        "fallback_used":           po_doc.get("fallback_used", False),
    }

    logger.info("OCR -> parser trace invoice_raw_ocr_text: %s", invoice_text)
    logger.info("OCR -> parser trace po_raw_ocr_text: %s", po_text)
    logger.info("Parsed invoice items: %s", invoice_items)
    logger.info("Parsed PO items: %s",      po_items)
    logger.info("Invoice parser diagnostics: %s", invoice_parser)
    logger.info("PO parser diagnostics: %s",      po_parser)
    logger.info("invoice_items count=%d",  len(invoice_items))
    logger.info("po_items count=%d",       len(po_items))

    # Log extraction mode, fallback used, parser confidence score
    print(f"extraction_mode: invoice={invoice_result.get('extraction_mode')}, po={po_result.get('extraction_mode')}", flush=True)
    print(f"fallback_used: invoice={invoice_result.get('fallback_used')}, po={po_result.get('fallback_used')}", flush=True)
    print(f"parser_confidence_score: invoice={invoice_parser.get('parser_confidence_score')}, po={po_parser.get('parser_confidence_score')}", flush=True)

    # Task 4 & 5: Run deterministic parser side-by-side and compare outputs
    from parser import build_structured_document
    invoice_det_doc = build_structured_document(invoice_text)
    det_invoice_items = invoice_det_doc.get("line_items", [])
    po_det_doc = build_structured_document(po_text)
    det_po_items = po_det_doc.get("line_items", [])
    
    import json
    print(f"[TRACE] DETERMINISTIC_OUTPUT (invoice): {json.dumps(det_invoice_items)}", flush=True)
    print(f"[TRACE] LLM_OUTPUT (invoice): {json.dumps(invoice_items)}", flush=True)
    
    print(f"[TRACE] DETERMINISTIC_OUTPUT (po): {json.dumps(det_po_items)}", flush=True)
    print(f"[TRACE] LLM_OUTPUT (po): {json.dumps(po_items)}", flush=True)
    
    # Side-by-side comparison for deviation warning
    has_deviation = False
    det_inv_map = {it.get("item", "").lower(): it for it in det_invoice_items if it.get("item")}
    llm_inv_map = {it.get("item", "").lower(): it for it in invoice_items if it.get("item")}
    for name, llm_it in llm_inv_map.items():
        if name in det_inv_map:
            det_it = det_inv_map[name]
            if llm_it.get("qty") != det_it.get("qty") or llm_it.get("price") != det_it.get("price"):
                has_deviation = True
                
    det_po_map = {it.get("item", "").lower(): it for it in det_po_items if it.get("item")}
    llm_po_map = {it.get("item", "").lower(): it for it in po_items if it.get("item")}
    for name, llm_it in llm_po_map.items():
        if name in det_po_map:
            det_it = det_po_map[name]
            if llm_it.get("qty") != det_it.get("qty") or llm_it.get("price") != det_it.get("price"):
                has_deviation = True
                
    if has_deviation:
        print("[WARNING] LLM_NUMERIC_DEVIATION", flush=True)

    if not invoice_items and not po_items:
        msg = "Could not parse structured invoice line items from OCR text."
        failure_path = (
            "llm.compare_invoice_po -> extract_structured -> "
            "invoice_items empty and po_items empty"
        )
        logger.error(
            "%s failure_path=%s invoice_failure_reason=%s po_failure_reason=%s",
            msg, failure_path,
            invoice_parser.get("failure_reason"),
            po_parser.get("failure_reason"),
        )
        confidence_flags = ["LOW_CONFIDENCE_OCR"]
        if invoice_result.get("fallback_used", False) or po_result.get("fallback_used", False):
            confidence_flags.append("OCR_FALLBACK_TRIGGERED")
            
        result_payload = {
            "discrepancies":    [],
            "summary":          "",
            "error":            msg,
            "invoice_items":    [],
            "po_items":         po_items,
            "invoice_totals":   invoice_doc.get("totals", {}),
            "po_totals":        po_doc.get("totals", {}),
            "invoice_parser":   invoice_parser,
            "po_parser":        po_parser,
            "failure_path":     failure_path,
            "confidence_flags": confidence_flags,
        }
        log_failure_case(invoice_text, po_text, result_payload)
        return result_payload

    warning = None
    if not invoice_items and po_items:
        warning = (
            "Invoice parser returned no line items; continuing reconciliation with PO items only. "
            f"invoice_failure_reason={invoice_parser.get('failure_reason')}"
        )
        logger.warning("%s failure_path=llm.compare_invoice_po.partial_invoice_parse", warning)
    if not po_items and invoice_items:
        warning = (
            "PO parser returned no line items; continuing reconciliation with invoice items only. "
            f"po_failure_reason={po_parser.get('failure_reason')}"
        )
        logger.warning("%s failure_path=llm.compare_invoice_po.partial_po_parse", warning)

    t_recon_start = time.perf_counter()
    
    # Log fuzzy input
    print("[TRACE] FUZZY_INPUT", flush=True)
    print(json.dumps(invoice_items), flush=True)
    print(json.dumps(po_items), flush=True)
    
    invoice_groups = _group_items(invoice_items)
    po_groups      = _group_items(po_items)

    # Log comparison input
    print("[TRACE] COMPARISON_INPUT", flush=True)
    print(json.dumps(invoice_items), flush=True)
    print(json.dumps(po_items), flush=True)

    discrepancies: list[dict] = []
    for item, bucket in invoice_groups.items():
        if bucket["has_duplicate"]:
            discrepancies.append(_duplicate_discrepancy(item, bucket["entries"], "Invoice"))
    for item, bucket in po_groups.items():
        if bucket["has_duplicate"]:
            discrepancies.append(_duplicate_discrepancy(item, bucket["entries"], "PO"))

    discrepancies.extend(_compare_groups(invoice_groups, po_groups))
    t_recon_end = time.perf_counter()
    recon_latency = (t_recon_end - t_recon_start) * 1000

    total_latency = (time.perf_counter() - t_start) * 1000

    # Structured logging of timings
    logger.info(
        "[TIMING] Stage timing latency breakdown:\n"
        "  - Invoice Extraction (parser path & timing): %.2f ms\n"
        "  - PO Extraction (parser path & timing): %.2f ms\n"
        "  - Reconciliation Engine: %.2f ms\n"
        "  - Total End-to-End Pipeline: %.2f ms",
        inv_latency, po_latency, recon_latency, total_latency
    )

    # ------------------------------------------------------------------
    # PHASE 3 — CONFIDENCE VALIDATION LAYER
    # ------------------------------------------------------------------
    confidence_flags = []

    # 1. OCR Confidence signaling
    inv_conf = invoice_result.get("extraction_confidence", 1.0)
    po_conf = po_result.get("extraction_confidence", 1.0)
    if inv_conf < 0.65 or po_conf < 0.65:
        confidence_flags.append("LOW_CONFIDENCE_OCR")

    # 2. OCR Fallback Trigger signaling
    if invoice_result.get("fallback_used", False) or po_result.get("fallback_used", False):
        confidence_flags.append("OCR_FALLBACK_TRIGGERED")

    # 3. Column Shift & Parser signaling
    has_swap = any(item.get("swapped", False) for item in invoice_items + po_items)
    # Check if we have mismatched values that suggest a possible column shift
    if has_swap or invoice_parser.get("parser_confidence_score", 1.0) < 0.65 or po_parser.get("parser_confidence_score", 1.0) < 0.65:
        confidence_flags.append("POSSIBLE_COLUMN_SHIFT")

    # 4. Reconstruction signaling
    has_reconstruct = any(item.get("reconstructed", False) for item in invoice_items + po_items)
    if has_reconstruct:
        confidence_flags.append("MATHEMATICAL_RECONSTRUCTION_USED")

    # 5. Reconciliation Match signaling
    total_distinct_items = max(len(invoice_groups), 1) + max(len(po_groups), 1)
    unmatched_count = len(invoice_groups.keys() - po_groups.keys()) + len(po_groups.keys() - invoice_groups.keys())
    # If more than 35% of distinct items couldn't be matched
    if unmatched_count / total_distinct_items > 0.35 or len(discrepancies) > 2:
        confidence_flags.append("LOW_MATCH_CONFIDENCE")

    result_payload = {
        "discrepancies": discrepancies,
        "summary": (
            f"{len(discrepancies)} discrepancy(s) found."
            if discrepancies else "No discrepancies found."
        ),
        "error":          None,
        "warning":        warning,
        "invoice_items":  invoice_items,
        "po_items":       po_items,
        "invoice_totals": invoice_doc.get("totals", {}),
        "po_totals":      po_doc.get("totals", {}),
        "invoice_parser": invoice_parser,
        "po_parser":      po_parser,
        "confidence_flags": confidence_flags,
    }

    # ------------------------------------------------------------------
    # PHASE 4 — FAILURE ANALYTICS LOGGING
    # ------------------------------------------------------------------
    log_failure_case(invoice_text, po_text, result_payload)

    return result_payload
