# ContractLens — create_job node (section 6.1)
# Creates audit job record and initializes graph state.

from __future__ import annotations

from packages.workflows.graph import AuditState


def create_job_node(state: AuditState) -> dict:
    """Node 1 — Create or initialize the audit job.
    
    Replay-safe: this node has no side effects before any possible interrupt.
    It only sets up state fields.
    """
    return {
        "audit_job_id": state.get("audit_job_id", ""),
        "current_step": "create_job",
        "errors": [],
    }
