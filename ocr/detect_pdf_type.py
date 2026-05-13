from __future__ import annotations

import logging
from io import BytesIO

import fitz
import pdfplumber

logger = logging.getLogger(__name__)

_MIN_TEXT_CHARS = 60
_MIN_AVG_CHARS_PER_PAGE = 20


def _extract_with_pymupdf(data: bytes) -> tuple[str, int]:
    parts: list[str] = []
    page_count = 0
    with fitz.open(stream=data, filetype="pdf") as doc:
        page_count = len(doc)
        for page in doc:
            parts.append(page.get_text("text") or "")
    return "\n".join(parts).strip(), page_count


def _extract_with_pdfplumber(data: bytes) -> tuple[str, int]:
    parts: list[str] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            try:
                parts.append((page.extract_text() or "").strip())
            except Exception as exc:
                logger.debug("pdfplumber page extraction failed: %s", exc)
                parts.append("")
    return "\n".join(part for part in parts if part).strip(), page_count


def detect_pdf_type(file_bytes: bytes) -> dict:
    """Classify a PDF as text or scanned using lightweight native extraction."""
    if not file_bytes:
        return {
            "pdf_type": "unknown",
            "reason": "empty_file",
            "text_length": 0,
            "page_count": 0,
            "avg_chars_per_page": 0.0,
        }

    data = bytes(file_bytes)

    fitz_text = ""
    fitz_pages = 0
    plumber_text = ""
    plumber_pages = 0

    try:
        fitz_text, fitz_pages = _extract_with_pymupdf(data)
    except Exception as exc:
        logger.debug("PyMuPDF type detection failed: %s", exc)

    try:
        plumber_text, plumber_pages = _extract_with_pdfplumber(data)
    except Exception as exc:
        logger.debug("pdfplumber type detection failed: %s", exc)

    extracted_text = plumber_text if len(plumber_text) >= len(fitz_text) else fitz_text
    page_count = max(fitz_pages, plumber_pages)
    text_length = len(extracted_text.strip())
    avg_chars = text_length / page_count if page_count else 0.0

    pdf_type = "text"
    reason = "sufficient_embedded_text"
    if text_length < _MIN_TEXT_CHARS or avg_chars < _MIN_AVG_CHARS_PER_PAGE:
        pdf_type = "scanned"
        reason = "embedded_text_too_low"

    result = {
        "pdf_type": pdf_type,
        "reason": reason,
        "text_length": text_length,
        "page_count": page_count,
        "avg_chars_per_page": round(avg_chars, 2),
        "text_preview": extracted_text[:500],
    }
    logger.info("PDF detection result: %s", result)
    return result
