"""SQLAlchemy ORM models for ContractLens.

Maps directly to the schema defined in spec section 7.2.
All tables use UUID primary keys generated server-side.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class AuditJob(Base):
    __tablename__ = "audit_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closing_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    client_hub_city: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total_contracts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=func.cast("0", Integer), default=0
    )
    processed_contracts: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=func.cast("0", Integer), default=0
    )
    aggregate_exposure_inr: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, server_default=func.cast("0", Numeric(18, 2)), default=Decimal("0.00")
    )
    summary_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=func.cast("'{}'", JSONB), default=dict
    )

    # Relationships
    contracts = relationship("Contract", back_populates="audit_job", cascade="all, delete-orphan")
    events = relationship("AuditEvent", back_populates="audit_job", cascade="all, delete-orphan")
    exports = relationship("Export", back_populates="audit_job", cascade="all, delete-orphan")
    provider_calls = relationship("ProviderCall", back_populates="audit_job", cascade="all, delete-orphan")


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (
        UniqueConstraint("audit_job_id", "file_hash", name="uq_contract_filehash_per_job"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_jobs.id", ondelete="CASCADE"), nullable=False
    )
    file_name: Mapped[str] = mapped_column(Text, nullable=False)
    file_hash: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    parser_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parser_quality_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    contract_type: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vendor_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    audit_job = relationship("AuditJob", back_populates="contracts")
    pages = relationship("ContractPage", back_populates="contract", cascade="all, delete-orphan")
    chunks = relationship("ContractChunk", back_populates="contract", cascade="all, delete-orphan")
    extractions = relationship("Extraction", back_populates="contract", cascade="all, delete-orphan")
    findings = relationship("LegalFinding", back_populates="contract", cascade="all, delete-orphan")
    risk_score = relationship("RiskScore", back_populates="contract", uselist=False, cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="contract", cascade="all, delete-orphan")
    human_reviews = relationship("HumanReview", back_populates="contract", cascade="all, delete-orphan")


class ContractPage(Base):
    __tablename__ = "contract_pages"
    __table_args__ = (
        UniqueConstraint("contract_id", "page_number", name="uq_contract_page_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False)
    ocr_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    text_hash: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    contract = relationship("Contract", back_populates="pages")


class ContractChunk(Base):
    __tablename__ = "contract_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    clause_family: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_hash: Mapped[str] = mapped_column(Text, nullable=False)
    router_score: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    contract = relationship("Contract", back_populates="chunks")


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    schema_version: Mapped[str] = mapped_column(Text, nullable=False)
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    structured_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    contract = relationship("Contract", back_populates="extractions")
    quotes = relationship("ExtractionQuote", back_populates="extraction", cascade="all, delete-orphan")


class ExtractionQuote(Base):
    __tablename__ = "extraction_quotes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    extraction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("extractions.id", ondelete="CASCADE"), nullable=False
    )
    field_name: Mapped[str] = mapped_column(Text, nullable=False)
    source_quote: Mapped[str] = mapped_column(Text, nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_char: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    end_char: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    extraction = relationship("Extraction", back_populates="quotes")


class LegalFinding(Base):
    __tablename__ = "legal_findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    finding_code: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    statute_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    financial_impact_inr: Mapped[Optional[Decimal]] = mapped_column(Numeric(18, 2), nullable=True)
    deterministic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    evidence_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=func.cast("'{}'", JSONB), default=dict
    )

    # Relationships
    contract = relationship("Contract", back_populates="findings")


class RiskScore(Base):
    __tablename__ = "risk_scores"
    __table_args__ = (
        UniqueConstraint("contract_id", name="uq_risk_scores_contract_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    total_score: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False)
    level: Mapped[str] = mapped_column(Text, nullable=False)
    exposure_inr: Mapped[Decimal] = mapped_column(
        Numeric(18, 2), nullable=False, default=Decimal("0.00")
    )
    scoring_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)

    # Relationships
    contract = relationship("Contract", back_populates="risk_score")


class ActionItem(Base):
    __tablename__ = "action_items"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_action_idempotency_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    external_system: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    external_ref: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    contract = relationship("Contract", back_populates="action_items")


class HumanReview(Base):
    __tablename__ = "human_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False
    )
    review_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    resolution_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    reviewer_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    contract = relationship("Contract", back_populates="human_reviews")


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_jobs.id", ondelete="CASCADE"), nullable=False
    )
    contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True
    )
    provider_name: Mapped[str] = mapped_column(Text, nullable=False)
    model_name: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_hash: Mapped[str] = mapped_column(Text, nullable=False)
    response_hash: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    audit_job = relationship("AuditJob", back_populates="provider_calls")
    contract = relationship("Contract")


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_jobs.id", ondelete="CASCADE"), nullable=False
    )
    contract_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=func.cast("'{}'", JSONB), default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    audit_job = relationship("AuditJob", back_populates="events")


class Export(Base):
    __tablename__ = "exports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audit_jobs.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    format: Mapped[str] = mapped_column(Text, nullable=False)
    storage_uri: Mapped[str] = mapped_column(Text, nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    audit_job = relationship("AuditJob", back_populates="exports")
