# ContractLens — route_clauses node (section 6.1)
# Deterministic (regex) clause routing per section 9.

from __future__ import annotations

from packages.workflows.graph import AuditState
from packages.rules.rules import validate_quote


# Section 9.1 — Keyword families for deterministic routing
CLAUSE_ROUTING_PATTERNS: dict[str, list[str]] = {
    "change_of_control": [
        "change of control", "change in control", "acquisition of",
        "merger", "sale of substantially all",
    ],
    "assignability": [
        "assignment", "assignee", "assigns", "novation",
    ],
    "termination": [
        "termination", "terminate", "terminated", "expiration", "expire",
    ],
    "notice": [
        "notice", "written notice", "prior notice", "notice period",
    ],
    "automatic_renewal": [
        "automatic renewal", "auto-renew", "automatically renew",
        "shall renew", "tacit reconduction",
    ],
    "price_escalation": [
        "escalation", "price increase", "increase by", "annual increase",
        "escalate",
    ],
    "liquidated_damages": [
        "liquidated damages", "ld", "penalty", "damages for delay",
    ],
    "penalty": [
        "penalty", "penal", "penalties", "late fee",
    ],
    "stamp_duty": [
        "stamp duty", "stamping", "duly stamped", "stamp paper",
    ],
    "arbitration": [
        "arbitration", "arbitral", "arbitrator", "conciliation",
    ],
    "jurisdiction": [
        "jurisdiction", "courts at", "exclusive jurisdiction",
        "subject to the jurisdiction",
    ],
    "indemnity": [
        "indemnity", "indemnify", "indemnification", "hold harmless",
    ],
    "consequential_damages": [
        "consequential damages", "indirect damages", "loss of profit",
        "loss of business",
    ],
    "lock_in": [
        "lock-in", "lock in", "minimum period", "non-terminable",
        "irrevocable",
    ],
}


def route_clauses_node(state: AuditState) -> dict:
    """Node 5 — Route chunks to clause families using deterministic patterns.
    
    Section 9.1: regex + keyword families select candidate paragraphs.
    Only routed chunks are sent to the LLM provider (section 9.3).
    """
    return {"current_step": "route_clauses"}
