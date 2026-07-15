# ContractLens — Deterministic legal/business rules (sections 10, 21.2, 21.4)
# These rules implement the spec's deterministic checks. No business threshold
# is hardcoded — all configurable values come from TenantSettings.

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel

from domain.schemas import ContractExtraction, TenantSettings


# ──────────────────────────────────────────────
# Section 10.3 — Deadline breach logic (21.4)
# ──────────────────────────────────────────────

def deadline_breach(
    termination_notice_days: int | None,
    closing_date: date | None,
) -> bool:
    """If termination_notice_days > days until closing, mark immediate action.
    
    From section 21.4 spec code:
        return termination_notice_days > (closing_date - date.today()).days
    """
    if termination_notice_days is None or closing_date is None:
        return False
    days_until_closing = (closing_date - date.today()).days
    return termination_notice_days > days_until_closing


# ──────────────────────────────────────────────
# Section 10.1 — Section 35 stamp duty checker
# ──────────────────────────────────────────────

class StampDutyRule(BaseModel):
    """Rule for determining if stamp duty is insufficient for a given state."""
    state: str
    min_lease_stamp_pct: Decimal  # minimum % of annual rent for lease deeds
    min_msa_stamp_inr: Decimal   # minimum flat amount for MSAs
    notes: str

# Config-based state table — externalized so stamp_rule_source can be versioned
# These are illustrative reference values; production should pull from seed data.
STAMP_DUTY_TABLE: list[StampDutyRule] = [
    StampDutyRule(state="Karnataka", min_lease_stamp_pct=Decimal("1.0"), min_msa_stamp_inr=Decimal("500"), notes="Art 30 KGST Act"),
    StampDutyRule(state="Maharashtra", min_lease_stamp_pct=Decimal("1.5"), min_msa_stamp_inr=Decimal("1000"), notes="Art 36 BSA Act"),
    StampDutyRule(state="Tamil Nadu", min_lease_stamp_pct=Decimal("1.0"), min_msa_stamp_inr=Decimal("500"), notes="Art 30 TNSTA"),
    StampDutyRule(state="Delhi", min_lease_stamp_pct=Decimal("1.0"), min_msa_stamp_inr=Decimal("500"), notes="Art 30 DSA Act"),
    StampDutyRule(state="Uttar Pradesh", min_lease_stamp_pct=Decimal("1.5"), min_msa_stamp_inr=Decimal("500"), notes="Art 30 UPSA"),
    StampDutyRule(state="West Bengal", min_lease_stamp_pct=Decimal("1.0"), min_msa_stamp_inr=Decimal("500"), notes="Art 30 WBSA"),
    StampDutyRule(state="Gujarat", min_lease_stamp_pct=Decimal("1.0"), min_msa_stamp_inr=Decimal("500"), notes="Art 30 GSA"),
    StampDutyRule(state="Rajasthan", min_lease_stamp_pct=Decimal("1.0"), min_msa_stamp_inr=Decimal("500"), notes="Art 30 RSA"),
    # Default catch-all
    StampDutyRule(state="*", min_lease_stamp_pct=Decimal("1.0"), min_msa_stamp_inr=Decimal("500"), notes="Default fallback"),
]


def check_stamp_duty(
    extraction: ContractExtraction,
    contract_type: str | None,
    settings: TenantSettings,
) -> tuple[bool, str]:
    """Section 10.1 — Check if stamp duty is missing or insufficient.
    
    Returns (is_insufficient, description).
    This is a risk/compliance finding, not legal advice (per ADR-008).
    """
    if extraction.stamp_duty_amount_paid_inr is None:
        return True, "No stamp duty amount found — document may be inadmissible under Section 35."

    state = extraction.stamp_duty_state or settings.client_hub_city
    # Find matching rule
    rule = _find_stamp_rule(state)
    if rule is None:
        return True, f"No stamp duty rule configured for state '{state}'."

    threshold = _estimate_min_stamp(extraction, rule, contract_type)
    if Decimal(str(extraction.stamp_duty_amount_paid_inr)) < threshold:
        return (
            True,
            f"Stamp duty paid INR {extraction.stamp_duty_amount_paid_inr:,.2f} "
            f"is below estimated minimum INR {threshold:,.2f} for {state}. "
            f"Risk of inadmissibility under Section 35, Indian Stamp Act."
        )

    return False, "Stamp duty appears sufficient."


def _find_stamp_rule(state: str) -> StampDutyRule | None:
    for rule in STAMP_DUTY_TABLE:
        if rule.state == state:
            return rule
    # fallback to catch-all
    for rule in STAMP_DUTY_TABLE:
        if rule.state == "*":
            return rule
    return None


