# ContractLens — deterministic rule engine
from .rules import (
    deadline_breach,
    check_stamp_duty,
    flag_section_74,
    check_automatic_renewal_escalation,
    check_venue_distance,
    validate_quote,
    validate_extraction_quotes,
    StampDutyRule,
    STAMP_DUTY_TABLE,
)
from .scoring import (
    compute_coc_exposure,
    compute_risk_score,
    RiskWeights,
    DEFAULT_RISK_WEIGHTS,
    RISK_LEVEL_THRESHOLDS,
)
from .router import (
    ClauseRouter,
    ROUTE_PATTERNS,
)
from .numeric_parser import (
    parse_inr_value,
)

__all__ = [
    "deadline_breach",
    "check_stamp_duty",
    "flag_section_74",
    "check_automatic_renewal_escalation",
    "check_venue_distance",
    "validate_quote",
    "validate_extraction_quotes",
    "StampDutyRule",
    "STAMP_DUTY_TABLE",
    "compute_coc_exposure",
    "compute_risk_score",
    "RiskWeights",
    "DEFAULT_RISK_WEIGHTS",
    "RISK_LEVEL_THRESHOLDS",
    "ClauseRouter",
    "ROUTE_PATTERNS",
    "parse_inr_value",
]
