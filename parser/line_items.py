from __future__ import annotations

import json
import logging
import re

from .normalize import (
    is_ocr_item_label_token,
    is_ocr_stop_label_token,
    normalize_currency_value,
    normalize_item_name,
    normalize_ocr_text,
    normalize_percentage,
    normalize_quantity,
    strip_ocr_field_labels,
)

logger = logging.getLogger(__name__)

PARSER_PATH_A = "A"
PARSER_PATH_B = "B"
PARSER_PATH_C = "C"

_FIELD_PATTERNS = {
    "qty": re.compile(r"(?i)\b(?:qty|quantity|qnty)\s*[:=\-]?\s*([0-9][0-9., ]*)"),
    "price": re.compile(r"(?i)\b(?:price|rate|unit\s*price|amount)\s*[:=\-]?\s*((?:rs\.?\s*)?[0-9][0-9, .]*)"),
    "tax": re.compile(r"(?i)\b(?:tax|gst|vat)\s*[:=\-]?\s*([0-9][0-9., ]*\s*%?)"),
    "total": re.compile(r"(?i)\b(?:total|line\s*total|amount)\s*[:=\-]?\s*((?:rs\.?\s*)?[0-9][0-9, .]*)"),
}
_SKIP_LINE_PATTERN = re.compile(
    r"(?i)\b(invoice|purchase\s*order|po\s*number|vendor|date|bill to|ship to|subtotal|grand total|total amount|hsn|sac)\b"
)
_DOCUMENT_TOTAL_PATTERN = re.compile(
    r"(?i)\b(?:grand total|total amount|invoice total|net amount|subtotal)\b\s*[:=\-]?\s*((?:rs\.?\s*)?[0-9][0-9, .]*)"
)
_ROW_START_PATTERN = re.compile(r"(?i)^\s*(?:[-*]|(?:\d+\s*[.)-]))\s*")
_KEYWORD_PATTERN = re.compile(r"(?i)\b(?:qty|quantity|qnty|price|rate|amount|tax|gst|vat|total)\b")
_NUMBER_PATTERN = re.compile(r"(?<![A-Za-z])(?:rs\.?\s*)?[0-9oilszgb]+(?:[.,][0-9oilszgb]+)?\s*%?", re.IGNORECASE)
_QUANTITY_MAX = 1000


def _preview_text(value: str, limit: int = 300) -> str:
    text = str(value or "")
    text = text.replace("\n", "\\n")
    return text[:limit]


def _looks_like_coordinate_payload(text: str) -> bool:
    compact = re.sub(r"\s+", "", str(text or ""))
    if not compact:
        return False

    coordinate_pairs = len(re.findall(r"\[\d+(?:\.\d+)?,\d+(?:\.\d+)?\]", compact))
    numeric_tokens = len(re.findall(r"-?\d+(?:\.\d+)?", compact))
    alphabetic_tokens = len(re.findall(r"[A-Za-z]{2,}", compact))

    return coordinate_pairs >= 2 and alphabetic_tokens == 0 and numeric_tokens >= coordinate_pairs * 2


def _clean_ocr_text(text: str) -> str:
    cleaned = normalize_ocr_text(text)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"(?i)\bqty(?=\d)", "qty ", cleaned)
    cleaned = re.sub(r"(?i)\bprice(?=\d)", "price ", cleaned)
    cleaned = re.sub(r"(?i)\brate(?=\d)", "rate ", cleaned)
    cleaned = re.sub(r"(?i)\b(?:tax|gst|vat)(?=\d)", lambda m: f"{m.group(0)} ", cleaned)
    # cleaned = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", cleaned)
    # cleaned = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"(?<!\n)(\b\d+\.\s+[A-Za-z])", r"\n\1", cleaned)
    cleaned = re.sub(r"(?<!\n)(\b(?:total|grand total|total amount)\b\s*:)", r"\n\1", cleaned, flags=re.I)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _merge_broken_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    buffer = ""

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            if buffer:
                merged.append(buffer.strip())
                buffer = ""
            continue

        if re.match(r"(?i)^(?:total|grand total|total amount)\b", line):
            if buffer:
                merged.append(buffer.strip())
                buffer = ""
            merged.append(line)
            continue

        if buffer and _SKIP_LINE_PATTERN.search(buffer) and _KEYWORD_PATTERN.search(line):
            merged.append(buffer.strip())
            buffer = line
            continue

        current_looks_complete = bool(re.search(r"[A-Za-z]", line) and len(re.findall(r"\d+(?:\.\d+)?", line)) >= 2)
        buffer_looks_complete = bool(buffer and re.search(r"[A-Za-z]", buffer) and len(re.findall(r"\d+(?:\.\d+)?", buffer)) >= 2)
        if buffer_looks_complete and current_looks_complete:
            merged.append(buffer.strip())
            buffer = line
            continue

        looks_continued = bool(buffer) and not _KEYWORD_PATTERN.search(buffer)
        starts_continuation = bool(re.match(r"^(?:[-:|]|qty|price|rate|tax|gst|vat|total)\b", line, re.I))

        if looks_continued or starts_continuation:
            buffer = f"{buffer} {line}".strip()
        else:
            if buffer:
                merged.append(buffer.strip())
            buffer = line

    if buffer:
        merged.append(buffer.strip())

    return merged


