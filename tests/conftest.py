"""Shared test fixtures for the Verifix test suite.

Provides reusable OCR text samples, mock objects, and Flask test client
so individual test modules stay focused on their domain.
"""
from __future__ import annotations

import json
import os
import sys
import pytest

# Ensure project root is on sys.path so imports work without pip install
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# OCR text fixtures — realistic samples for parser and reconciliation tests
# ---------------------------------------------------------------------------

CLEAN_INVOICE_OCR = """
INVOICE
Invoice No: INV-2024-001
Date: 15/03/2024
Vendor: ABC Enterprises

Sr No | Item        | Qty | Rate    | Amount
1     | Laptop      | 10  | 45000   | 450000
2     | Mouse       | 20  | 500     | 10000
3     | Monitor     | 5   | 12000   | 60000
4     | Keyboard    | 15  | 800     | 12000

Subtotal: 532000
GST @ 18%: 95760
Grand Total: 627760
"""

CLEAN_PO_OCR = """
PURCHASE ORDER
PO No: PO-2024-001
Date: 10/03/2024
Vendor: ABC Enterprises

Sr No | Item        | Qty | Rate    | Amount
1     | Laptop      | 10  | 45000   | 450000
2     | Mouse       | 20  | 500     | 10000
3     | Monitor     | 5   | 12000   | 60000
4     | Keyboard    | 15  | 800     | 12000

Subtotal: 532000
GST @ 18%: 95760
Grand Total: 627760
"""

# Invoice with quantity and price mismatches
MISMATCHED_INVOICE_OCR = """
INVOICE
Invoice No: INV-2024-002
Date: 20/03/2024

Sr No | Item        | Qty | Rate    | Amount
1     | Laptop      | 12  | 45000   | 540000
2     | Mouse       | 20  | 600     | 12000
3     | Monitor     | 5   | 12000   | 60000
4     | Keyboard    | 15  | 800     | 12000
"""

MISMATCHED_PO_OCR = """
PURCHASE ORDER
PO No: PO-2024-002
Date: 15/03/2024

Sr No | Item        | Qty | Rate    | Amount
1     | Laptop      | 10  | 45000   | 450000
2     | Mouse       | 20  | 500     | 10000
3     | Monitor     | 5   | 12000   | 60000
4     | Keyboard    | 15  | 800     | 12000
"""

# OCR text with realistic corruption (scanned invoice simulation)
CORRUPTED_OCR_TEXT = """
lnv0ice No: lNV-2024-003
Date: 25/O3/2024

Sr No | ltem        | oty | Prlce   | Am0unt
1     | Lapt0p      | l0  | 45,OOO  | 45O,OOO
2     | M0use       | 2O  | 5OO     | lO,OOO
3     | Monltor     | 5   | 12,OOO  | 6O,OOO
4     | Keyb0ard    | l5  | 8OO     | l2,OOO
"""

# Blurry OCR — lots of missing/garbled data
BLURRY_OCR_TEXT = """
INV
Date: 1 /0 /202

Item Qty Price
Laptop 10 45000
Mou e 20 0
M nitor 5 12000
"""

# GST-heavy invoice
GST_INVOICE_OCR = """
TAX INVOICE
Invoice No: GST/2024/001
GSTIN: 27AABCU9603R1ZM
Date: 01/04/2024

Sr | Item        | HSN   | Qty | Rate  | Taxable | CGST 9% | SGST 9% | Total
1  | Office Chair| 94017 | 10  | 5000  | 50000   | 4500    | 4500    | 59000
2  | Desk        | 94036 | 5   | 12000 | 60000   | 5400    | 5400    | 70800
3  | Filing Cab  | 94031 | 3   | 8000  | 24000   | 2160    | 2160    | 28320

Subtotal: 134000
CGST: 12060
SGST: 12060
Grand Total: 158120
"""

# Invoice with duplicate items
DUPLICATE_ITEMS_OCR = """
INVOICE
Invoice No: INV-2024-004

Item        | Qty | Rate
Laptop      | 5   | 45000
Mouse       | 10  | 500
Laptop      | 5   | 45000
Keyboard    | 8   | 800
"""

# Invoice with missing items (fewer items than PO)
MISSING_ITEMS_INVOICE_OCR = """
INVOICE
Invoice No: INV-2024-005

Item        | Qty | Rate
Laptop      | 10  | 45000
Mouse       | 20  | 500
"""

MISSING_ITEMS_PO_OCR = """
PURCHASE ORDER
PO No: PO-2024-005

Item        | Qty | Rate
Laptop      | 10  | 45000
Mouse       | 20  | 500
Monitor     | 5   | 12000
Keyboard    | 15  | 800
"""

# Empty / minimal text
EMPTY_OCR_TEXT = ""
TOO_SHORT_OCR_TEXT = "Invoice No: 001"

# Coordinate garbage (PaddleOCR failure mode)
COORDINATE_GARBAGE_TEXT = """
[123.45, 678.90] [234.56, 789.01] [345.67, 890.12]
[456.78, 901.23] [567.89, 012.34] [678.90, 123.45]
"""


# ---------------------------------------------------------------------------
# Minimal PDF fixtures
# ---------------------------------------------------------------------------

def make_minimal_pdf(text: str = "Test content") -> bytes:
    """Create a minimal valid PDF in memory for testing."""
    try:
        import fitz
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        data = doc.tobytes()
        doc.close()
        return data
    except ImportError:
        # Fallback: hand-craft a minimal PDF
        content = text.encode("latin-1")
        pdf = (
            b"%PDF-1.4\n"
            b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
            b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
            b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R>>endobj\n"
            b"4 0 obj<</Length " + str(len(content) + 30).encode() + b">>\n"
            b"stream\nBT /F1 12 Tf 72 720 Td (" + content + b") Tj ET\nendstream\nendobj\n"
            b"xref\n0 5\n"
            b"0000000000 65535 f \n"
            b"0000000009 00000 n \n"
            b"0000000058 00000 n \n"
            b"0000000115 00000 n \n"
            b"0000000214 00000 n \n"
            b"trailer<</Size 5/Root 1 0 R>>\n"
            b"startxref\n350\n%%EOF"
        )
        return pdf


CORRUPT_PDF_BYTES = b"not a pdf at all"
EMPTY_PDF_BYTES = b""
TRUNCATED_PDF_BYTES = b"%PDF-1.4\ntruncated..."


# ---------------------------------------------------------------------------
# Flask test client
# ---------------------------------------------------------------------------

@pytest.fixture
def app_client():
    """Create a Flask test client for API testing."""
    os.environ.setdefault("LOG_LEVEL", "WARNING")  # quiet during tests
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def valid_pdf_bytes():
    """Generate a minimal valid PDF."""
    return make_minimal_pdf("Invoice test content with enough text to pass minimum thresholds for OCR extraction testing purposes")
