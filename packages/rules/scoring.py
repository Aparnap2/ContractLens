# ContractLens — Risk scoring engine (sections 10.6, 10.7)
# All weights are config-driven. No business threshold is hardcoded.

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field

from domain.schemas import ContractExtraction, TenantSettings


class RiskWeights(BaseModel):
    """Config-driven risk score weights (section 10.7)."""
    insufficient_stamp_weight: float = 30.0
    deadline_breach_weight: float = 25.0
    change_of_control_weight: float = 20.0
    high_ld_weight: float = 15.0
    auto_renew_escalation_weight: float = 10.0
    distant_venue_weight: float = 5.0
    uncapped_consequential_weight: float = 5.0


# These are the defaults from section 10.7
DEFAULT_RISK_WEIGHTS = RiskWeights()


# Thresholds for risk level — also config-driven
RISK_LEVEL_THRESHOLDS: list[tuple[float, float, str]] = [
    (0, 9, "INFO"),
    (10, 29, "LOW"),
    (30, 49, "MEDIUM"),
    (50, 69, "HIGH"),
    (70, float("inf"), "CRITICAL"),
]


def compute_coc_exposure(
    extraction: ContractExtraction,
) -> Decimal:
    """Section 10.6 — Aggregate CoC exposure.
    
    Sum of change-of-control penalties plus deterministic immediate
    stamp/other monetary liabilities where applicable.
    """
    total = Decimal("0.00")
    if extraction.change_of_control_penalty_inr is not None:
        total += Decimal(str(extraction.change_of_control_penalty_inr))
    if extraction.liquidated_damages_amount_inr is not None:
        total += Decimal(str(extraction.liquidated_damages_amount_inr))
    return total


def compute_risk_score(
    extraction: ContractExtraction,
    findings: dict[str, bool],
    weights: Optional[RiskWeights] = None,
) -> tuple[Decimal, str, dict]:
    """Section 10.7 — Compute weighted risk score.
    
    Returns (total_score, risk_level, scoring_breakdown).
    
    The findings dict should contain boolean flags keyed by finding code:
    - "STAMP_35"      -> insufficient_stamp_flag
    - "DEADLINE_BREACH" -> deadline_breach_flag
    - "COC"           -> change_of_control_flag
    - "LD_74"         -> high_ld_flag
    - "AUTO_RENEWAL"  -> auto_renew_escalation_flag
    - "VENUE"         -> distant_venue_flag
    - "UNCAP_CONSEQ"  -> uncapped_consequential_flag
    """
    w = weights or DEFAULT_RISK_WEIGHTS

    flags = {
        "insufficient_stamp": findings.get("STAMP_35", False),
        "deadline_breach": findings.get("DEADLINE_BREACH", False),
        "change_of_control": findings.get("COC", False),
        "high_ld": findings.get("LD_74", False),
        "auto_renew_escalation": findings.get("AUTO_RENEWAL", False),
        "distant_venue": findings.get("VENUE", False),
        "uncapped_consequential": findings.get("UNCAP_CONSEQ", False),
    }

    breakdown = {
        "insufficient_stamp": w.insufficient_stamp_weight if flags["insufficient_stamp"] else 0,
        "deadline_breach": w.deadline_breach_weight if flags["deadline_breach"] else 0,
        "change_of_control": w.change_of_control_weight if flags["change_of_control"] else 0,
        "high_ld": w.high_ld_weight if flags["high_ld"] else 0,
        "auto_renew_escalation": w.auto_renew_escalation_weight if flags["auto_renew_escalation"] else 0,
        "distant_venue": w.distant_venue_weight if flags["distant_venue"] else 0,
        "uncapped_consequential": w.uncapped_consequential_weight if flags["uncapped_consequential"] else 0,
    }

    total = Decimal(str(sum(breakdown.values())))
    level = _risk_level(total)
    return total, level, breakdown


def _risk_level(score: Decimal) -> str:
    s = float(score)
    for lo, hi, label in RISK_LEVEL_THRESHOLDS:
        if lo <= s <= hi:
            return label
    return "CRITICAL"
