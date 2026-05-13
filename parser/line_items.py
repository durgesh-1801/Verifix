from __future__ import annotations

import json
import logging
import re

from .normalize import (
    normalize_currency_value,
    normalize_item_name,
    normalize_percentage,
    normalize_quantity,
)

logger = logging.getLogger(__name__)

_FIELD_PATTERNS = {
    "quantity": re.compile(r"(?i)\b(?:qty|quantity|qnty)\s*[:\-]?\s*([0-9][0-9., ]*)"),
    "price": re.compile(r"(?i)\b(?:price|rate|unit\s*price|amount)\s*[:\-]?\s*([₹]?\s*(?:rs\.?\s*)?[0-9][0-9, .]*)"),
    "tax": re.compile(r"(?i)\b(?:tax|gst|vat)\s*[:\-]?\s*([0-9][0-9., ]*\s*%?)"),
    "total": re.compile(r"(?i)\b(?:total|line\s*total|amount)\s*[:\-]?\s*([₹]?\s*(?:rs\.?\s*)?[0-9][0-9, .]*)"),
}
_SKIP_LINE_PATTERN = re.compile(
    r"(?i)\b(invoice|purchase\s*order|po\s*number|vendor|date|bill to|ship to|subtotal|grand total|total amount)\b"
)
_DOCUMENT_TOTAL_PATTERN = re.compile(
    r"(?i)\b(?:grand total|total amount|invoice total|net amount|subtotal)\b\s*[:\-]?\s*([₹]?\s*(?:rs\.?\s*)?[0-9][0-9, .]*)"
)


def _clean_ocr_text(text: str) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace("|", " | ")
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"([A-Za-z])([0-9])", r"\1 \2", cleaned)
    cleaned = re.sub(r"([0-9])([A-Za-z])", r"\1 \2", cleaned)
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

        looks_continued = bool(buffer) and not re.search(r"(?i)\b(?:qty|price|rate|tax|total)\b", buffer)
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


def _split_candidate_lines(text: str) -> list[str]:
    cleaned_text = _clean_ocr_text(text)
    if re.search(r"(?i)\bitems?\s*:", cleaned_text):
        cleaned_text = re.split(r"(?i)\bitems?\s*:", cleaned_text, maxsplit=1)[1]

    lines = [line.strip() for line in cleaned_text.split("\n")]
    merged = _merge_broken_lines(lines)
    candidates: list[str] = []

    for line in merged:
        if re.match(r"(?i)^(?:total|grand total|total amount)\b", line):
            continue
        if _SKIP_LINE_PATTERN.search(line) and not re.search(r"(?i)\b(?:qty|price|rate)\b", line):
            continue
        if re.search(r"(?i)\b(?:qty|price|rate|gst|vat|tax)\b", line):
            candidates.append(line)
            continue
        if "|" in line and re.search(r"\d", line):
            candidates.append(line)

    return candidates


def _extract_item_name(line: str) -> str:
    head = re.split(r"(?i)\b(?:qty|quantity|qnty|price|rate|tax|gst|vat|total|amount)\b", line, maxsplit=1)[0]
    head = head.replace("|", " ")
    return normalize_item_name(head)


def _extract_field(pattern_name: str, line: str):
    match = _FIELD_PATTERNS[pattern_name].search(line)
    if not match:
        return None
    return match.group(1)


def _extract_columnar_values(line: str) -> dict:
    parts = [part.strip() for part in line.split("|") if part.strip()]
    if len(parts) < 2:
        return {}

    item = normalize_item_name(parts[0])
    numeric_parts = parts[1:]
    values = [normalize_currency_value(part) for part in numeric_parts]
    values = [value for value in values if value is not None]
    if not item or not values:
        return {}

    parsed = {"item": item}
    if len(values) >= 1:
        parsed["quantity"] = normalize_quantity(values[0])
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
    return parsed


def _parse_candidate_line(line: str, confidence: float | None = None) -> dict | None:
    parsed = _extract_columnar_values(line)
    if not parsed:
        item = _extract_item_name(line)
        if not item:
            return None

        parsed = {
            "item": item,
            "quantity": normalize_quantity(_extract_field("quantity", line)),
            "price": normalize_currency_value(_extract_field("price", line)),
            "tax": normalize_percentage(_extract_field("tax", line)),
            "total": normalize_currency_value(_extract_field("total", line)),
        }

    usable_fields = [key for key in ("quantity", "price", "tax", "total") if parsed.get(key) is not None]
    if not parsed.get("item") or not usable_fields:
        return None

    parsed["confidence"] = round(confidence, 4) if confidence is not None else None
    return parsed


def extract_line_items(text: str, confidence: float | None = None) -> list[dict]:
    if not text or not text.strip():
        return []

    items: list[dict] = []
    seen: set[tuple] = set()

    for line in _split_candidate_lines(text):
        parsed = _parse_candidate_line(line, confidence=confidence)
        if not parsed:
            continue
        key = (
            parsed.get("item"),
            parsed.get("quantity"),
            parsed.get("price"),
            parsed.get("tax"),
            parsed.get("total"),
        )
        if key in seen:
            continue
        seen.add(key)
        items.append(parsed)

    logger.info("Structured parser extracted %d line item(s)", len(items))
    return items


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
    items = extract_line_items(text, confidence=confidence)
    totals = extract_totals(text)
    return {
        "line_items": items,
        "totals": totals,
        "line_item_count": len(items),
        "structured_json": json.dumps({"line_items": items, "totals": totals}, ensure_ascii=True),
        "parse_success": bool(items or totals),
    }