def _is_candidate_line(line: str) -> bool:
    if re.match(r"(?i)^(?:total|grand total|total amount)\b", line):
        return False
    if _SKIP_LINE_PATTERN.search(line) and not re.search(r"(?i)\b(?:qty|price|rate)\b", line):
        return False
    if _KEYWORD_PATTERN.search(line):
        return True
    if "|" in line and re.search(r"\d", line):
        return True
    return bool(re.search(r"[A-Za-z]", line) and len(re.findall(r"\d+(?:\.\d+)?", line)) >= 2)


def _split_candidate_lines(text: str) -> list[dict]:
    cleaned_text = _clean_ocr_text(text)
    if re.search(r"(?i)\bitems?\s*:", cleaned_text):
        cleaned_text = re.split(r"(?i)\bitems?\s*:", cleaned_text, maxsplit=1)[1]

    raw_lines = [line.strip() for line in cleaned_text.split("\n")]
    merged = _merge_broken_lines(raw_lines)
    candidates: list[dict] = []

    for raw_line in merged:
        cleaned_line = _clean_ocr_text(raw_line)
        if _is_candidate_line(cleaned_line):
            candidates.append({"raw": raw_line, "cleaned": cleaned_line})

    return candidates


def _extract_item_name(line: str) -> str:
    tokens = re.findall(r"\S+", line)
    head_tokens: list[str] = []
    started = False
    for token in tokens:
        if is_ocr_item_label_token(token) and not started:
            continue
        if is_ocr_stop_label_token(token):
            if started:
                break
            continue
        started = True
        head_tokens.append(token)

    head = " ".join(head_tokens) if head_tokens else line
    head = re.split(r"(?i)\b(?:qty|quantity|qnty|price|rate|tax|gst|vat|total|amount)\b", head, maxsplit=1)[0]
    head = head.replace("|", " ")
    return normalize_item_name(head)


def _extract_field(pattern_name: str, line: str):
    match = _FIELD_PATTERNS[pattern_name].search(line)
    if not match:
        return None
    return match.group(1)


