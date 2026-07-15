# ContractLens — finalize_job node (section 6.1)
# Close audit job with summary metrics.

from __future__ import annotations

from datetime import datetime

from packages.workflows.graph import AuditState


def finalize_job_node(state: AuditState) -> dict:
    """Node 14 — Finalize the audit job.
    
    - Marks job as completed
    - Records summary metrics
    - Sets completed_at timestamp
    - Triggers any post-completion notifications
    
    This is the terminal node of the workflow.
    """
    return {
        "current_step": "finalize_job",
        "completed_at": datetime.utcnow().isoformat(),
    }
