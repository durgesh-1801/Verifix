from __future__ import annotations

import logging
import re
from io import BytesIO

import pdfplumber
import pypdfium2 as pdfium
import pytesseract
from PIL import Image
from pytesseract import TesseractError, TesseractNotFoundError

from .detect_pdf_type import detect_pdf_type
from .preprocess import preprocess_image

logger = logging.getLogger(__name__)

try:
    from paddleocr import PaddleOCR
except ImportError:  # pragma: no cover - depends on runtime package availability
    PaddleOCR = None

_MIN_DIRECT_TEXT_CHARS = 80
_PADDLE_OCR = None


def _clean_text(text: str) -> str:
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_text_pdfplumber(data: bytes) -> tuple[str, list[dict]]:
    parts: list[str] = []
    pages: list[dict] = []
    with pdfplumber.open(BytesIO(data)) as pdf:
        for index, page in enumerate(pdf.pages):
            try:
                raw_text = page.extract_text() or ""
                table_rows = page.extract_tables() or []
            except Exception as exc:
                logger.warning("pdfplumber page %d failed: %s", index, exc)
                raw_text = ""
                table_rows = []

            page_parts: list[str] = []
            if raw_text.strip():
                page_parts.append(raw_text.strip())

            for table in table_rows:
                normalized_rows = []
                for row in table:
                    cells = [cell.strip() for cell in row if cell and cell.strip()]
                    if cells:
                        normalized_rows.append(" | ".join(cells))
                if normalized_rows:
                    page_parts.append("\n".join(normalized_rows))

            page_text = "\n".join(page_parts).strip()
            pages.append(
                {
                    "page_number": index + 1,
                    "text": page_text,
                    "confidence": 1.0 if page_text else 0.0,
                    "engine": "pdfplumber",
                }
            )
            if page_text:
                parts.append(page_text)

    return _clean_text("\n\n".join(parts)), pages


def _get_paddle_ocr():
    global _PADDLE_OCR
    if PaddleOCR is None:
        return None
    if _PADDLE_OCR is None:
        _PADDLE_OCR = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    return _PADDLE_OCR


def _group_paddle_lines(result: list) -> tuple[str, float]:
    rows: list[tuple[float, float, str, float]] = []
    for line in result or []:
        if not line or len(line) < 2:
            continue
        box, payload = line[0], line[1]
        if not payload or len(payload) < 2:
            continue
        text, confidence = payload[0], float(payload[1])
        xs = [point[0] for point in box]
        ys = [point[1] for point in box]
        rows.append((sum(ys) / len(ys), min(xs), text.strip(), confidence))

    if not rows:
        return "", 0.0

    rows.sort(key=lambda entry: (round(entry[0] / 12), entry[1]))
    grouped: list[list[tuple[float, float, str, float]]] = []
    for row in rows:
        if not grouped or abs(grouped[-1][-1][0] - row[0]) > 12:
            grouped.append([row])
        else:
            grouped[-1].append(row)

    lines: list[str] = []
    confidences: list[float] = []
    for group in grouped:
        group.sort(key=lambda entry: entry[1])
        line_text = " | ".join(item[2] for item in group if item[2])
        if line_text:
            lines.append(line_text)
            confidences.extend(item[3] for item in group)

    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return _clean_text("\n".join(lines)), round(average_confidence, 4)


def _ocr_page_with_paddle(image: Image.Image) -> tuple[str, float]:
    ocr = _get_paddle_ocr()
    if ocr is None:
        return "", 0.0

    result = ocr.ocr(image, cls=True)
    if not result:
        return "", 0.0
    return _group_paddle_lines(result[0] if isinstance(result, list) else result)


def _ocr_page_with_tesseract(image: Image.Image) -> tuple[str, float]:
    data = pytesseract.image_to_data(
        image,
        config="--oem 3 --psm 6",
        output_type=pytesseract.Output.DICT,
    )
    tokens: list[str] = []
    confidences: list[float] = []
    for index, token in enumerate(data.get("text", [])):
        text = (token or "").strip()
        if not text:
            continue
        confidence_raw = data.get("conf", [])[index]
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = -1.0
        if confidence >= 0:
            confidences.append(confidence / 100.0)
        tokens.append(text)

    text = _clean_text(" ".join(tokens))
    average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
    return text, round(average_confidence, 4)