def _extract_columnar_values(line: str, header_indices: dict = None) -> tuple[dict, float, str] | None:
    parts = [part.strip() for part in line.split("|")]
    
    # If dynamic header mapping is available and valid, map fields explicitly by column index
    if header_indices and len(parts) >= max(header_indices.values()) + 1:
        item_idx = header_indices.get("item")
        qty_idx = header_indices.get("qty")
        price_idx = header_indices.get("price")
        total_idx = header_indices.get("total")
        
        if item_idx is not None and (qty_idx is not None or price_idx is not None or total_idx is not None):
            item = normalize_item_name(strip_ocr_field_labels(parts[item_idx]))
            if item:
                parsed = {"item": item}
                if qty_idx is not None:
                    parsed["qty"] = normalize_quantity(parts[qty_idx])
                if price_idx is not None:
                    parsed["price"] = normalize_currency_value(parts[price_idx])
                if total_idx is not None:
                    parsed["total"] = normalize_currency_value(parts[total_idx])
                
                usable_fields = [key for key in ("qty", "price", "total") if parsed.get(key) is not None]
                if usable_fields:
                    parsed = _finalize_numeric_inference(line, parsed, PARSER_PATH_A, "_extract_columnar_values")
                    if parsed:
                        return parsed, 0.98, "columnar"

    # Fallback to structural heuristic
    parts = [part.strip() for part in parts if part.strip()]
    if len(parts) < 2:
        return None

    # Recover from merged columns or missing delimiters within parts
    new_parts = []
    for part in parts:
        sub_tokens = [tok.strip() for tok in re.split(r"\s+", part) if tok.strip()]
        if len(sub_tokens) >= 2 and all(normalize_currency_value(tok) is not None for tok in sub_tokens):
            new_parts.extend(sub_tokens)
        else:
            new_parts.append(part)
    parts = new_parts

    # Improve column alignment robustness by detecting leading serial numbers
    is_serial = False
    if len(parts) >= 3:
        val0 = normalize_currency_value(parts[0])
        val1 = normalize_currency_value(parts[1])
        if val0 is not None and val1 is None:
            if isinstance(val0, int) and 0 < val0 <= 200:
                is_serial = True

    if is_serial:
        item = normalize_item_name(strip_ocr_field_labels(parts[1]))
        numeric_parts = parts[2:]
    else:
        item = normalize_item_name(strip_ocr_field_labels(parts[0]))
        numeric_parts = parts[1:]

    values = [normalize_currency_value(part) for part in numeric_parts]
    values = [value for value in values if value is not None]
    if not item or not values:
        return None

    parsed = {"item": item}
    if len(values) >= 1:
        parsed["qty"] = normalize_quantity(values[0])
    if len(values) >= 2:
        parsed["price"] = normalize_currency_value(values[1])
    if len(values) >= 3:
        maybe_tax = normalize_percentage(values[2])
        if maybe_tax is not None and maybe_tax <= 100:
            parsed["tax"] = maybe_tax
        else:
            parsed["total"] = normalize_currency_value(values[2])
    if len(values) >= 4:
        parsed["total"] = normalize_currency_value(values[3])
    parsed = _finalize_numeric_inference(line, parsed, PARSER_PATH_A, "_extract_columnar_values")
    if not parsed:
        return None
    return parsed, 0.95, "columnar"


def _extract_labeled_values(line: str) -> tuple[dict, float, str] | None:
    item = _extract_item_name(line)
    if not item:
        return None

    parsed = {
        "item": item,
        "qty": normalize_quantity(_extract_field("qty", line)),
        "price": normalize_currency_value(_extract_field("price", line)),
        "tax": normalize_percentage(_extract_field("tax", line)),
        "total": normalize_currency_value(_extract_field("total", line)),
    }
    usable_fields = [key for key in ("qty", "price", "tax", "total") if parsed.get(key) is not None]
    if not usable_fields:
        return None
    parsed = _finalize_numeric_inference(line, parsed, PARSER_PATH_B, "_extract_labeled_values")
    if not parsed:
        return None
    return parsed, 0.9 if len(usable_fields) >= 2 else 0.78, "labeled"


def _numeric_matches(line: str) -> list[dict]:
    matches: list[dict] = []
    for match in _NUMBER_PATTERN.finditer(line):
        token = match.group(0).strip()
        value = normalize_currency_value(token)
        if value is None:
            continue
        left_context = line[max(0, match.start() - 16):match.start()].lower()
        right_context = line[match.end():match.end() + 16].lower()
        segment = f"{left_context}{token.lower()}{right_context}"
        matches.append(
            {
                "text": token,
                "value": value,
                "start": match.start(),
                "end": match.end(),
                "is_percent": "%" in token or any(label in segment for label in ("tax", "gst", "vat")),
                "segment": segment,
                "left_context": left_context,
                "right_context": right_context,
            }
        )
    return matches


def _log_numeric_assignment(line: str, values: list[dict], qty: object, price: object, item: str) -> None:
    logger.info(
        "Numeric inference line=%r detected numeric tokens=%s assigned qty=%r assigned price=%r final cleaned item name=%r",
        line,
        [{"text": entry["text"], "value": entry["value"]} for entry in values],
        qty,
        price,
        item,
    )


