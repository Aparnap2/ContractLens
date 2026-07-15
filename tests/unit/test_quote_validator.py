"""Tests for quote validation logic — Master Spec §8.1, §21.2.

Validates that:
  - Quote found in page text → valid
  - Quote not found → invalid
  - Invalid page number → error
  - Boundary: empty quote, empty page text
"""

from __future__ import annotations

import pytest

from domain.schemas import ContractExtraction, QuoteRef
from packages.rules.rules import validate_quote, validate_extraction_quotes


class TestValidateQuote:
    """§21.2 — validate_quote: checks if quote is a substring of page text."""

    def test_quote_found_verbatim(self) -> None:
        """Quote that appears verbatim in page text passes."""
        page = "The termination notice period shall be thirty (30) days."
        quote = "thirty (30) days"
        assert validate_quote(page, quote) is True

    def test_quote_found_with_extra_whitespace(self) -> None:
        """Leading/trailing whitespace in quote is stripped before check."""
        page = "Either party may terminate upon ninety days notice."
        quote = "  ninety days notice  "
        assert validate_quote(page, quote) is True

    def test_quote_not_found(self) -> None:
        """Quote that does not appear in page text fails."""
        page = "The parties agree to the terms set forth herein."
        quote = "liquidated damages of INR 5,00,000"
        assert validate_quote(page, quote) is False

    def test_case_sensitive_mismatch(self) -> None:
        """Matching is case-sensitive (substring check, not case-insensitive)."""
        page = "Governing Law: This agreement shall be governed by..."
        quote = "this agreement"  # lowercase 't'
        assert validate_quote(page, quote) is False

    def test_empty_quote(self) -> None:
        """An empty quote string — strip reduces to '', which is in any string."""
        page = "Any page text at all."
        assert validate_quote(page, "") is True
        assert validate_quote(page, "   ") is True

    def test_empty_page_text(self) -> None:
        """Empty page text with non-empty quote always fails."""
        page = ""
        quote = "Any quote"
        assert validate_quote(page, quote) is False

    def test_quote_exact_match(self) -> None:
        """Quote matching the entire page text."""
        page = "Exact text"
        assert validate_quote(page, "Exact text") is True

    def test_quote_longer_than_page(self) -> None:
        """Quote longer than page text cannot be found."""
        page = "Short text"
        quote = "Short text with extra characters beyond page"
        assert validate_quote(page, quote) is False


class TestValidateExtractionQuotes:
    """§21.2 — validate_extraction_quotes: validates all quote refs in extraction."""

    def test_all_quotes_valid(self, clean_extraction, clean_page_lookup) -> None:
        """All quotes reference existing pages and appear verbatim."""
        errors = validate_extraction_quotes(clean_extraction, clean_page_lookup)
        assert errors == []

    def test_high_risk_all_quotes_valid(self, high_risk_extraction, high_risk_page_lookup) -> None:
        """High-risk extraction quotes all match their pages."""
        errors = validate_extraction_quotes(high_risk_extraction, high_risk_page_lookup)
        assert errors == []

    def test_quote_not_in_page_text(self, extraction_with_missing_quote, clean_page_lookup) -> None:
        """Quote that does not appear in the referenced page is caught."""
        errors = validate_extraction_quotes(extraction_with_missing_quote, clean_page_lookup)

        # The change_of_control_quote references page 1 but "This exact sentence does not exist" is not on page 1
        change_of_control_errors = [e for e in errors if "change_of_control_quote" in e]
        assert len(change_of_control_errors) >= 1
        assert "quote not found" in change_of_control_errors[0]

        # The termination_notice_quote references page 2, but "Sixty days notice is required"
        # is not in page 2 text
        term_errors = [e for e in errors if "termination_notice_quote" in e]
        assert len(term_errors) >= 1

    def test_invalid_page_number(self, extraction_with_invalid_page, clean_page_lookup) -> None:
        """Quote referencing a page number not in the page_lookup is caught."""
        errors = validate_extraction_quotes(extraction_with_invalid_page, clean_page_lookup)
        page_errors = [e for e in errors if "page 99" in e or "invalid page" in e]
        assert len(page_errors) >= 1

    def test_no_quote_fields_populated(self) -> None:
        """Extraction with all quote fields as None passes validation."""
        ext = ContractExtraction(extraction_confidence=0.5)
        errors = validate_extraction_quotes(ext, {1: "text"})
        assert errors == []

    def test_partial_quote_population(self) -> None:
        """Only populated quote fields are validated; None fields are skipped."""
        ext = ContractExtraction(
            change_of_control_clause_present=True,
            change_of_control_quote=QuoteRef(
                source_quote="Change of control provision",
                page_number=1,
            ),
            extraction_confidence=0.9,
        )
        errors = validate_extraction_quotes(ext, {1: "Change of control provision"})
        assert errors == []

    def test_mixed_valid_invalid(self, clean_page_lookup) -> None:
        """Some valid and some invalid quotes — only invalid ones reported."""
        ext = ContractExtraction(
            change_of_control_clause_present=True,
            change_of_control_quote=QuoteRef(
                source_quote="This text is on page 1",
                page_number=1,
            ),
            termination_notice_quote=QuoteRef(
                source_quote="This text does NOT appear anywhere",
                page_number=2,
            ),
            extraction_confidence=0.9,
        )
        # Ensure a key that might be referenced in page 1 exists
        lookup = {1: "This text is on page 1 and some other content", 2: "Page two content"}
        errors = validate_extraction_quotes(ext, lookup)
        assert len(errors) == 1
        assert "termination_notice_quote" in errors[0]

    def test_empty_page_lookup(self) -> None:
        """Empty page_lookup causes all quoted fields to report invalid page."""
        ext = ContractExtraction(
            change_of_control_clause_present=True,
            change_of_control_quote=QuoteRef(
                source_quote="Any quote",
                page_number=1,
            ),
            extraction_confidence=0.9,
        )
        errors = validate_extraction_quotes(ext, {})
        assert len(errors) == 1
        assert "not found in extracted pages" in errors[0]

    def test_empty_quote_in_quote_ref(self) -> None:
        """A QuoteRef with an empty source_quote is valid (empty string is in any text)."""
        ext = ContractExtraction(
            change_of_control_clause_present=True,
            change_of_control_quote=QuoteRef(source_quote="", page_number=1),
            extraction_confidence=0.9,
        )
        errors = validate_extraction_quotes(ext, {1: "Some page text"})
        assert errors == []
