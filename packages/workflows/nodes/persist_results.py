# ContractLens — persist_results node (section 6.1)
# Write risk register rows and all computed results to persistent storage.

from __future__ import annotations

from packages.workflows.graph import AuditState


def persist_results_node(state: AuditState) -> dict:
    """Node 11 — Persist all computed results to the database.
    
    Writes extractions, legal findings, risk scores, and audit events.
    This is the first irreversible side-effect node in the workflow.
    """
    return {"current_step": "persist_results"}