def _choose_qty_price_tax_total(values: list[dict], line: str | None = None) -> tuple[object, object, object, object]:
    qty = None
    price = None
    tax = None
    total = None

    explicit_qty = next((entry for entry in values if any(label in entry.get("left_context", "") for label in ("qty", "quantity", "qnty"))), None)
    explicit_price = next((entry for entry in values if any(label in entry.get("left_context", "") for label in ("price", "rate", "amount"))), None)
    explicit_tax = next((entry for entry in values if entry["is_percent"] or any(label in entry.get("left_context", "") for label in ("tax", "gst", "vat"))), None)

    if explicit_qty:
        qty = normalize_quantity(explicit_qty["value"])
    if explicit_price:
        price = normalize_currency_value(explicit_price["value"])
    if explicit_tax:
        tax = normalize_percentage(explicit_tax["value"])

    # Detect if the first numeric token is a serial number at the start of the line
    serial_entry = None
    if line is not None and len(values) >= 3:
        first_val = values[0]
        if "start" in first_val:
            prefix = line[:first_val["start"]]
            if not re.search(r"[A-Za-z0-9]", prefix):
                val_num = first_val["value"]
                if isinstance(val_num, int) and 0 < val_num <= 200:
                    serial_entry = first_val

    trailing = [entry for entry in values if not entry["is_percent"] and entry is not serial_entry]
    if len(trailing) >= 3:
        total = normalize_currency_value(trailing[-1]["value"])

    if qty is None and trailing:
        qty_candidate = next((entry for entry in trailing[:-1] if entry["value"] <= _QUANTITY_MAX), None)
        if qty_candidate is None:
            qty_candidate = next((entry for entry in trailing if entry["value"] <= _QUANTITY_MAX), None)
        if qty_candidate is None and len(trailing) == 1:
            qty_candidate = trailing[0]
        if qty_candidate is not None:
            qty = normalize_quantity(qty_candidate["value"])

    if price is None and trailing:
        ordered_candidates = trailing[:-1] if len(trailing) >= 3 else trailing
        if qty is not None:
            ordered_candidates = [entry for entry in ordered_candidates if normalize_quantity(entry["value"]) != qty]
        price_candidate = None
        if ordered_candidates:
            price_candidate = ordered_candidates[-1]
        elif len(trailing) >= 2:
            price_candidate = trailing[-2]
        elif trailing and qty is None:
            price_candidate = trailing[0]
        if price_candidate is not None:
            price = normalize_currency_value(price_candidate["value"])

    if tax is None:
        percent_candidate = next((entry for entry in values if entry["value"] <= 100 and entry["is_percent"]), None)
        if percent_candidate:
            tax = normalize_percentage(percent_candidate["value"])

    return qty, price, tax, total


def _is_tax_or_subtotal_line(item_name: str) -> bool:
    name_lower = item_name.lower().strip()
    # Keywords that indicate a summary, subtotal, tax, or administrative line
    tax_keywords = {
        "cgst", "sgst", "igst", "utgst", "gst", "tax", "vat", "service tax", 
        "subtotal", "sub-total", "grand total", "total", "round off", 
        "rounding", "cess", "hsn", "sac", "taxable", "net amount", "total amount",
        "discount", "handling", "shipping", "freight"
    }
    
    # Clean punctuation/spaces
    cleaned_name = re.sub(r"[^a-z0-9\s%]", " ", name_lower)
    tokens = set(cleaned_name.split())
    
    # If any token matches a tax/summary keyword
    for token in tokens:
        if token in tax_keywords:
            return True
            
    # Check if it contains percentage + tax pattern, e.g., "cgst 9%" or "sgst 9" or "gst 18"
    if re.search(r"\b(?:cgst|sgst|igst|utgst|gst|tax|vat)\b.*\b\d+", name_lower):
        return True
        
    return False


