"""Quote validation — Master Spec §8.1, §21.2."""

from typing import Optional

from domain.schemas import ContractExtraction, QuoteRef


def validate_quote(page_text: str, quote: str) -> bool:
    """Return True if the trimmed quote appears verbatim in the page text.

    Spec §21.2: ``return quote.strip() in page_text``
    """
    return quote.strip() in page_text


def validate_extraction_quotes(
    extraction: ContractExtraction,
    page_lookup: dict[int, str],
) -> list[str]:
    """Validate every populated *_quote field against the actual page text.

    Returns a list of error messages (empty = all valid).
    Spec §21.2.
    """
    errors: list[str] = []
    for field_name, value in extraction.model_dump().items():
        if field_name.endswith("_quote") and value is not None:
            page: int = value["page_number"]
            quote: str = value["source_quote"]
            if page not in page_lookup:
                errors.append(f"{field_name}: invalid page")
            elif not validate_quote(page_lookup[page], quote):
                errors.append(f"{field_name}: quote not found in page text")
    return errors
