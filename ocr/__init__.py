"""Public OCR entrypoints used by the Flask app.

The package exposes the same simple API the MVP had while adding
modular detection, preprocessing, and engine selection internally.
"""

from .detect_pdf_type import detect_pdf_type
from .extract import extract_pdf_content, extract_text_from_pdf

__all__ = ["detect_pdf_type", "extract_pdf_content", "extract_text_from_pdf"]
