"""Pydantic v2 schemas for ContractLens API request/response models.

Spec sections: 13 (API design), 8 (canonical extraction schema).
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ─── Error Handling ───────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Structured error response (spec section 13 — proper HTTP semantics)."""
    error: str = Field(..., description="Machine-readable error code string")
    detail: Optional[str] = Field(None, description="Human-readable error detail")
    code: str = Field(..., description="Internal error classification code")


# ─── Audit Jobs ───────────────────────────────────────────────────────────────

class AuditJobCreate(BaseModel):
    """Request schema for POST /audit-jobs (spec section 13.2)."""
    closing_date: Optional[date] = Field(
        None, description="Target closing date for the transaction"
    )
    client_hub_city: Optional[str] = Field(
        None, description="Primary client office city for venue comparison"
    )
    ticket_system: Optional[str] = Field(
        None, description="External ticket system (linear/jira)"
    )
    email_enabled: Optional[bool] = Field(
        None, description="Allow automated email drafts"
    )


class AuditJobResponse(BaseModel):
    """Response schema for an audit job."""
    id: UUID
    status: str
    created_by: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    closing_date: Optional[date] = None
    client_hub_city: Optional[str] = None
    total_contracts: int = 0
    processed_contracts: int = 0
    aggregate_exposure_inr: Decimal = Decimal("0.00")
    summary_json: dict = {}

    model_config = {"from_attributes": True}


class AuditJobListResponse(BaseModel):
    """Minimal job info for listing contexts."""
    id: UUID
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_contracts: int
    processed_contracts: int

    model_config = {"from_attributes": True}


# ─── Contracts ────────────────────────────────────────────────────────────────

class ContractResponse(BaseModel):
    """Response schema for a contract within an audit job."""
    id: UUID
    audit_job_id: UUID
    file_name: str
    file_hash: str
    storage_uri: str
    mime_type: str
    parser_used: Optional[str] = None
    parser_quality_score: Optional[Decimal] = None
    contract_type: Optional[str] = None
    vendor_name: Optional[str] = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Findings ─────────────────────────────────────────────────────────────────

class FindingResponse(BaseModel):
    """Response schema for a legal finding."""
    id: UUID
    contract_id: UUID
    finding_code: str
    severity: str
    title: str
    description: str
    statute_reference: Optional[str] = None
    financial_impact_inr: Optional[Decimal] = None
    deterministic: bool = True
    evidence_json: dict = {}

    model_config = {"from_attributes": True}


# ─── Human Reviews ────────────────────────────────────────────────────────────

class ReviewResolution(BaseModel):
    """Request schema for POST /human-reviews/{id}/resolve (spec section 13.3)."""
    approved: bool = Field(
        ..., description="Whether the proposed extraction is approved"
    )
    patched_extraction: Optional[dict] = Field(
        None, description="Corrected extraction values if reviewer disagrees"
    )
    review_notes: Optional[str] = Field(
        None, description="Free-text notes explaining the resolution"
    )


# ─── Exports ──────────────────────────────────────────────────────────────────

class ExportResponse(BaseModel):
    """Response schema for an export record."""
    id: UUID
    audit_job_id: UUID
    status: str
    format: str
    storage_uri: str
    file_size_bytes: Optional[int] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Upload ────────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    """Response after file upload processing."""
    contract_ids: list[UUID] = Field(
        ..., description="UUIDs of the created contract records"
    )
    file_names: list[str] = Field(
        ..., description="Names of the files processed"
    )
    duplicates_skipped: int = Field(
        0, description="Number of duplicate files skipped"
    )
