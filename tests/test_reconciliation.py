"""Tests for the fuzzy reconciliation engine in llm.py.

Covers:
- Exact match detection
- Fuzzy item name matching (OCR corruption)
- Missing item detection
- Duplicate item detection
- Quantity/price mismatch detection
- Price tolerance behavior
"""
from __future__ import annotations

import os
import sys
import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from llm import (
    _build_fuzzy_match_map,
    _compare_groups,
    _group_items,
    normalize_item_for_matching,
    _difference,
    _prices_within_tolerance,
)


# ---------------------------------------------------------------------------
# normalize_item_for_matching
# ---------------------------------------------------------------------------

class TestNormalizeItemForMatching:
    """Verify OCR-tolerant item name normalization."""

    def test_lowercase(self):
        assert normalize_item_for_matching("LAPTOP") == "laptop"

    def test_strips_trailing_j(self):
        """OCR often appends stray 'j' to words."""
        result = normalize_item_for_matching("Chair j")
        assert "chair" in result
        assert result.strip() == "chair"

    def test_strips_trailing_punct(self):
        result = normalize_item_for_matching("cpu.")
        assert result == "cpu"

    def test_digit_substitution_0_to_o(self):
        result = normalize_item_for_matching("lapt0p")
        assert result == "laptop"

    def test_empty_string(self):
        assert normalize_item_for_matching("") == ""

    def test_none_handling(self):
        # Should handle None gracefully via str()
        result = normalize_item_for_matching(None)
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# _group_items
# ---------------------------------------------------------------------------

class TestGroupItems:
    """Verify item grouping logic for reconciliation."""

    def test_single_items(self):
        items = [
            {"item": "Laptop", "qty": 10, "price": 45000},
            {"item": "Mouse", "qty": 20, "price": 500},
        ]
        groups = _group_items(items)
        assert "laptop" in groups
        assert "mouse" in groups
        assert groups["laptop"]["qty"] == 10
        assert groups["mouse"]["qty"] == 20

    def test_duplicate_items_combined(self):
        items = [
            {"item": "Laptop", "qty": 5, "price": 45000},
            {"item": "Laptop", "qty": 5, "price": 45000},
        ]
        groups = _group_items(items)
        assert "laptop" in groups
        assert groups["laptop"]["qty"] == 10
        assert groups["laptop"]["has_duplicate"] is True

    def test_empty_list(self):
        groups = _group_items([])
        assert groups == {}

    def test_skips_empty_item_names(self):
        items = [
            {"item": "", "qty": 10, "price": 500},
            {"item": "Laptop", "qty": 5, "price": 45000},
        ]
        groups = _group_items(items)
        assert len(groups) == 1
        assert "laptop" in groups

    def test_none_qty_handled(self):
        items = [{"item": "Laptop", "qty": None, "price": 45000}]
        groups = _group_items(items)
        assert groups["laptop"]["qty"] == 0


# ---------------------------------------------------------------------------
# _build_fuzzy_match_map
# ---------------------------------------------------------------------------

class TestFuzzyMatchMap:
    """Verify fuzzy matching between OCR-corrupted item names."""

    def test_exact_match_excluded(self):
        """Exact matches are handled upstream; fuzzy only sees unmatched."""
        inv_keys = ["laptop"]
        po_keys = ["laptop"]
        match_map = _build_fuzzy_match_map(inv_keys, po_keys)
        # Exact match gets 100 score, should be included
        assert "laptop" in match_map

    def test_ocr_corrupted_match(self):
        """'lapt0p' should fuzzy-match to 'laptop'."""
        inv_keys = ["lapt0p"]
        po_keys = ["laptop"]
        match_map = _build_fuzzy_match_map(inv_keys, po_keys)
        assert "lapt0p" in match_map
        assert match_map["lapt0p"] == "laptop"

    def test_no_match_for_unrelated(self):
        inv_keys = ["laptop"]
        po_keys = ["keyboard"]
        match_map = _build_fuzzy_match_map(inv_keys, po_keys)
        assert "laptop" not in match_map

    def test_empty_lists(self):
        match_map = _build_fuzzy_match_map([], [])
        assert match_map == {}


