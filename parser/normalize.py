from __future__ import annotations

import re


def _compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def normalize_currency_value(value: object) -> float | int | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    text = re.sub(r"(?i)\b(?:rs|inr)\.?\s*", "", text)
    text = text.replace("₹", "")
    text = text.replace(",", "")
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    text = re.sub(r"[^\d.\-]", "", text)

    if not text or text in {".", "-", "-."}:
        return None

    try:
        number = float(text)
    except ValueError:
        return None

    return int(number) if number.is_integer() else round(number, 2)


def normalize_quantity(value: object) -> float | int | None:
    number = normalize_currency_value(value)
    if number is None:
        return None
    if isinstance(number, float) and number.is_integer():
        return int(number)
    return number


def normalize_percentage(value: object) -> float | int | None:
    if value is None:
        return None
    text = str(value).replace("%", "").strip()
    number = normalize_currency_value(text)
    if number is None:
        return None
    if isinstance(number, (int, float)) and number < 0:
        return None
    return number


def normalize_item_name(value: object) -> str:
    text = _compact_whitespace(str(value or ""))
    text = re.sub(r"^[\W_]+", "", text)
    text = re.sub(r"[\W_]+$", "", text)
    text = re.sub(r"(?i)\b(?:item|description|desc|particulars)\b\s*[:\-]?\s*", "", text)
    text = re.sub(r"^\d+\s*[.)-]\s*", "", text)
    return text.title()
