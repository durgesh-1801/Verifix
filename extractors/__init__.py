# extractors/__init__.py
"""LLM-powered structured extraction package.

Public entry point:
    from extractors.llm_structured_extractor import extract_structured
"""
from .llm_structured_extractor import extract_structured

__all__ = ["extract_structured"]