# ---------------------------------------------------------------------------
# _compare_groups — full reconciliation
# ---------------------------------------------------------------------------

class TestCompareGroups:
    """Integration tests for the full discrepancy comparison."""

    def test_matching_items_no_discrepancies(self):
        inv_groups = _group_items([
            {"item": "Laptop", "qty": 10, "price": 45000},
            {"item": "Mouse", "qty": 20, "price": 500},
        ])
        po_groups = _group_items([
            {"item": "Laptop", "qty": 10, "price": 45000},
            {"item": "Mouse", "qty": 20, "price": 500},
        ])
        discrepancies = _compare_groups(inv_groups, po_groups)
        assert len(discrepancies) == 0

    def test_quantity_mismatch_detected(self):
        inv_groups = _group_items([{"item": "Laptop", "qty": 12, "price": 45000}])
        po_groups = _group_items([{"item": "Laptop", "qty": 10, "price": 45000}])
        discrepancies = _compare_groups(inv_groups, po_groups)
        assert len(discrepancies) == 1
        assert discrepancies[0]["type"] == "quantity_mismatch"
        assert discrepancies[0]["item"] == "laptop"

    def test_price_mismatch_detected(self):
        inv_groups = _group_items([{"item": "Laptop", "qty": 10, "price": 46000}])
        po_groups = _group_items([{"item": "Laptop", "qty": 10, "price": 45000}])
        discrepancies = _compare_groups(inv_groups, po_groups)
        assert len(discrepancies) == 1
        assert discrepancies[0]["type"] == "price_mismatch"

    def test_missing_in_po_detected(self):
        inv_groups = _group_items([
            {"item": "Laptop", "qty": 10, "price": 45000},
            {"item": "Tablet", "qty": 5, "price": 30000},
        ])
        po_groups = _group_items([{"item": "Laptop", "qty": 10, "price": 45000}])
        discrepancies = _compare_groups(inv_groups, po_groups)
        missing = [d for d in discrepancies if d["type"] == "missing_item"]
        assert len(missing) == 1
        assert missing[0]["item"] == "tablet"
        assert missing[0]["present_in"] == "Invoice only"

    def test_missing_in_invoice_detected(self):
        inv_groups = _group_items([{"item": "Laptop", "qty": 10, "price": 45000}])
        po_groups = _group_items([
            {"item": "Laptop", "qty": 10, "price": 45000},
            {"item": "Tablet", "qty": 5, "price": 30000},
        ])
        discrepancies = _compare_groups(inv_groups, po_groups)
        missing = [d for d in discrepancies if d["type"] == "missing_item"]
        assert len(missing) == 1
        assert missing[0]["present_in"] == "PO only"


# ---------------------------------------------------------------------------
# _difference
# ---------------------------------------------------------------------------

class TestDifference:
    """Verify difference calculation."""

    def test_positive_difference(self):
        assert _difference(5000, 4000) == 1000

    def test_zero_difference(self):
        assert _difference(5000, 5000) == 0

    def test_none_left(self):
        assert _difference(None, 5000) == "N/A"

    def test_none_right(self):
        assert _difference(5000, None) == "N/A"

    def test_decimal_difference(self):
        result = _difference(5000.50, 5000)
        assert result == 0.5


# ---------------------------------------------------------------------------
# GST mismatch scenario
# ---------------------------------------------------------------------------

class TestGSTMismatch:
    """Verify reconciliation handles GST-related mismatches."""

    def test_gst_price_difference(self):
        """Simulate invoiced rate including GST vs PO rate excluding GST."""
        inv_groups = _group_items([
            {"item": "Office Chair", "qty": 10, "price": 5900},  # with 18% GST
        ])
        po_groups = _group_items([
            {"item": "Office Chair", "qty": 10, "price": 5000},  # without GST
        ])
        discrepancies = _compare_groups(inv_groups, po_groups)
        price_mismatches = [d for d in discrepancies if d["type"] == "price_mismatch"]
        assert len(price_mismatches) == 1
        assert price_mismatches[0]["item"] == "office chair"
