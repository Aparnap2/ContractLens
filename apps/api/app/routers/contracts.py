"""Contract and finding endpoints.

Spec section 13:
  GET /contracts/{id}/findings — get legal findings for a contract
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Contract, LegalFinding
from app.schemas import ErrorResponse, FindingResponse

router = APIRouter(tags=["Contracts"])


# ─── GET /contracts/{id}/findings ────────────────────────────────────────────

@router.get(
    "/{contract_id}/findings",
    response_model=list[FindingResponse],
    responses={
        200: {"description": "List of legal findings for the contract"},
        404: {"model": ErrorResponse, "description": "Contract not found"},
    },
)
async def get_contract_findings(
    contract_id: uuid.UUID,
    severity: str | None = Query(None, alias="severity"),
    code: str | None = Query(None, alias="code"),
    deterministic: bool | None = Query(None, alias="deterministic"),
    db: AsyncSession = Depends(get_db),
):
    """Get all legal findings for a given contract.

    Supports optional filters:
    - severity: filter by risk severity level (INFO, LOW, MEDIUM, HIGH, CRITICAL)
    - code: filter by finding code
    - deterministic: filter by whether the finding is deterministic (true) or LLM-derived (false)
    """
    # Verify contract exists
    result = await db.execute(select(Contract).where(Contract.id == contract_id))
    contract = result.scalar_one_or_none()
    if not contract:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "detail": f"Contract {contract_id} not found",
                "code": "CONTRACT_NOT_FOUND",
            },
        )

    # Build query with optional filters
    query = select(LegalFinding).where(LegalFinding.contract_id == contract_id)

    if severity:
        query = query.where(LegalFinding.severity == severity.upper())
    if code:
        query = query.where(LegalFinding.finding_code == code)
    if deterministic is not None:
        query = query.where(LegalFinding.deterministic == deterministic)

    query = query.order_by(LegalFinding.severity, LegalFinding.finding_code)

    result = await db.execute(query)
    return result.scalars().all()
