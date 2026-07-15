"""Tests for all deterministic legal/business rules — Master Spec §10."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from domain.schemas import ContractExtraction, TenantSettings, QuoteRef
from packages.rules.rules import (
    deadline_breach,
    check_stamp_duty,
    flag_section_74,
    check_automatic_renewal_escalation,
    check_venue_distance,
    validate_quote,
    validate_extraction_quotes,
)
from packages.rules.scoring import compute_coc_exposure, compute_risk_score


@pytest.fixture
def settings() -> TenantSettings:
    return TenantSettings(
        client_hub_city="Bengaluru",
        closing_date=date(2026, 9, 15),
        ld_high_threshold_inr=5_000_000,
        renewal_escalation_threshold_pct=15,
        confidence_threshold=0.78,
        max_provider_retries=3,
        allow_semantic_routing=False,
        allow_auto_ticket_creation=True,
        allow_auto_email_drafts=True,
        stamp_rule_source="seed_table_v1",
    )


# ═══════════════════════════════════════════════════════════════════════════════
# §21.2 — Quote validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestQuoteValidator:
    def test_quote_found_in_page_text(self) -> None:
        assert validate_quote("This is page text with a clause.", "page text with") is True

    def test_quote_not_found(self) -> None:
        assert validate_quote("This is page text.", "missing text") is False

    def test_empty_quote(self) -> None:
        assert validate_quote("Any text here.", "") is True

    def test_empty_page_text(self) -> None:
        assert validate_quote("", "something") is False

    def test_whitespace_insensitive(self) -> None:
        assert validate_quote("This is page text.", "  page text  ") is True


class TestExtractionQuotesValidator:
    def test_all_quotes_valid(self, clean_extraction, clean_page_lookup) -> None:
        errors = validate_extraction_quotes(clean_extraction, clean_page_lookup)
        assert errors == []

    def test_missing_quote_triggers_error(self, extraction_with_missing_quote, clean_page_lookup) -> None:
        errors = validate_extraction_quotes(extraction_with_missing_quote, clean_page_lookup)
        assert len(errors) > 0
        assert any("quote not found" in e.lower() for e in errors)

    def test_invalid_page_triggers_error(self, extraction_with_invalid_page, clean_page_lookup) -> None:
        errors = validate_extraction_quotes(extraction_with_invalid_page, clean_page_lookup)
        assert any("page 99 not found" in e for e in errors)


# ═══════════════════════════════════════════════════════════════════════════════
# §10.3 — Deadline breach
# ═══════════════════════════════════════════════════════════════════════════════


class TestDeadlineBreach:
    def test_breach_when_notice_exceeds_days(self) -> None:
        closing = date(2026, 2, 1)
        assert deadline_breach(90, closing) is True

    def test_no_breach_when_notice_within_days(self) -> None:
        closing = date(2027, 1, 1)
        assert deadline_breach(30, closing) is False

    def test_none_notice_days(self) -> None:
        assert deadline_breach(None, date(2026, 9, 15)) is False

    def test_none_closing_date(self) -> None:
        assert deadline_breach(90, None) is False

    def test_both_none(self) -> None:
        assert deadline_breach(None, None) is False


# ═══════════════════════════════════════════════════════════════════════════════
# §10.4 — Auto-renewal escalation
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoRenewalEscalation:
    def test_escalation_exceeds_threshold(self, settings) -> None:
        ext = ContractExtraction(
            automatic_renewal=True,
            renewal_escalation_pct=20.0,
            extraction_confidence=0.9,
        )
        flagged, msg = check_automatic_renewal_escalation(ext, settings)
        assert flagged is True
        assert "exceeds" in msg

    def test_escalation_below_threshold(self, settings) -> None:
        ext = ContractExtraction(
            automatic_renewal=True,
            renewal_escalation_pct=5.0,
            extraction_confidence=0.9,
        )
        flagged, msg = check_automatic_renewal_escalation(ext, settings)
        assert flagged is False

    def test_no_automatic_renewal(self, settings) -> None:
        ext = ContractExtraction(
            automatic_renewal=False,
            extraction_confidence=0.9,
        )
        flagged, msg = check_automatic_renewal_escalation(ext, settings)
        assert flagged is False

    def test_none_escalation_pct(self, settings) -> None:
        ext = ContractExtraction(
            automatic_renewal=True,
            renewal_escalation_pct=None,
            extraction_confidence=0.9,
        )
        flagged, msg = check_automatic_renewal_escalation(ext, settings)
        assert flagged is True
        assert "unspecified" in msg.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# §10.5 — Venue distance
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckVenueDistance:
    def test_matching_city(self, settings) -> None:
        ext = ContractExtraction(
            arbitration_city="Bengaluru",
            extraction_confidence=0.9,
        )
        flagged, msg = check_venue_distance(ext, settings)
        assert flagged is False

    def test_different_city(self, settings) -> None:
        ext = ContractExtraction(
            arbitration_city="New Delhi",
            extraction_confidence=0.9,
        )
        flagged, msg = check_venue_distance(ext, settings)
        assert flagged is True
        assert "differs" in msg

    def test_no_venue_found(self, settings) -> None:
        ext = ContractExtraction(extraction_confidence=0.9)
        flagged, msg = check_venue_distance(ext, settings)
        assert flagged is False

    def test_case_insensitive(self, settings) -> None:
        ext = ContractExtraction(
            arbitration_city="bengaluru",
            extraction_confidence=0.9,
        )
        flagged, msg = check_venue_distance(ext, settings)
        assert flagged is False


# ═══════════════════════════════════════════════════════════════════════════════
# §10.1 — Stamp duty
# ═══════════════════════════════════════════════════════════════════════════════


class TestCheckStampDuty:
    def test_missing_stamp_duty(self, settings) -> None:
        ext = ContractExtraction(
            stamp_duty_amount_paid_inr=None,
            extraction_confidence=0.9,
        )
        flagged, msg = check_stamp_duty(ext, "MSA", settings)
        assert flagged is True

    def test_sufficient_stamp_duty(self, settings) -> None:
        ext = ContractExtraction(
            stamp_duty_amount_paid_inr=10_000,
            stamp_duty_state="Karnataka",
            extraction_confidence=0.9,
        )
        flagged, msg = check_stamp_duty(ext, "MSA", settings)
        assert flagged is False


# ═══════════════════════════════════════════════════════════════════════════════
# §10.2 — Section 74 LD flag
# ═══════════════════════════════════════════════════════════════════════════════


class TestFlagSection74:
    def test_large_ld_amount(self, settings) -> None:
        ext = ContractExtraction(
            liquidated_damages_amount_inr=10_000_000,
            extraction_confidence=0.9,
        )
        flagged, msg = flag_section_74(ext, settings)
        assert flagged is True

    def test_small_ld_amount(self, settings) -> None:
        ext = ContractExtraction(
            liquidated_damages_amount_inr=1_000,
            extraction_confidence=0.9,
        )
        flagged, msg = flag_section_74(ext, settings)
        assert flagged is False

    def test_none_ld_amount(self, settings) -> None:
        ext = ContractExtraction(
            liquidated_damages_amount_inr=None,
            extraction_confidence=0.9,
        )
        flagged, msg = flag_section_74(ext, settings)
        assert flagged is False


# ═══════════════════════════════════════════════════════════════════════════════
# §10.6 — CoC exposure
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeCoCExposure:
    def test_with_coc_penalty(self) -> None:
        ext = ContractExtraction(
            change_of_control_clause_present=True,
            change_of_control_penalty_inr=50_000_000,
            extraction_confidence=0.9,
        )
        total = compute_coc_exposure(ext)
        assert total == Decimal("50000000")

    def test_no_coc(self) -> None:
        ext = ContractExtraction(extraction_confidence=0.9)
        total = compute_coc_exposure(ext)
        assert total == Decimal("0")

    def test_coc_without_penalty(self) -> None:
        ext = ContractExtraction(
            change_of_control_clause_present=True,
            change_of_control_penalty_inr=None,
            extraction_confidence=0.9,
        )
        total = compute_coc_exposure(ext)
        assert total == Decimal("0")


# ═══════════════════════════════════════════════════════════════════════════════
# §10.7 — Risk score
# ═══════════════════════════════════════════════════════════════════════════════


class TestComputeRiskScore:
    def test_no_findings(self) -> None:
        ext = ContractExtraction(extraction_confidence=0.9)
        total, level, breakdown = compute_risk_score(ext, {})
        assert total == Decimal("0")
        assert level == "INFO"

    def test_all_findings(self) -> None:
        ext = ContractExtraction(
            change_of_control_clause_present=True,
            change_of_control_penalty_inr=10_000_000,
            automatic_renewal=True,
            renewal_escalation_pct=20.0,
            extraction_confidence=0.9,
        )
        findings = {
            "STAMP_35": True,
            "DEADLINE_BREACH": True,
            "COC": True,
            "LD_74": True,
            "AUTO_RENEWAL": True,
            "VENUE": True,
            "UNCAP_CONSEQ": True,
        }
        total, level, breakdown = compute_risk_score(ext, findings)
        expected = Decimal("110")  # 30 + 25 + 20 + 15 + 10 + 5 + 5 = 110
        assert total == expected
        assert level == "CRITICAL"

    def test_medium_risk(self) -> None:
        ext = ContractExtraction(extraction_confidence=0.9)
        total, level, breakdown = compute_risk_score(ext, {"STAMP_35": True, "AUTO_RENEWAL": True})
        assert total == Decimal("40")
        assert level == "MEDIUM"

    def test_low_risk(self) -> None:
        ext = ContractExtraction(extraction_confidence=0.9)
        total, level, breakdown = compute_risk_score(ext, {"VENUE": True, "UNCAP_CONSEQ": True})
        assert total == Decimal("10")
        assert level == "LOW"

    def test_info_risk(self) -> None:
        ext = ContractExtraction(extraction_confidence=0.9)
        total, level, breakdown = compute_risk_score(ext, {"VENUE": True})
        assert total == Decimal("5")
        assert level == "INFO"

    def test_risk_level_boundaries(self) -> None:
        ext = ContractExtraction(extraction_confidence=0.9)
        cases = [
            ({}, "INFO", 0),
            ({"VENUE": True, "UNCAP_CONSEQ": True}, "LOW", 10),
            ({"STAMP_35": True}, "MEDIUM", 30),
            ({"STAMP_35": True, "DEADLINE_BREACH": True}, "HIGH", 55),
            ({"STAMP_35": True, "DEADLINE_BREACH": True, "COC": True, "LD_74": True}, "CRITICAL", 75),
        ]
        for findings, expected_level, _ in cases:
            total, level, _ = compute_risk_score(ext, findings)
            assert level == expected_level, f"findings={findings} expected={expected_level} got={level}"
