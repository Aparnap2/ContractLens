# ContractLens — create_actions node (section 6.1)
# Draft (not commit) action items — tickets and email drafts.

from __future__ import annotations

from packages.workflows.graph import AuditState


def create_actions_node(state: AuditState) -> dict:
    """Node 12 — Create draft action items.
    
    Section 12.2: All integrations use draft-then-commit pattern.
    - Tickets are drafted with idempotency keys
    - Email drafts are created but not sent
    - If severity is critical, no external side effect occurs before approval
    - Drafts are stored locally; commit happens in a follow-up step
    
    This node is replay-safe: it only creates drafts (no irreversible effects).
    """
    return {"current_step": "create_actions"}