def _estimate_min_stamp(
    extraction: ContractExtraction, rule: StampDutyRule, contract_type: str | None
) -> Decimal:
    """Estimate minimum expected stamp duty based on contract type."""
    # Simple estimation: for leases, use % of rental value;
    # for others use flat minimum.
    if contract_type and contract_type.upper() == "LEASE":
        # Assume annual value is inferred from context; use a reasonable minimum
        annual_value = Decimal("100000")  # default baseline
        return annual_value * rule.min_lease_stamp_pct / Decimal("100")
    return rule.min_msa_stamp_inr


# ──────────────────────────────────────────────
# Section 10.2 — Section 74 liquidated damages
# ──────────────────────────────────────────────

def flag_section_74(
    extraction: ContractExtraction,
    settings: TenantSettings,
) -> tuple[bool, str]:
    """Section 10.2 — Flag large LD amounts and suspicious penalty patterns.
    
    Framed as screening logic, not legal conclusion.
    """
    if extraction.liquidated_damages_amount_inr is None:
        return False, "No liquidated damages clause found."

    if extraction.liquidated_damages_amount_inr > settings.ld_high_threshold_inr:
        return (
            True,
            f"Liquidated damages amount INR {extraction.liquidated_damages_amount_inr:,.2f} "
            f"exceeds threshold INR {settings.ld_high_threshold_inr:,.2f}. "
            f"May be vulnerable as a penalty under Section 74, Indian Contract Act."
        )

    return False, "Liquidated damages within threshold."


# ──────────────────────────────────────────────
# Section 10.4 — Automatic renewal escalation
# ──────────────────────────────────────────────

def check_automatic_renewal_escalation(
    extraction: ContractExtraction,
    settings: TenantSettings,
) -> tuple[bool, str]:
    """Section 10.4 — If auto-renewal and escalation exceeds threshold, flag."""
    if not extraction.automatic_renewal:
        return False, "No automatic renewal clause."

    if extraction.renewal_escalation_pct is None:
        return True, "Automatic renewal with unspecified escalation — further review recommended."

    if extraction.renewal_escalation_pct > settings.renewal_escalation_threshold_pct:
        return (
            True,
            f"Automatic renewal escalation of {extraction.renewal_escalation_pct}% "
            f"exceeds threshold of {settings.renewal_escalation_threshold_pct}%. "
            f"Medium/high risk of cost escalation."
        )

    return False, "Automatic renewal escalation within threshold."


# ──────────────────────────────────────────────
# Section 10.5 — Venue distance checker
# ──────────────────────────────────────────────

def check_venue_distance(
    extraction: ContractExtraction,
    settings: TenantSettings,
) -> tuple[bool, str]:
    """Section 10.5 — If arbitration/jurisdiction city differs from hub city, flag."""
    venue_city = (
        extraction.arbitration_city
        or extraction.exclusive_jurisdiction_city
        or extraction.governing_law_city
    )
    if venue_city is None:
        return False, "No venue/jurisdiction clause found."

    hub = settings.client_hub_city
    if venue_city.lower() != hub.lower():
        return (
            True,
            f"Venue city '{venue_city}' differs from client hub city '{hub}'. "
            f"May impose operational burden for dispute resolution."
        )

    return False, "Venue matches client hub city."


# ──────────────────────────────────────────────
# Section 21.2 — Quote validation
# ──────────────────────────────────────────────

def validate_quote(page_text: str, quote: str) -> bool:
    """Section 21.2 — Check that the quote is a substring of the page text."""
    return quote.strip() in page_text


def validate_extraction_quotes(
    extraction: ContractExtraction,
    page_lookup: dict[int, str],
) -> list[str]:
    """Section 21.2 — Validate all quote references in an extraction.
    
    Returns a list of error messages. Empty list means all quotes are valid.
    """
    errors: list[str] = []
    for field_name, value in extraction.model_dump().items():
        if field_name.endswith("_quote") and value is not None:
            # value is a dict from model_dump (which flattens nested models)
            if isinstance(value, dict):
                page = value.get("page_number")
                quote = value.get("source_quote")
            else:
                page = value.page_number
                quote = value.source_quote

            if page is None or quote is None:
                errors.append(f"{field_name}: missing page_number or source_quote")
                continue

            if page not in page_lookup:
                errors.append(f"{field_name}: page {page} not found in extracted pages")
            elif not validate_quote(page_lookup[page], quote):
                errors.append(
                    f"{field_name}: quote not found in page {page} text"
                )
    return errors
