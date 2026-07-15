"""Tests for INR numeric parsing — Master Spec §8 hard validation rules."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import pytest


def parse_inr_value(text: str | None) -> Decimal | None:
    if text is None:
        return None
    s = text.strip()
    s = re.sub(r"(?i)^(INR|Rs\.?)\s*", "", s)
    s = s.replace("₹", "").replace(",", "").strip()
    multiplier = Decimal("1")
    if "crore" in s.lower():
        multiplier = Decimal("10000000")
        s = re.sub(r"(?i)\s*cro(re|s).*$", "", s)
    elif "lakh" in s.lower():
        multiplier = Decimal("100000")
        s = re.sub(r"(?i)\s*lakh.*$", "", s)
    s = s.strip()
    if not s:
        return None
    try:
        return Decimal(s) * multiplier
    except InvalidOperation:
        return None


class TestParseInrValue:
    def test_rupee_symbol_with_commas(self) -> None:
        assert parse_inr_value("₹5,00,000") == Decimal("500000")

    def test_inr_prefix_with_commas(self) -> None:
        assert parse_inr_value("INR 1,00,00,000") == Decimal("10000000")

    def test_rs_dot_prefix(self) -> None:
        assert parse_inr_value("Rs. 10,000") == Decimal("10000")

    def test_lakhs_text(self) -> None:
        assert parse_inr_value("Rs. 10 lakhs") == Decimal("1000000")

    def test_crores_text(self) -> None:
        assert parse_inr_value("Rs. 5 crores") == Decimal("50000000")

    def test_plain_number(self) -> None:
        assert parse_inr_value("500000") == Decimal("500000")

    def test_empty_string(self) -> None:
        assert parse_inr_value("") is None

    def test_none_value(self) -> None:
        assert parse_inr_value(None) is None

    def test_invalid_text(self) -> None:
        assert parse_inr_value("N/A") is None

    def test_decimal_amount(self) -> None:
        assert parse_inr_value("₹1,234.56") == Decimal("1234.56")
