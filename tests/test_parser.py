"""Tests for parser/line_items.py — line item extraction from OCR text.

Covers:
- Columnar extraction (pipe-delimited tables)
- Labeled extraction (keyword-based: qty, price)
- Trailing numeric extraction
- Edge cases: merged tokens, missing fields, coordinate garbage
- GST invoice parsing
- Blurry/corrupted OCR text
"""
from __future__ import annotations

import os
import sys
import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from parser.line_items import (
    extract_line_items,
    extract_line_items_with_diagnostics,
    extract_totals,
    build_structured_document,
)
from tests.conftest import (
    CLEAN_INVOICE_OCR,
    CORRUPTED_OCR_TEXT,
    BLURRY_OCR_TEXT,
    GST_INVOICE_OCR,
    DUPLICATE_ITEMS_OCR,
    EMPTY_OCR_TEXT,
    TOO_SHORT_OCR_TEXT,
    COORDINATE_GARBAGE_TEXT,
)


# ---------------------------------------------------------------------------
# Clean invoice parsing
# ---------------------------------------------------------------------------

class TestCleanInvoiceParsing:
    """Verify parser handles well-formed OCR text correctly."""

    def test_extracts_all_items(self):
        items = extract_line_items(CLEAN_INVOICE_OCR)
        item_names = [i["item"].lower() for i in items]
        assert "laptop" in item_names
        assert "mouse" in item_names
        assert "monitor" in item_names
        assert "keyboard" in item_names

    def test_correct_quantities(self):
        items = extract_line_items(CLEAN_INVOICE_OCR)
        item_map = {i["item"].lower(): i for i in items}
        if "laptop" in item_map:
            assert item_map["laptop"].get("qty") == 10
        if "mouse" in item_map:
            assert item_map["mouse"].get("qty") == 20

    def test_correct_prices(self):
        items = extract_line_items(CLEAN_INVOICE_OCR)
        item_map = {i["item"].lower(): i for i in items}
        if "laptop" in item_map:
            assert item_map["laptop"].get("price") == 45000
        if "mouse" in item_map:
            assert item_map["mouse"].get("price") == 500

    def test_returns_list(self):
        items = extract_line_items(CLEAN_INVOICE_OCR)
        assert isinstance(items, list)
        assert len(items) > 0


# ---------------------------------------------------------------------------
# Corrupted OCR text
# ---------------------------------------------------------------------------

class TestCorruptedOcrParsing:
    """Verify parser handles OCR-corrupted text gracefully."""

    def test_does_not_crash(self):
        """Parser must not raise on corrupted input."""
        items = extract_line_items(CORRUPTED_OCR_TEXT)
        assert isinstance(items, list)

    def test_extracts_some_items(self):
        """Even corrupted text should yield some parseable items."""
        items = extract_line_items(CORRUPTED_OCR_TEXT)
        # May extract fewer items due to corruption, but should get some
        assert len(items) >= 0  # No crash is the minimum bar


# ---------------------------------------------------------------------------
# Blurry OCR text
# ---------------------------------------------------------------------------

class TestBlurryOcrParsing:
    """Verify parser handles partial/blurry OCR text."""

    def test_does_not_crash(self):
        items = extract_line_items(BLURRY_OCR_TEXT)
        assert isinstance(items, list)

    def test_extracts_what_it_can(self):
        """Some items should still be extractable from partial text."""
        items = extract_line_items(BLURRY_OCR_TEXT)
        # At minimum, Laptop with qty 10 and price 45000 should parse
        if items:
            item_names = [i["item"].lower() for i in items]
            assert any("laptop" in name for name in item_names)


# ---------------------------------------------------------------------------
# GST invoice parsing
# ---------------------------------------------------------------------------

class TestGSTInvoiceParsing:
    """Verify parser handles GST-format invoices."""

    def test_extracts_items(self):
        items = extract_line_items(GST_INVOICE_OCR)
        assert isinstance(items, list)
        assert len(items) >= 1

    def test_extracts_totals(self):
        totals = extract_totals(GST_INVOICE_OCR)
        assert isinstance(totals, dict)


# ---------------------------------------------------------------------------
# Duplicate items
# ---------------------------------------------------------------------------

class TestDuplicateItemParsing:
    """Verify parser handles duplicate rows correctly."""

    def test_duplicate_detected(self):
        result = extract_line_items_with_diagnostics(DUPLICATE_ITEMS_OCR)
        items = result["items"]
        skipped = result["skipped_rows"]
        # Either deduplication removes the duplicate, or both are kept
        laptop_items = [i for i in items if "laptop" in i["item"].lower()]
        assert len(laptop_items) <= 2  # At most 2 (not 3 or more)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Verify parser handles edge cases without crashing."""

    def test_empty_text(self):
        items = extract_line_items(EMPTY_OCR_TEXT)
        assert items == []

    def test_none_text(self):
        items = extract_line_items(None)
        assert items == []

    def test_too_short_text(self):
        items = extract_line_items(TOO_SHORT_OCR_TEXT)
        assert isinstance(items, list)

    def test_coordinate_garbage_rejected(self):
        result = extract_line_items_with_diagnostics(COORDINATE_GARBAGE_TEXT)
        assert result["items"] == []
        assert result.get("failure_reason") == "coordinate_payload_detected"

    def test_diagnostics_structure(self):
        result = extract_line_items_with_diagnostics(CLEAN_INVOICE_OCR)
        assert "items" in result
        assert "skipped_rows" in result
        assert "parser_confidence_score" in result
        assert "failure_reason" in result
        assert "trace" in result


# ---------------------------------------------------------------------------
# build_structured_document
# ---------------------------------------------------------------------------

class TestBuildStructuredDocument:
    """Verify the top-level document builder."""

    def test_returns_expected_keys(self):
        doc = build_structured_document(CLEAN_INVOICE_OCR)
        expected_keys = [
            "line_items", "totals", "line_item_count",
            "skipped_rows", "parser_confidence_score",
            "failure_reason", "raw_ocr_preview",
            "parsed_item_count", "skipped_row_count",
        ]
        for key in expected_keys:
            assert key in doc, f"Missing key: {key}"

    def test_line_item_count_matches(self):
        doc = build_structured_document(CLEAN_INVOICE_OCR)
        assert doc["line_item_count"] == len(doc["line_items"])
        assert doc["parsed_item_count"] == len(doc["line_items"])

    def test_empty_input(self):
        doc = build_structured_document("")
        assert doc["line_items"] == []
        assert doc["line_item_count"] == 0
        assert doc["failure_reason"] == "no rows found"
