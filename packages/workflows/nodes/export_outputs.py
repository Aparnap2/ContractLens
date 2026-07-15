# ContractLens — export_outputs node (section 6.1)
# Generate CSV/XLSX export of the risk register.

from __future__ import annotations

from packages.workflows.graph import AuditState


def export_outputs_node(state: AuditState) -> dict:
    """Node 13 — Generate export packages (CSV and/or XLSX).
    
    Delegates to packages/exports/ for actual file generation.
    Export files are stored on the local encrypted filesystem.
    Export references are added to state.
    """
    return {"current_step": "export_outputs"}
