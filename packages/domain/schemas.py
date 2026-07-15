"""ContractLens — Pydantic domain schemas (Master Spec §7, §8)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ── §8 Canonical extraction schema ──────────────────────────────────────────


class QuoteRef(BaseModel):
    """A quote reference with source text and page number."""

    source_quote: str
    page_number: int


class ContractExtraction(BaseModel):
    """Structured extraction output for a single contract."""

    vendor_name: Optional[str] = None
    contract_type: Optional[Literal["LEASE", "MSA", "NDA", "EMPLOYMENT", "SAAS", "OTHER"]] = None
    governing_law_city: Optional[str] = None
    arbitration_city: Optional[str] = None

    change_of_control_clause_present: bool = False
    change_of_control_penalty_inr: Optional[float] = None
    change_of_control_quote: Optional[QuoteRef] = None

    termination_notice_days: Optional[int] = None
    termination_notice_quote: Optional[QuoteRef] = None

    automatic_renewal: bool = False
    renewal_escalation_pct: Optional[float] = None
    renewal_quote: Optional[QuoteRef] = None

    stamp_duty_amount_paid_inr: Optional[float] = None
    stamp_duty_state: Optional[str] = None
    stamp_duty_quote: Optional[QuoteRef] = None

    lock_in_period_months: Optional[int] = None
    lock_in_quote: Optional[QuoteRef] = None

    liquidated_damages_clause_text: Optional[str] = None
    liquidated_damages_amount_inr: Optional[float] = None
    liquidated_damages_quote: Optional[QuoteRef] = None

    consequential_damages_capped: Optional[bool] = None
    consequential_damages_quote: Optional[QuoteRef] = None

    indemnity_cap_inr: Optional[float] = None
    indemnity_quote: Optional[QuoteRef] = None

    exclusive_jurisdiction_city: Optional[str] = None
    exclusive_jurisdiction_quote: Optional[QuoteRef] = None

    extraction_confidence: float = Field(ge=0, le=1)
    ambiguity_notes: list[str] = []


# ── §7.2 Core entities ──────────────────────────────────────────────────────


class AuditJob(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "pending"
    created_by: str = "analyst"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    closing_date: Optional[date] = None
    client_hub_city: Optional[str] = None
    total_contracts: int = 0
    processed_contracts: int = 0
    aggregate_exposure_inr: Decimal = Decimal("0")
    summary_json: dict = Field(default_factory=dict)


class Contract(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_job_id: str
    file_name: str
    file_hash: str
    storage_uri: str
    mime_type: str = "application/pdf"
    parser_used: Optional[str] = None
    parser_quality_score: Optional[float] = None
    contract_type: Optional[str] = None
    vendor_name: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ContractPage(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str
    page_number: int
    extracted_text: str
    ocr_used: bool = False
    text_hash: str


class ContractChunk(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str
    page_number: int
    chunk_index: int
    clause_family: Optional[str] = None
    chunk_text: str
    chunk_hash: str
    router_score: Optional[float] = None
    selected: bool = False


class Extraction(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str
    schema_version: str = "1.0"
    provider_name: str
    model_name: str
    attempt_no: int = 1
    confidence: Optional[float] = None
    structured_json: dict = Field(default_factory=dict)
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractionQuote(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    extraction_id: str
    field_name: str
    source_quote: str
    page_number: int
    start_char: Optional[int] = None
    end_char: Optional[int] = None


class LegalFinding(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str
    finding_code: str
    severity: str
    title: str
    description: str
    statute_reference: Optional[str] = None
    financial_impact_inr: Optional[Decimal] = None
    deterministic: bool = True
    evidence_json: dict = Field(default_factory=dict)


class RiskScore(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str
    total_score: float
    level: str
    exposure_inr: Decimal = Decimal("0")
    scoring_breakdown: dict = Field(default_factory=dict)


class ActionItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str
    action_type: str
    external_system: Optional[str] = None
    idempotency_key: str
    payload_json: dict = Field(default_factory=dict)
    status: str = "draft"
    external_ref: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HumanReview(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    contract_id: str
    review_type: str
    status: str = "pending"
    prompt_json: dict = Field(default_factory=dict)
    resolution_json: Optional[dict] = None
    reviewer_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class ProviderCall(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_job_id: str
    contract_id: Optional[str] = None
    provider_name: str
    model_name: str
    prompt_hash: str
    response_hash: Optional[str] = None
    latency_ms: Optional[int] = None
    success: bool
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    error_code: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    audit_job_id: str
    contract_id: Optional[str] = None
    event_type: str
    event_json: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Provider types (§5, §21.1) ──────────────────────────────────────────────


class ExtractionRequest(BaseModel):
    system_prompt: str
    user_prompt: str
    response_schema: dict
    timeout_s: int = 30


class ExtractionCandidate(BaseModel):
    provider_name: str
    model: str
    priority: int = 0


from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMProvider(Protocol):
    async def structured_extract(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        timeout_s: int = 30,
    ) -> BaseModel: ...


# ── Config types (§11) ──────────────────────────────────────────────────────


class TenantSettings(BaseModel):
    client_hub_city: str = "Bengaluru"
    closing_date: Optional[date] = None
    ld_high_threshold_inr: float = 5_000_000
    renewal_escalation_threshold_pct: float = 15.0
    confidence_threshold: float = 0.78
    max_provider_retries: int = 3
    allow_semantic_routing: bool = False
    allow_auto_ticket_creation: bool = True
    allow_auto_email_drafts: bool = True
    stamp_rule_source: str = "seed_table_v1"


class ProviderCredentials(BaseModel):
    openrouter_key: Optional[str] = None
    groq_key: Optional[str] = None
    poolside_key: Optional[str] = None


class ProviderPolicy(BaseModel):
    max_retries: int = 3
    temperature: float = 0.0
    candidates: list[ExtractionCandidate] = Field(default_factory=list)
