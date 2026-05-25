"""Tests for Flask API routes — validation, error handling, response format.

Covers:
- /verify route validation (file type, size, encryption, magic bytes)
- /api/verify-invoice route
- /export-pdf route
- Error handler JSON responses
- Edge cases: empty files, corrupt PDFs, missing fields
"""
from __future__ import annotations

import io
import json
import os
import sys
import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.conftest import (
    CORRUPT_PDF_BYTES,
    EMPTY_PDF_BYTES,
    make_minimal_pdf,
)


@pytest.fixture
def client():
    """Flask test client with quiet logging."""
    os.environ["LOG_LEVEL"] = "WARNING"
    from app import app
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Error handler tests
# ---------------------------------------------------------------------------

class TestErrorHandlers:
    """Verify Flask error handlers return valid JSON."""

    def test_404_returns_json(self, client):
        response = client.get("/nonexistent-route")
        assert response.status_code == 404
        data = response.get_json()
        assert data is not None
        assert data["error"] is True
        assert "message" in data

    def test_413_content_type(self, client):
        """Uploading a file larger than MAX_CONTENT_LENGTH should return 413."""
        # Create a 17 MB payload (over 16 MB limit)
        large_data = b"x" * (17 * 1024 * 1024)
        response = client.post(
            "/verify",
            data={
                "invoice": (io.BytesIO(large_data), "big.pdf"),
                "purchase_order": (io.BytesIO(large_data), "big2.pdf"),
            },
            content_type="multipart/form-data",
        )
        # Should be 413 (Request Entity Too Large)
        assert response.status_code == 413
        data = response.get_json()
        assert data is not None
        assert data["error"] is True


# ---------------------------------------------------------------------------
# /verify route validation
# ---------------------------------------------------------------------------

class TestVerifyRoute:
    """Tests for the /verify endpoint validation logic."""

    def test_missing_files_returns_400(self, client):
        response = client.post("/verify")
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] is True
        assert "upload both" in data["message"].lower() or "pdf" in data["message"].lower()

    def test_missing_one_file_returns_400(self, client):
        pdf = make_minimal_pdf("Test invoice")
        response = client.post(
            "/verify",
            data={"invoice": (io.BytesIO(pdf), "invoice.pdf")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 400

    def test_non_pdf_extension_returns_400(self, client):
        pdf = make_minimal_pdf("Test")
        response = client.post(
            "/verify",
            data={
                "invoice": (io.BytesIO(pdf), "invoice.txt"),
                "purchase_order": (io.BytesIO(pdf), "po.pdf"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "pdf" in data["message"].lower()

    def test_corrupt_pdf_returns_400(self, client):
        response = client.post(
            "/verify",
            data={
                "invoice": (io.BytesIO(CORRUPT_PDF_BYTES), "invoice.pdf"),
                "purchase_order": (io.BytesIO(CORRUPT_PDF_BYTES), "po.pdf"),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] is True
        assert "invalid" in data["message"].lower()

    def test_empty_file_returns_400(self, client):
        response = client.post(
            "/verify",
            data={
                "invoice": (io.BytesIO(EMPTY_PDF_BYTES), "invoice.pdf"),
                "purchase_order": (io.BytesIO(EMPTY_PDF_BYTES), "po.pdf"),
            },
            content_type="multipart/form-data",
        )
        # Empty file → no magic bytes → 400
        assert response.status_code == 400

    def test_oversized_pdf_returns_400(self, client):
        """PDF header valid but content exceeds 10MB per-file limit."""
        # Create a valid PDF header + 11 MB of padding
        padding = b"%PDF-1.4" + (b"\x00" * (11 * 1024 * 1024))
        response = client.post(
            "/verify",
            data={
                "invoice": (io.BytesIO(padding), "invoice.pdf"),
                "purchase_order": (io.BytesIO(padding), "po.pdf"),
            },
            content_type="multipart/form-data",
        )
        # Either 400 (file size check) or 413 (MAX_CONTENT_LENGTH)
        assert response.status_code in (400, 413)


# ---------------------------------------------------------------------------
# /api/verify-invoice route
# ---------------------------------------------------------------------------

class TestApiVerifyInvoice:
    """Tests for the /api/verify-invoice JSON API endpoint."""

    def test_missing_invoice_returns_400(self, client):
        pdf = make_minimal_pdf("Purchase order content here for testing")
        response = client.post(
            "/api/verify-invoice",
            data={"po_pdf": (io.BytesIO(pdf), "po.pdf")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data is not None
        assert "error" in data

    def test_missing_po_returns_400(self, client):
        pdf = make_minimal_pdf("Invoice content here for testing")
        response = client.post(
            "/api/verify-invoice",
            data={"invoice_pdf": (io.BytesIO(pdf), "invoice.pdf")},
            content_type="multipart/form-data",
        )
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data

    def test_response_always_json(self, client):
        """Even on error, response should be valid JSON."""
        response = client.post("/api/verify-invoice")
        assert response.content_type.startswith("application/json")
        data = response.get_json()
        assert data is not None


# ---------------------------------------------------------------------------
# /export-pdf route
# ---------------------------------------------------------------------------

class TestExportPdf:
    """Tests for the PDF export endpoint."""

    def test_export_with_valid_data(self, client):
        discrepancies = [
            {
                "item": "Laptop",
                "field": "quantity",
                "invoice_value": 12,
                "po_value": 10,
                "difference": 2,
                "issue": "quantity mismatch",
            }
        ]
        response = client.post(
            "/export-pdf",
            data={
                "status": "Discrepancies Found",
                "total_issues": "1",
                "total_difference": "2",
                "discrepancies_json": json.dumps(discrepancies),
            },
        )
        assert response.status_code == 200
        assert response.content_type == "application/pdf"
        # Verify it starts with PDF magic bytes
        assert response.data[:4] == b"%PDF"

    def test_export_with_empty_discrepancies(self, client):
        response = client.post(
            "/export-pdf",
            data={
                "status": "No Discrepancies Found",
                "total_issues": "0",
                "total_difference": "0",
                "discrepancies_json": "[]",
            },
        )
        assert response.status_code == 200
        assert response.data[:4] == b"%PDF"

    def test_export_with_malformed_json(self, client):
        """Malformed discrepancies_json should not crash."""
        response = client.post(
            "/export-pdf",
            data={
                "status": "Unknown",
                "total_issues": "0",
                "total_difference": "0",
                "discrepancies_json": "this is not json",
            },
        )
        # Should still return a PDF (with empty discrepancy table)
        assert response.status_code == 200
        assert response.data[:4] == b"%PDF"

    def test_export_with_missing_fields(self, client):
        """Missing form fields should use defaults."""
        response = client.post("/export-pdf", data={})
        assert response.status_code == 200
        assert response.data[:4] == b"%PDF"