def _apply_mathematical_consistency(parsed: dict) -> dict:
    qty = parsed.get("qty")
    price = parsed.get("price")
    total = parsed.get("total")
    tax = parsed.get("tax") or 0.0

    # 1. Quantity/Price Swap Detection
    # Only swap if they are mathematically inconsistent in original order,
    # OR if total is missing and qty is extremely large compared to price.
    if qty is not None and price is not None:
        original_consistent = False
        if total is not None:
            calc_total = qty * price
            calc_total_with_tax = calc_total * (1 + tax / 100.0)
            if abs(calc_total - total) < 0.1 or abs(calc_total_with_tax - total) < 0.1:
                original_consistent = True

        if not original_consistent:
            # Let's check if swapped order is consistent:
            swapped_consistent = False
            if total is not None:
                calc_total = price * qty
                calc_total_with_tax = calc_total * (1 + tax / 100.0)
                if abs(calc_total - total) < 0.1 or abs(calc_total_with_tax - total) < 0.1:
                    swapped_consistent = True

            # Swap if swapped is consistent, or if total is missing and it's an obvious swap (qty > 200 and price <= 200 and qty > price)
            if swapped_consistent or (total is None and qty > 200 and price <= 200 and qty > price):
                parsed["qty"] = price
                parsed["price"] = qty
                parsed["swapped"] = True
                qty, price = price, qty

    # 2. Mathematical Field Reconstruction
    # Case A: Qty and Price exist, but Total is missing
    if qty is not None and price is not None and total is None:
        subtotal = qty * price
        parsed["total"] = round(subtotal * (1 + tax / 100.0), 2)
        parsed["reconstructed"] = True
        if parsed["total"].is_integer():
            parsed["total"] = int(parsed["total"])

    # Case B: Price and Total exist, but Qty is missing
    elif qty is None and price is not None and price > 0 and total is not None:
        calc_qty = total / price
        if abs(calc_qty - round(calc_qty)) < 0.01 and 0 < calc_qty <= 1000:
            parsed["qty"] = int(round(calc_qty))
            parsed["reconstructed"] = True
        else:
            calc_qty = (total / (1 + tax / 100.0)) / price
            if abs(calc_qty - round(calc_qty)) < 0.01 and 0 < calc_qty <= 1000:
                parsed["qty"] = int(round(calc_qty))
                parsed["reconstructed"] = True

    # Case C: Qty and Total exist, but Price is missing
    elif qty is not None and qty > 0 and price is None and total is not None:
        calc_price = total / qty
        calc_price_ex_tax = calc_price / (1 + tax / 100.0)
        parsed["price"] = round(calc_price_ex_tax, 2)
        parsed["reconstructed"] = True
        if parsed["price"].is_integer():
            parsed["price"] = int(parsed["price"])

    return parsed


def _finalize_numeric_inference(line: str, parsed: dict, parser_path: str, parser_function: str) -> dict | None:
    values = _numeric_matches(line)
    non_percent_values = [entry for entry in values if not entry["is_percent"]]
    if not non_percent_values and not parsed.get("item"):
        return None

    item = _clean_item_name_from_numeric_tokens(line, non_percent_values) or normalize_item_name(parsed.get("item"))
    qty, price, tax, total = _choose_qty_price_tax_total(values, line)
    finalized = {"item": item, "qty": qty, "price": price, "tax": tax}
    if total is not None:
        finalized["total"] = total

    # Prioritize values that were explicitly parsed by high-confidence structures
    for field in ("qty", "price", "tax", "total"):
        if parsed.get(field) is not None:
            finalized[field] = parsed.get(field)

    if not finalized.get("item"):
        return None

    # Filter out tax/subtotal rows to prevent them from becoming line items
    if _is_tax_or_subtotal_line(finalized["item"]) or _is_tax_or_subtotal_line(line):
        logger.info("[FILTER-TAX] Excluded tax/subtotal line from items: %r (line: %r)", finalized["item"], line)
        return None

    # Apply mathematical consistency check and reconstruction
    finalized = _apply_mathematical_consistency(finalized)

    _log_numeric_assignment(line, non_percent_values, finalized.get("qty"), finalized.get("price"), finalized["item"])
    logger.info(
        "USING PARSER PATH %s parser_function=%s line=%r parsed=%s",
        parser_path,
        parser_function,
        line,
        finalized,
    )
    return finalized


def _clean_item_name_from_numeric_tokens(line: str, values: list[dict]) -> str:
    cleaned_line = line
    for entry in sorted(values, key=lambda value: value["start"], reverse=True):
        cleaned_line = f"{cleaned_line[:entry['start']]} {cleaned_line[entry['end']:]}"

    cleaned_line = re.sub(r"(?i)\b(?:qty|quantity|qnty|price|rate|amount)\b\s*[:=\-]?\s*", " ", cleaned_line)
    cleaned_line = re.sub(r"\s+", " ", cleaned_line).strip()
    return normalize_item_name(strip_ocr_field_labels(cleaned_line))


def _extract_trailing_numeric_values(line: str) -> tuple[dict, float, str] | None:
    values = _numeric_matches(line)
    if len(values) < 2:
        return None

    non_percent_values = [entry for entry in values if not entry["is_percent"]]
    item = _clean_item_name_from_numeric_tokens(line, non_percent_values)
    if not item:
        pivot = non_percent_values[-2]["start"] if len(non_percent_values) >= 2 else values[0]["start"]
        item = normalize_item_name(strip_ocr_field_labels(re.sub(_NUMBER_PATTERN, " ", line)))
        if not item:
            item = normalize_item_name(strip_ocr_field_labels(line[:pivot]))
    if not item:
        return None

    qty, price, tax, total = _choose_qty_price_tax_total(values, line)
    parsed = {"item": item, "qty": qty, "price": price, "tax": tax}
    if total is not None:
        parsed["total"] = total
    parsed = _finalize_numeric_inference(line, parsed, PARSER_PATH_C, "_extract_trailing_numeric_values")
    if not parsed:
        return None

    usable_fields = [key for key in ("qty", "price", "tax", "total") if parsed.get(key) is not None]
    if not usable_fields:
        return None
    return parsed, 0.72 if len(usable_fields) >= 2 else 0.62, "trailing_numeric"


