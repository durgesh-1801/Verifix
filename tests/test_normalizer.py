"""Tests for parser/normalize.py — currency, quantity, item name normalization.

These tests verify the normalization layer handles:
- Standard numeric formats
- Indian number formatting (1,50,000)
- Currency prefixes (Rs, INR)
- OCR-corrupted numbers
- Edge cases (empty, None, garbage)
"""
from __future__ import annotations

import os
import sys
import pytest

# Ensure project root is on sys.path
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from parser.normalize import (
    normalize_currency_value,
    normalize_item_name,
    normalize_ocr_text,
    normalize_percentage,
    normalize_quantity,
)


# ---------------------------------------------------------------------------
# normalize_currency_value
# ---------------------------------------------------------------------------

class TestNormalizeCurrencyValue:
    """Tests for normalize_currency_value."""

    def test_integer(self):
        assert normalize_currency_value("5000") == 5000

    def test_float(self):
        assert normalize_currency_value("5000.50") == 5000.50

    def test_comma_thousands(self):
        assert normalize_currency_value("1,500") == 1500

    def test_indian_format(self):
        assert normalize_currency_value("1,50,000") == 150000

    def test_rs_prefix(self):
        assert normalize_currency_value("Rs. 5000") == 5000

    def test_rs_no_space(self):
        assert normalize_currency_value("Rs.5000") == 5000

    def test_inr_prefix(self):
        assert normalize_currency_value("INR 5000") == 5000

    def test_none_returns_none(self):
        assert normalize_currency_value(None) is None

    def test_empty_string_returns_none(self):
        assert normalize_currency_value("") is None

    def test_garbage_returns_none(self):
        assert normalize_currency_value("abc") is None

    def test_just_dot_returns_none(self):
        assert normalize_currency_value(".") is None

    def test_negative(self):
        assert normalize_currency_value("-500") == -500

    def test_integer_object(self):
        assert normalize_currency_value(5000) == 5000

    def test_float_object(self):
        assert normalize_currency_value(5000.50) == 5000.50

    def test_comma_with_spaces(self):
        """Indian OCR sometimes adds spaces near commas: '1, 500'"""
        assert normalize_currency_value("1, 500") == 1500

    def test_zero(self):
        assert normalize_currency_value("0") == 0

    def test_large_number(self):
        assert normalize_currency_value("10,00,000") == 1000000


# ---------------------------------------------------------------------------
# normalize_quantity
# ---------------------------------------------------------------------------

class TestNormalizeQuantity:
    """Tests for normalize_quantity."""

    def test_integer_string(self):
        assert normalize_quantity("10") == 10

    def test_float_to_int(self):
        assert normalize_quantity("10.0") == 10

    def test_fractional(self):
        assert normalize_quantity("2.5") == 2.5

    def test_none(self):
        assert normalize_quantity(None) is None

    def test_garbage(self):
        assert normalize_quantity("abc") is None

    def test_numeric_input(self):
        assert normalize_quantity(10) == 10


# ---------------------------------------------------------------------------
# normalize_percentage
# ---------------------------------------------------------------------------

class TestNormalizePercentage:
    """Tests for normalize_percentage."""

    def test_with_percent_sign(self):
        assert normalize_percentage("18%") == 18

    def test_without_percent_sign(self):
        assert normalize_percentage("18") == 18

    def test_decimal(self):
        assert normalize_percentage("9.5%") == 9.5

    def test_none(self):
        assert normalize_percentage(None) is None

    def test_negative_rejected(self):
        assert normalize_percentage("-5%") is None


# ---------------------------------------------------------------------------
# normalize_item_name
# ---------------------------------------------------------------------------

class TestNormalizeItemName:
    """Tests for normalize_item_name."""

    def test_clean_name(self):
        result = normalize_item_name("Laptop")
        assert "laptop" in result.lower()

    def test_strips_serial_number(self):
        result = normalize_item_name("1. Laptop")
        assert result.lower().strip() == "laptop"

    def test_strips_leading_numbers(self):
        result = normalize_item_name("01 Laptop")
        assert "laptop" in result.lower()

    def test_strips_field_labels(self):
        result = normalize_item_name("Item: Laptop")
        assert "laptop" in result.lower()
        assert "item" not in result.lower()

    def test_empty_string(self):
        result = normalize_item_name("")
        assert result == ""

    def test_none_input(self):
        result = normalize_item_name(None)
        assert isinstance(result, str)

    def test_preserves_compound_names(self):
        result = normalize_item_name("Office Chair")
        assert "office" in result.lower()
        assert "chair" in result.lower()


# ---------------------------------------------------------------------------
# normalize_ocr_text
# ---------------------------------------------------------------------------

class TestNormalizeOcrText:
    """Tests for normalize_ocr_text."""

    def test_fixes_qty_merged_with_number(self):
        result = normalize_ocr_text("qty10")
        assert "qty" in result.lower()
        assert "10" in result
        # Should have a space between qty and 10
        assert "qty 10" in result.lower() or "qty10" not in result.lower()

    def test_fixes_price_merged_with_number(self):
        result = normalize_ocr_text("price5000")
        assert "price" in result.lower()
        assert "5000" in result

    def test_fixes_prlce_typo(self):
        result = normalize_ocr_text("prlce")
        assert result.lower().strip() == "price"

    def test_fixes_pr1ce_typo(self):
        result = normalize_ocr_text("pr1ce")
        assert result.lower().strip() == "price"

    def test_fixes_1tem_typo(self):
        result = normalize_ocr_text("1tem")
        assert result.lower().strip() == "item"

    def test_fixes_spaced_qty(self):
        result = normalize_ocr_text("q t y")
        assert "qty" in result.lower()

    def test_preserves_normal_text(self):
        result = normalize_ocr_text("Laptop Mouse Monitor")
        assert "laptop" in result.lower()
        assert "mouse" in result.lower()
        assert "monitor" in result.lower()

    def test_rupee_symbol_handling(self):
        """OCR often corrupts ₹ into multi-byte garbage."""
        result = normalize_ocr_text("â‚¹5000")
        assert "5000" in result
