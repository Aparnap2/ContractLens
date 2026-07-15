# ContractLens — CSV export of risk register (section 1.3)
# Generates a CSV file with one row per contract finding.

from __future__ import annotations

import csv
import io
from typing import Sequence

from packages.domain.schemas import LegalFinding, RiskScore, Contract


def export_risk_register_csv(
    contract: Contract,
    findings: Sequence[LegalFinding],
    risk_score: RiskScore | None,
) -> str:
    """Generate a CSV string of the risk register for one contract.
    
    Each finding becomes one row with contract metadata, finding details,
    risk score, and financial impact.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row
    writer.writerow([
        "Contract ID",
        "File Name",
        "Vendor Name",
        "Contract Type",
        "Finding Code",
        "Severity",
        "Title",
        "Description",
        "Statute Reference",
        "Deterministic",
        "Financial Impact (INR)",
        "Risk Score",
        "Risk Level",
    ])

    if not findings and risk_score is None:
        writer.writerow(["No findings for this contract."])
        return output.getvalue()

    for finding in findings:
        writer.writerow([
            str(contract.id),
            contract.file_name,
            contract.vendor_name or "",
            contract.contract_type or "",
            finding.finding_code,
            finding.severity,
            finding.title,
            finding.description,
            finding.statute_reference or "",
            "Yes" if finding.deterministic else "No",
            str(finding.financial_impact_inr or "0.00"),
            str(risk_score.total_score if risk_score else ""),
            risk_score.level if risk_score else "",
        ])

    return output.getvalue()
