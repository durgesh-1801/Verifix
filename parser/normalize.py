from __future__ import annotations

from difflib import SequenceMatcher
import re


def _compact_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


_ITEM_FIELD_LABELS = ("item", "qty", "quantity", "price", "rate", "amount")
_ITEM_STOP_LABELS = _ITEM_FIELD_LABELS + ("tax", "gst", "vat", "total")
_OCR_FUZZY_TRANSLATION = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "5": "s",
        "|": "i",
        "!": "i",
        "l": "i",
        "v": "y",
    }
)


def _normalize_ocr_token_for_match(token: str) -> str:
    token = re.sub(r"^[\W_]+|[\W_]+$", "", (token or "").lower())
    token = token.translate(_OCR_FUZZY_TRANSLATION)
    return re.sub(r"[^a-z]", "", token)


def _looks_like_ocr_field_label(token: str, labels: tuple[str, ...] = _ITEM_STOP_LABELS) -> bool:
    normalized_token = _normalize_ocr_token_for_match(token)
    if not normalized_token:
        return False

    for label in labels:
        if normalized_token == label:
            return True
        if abs(len(normalized_token) - len(label)) > 2:
            continue
        if SequenceMatcher(None, normalized_token, label).ratio() >= 0.72:
            return True
    return False


def is_ocr_item_label_token(token: str) -> bool:
    return _looks_like_ocr_field_label(token, labels=("item",))


def is_ocr_stop_label_token(token: str) -> bool:
    return _looks_like_ocr_field_label(token)


def strip_ocr_field_labels(value: object) -> str:
    tokens = re.findall(r"\S+", normalize_ocr_text(value).lower())
    cleaned_tokens: list[str] = []
    for token in tokens:
        stripped = re.sub(r"^[\W_]+|[\W_]+$", "", token)
        if _looks_like_ocr_field_label(stripped):
            continue
        cleaned_tokens.append(token)
    return _compact_whitespace(" ".join(cleaned_tokens))


