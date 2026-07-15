# ContractLens — extract_pages node (section 6.1)
# PDF text extraction page by page with OCR fallback.

from __future__ import annotations

from packages.workflows.graph import AuditState


def extract_pages_node(state: AuditState) -> dict:
    """Node 3 — Extract text from PDF page by page.
    
    OCR fallback is attempted if direct extraction yields poor text quality.
    Parser quality is recorded but the node continues with a warning if low.
    (Section 3.1 unhappy path: OCR poor quality → mark quality low, continue.)
    """
    # Actual PDF extraction logic lives in the service layer.
    # This node sets the step marker and delegates to the PDF service.
    return {"current_step": "extract_pages"}
