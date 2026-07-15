"""ContractLens — Configuration loading (Master Spec §11)."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class ContractLensSettings(BaseSettings):
    """Application-wide settings, loaded from environment / .env file."""

    model_config = SettingsConfigDict(env_prefix="CONTRACTLENS_", env_file=".env", extra="ignore")

    # ── Core ──
    debug: bool = False
    database_url: str = "postgresql+asyncpg://contractlens:contractlens@localhost:5432/contractlens"
    redis_url: str = "redis://localhost:6379/0"

    # ── Provider keys ──
    openrouter_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    poolside_api_key: Optional[str] = None

    # ── Tenant defaults (§11) ──
    client_hub_city: str = "Bengaluru"
    closing_date: Optional[str] = None
    ld_high_threshold_inr: float = 5_000_000
    renewal_escalation_threshold_pct: float = 15.0
    confidence_threshold: float = 0.78
    max_provider_retries: int = 3
    allow_semantic_routing: bool = False
    allow_auto_ticket_creation: bool = True
    allow_auto_email_drafts: bool = True
    stamp_rule_source: str = "seed_table_v1"

    # ── Eval thresholds (§22.5) ──
    eval_precision_threshold: float = 0.95
    eval_recall_threshold: float = 0.90
    eval_quote_fidelity_required: float = 1.00


settings = ContractLensSettings()