def normalize_ocr_text(value: object) -> str:
    text = str(value or "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("â‚¹", " rs ")
    text = text.replace("Ã¢â€šÂ¹", " rs ")
    text = text.replace("|", " | ")
    text = text.replace("â€”", "-").replace("â€“", "-")
    text = re.sub(r"([:;.,\-])\1+", r"\1", text)
    text = re.sub(r"(?i)\b(qty|quantity|qnty)(\d)", r"\1 \2", text)
    text = re.sub(r"(?i)\b(price|rate|amount|tax|gst|vat)(\d)", r"\1 \2", text)
    text = re.sub(r"(?i)(\d)(qty|quantity|qnty|price|rate|amount|tax|gst|vat)\b", r"\1 \2", text)
    text = re.sub(r"(?i)\bq\s*t\s*y\b", "qty", text)
    text = re.sub(r"(?i)\bq\s*u\s*a\s*n\s*t\s*i\s*t\s*y\b", "quantity", text)
    text = re.sub(r"(?i)\bpr1ce\b", "price", text)
    text = re.sub(r"(?i)\bprlce\b", "price", text)
    text = re.sub(r"(?i)\bp\s*r\s*i\s*c\s*e\b", "price", text)
    text = re.sub(r"(?i)\br\s*a\s*t\s*e\b", "rate", text)
    text = re.sub(r"(?i)\bam0unt\b", "amount", text)
    text = re.sub(r"(?i)\bqt[yv]\b", "qty", text)
    text = re.sub(r"(?i)\b1tem\b", "item", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def clean_ocr_numeric_token(text: str) -> str:
    if not text:
        return text
    t = text.strip()
    
    # If the token is purely alphabetical (contains only letters) and has no digits or punctuation,
    # then it is a text word, not a number! (e.g. "is", "so", "lo").
    has_digit = any(c.isdigit() for c in t)
    has_numeric_symbol = any(c in ".,-%$" for c in t)
    if not has_digit and not has_numeric_symbol:
        return t

    # If the token contains any alphabetical character that is not a numeric homoglyph (not in oilszgb), 
    # then it is a text word rather than a number. We should NOT clean it or treat it as numeric!
    has_non_homoglyph_letters = any(c.isalpha() and c.lower() not in "oilszgb" for c in t)
    if has_non_homoglyph_letters:
        return t

    # Check if the token is a candidate for homoglyph translation.
    # It must contain at least one digit or be composed entirely of digits/letters/symbols 
    # that are common OCR misreads (e.g. l, i, o, O, I, |, !, s, S, z, Z, g, b) plus commas/periods/percent/currency signs.
    is_numeric_homoglyph = all(c.isdigit() or c.lower() in "oilszgb.,%-$ \t|!" for c in t)
    
    if has_digit or is_numeric_homoglyph:
        # Create a translation table mapping lowercase letters to their numeric equivalents
        translation = {
            'o': '0',
            'i': '1',
            'l': '1',
            '|': '1',
            '!': '1',
            's': '5',
            'z': '2',
            'g': '9',
            'b': '8'
        }
        chars = []
        for char in t:
            cl = char.lower()
            if cl in translation:
                chars.append(translation[cl])
            else:
                chars.append(char)
        return "".join(chars)
    return t


def normalize_currency_value(value: object) -> float | int | None:
    """Parse a single numeric token into a Python int or float.

    This function is intentionally conservative: it operates on ONE numeric
    token at a time and must not merge adjacent numbers that were separated by
    whitespace in the original OCR text (e.g. ``"6 5000"`` must NOT become
    ``65000``).  Token splitting should happen at the OCR reconstruction layer
    *before* individual tokens reach this function.

    Safe transformations applied:
    - Strip leading ``rs`` / ``inr`` currency prefixes.
    - Remove comma thousands separators (``1,500`` → ``1500``).
    - Strip any remaining non-numeric characters (except ``.`` and ``-``).
    - Spaces adjacent to a comma are collapsed (handles ``"1, 500"`` style).
    """
    if value is None:
        return None

    text = normalize_ocr_text(value).strip()
    if not text:
        return None

    # Remove currency prefixes first to prevent their letters (e.g. 's' in 'Rs.', 'i' in 'INR') from being translated as digits
    text = re.sub(r"(?i)\b(?:rs|inr)\.?\s*", "", text)

    # If the token is purely alphabetical and has no digits or symbols, reject it
    has_digit = any(c.isdigit() for c in text)
    has_numeric_symbol = any(c in ".,-%$" for c in text)
    if not has_digit and not has_numeric_symbol:
        return None

    # If the token contains non-homoglyph alphabet characters (e.g. "Lapt0p", "M0use"), it is a text word, not a number!
    if any(c.isalpha() and c.lower() not in "oilszgb" for c in text):
        return None

    text = clean_ocr_numeric_token(text)
    # Remove commas used as thousands separators, including any surrounding
    # whitespace strictly adjacent to a comma digit group
    # e.g. "1,500" -> "1500",  "1, 500" -> "1500", but "6 5000" -> kept as-is
    text = re.sub(r"(\d)\s*,\s*(\d)", r"\1\2", text)
    # Strip all non-numeric chars except decimal point and negative sign
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
    text = normalize_ocr_text(value).replace("%", "").strip()
    number = normalize_currency_value(text)
    if number is None:
        return None
    if isinstance(number, (int, float)) and number < 0:
        return None
    return number


def normalize_item_name(value: object) -> str:
    text = strip_ocr_field_labels(value)
    text = _compact_whitespace(text)
    text = re.sub(r"(?i)^(?:invoice|invoice no|invoice number|purchase order|po|po no|po number)\b[\s:#-]*[a-z0-9-]*\s*", "", text)
    text = re.sub(r"^\d+\s+", "", text)
    text = re.sub(r"^[\W_]+", "", text)
    text = re.sub(r"[\W_]+$", "", text)
    text = re.sub(r"(?i)\b(?:item|description|desc|particulars)\b\s*[:\-]?\s*", "", text)
    text = re.sub(r"^\d+\s*[.)-]\s*", "", text)
    text = re.sub(r"[^\w\s\-./&]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text