def _extract_text_ocr(data: bytes) -> tuple[str, list[dict], str]:
    pages: list[dict] = []
    text_parts: list[str] = []
    engine_used = "pytesseract"
    pdf = pdfium.PdfDocument(BytesIO(data), autoclose=True)
    scale = 300 / 72

    try:
        for index in range(len(pdf)):
            page = pdf[index]
            try:
                bitmap = page.render(scale=scale)
                pil_image = bitmap.to_pil()
                processed = preprocess_image(pil_image)

                page_text, confidence = _ocr_page_with_paddle(processed)
                if page_text:
                    engine = "paddleocr"
                    engine_used = "paddleocr"
                else:
                    page_text, confidence = _ocr_page_with_tesseract(processed)
                    engine = "pytesseract"

                pages.append(
                    {
                        "page_number": index + 1,
                        "text": page_text,
                        "confidence": confidence,
                        "engine": engine,
                        "uncertain": confidence < 0.6 if confidence else True,
                    }
                )
                if page_text:
                    text_parts.append(page_text)
            except Exception as exc:
                logger.warning("OCR page %d failed: %s", index, exc)
                pages.append(
                    {
                        "page_number": index + 1,
                        "text": "",
                        "confidence": 0.0,
                        "engine": engine_used,
                        "uncertain": True,
                        "error": str(exc),
                    }
                )
            finally:
                page.close()
    finally:
        pdf.close()

    return _clean_text("\n\n".join(text_parts)), pages, engine_used


def extract_pdf_content(file_bytes: bytes) -> dict:
    """Return text plus OCR metadata while avoiding OCR for text PDFs."""
    if not file_bytes:
        return {
            "text": "",
            "pages": [],
            "pdf_type": "unknown",
            "engine": "none",
            "confidence": 0.0,
        }

    data = bytes(file_bytes)
    detection = detect_pdf_type(data)

    direct_text = ""
    direct_pages: list[dict] = []
    if detection["pdf_type"] == "text":
        try:
            direct_text, direct_pages = _extract_text_pdfplumber(data)
        except Exception as exc:
            logger.warning("Direct text extraction failed, falling back to OCR: %s", exc)

    if detection["pdf_type"] == "text" and len(direct_text) >= _MIN_DIRECT_TEXT_CHARS:
        return {
            "text": direct_text,
            "pages": direct_pages,
            "pdf_type": detection["pdf_type"],
            "engine": "pdfplumber",
            "confidence": 1.0 if direct_text else 0.0,
            "detection": detection,
        }

    try:
        ocr_text, ocr_pages, engine = _extract_text_ocr(data)
    except (TesseractNotFoundError, TesseractError, OSError, RuntimeError) as exc:
        logger.error("OCR unavailable: %s", exc)
        return {
            "text": direct_text,
            "pages": direct_pages,
            "pdf_type": detection["pdf_type"],
            "engine": "pdfplumber" if direct_text else "none",
            "confidence": 1.0 if direct_text else 0.0,
            "detection": detection,
            "error": str(exc),
        }

    overall_confidence = 0.0
    confidences = [page["confidence"] for page in ocr_pages if page.get("confidence") is not None]
    if confidences:
        overall_confidence = round(sum(confidences) / len(confidences), 4)

    return {
        "text": ocr_text or direct_text,
        "pages": ocr_pages if ocr_text else direct_pages,
        "pdf_type": "scanned" if ocr_text else detection["pdf_type"],
        "engine": engine if ocr_text else "pdfplumber",
        "confidence": overall_confidence if ocr_text else (1.0 if direct_text else 0.0),
        "detection": detection,
    }


def extract_text_from_pdf(file_bytes: bytes) -> str:
    return extract_pdf_content(file_bytes).get("text", "")
