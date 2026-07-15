# ContractLens — ingest_contract node (section 6.1)
# Read file, hash, deduplicate, store.

from __future__ import annotations

from packages.workflows.graph import AuditState


def ingest_contract_node(state: AuditState) -> dict:
    """Node 2 — Read uploaded file, compute hash, deduplicate, store reference.
    
    Replay-safe: writes only to local state references.
    Side effects (persistence) happen in persist_results node.
    """
    contract_id = state.get("contract_id")
    if contract_id and contract_id not in state.get("contract_ids", []):
        return {"contract_ids": [*state.get("contract_ids", []), contract_id]}
    return {}
