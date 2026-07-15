"""INR value extraction from contract text — Master Spec §8.1, §5.4.

Numbers must be reparsed deterministically from source quotes rather
than relying on LLM numeric output alone.
"""

from __future__ import annotations

import re
from typing import Optional

# ── Indian number system patterns ───────────────────────────────────────────

# Matches: ₹5,00,000 | INR 1,00,00,000 | Rs. 10 lakhs | Rs. 5 crores
# Also matches plain "5,00,000" with INR context

_INR_PATTERNS: list[re.Pattern] = [
    # ₹ / INR / Rs. with Indian-style comma grouping
    re.compile(
        r"(?:₹|INR|Rs\.?)\s*([\d,]+)\s*(lakh|crore|cr|lc)?\b",
        re.IGNORECASE,
    ),
    # "X lakhs" / "X crores" standalone
    re.compile(
        r"(\d+(?:,\d+)?)\s*(lakhs?|crores?|cr\.?)",
        re.IGNORECASE,
    ),
    # Plain number with comma grouping and INR context
    re.compile(
        r"(?:₹|INR|Rs\.?)\s*([\d,]+(?:\.\d{1,2})?)",
        re.IGNORECASE,
    ),
]


def _parse_indian_number(num_str: str) -> int:
    """Convert an Indian-format number string to an integer.

    Handles "5,00,000" → 500000, "10,00,000" → 1000000.
    Commas are stripped; pure digits remain.
    """
    cleaned = num_str.replace(",", "")
    return int(cleaned)


def _apply_multiplier(value: int, suffix: str | None) -> int:
    """Apply Indian number-system multiplier.

    - "lakh" / "lakhs" → × 100,000
    - "crore" / "crores" / "cr" → × 10,000,000
    """
    if not suffix:
        return value
    suffix_lower = suffix.strip().lower()
    if suffix_lower in ("lakh", "lakhs"):
        return value * 100_000
    if suffix_lower in ("crore", "crores", "cr"):
        return value * 10_000_000
    return value


def parse_inr_value(text: str) -> Optional[int]:
    """Extract an INR monetary value from a text snippet.

    Returns the value in INR (as int, i.e. paise-free whole rupees), or
    None if no value can be parsed deterministically.

    Spec §5.4: numbers must be reparsed deterministically from source quote.
    """
    text_clean = text.replace("\u20b9", "₹")  # Normalise rupee sign

    for pattern in _INR_PATTERNS:
        match = pattern.search(text_clean)
        if not match:
            continue

        groups = match.groups()
        num_part: str = groups[0]
        suffix: str | None = groups[1] if len(groups) > 1 else None

        try:
            base_value = _parse_indian_number(num_part)
        except (ValueError, IndexError):
            continue

        return _apply_multiplier(base_value, suffix)

    return None