def _extract_token_fallback(line: str) -> tuple[dict, float, str] | None:
    compact = re.sub(r"[|:/\\-]+", " ", line)
    compact = _ROW_START_PATTERN.sub("", compact)
    tokens = [token for token in compact.split() if token]
    if len(tokens) < 3:
        return None

    numeric_indices = [index for index, token in enumerate(tokens) if normalize_currency_value(token) is not None]
    if len(numeric_indices) < 2:
        return None

    numeric_entries = []
    for index in numeric_indices:
        token = tokens[index]
        value = normalize_currency_value(token)
        if value is None:
            continue
        segment = " ".join(tokens[max(0, index - 1): min(len(tokens), index + 2)]).lower()
        numeric_entries.append(
            {
                "text": token,
                "value": value,
                "segment": segment,
                "is_percent": "%" in token or any(label in segment for label in ("tax", "gst", "vat")),
                "start": index,
            }
        )

    item_tokens = [token for token in tokens if normalize_currency_value(token) is None]
    item = normalize_item_name(strip_ocr_field_labels(" ".join(item_tokens[:3] if not item_tokens else item_tokens)))
    if not item:
        return None

    qty, price, tax, total = _choose_qty_price_tax_total(numeric_entries, line)
    parsed = {"item": item, "qty": qty, "price": price, "tax": tax}
    if total is not None:
        parsed["total"] = total

    usable_fields = [key for key in ("qty", "price", "tax", "total") if parsed.get(key) is not None]
    if not usable_fields:
        return None
    return parsed, 0.58 if len(usable_fields) >= 2 else 0.5, "token_fallback"


_ACTIVE_ROW_EXTRACTORS = (
    _extract_columnar_values,
    _extract_labeled_values,
    _extract_trailing_numeric_values,
)


def _parse_candidate_line(line: str, confidence: float | None = None, header_indices: dict = None) -> dict | None:
    for extractor in _ACTIVE_ROW_EXTRACTORS:
        if extractor == _extract_columnar_values:
            extracted = extractor(line, header_indices=header_indices)
        else:
            extracted = extractor(line)
        if not extracted:
            continue
        parsed, base_confidence, strategy = extracted
        usable_fields = [key for key in ("qty", "price", "tax", "total") if parsed.get(key) is not None]
        if not parsed.get("item") or not usable_fields:
            continue

        final_confidence = base_confidence
        if confidence is not None:
            final_confidence = round((base_confidence + confidence) / 2, 4)

        parsed["confidence"] = round(final_confidence, 4)
        parsed["parse_strategy"] = strategy
        return parsed

    return None


def _classify_failed_row(cleaned_line: str) -> str:
    if not cleaned_line.strip():
        return "no rows found"

    if not _extract_item_name(cleaned_line):
        return "regex mismatch"

    numeric_values = _numeric_matches(cleaned_line)
    if len(numeric_values) < 2 and not _KEYWORD_PATTERN.search(cleaned_line) and "|" not in cleaned_line:
        return "regex mismatch"

    parsed_with_missing_values = False
    for extractor in _ACTIVE_ROW_EXTRACTORS:
        extracted = extractor(cleaned_line)
        if not extracted:
            continue
        parsed, _, _ = extracted
        parsed_with_missing_values = True
        if parsed.get("qty") is None:
            return "qty missing"
        if parsed.get("price") is None:
            return "price missing"

    if parsed_with_missing_values:
        return "regex mismatch"

    if _KEYWORD_PATTERN.search(cleaned_line) or "|" in cleaned_line or numeric_values:
        return "qty missing"

    return "regex mismatch"


