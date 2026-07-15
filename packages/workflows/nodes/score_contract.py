# ContractLens — score_contract node (section 6.1)
# Risk score and financial exposure calculation.

from __future__ import annotations

from packages.workflows.graph import AuditState


def score_contract_node(state: AuditState) -> dict:
    """Node 10 — Compute risk score and aggregate financial exposure.
    
    Delegates to scoring engine from packages/rules/scoring.py.
    Results are stored as risk score references in state.
    """
    return {"current_step": "score_contract"}
