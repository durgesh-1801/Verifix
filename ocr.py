"""PDF text extraction: pdfplumber first, Tesseract OCR fallback for scanned pages.
Supports raw bytes or file-like objects. Includes per-page debug logging.
"""

from __future__ import annotations

import logging
import re
from io import BytesIO

import pdfplumber
import pytesseract
import pypdfium2 as pdfium
from pytesseract import TesseractError, TesseractNotFoundError

logger = logging.getLogger(__name__)

# If pdfplumber yields fewer chars than this, treat the PDF as scanned → OCR.
_MIN_CHARS_FOR_DIRECT_EXTRACT = 100  # raised from 50 – 50 is too low for real invoices


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text_pdfplumber(data: bytes) -> str:
    parts: list[str] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        logger.debug("pdfplumber: %d page(s) found", len(pdf.pages))
        for i, page in enumerate(pdf.pages):
            try:
                raw = page.extract_text() or ""
            except Exception as exc:
                logger.warning("pdfplumber page %d failed: %s", i, exc)
                raw = ""
            logger.debug("pdfplumber page %d: %d chars", i, len(raw.strip()))
            if raw.strip():
                parts.append(raw.strip())
    return _clean_text("\n\n".join(parts))


def _extract_text_ocr(data: bytes) -> str:
    """Rasterise every page at ~300 DPI and run Tesseract."""
    parts: list[str] = []
    pdf = pdfium.PdfDocument(BytesIO(data), autoclose=True)
    scale = 300 / 72  # ~300 DPI
    try:
        logger.debug("OCR: %d page(s) to rasterise", len(pdf))
        for i in range(len(pdf)):
            page = pdf[i]
            try:
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                chunk = pytesseract.image_to_string(pil_image, config="--psm 6")
            except Exception as exc:
                logger.warning("OCR page %d failed: %s", i, exc)
                chunk = ""
            finally:
                page.close()
            logger.debug("OCR page %d: %d chars", i, len(chunk.strip()))
            if chunk.strip():
                parts.append(chunk.strip())
    finally:
        pdf.close()
    return _clean_text("\n\n".join(parts))


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extract text from a PDF (multi-page).
    Strategy:
      1. pdfplumber  → fast, works for text-based PDFs
      2. Tesseract   → fallback for scanned / image-only PDFs

    Returns cleaned text string. Never raises — returns "" on complete failure.
    """
    if not file_bytes:
        logger.warning("extract_text_from_pdf: received empty bytes")
        return ""
    if not isinstance(file_bytes, (bytes, bytearray)):
        logger.error("extract_text_from_pdf: expected bytes, got %s", type(file_bytes))
        return ""

    data = bytes(file_bytes)
    direct = ""

    try:
        direct = _extract_text_pdfplumber(data)
        logger.info("pdfplumber extracted %d chars", len(direct))
    except Exception as exc:
        logger.error("pdfplumber failed entirely: %s", exc)
        direct = ""

    if len(direct) >= _MIN_CHARS_FOR_DIRECT_EXTRACT:
        return direct

    logger.info(
        "pdfplumber result too short (%d chars) — falling back to OCR", len(direct)
    )

    try:
        ocr_text = _extract_text_ocr(data)
        logger.info("OCR extracted %d chars", len(ocr_text))
    except (TesseractNotFoundError, TesseractError, OSError, RuntimeError) as exc:
        logger.error("OCR unavailable: %s", exc)
        return direct
    except Exception as exc:
        logger.error("OCR unexpected failure: %s", exc)
        return direct

    return ocr_text if ocr_text else directpp