def extract_line_items_with_diagnostics(text: str, confidence: float | None = None) -> dict:
    if not text or not text.strip():
        trace = {
            "raw_ocr_text": str(text or ""),
            "normalized_ocr_text": "",
            "candidate_rows": [],
            "cleaned_rows": [],
            "parsed_line_items": [],
            "skipped_rows": [],
            "failure_reason": "no rows found",
            "skipped_row_count": 0,
            "parsed_item_count": 0,
            "parser_confidence_score": 0.0,
        }
        logger.warning("Parser received empty OCR text; failure_reason=no rows found")
        return {"items": [], "skipped_rows": [], "parser_confidence_score": 0.0, "failure_reason": "no rows found", "trace": trace}

    if _looks_like_coordinate_payload(text):
        trace = {
            "raw_ocr_text": str(text or ""),
            "normalized_ocr_text": "",
            "candidate_rows": [],
            "cleaned_rows": [],
            "parsed_line_items": [],
            "skipped_rows": [],
            "failure_reason": "coordinate_payload_detected",
            "skipped_row_count": 0,
            "parsed_item_count": 0,
            "parser_confidence_score": 0.0,
        }
        logger.warning(
            "Parser rejected OCR text because it still looks like coordinate arrays. raw_ocr_preview=%s",
            _preview_text(text),
        )
        return {
            "items": [],
            "skipped_rows": [],
            "parser_confidence_score": 0.0,
            "failure_reason": "coordinate_payload_detected",
            "trace": trace,
        }

    items: list[dict] = []
    seen: set[tuple] = set()
    skipped_rows: list[dict] = []
    normalized_text = _clean_ocr_text(text)
    candidate_lines = _split_candidate_lines(text)
    trace = {
        "raw_ocr_text": text,
        "normalized_ocr_text": normalized_text,
        "candidate_rows": [entry["raw"] for entry in candidate_lines],
        "cleaned_rows": [entry["cleaned"] for entry in candidate_lines],
        "parsed_line_items": [],
        "skipped_rows": skipped_rows,
    }

    logger.info("Parser raw OCR text (%d chars): %s", len(text), text)
    logger.info("Parser normalized OCR text (%d chars): %s", len(normalized_text), normalized_text)
    logger.info("Parser split candidate rows (%d): %s", len(trace["candidate_rows"]), trace["candidate_rows"])
    logger.info("Parser cleaned rows (%d): %s", len(trace["cleaned_rows"]), trace["cleaned_rows"])
    logger.info(
        "Parser entrypoint=extract_line_items_with_diagnostics active_paths=%s legacy_disabled=%s",
        ["_extract_columnar_values", "_extract_labeled_values", "_extract_trailing_numeric_values"],
        ["_extract_token_fallback"],
    )

    # Dynamic table header detection and column alignment mapping
    header_indices = {}
    for line in text.split("\n"):
        if "|" in line:
            parts = [p.strip().lower() for p in line.split("|")]
            if any(h in parts for h in ("item", "description", "particulars", "qty", "quantity", "price", "rate", "total", "amount", "hsn", "sac")):
                for idx, part in enumerate(parts):
                    if not part:
                        continue
                    if any(k in part for k in ("item", "description", "desc", "particulars")):
                        header_indices["item"] = idx
                    elif any(k in part for k in ("qty", "quantity", "qnty")):
                        header_indices["qty"] = idx
                    elif any(k in part for k in ("price", "rate", "unit price")):
                        if "total" not in part and "taxable" not in part:
                            header_indices["price"] = idx
                    elif "total" in part or "amount" in part:
                        if "taxable" not in part:
                            header_indices["total"] = idx
                    elif "hsn" in part or "sac" in part:
                        header_indices["hsn"] = idx
                    elif "taxable" in part:
                        header_indices["taxable"] = idx
                    elif any(k in part for k in ("cgst", "sgst", "igst", "utgst", "gst")):
                        header_indices["gst"] = idx
                logger.info("[HEADER-ALIGN] Dynamic column header mapping: %s", header_indices)
                break

    for entry in candidate_lines:
        raw_line = entry["raw"]
        cleaned_line = entry["cleaned"]
        parsed = _parse_candidate_line(cleaned_line, confidence=confidence, header_indices=header_indices)
        extracted_item_name = parsed.get("item") if parsed else _extract_item_name(cleaned_line)
        logger.info(
            "Parser item extraction raw_row=%r cleaned_row=%r extracted_item_name=%r",
            raw_line,
            cleaned_line,
            extracted_item_name,
        )
        if not parsed:
            if _extract_token_fallback(cleaned_line):
                logger.warning(
                    "Legacy fallback parser disabled for row raw_row=%r cleaned_row=%r parser_function=_extract_token_fallback",
                    raw_line,
                    cleaned_line,
                )
            skip_reason = _classify_failed_row(cleaned_line)
            skipped_rows.append({"raw": raw_line, "cleaned": cleaned_line, "reason": skip_reason})
            logger.info("Parser skipped row: %s", {"raw": raw_line, "cleaned": cleaned_line, "reason": skip_reason})
            continue

        key = (
            parsed.get("item"),
            parsed.get("qty"),
            parsed.get("price"),
            parsed.get("tax"),
            parsed.get("total"),
        )
        if key in seen:
            skipped_rows.append({"raw": raw_line, "cleaned": cleaned_line, "reason": "duplicate_row"})
            logger.info("Parser skipped row: %s", {"raw": raw_line, "cleaned": cleaned_line, "reason": "duplicate_row"})
            continue

        seen.add(key)
        items.append(parsed)
        trace["parsed_line_items"].append(parsed)
        logger.info("Parser parsed row: %s", {"raw": raw_line, "cleaned": cleaned_line, "parsed": parsed})

    confidence_values = [item.get("confidence") for item in items if item.get("confidence") is not None]
    base_score = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    coverage = len(items) / len(candidate_lines) if candidate_lines else 0.0
    parser_confidence_score = round((base_score * 0.7) + (coverage * 0.3), 4) if items else 0.0
    if not candidate_lines:
        failure_reason = "no rows found"
    elif not items and skipped_rows:
        distinct_skip_reasons = {row.get("reason") for row in skipped_rows}
        if distinct_skip_reasons == {"regex mismatch"}:
            failure_reason = "regex mismatch"
        elif distinct_skip_reasons == {"qty missing"}:
            failure_reason = "qty missing"
        elif distinct_skip_reasons == {"price missing"}:
            failure_reason = "price missing"
        else:
            failure_reason = "all rows skipped"
    elif not items:
        failure_reason = "parser returned empty list"
    else:
        failure_reason = None

    trace["failure_reason"] = failure_reason
    trace["skipped_row_count"] = len(skipped_rows)
    trace["parsed_item_count"] = len(items)
    trace["parser_confidence_score"] = parser_confidence_score

    logger.info(
        "Structured parser extracted %d line item(s), skipped %d row(s), parser_confidence_score=%s",
        len(items),
        len(skipped_rows),
        parser_confidence_score,
    )
    logger.info("Parser parsed line item objects: %s", items)
    logger.info("Parser skipped rows: %s", skipped_rows)
    if failure_reason:
        logger.warning("Parser failure_reason=%s raw_ocr_preview=%s", failure_reason, _preview_text(text))

    return {
        "items": items,
        "skipped_rows": skipped_rows,
        "parser_confidence_score": parser_confidence_score,
        "failure_reason": failure_reason,
        "trace": trace,
    }


