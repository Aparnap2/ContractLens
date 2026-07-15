# ContractLens — chunk_contract node (section 6.1)
# Split pages into paragraphs/chunks with page anchors.

from __future__ import annotations

from packages.workflows.graph import AuditState


def chunk_contract_node(state: AuditState) -> dict:
    """Node 4 — Split extracted page text into paragraph chunks.
    
    Each chunk retains a page_number anchor for quote validation.
    Chunks are stored as references; full text is not kept in state.
    """
    return {"current_step": "chunk_contract"}
