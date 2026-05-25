"""Tests for extractors/llm_structured_extractor.py — LLM response handling.

These tests mock LLM calls and focus on:
- JSON parsing from raw LLM responses
- Markdown fence stripping
- Item validation and quality gating
- Confidence scoring
- Fallback to regex parser
- Edge cases: empty responses, malformed JSON, truncated output
"""
from __future__ import annotations

import json
import os
import sys
import pytest

_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from extractors.llm_structured_extractor import (
    _parse_llm_response,
    _strip_markdown_fences,
    _safe_number,
    _validate_items,
    _score_confidence,
    normalize_item_quality_score,
)


# ---------------------------------------------------------------------------
# _strip_markdown_fences
# ---------------------------------------------------------------------------

class TestStripMarkdownFences:
    """Verify markdown code fence removal from LLM responses."""

    def test_json_fence(self):
        text = '```json\n{"items": []}\n```'
        assert _strip_markdown_fences(text) == '{"items": []}'

    def test_plain_fence(self):
        text = '```\n{"items": []}\n```'
        assert _strip_markdown_fences(text) == '{"items": []}'

    def test_no_fence(self):
        text = '{"items": []}'
        assert _strip_markdown_fences(text) == '{"items": []}'

    def test_whitespace(self):
        text = '  ```json\n  {"items": []}  \n```  '
        result = _strip_markdown_fences(text)
        assert '"items"' in result


# ---------------------------------------------------------------------------
# _safe_number
# ---------------------------------------------------------------------------

class TestSafeNumber:
    """Verify numeric coercion from various formats."""

    def test_integer(self):
        assert _safe_number(42) == 42

    def test_float(self):
        assert _safe_number(3.14) == 3.14

    def test_string_integer(self):
        assert _safe_number("42") == 42

    def test_string_float(self):
        assert _safe_number("3.14") == 3.14

    def test_comma_string(self):
        assert _safe_number("1,500") == 1500

    def test_currency_prefix(self):
        assert _safe_number("Rs. 5000") == 5000

    def test_garbage(self):
        assert _safe_number("abc") is None

    def test_none(self):
        assert _safe_number(None) is None

    def test_empty_string(self):
        assert _safe_number("") is None


# ---------------------------------------------------------------------------
# _parse_llm_response
# ---------------------------------------------------------------------------

class TestParseLlmResponse:
    """Verify LLM JSON response parsing with various formats."""

    def test_clean_json(self):
        raw = '{"document_type": "invoice", "items": [{"item": "laptop", "qty": 10, "price": 45000}]}'
        result = _parse_llm_response(raw)
        assert result["items"][0]["item"] == "laptop"

    def test_json_with_markdown_fences(self):
        raw = '```json\n{"items": [{"item": "laptop", "qty": 10, "price": 45000}]}\n```'
        result = _parse_llm_response(raw)
        assert len(result["items"]) == 1

    def test_json_embedded_in_text(self):
        raw = 'Here is the result:\n{"items": [{"item": "laptop", "qty": 10, "price": 45000}]}\nDone.'
        result = _parse_llm_response(raw)
        assert "items" in result

    def test_invalid_json_raises(self):
        with pytest.raises(ValueError):
            _parse_llm_response("this is not json at all with no braces")

    def test_non_dict_raises(self):
        with pytest.raises(ValueError):
            _parse_llm_response('"just a string"')

    def test_empty_items_list(self):
        raw = '{"items": []}'
        result = _parse_llm_response(raw)
        assert result["items"] == []


# ---------------------------------------------------------------------------
# _validate_items
# ---------------------------------------------------------------------------

class TestValidateItems:
    """Verify item validation and quality gating."""

    def test_valid_items_accepted(self):
        items = [
            {"item": "Laptop", "qty": 10, "price": 45000},
            {"item": "Mouse", "qty": 20, "price": 500},
        ]
        valid = _validate_items(items)
        assert len(valid) == 2

    def test_missing_item_name_rejected(self):
        items = [{"item": "", "qty": 10, "price": 500}]
        valid = _validate_items(items)
        assert len(valid) == 0

    def test_zero_qty_rejected(self):
        items = [{"item": "Laptop", "qty": 0, "price": 45000}]
        valid = _validate_items(items)
        assert len(valid) == 0

    def test_negative_qty_rejected(self):
        items = [{"item": "Laptop", "qty": -5, "price": 45000}]
        valid = _validate_items(items)
        assert len(valid) == 0

    def test_negative_price_rejected(self):
        items = [{"item": "Laptop", "qty": 10, "price": -100}]
        valid = _validate_items(items)
        assert len(valid) == 0

    def test_duplicates_removed(self):
        items = [
            {"item": "Laptop", "qty": 10, "price": 45000},
            {"item": "Laptop", "qty": 10, "price": 45000},
        ]
        valid = _validate_items(items)
        assert len(valid) == 1

    def test_non_list_returns_empty(self):
        valid = _validate_items("not a list")
        assert valid == []

    def test_non_dict_entries_skipped(self):
        items = [
            "not a dict",
            {"item": "Laptop", "qty": 10, "price": 45000},
        ]
        valid = _validate_items(items)
        assert len(valid) == 1


# ---------------------------------------------------------------------------
# normalize_item_quality_score
# ---------------------------------------------------------------------------

class TestItemQualityScore:
    """Verify OCR quality scoring for item names."""

    def test_clean_name_high_score(self):
        score, reason = normalize_item_quality_score("Laptop")
        assert score >= 0.4
        assert reason == "ok"

    def test_ocr_corrupted_acceptable(self):
        """OCR-corrupted but recognizable names should pass."""
        score, reason = normalize_item_quality_score("lapt0p")
        assert score >= 0.3  # Should pass quality gate

    def test_single_char_rejected(self):
        score, reason = normalize_item_quality_score("j")
        assert score == 0.0

    def test_garbage_token_rejected(self):
        score, reason = normalize_item_quality_score("oty")
        assert score == 0.0

    def test_repeated_symbols_rejected(self):
        score, reason = normalize_item_quality_score("---")
        assert score == 0.0

    def test_empty_string(self):
        score, reason = normalize_item_quality_score("")
        assert score == 0.0

    def test_compound_name_ok(self):
        score, reason = normalize_item_quality_score("Office Chair")
        assert score >= 0.4


# ---------------------------------------------------------------------------
# _score_confidence
# ---------------------------------------------------------------------------

class TestScoreConfidence:
    """Verify extraction confidence scoring."""

    def test_no_items_zero_confidence(self):
        assert _score_confidence([], {}, "some text") == 0.0

    def test_grounded_items_higher(self):
        """Items found in OCR text should boost confidence."""
        items = [{"item": "laptop", "qty": 10, "price": 45000}]
        payload = {"invoice_number": "INV-001", "vendor": "ABC", "date": "2024-01-01"}
        ocr_text = "Invoice laptop qty 10 price 45000"
        score = _score_confidence(items, payload, ocr_text)
        assert score > 0.3

    def test_ungrounded_items_lower(self):
        """Items NOT in OCR text should have lower confidence."""
        items = [{"item": "helicopter", "qty": 1, "price": 1000000}]
        payload = {}
        ocr_text = "Invoice laptop qty 10 price 45000"
        score = _score_confidence(items, payload, ocr_text)
        assert score < 0.5