def extract_line_items(text: str, confidence: float | None = None) -> list[dict]:
    return extract_line_items_with_diagnostics(text, confidence=confidence)["items"]


def extract_totals(text: str) -> dict:
    totals: dict[str, float | int] = {}
    if not text:
        return totals

    for match in _DOCUMENT_TOTAL_PATTERN.finditer(text):
        label = re.sub(r"\s+", "_", match.group(0).split(":")[0].split("-")[0].strip().lower())
        value = normalize_currency_value(match.group(1))
        if value is not None:
            totals[label] = value

    return totals


def build_structured_document(text: str, confidence: float | None = None) -> dict:
    logger.info("CALL CHAIN parser entrypoint=build_structured_document text_len=%d", len(text or ""))
    line_item_result = extract_line_items_with_diagnostics(text, confidence=confidence)
    items = line_item_result["items"]
    totals = extract_totals(text)
    return {
        "line_items": items,
        "totals": totals,
        "line_item_count": len(items),
        "skipped_rows": line_item_result["skipped_rows"],
        "parser_confidence_score": line_item_result["parser_confidence_score"],
        "failure_reason": line_item_result.get("failure_reason"),
        "raw_ocr_preview": _preview_text(text),
        "parsed_item_count": len(items),
        "skipped_row_count": len(line_item_result["skipped_rows"]),
        "parser_trace": line_item_result.get("trace", {}),
        "structured_json": json.dumps(
            {
                "line_items": items,
                "totals": totals,
                "skipped_rows": line_item_result["skipped_rows"],
                "parser_confidence_score": line_item_result["parser_confidence_score"],
                "failure_reason": line_item_result.get("failure_reason"),
            },
            ensure_ascii=True,
        ),
        "parse_success": bool(items or totals),
    }
