"""Shared pytest fixtures for ContractLens tests.

Provides:
  - Async PostgreSQL test database (testcontainers / direct connection)
  - Redis test container
  - FastAPI test client (httpx.AsyncClient)
  - Sample ContractExtraction fixtures
  - Sample audit_job fixture
  - Mock provider fixture (returns controlled JSON)
  - Reference date fixture for deterministic deadline tests
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, AsyncGenerator, Optional

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from domain.schemas import (
    AuditJob,
    ContractExtraction,
    HumanReview,
    LegalFinding,
    QuoteRef,
)

# ── Attempt async DB + Redis containers ─────────────────────────────────────
# These are conditionally available; tests skip gracefully if not installed.

try:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.redis import RedisContainer

    _HAS_TESTCONTAINERS = True
except ImportError:
    _HAS_TESTCONTAINERS = False

try:
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

    _HAS_SQLALCHEMY = True
except ImportError:
    _HAS_SQLALCHEMY = False


# ── FastAPI app ─────────────────────────────────────────────────────────────
# Imported here so conftest works even without the full app stack.
try:
    from apps.api.main import app, reset_store

    _HAS_API = True
except ImportError:
    _HAS_API = False


# ═══════════════════════════════════════════════════════════════════════════════
# §17.1 Build checklist: tests written, golden eval fixtures created
# ═══════════════════════════════════════════════════════════════════════════════


# ── Path helpers ─────────────────────────────────────────────────────────────


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def fixture_path(name: str) -> Path:
    return FIXTURES_DIR / name


def read_fixture(name: str) -> str:
    return fixture_path(name).read_text(encoding="utf-8")


# ── Reference date for deterministic tests ───────────────────────────────────
# Spec §10.3 deadline_breach uses date.today(); tests override via reference_date.


@pytest.fixture
def reference_date() -> date:
    """A fixed reference date so deadline_breach tests are deterministic.

    Default: 2026-01-01 (well before any closing date in fixtures).
    """
    return date(2026, 1, 1)


# ═══════════════════════════════════════════════════════════════════════════════
# Sample ContractExtraction fixtures (§8 schema)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def clean_extraction() -> ContractExtraction:
    """A low-risk contract extraction — no poison pills, moderate terms.

    Mirrors sample_contract_clean.txt: standard termination, Bengaluru venue,
    no CoC, no auto-renewal.
    """
    return ContractExtraction(
        vendor_name="XYZ Solutions Private Limited",
        contract_type="MSA",
        governing_law_city="Bengaluru",
        arbitration_city="Bengaluru",
        change_of_control_clause_present=False,
        termination_notice_days=30,
        termination_notice_quote=QuoteRef(
            source_quote="Either party may terminate this Agreement by giving not less than thirty (30) days prior written notice",
            page_number=1,
        ),
        automatic_renewal=False,
        stamp_duty_amount_paid_inr=500.0,
        stamp_duty_state="Karnataka",
        exclusive_jurisdiction_city="Bengaluru",
        exclusive_jurisdiction_quote=QuoteRef(
            source_quote="The exclusive jurisdiction for any legal proceedings shall be the courts in Bengaluru",
            page_number=2,
        ),
        liquidated_damages_amount_inr=None,
        consequential_damages_capped=True,
        extraction_confidence=0.95,
    )


@pytest.fixture
def high_risk_extraction() -> ContractExtraction:
    """A high-risk contract extraction — CoC, auto-renewal, distant venue.

    Mirrors sample_contract_high_risk.txt.
    """
    return ContractExtraction(
        vendor_name="DataServe India Private Limited",
        contract_type="MSA",
        governing_law_city="New Delhi",
        arbitration_city="New Delhi",
        change_of_control_clause_present=True,
        change_of_control_penalty_inr=5_00_00_000,  # 5 crores
        change_of_control_quote=QuoteRef(
            source_quote="the Service Provider shall pay the Company a change of control penalty of INR 5,00,00,000",
            page_number=1,
        ),
        termination_notice_days=120,
        termination_notice_quote=QuoteRef(
            source_quote="The Service Provider may terminate this MSA for convenience upon providing not less than one hundred twenty (120) days prior written notice",
            page_number=2,
        ),
        automatic_renewal=True,
        renewal_escalation_pct=20.0,
        renewal_quote=QuoteRef(
            source_quote="shall automatically increase by twenty percent (20%) over the fees applicable during the preceding term",
            page_number=2,
        ),
        stamp_duty_amount_paid_inr=100.0,
        stamp_duty_state="Karnataka",
        stamp_duty_quote=QuoteRef(
            source_quote="This MSA has been executed on stamp paper of INR 100",
            page_number=3,
        ),
        lock_in_period_months=36,
        liquidated_damages_amount_inr=50_000,
        liquidated_damages_clause_text="liquidated damages at the rate of INR 50,000 per day of delay",
        liquidated_damages_quote=QuoteRef(
            source_quote="the Service Provider shall pay liquidated damages at the rate of INR 50,000 per day of delay",
            page_number=2,
        ),
        consequential_damages_capped=True,
        consequential_damages_quote=QuoteRef(
            source_quote="Neither party shall be liable to the other for any indirect, incidental, special, consequential, or punitive damages",
            page_number=4,
        ),
        exclusive_jurisdiction_city="New Delhi",
        exclusive_jurisdiction_quote=QuoteRef(
            source_quote="The exclusive jurisdiction for all matters arising under this MSA shall vest solely with the courts in New Delhi",
            page_number=3,
        ),
        extraction_confidence=0.92,
    )


@pytest.fixture
def lease_extraction() -> ContractExtraction:
    """A lease deed extraction with insufficient stamping.

    Low stamp duty paid for a lease of significant value.
    """
    return ContractExtraction(
        vendor_name="Property Holdings Ltd",
        contract_type="LEASE",
        governing_law_city="Mumbai",
        arbitration_city="Mumbai",
        change_of_control_clause_present=False,
        termination_notice_days=90,
        automatic_renewal=False,
        stamp_duty_amount_paid_inr=500.0,  # Insufficient for lease value
        stamp_duty_state="Maharashtra",
        stamp_duty_quote=QuoteRef(
            source_quote="Stamp duty of INR 500 paid",
            page_number=5,
        ),
        liquidated_damages_amount_inr=None,
        consequential_damages_capped=None,
        exclusive_jurisdiction_city="Mumbai",
        extraction_confidence=0.88,
    )


@pytest.fixture
def extraction_with_missing_quote() -> ContractExtraction:
    """An extraction where one quote does NOT appear in the page text.

    Used to test validate_extraction_quotes rejection path.
    """
    return ContractExtraction(
        vendor_name="Test Vendor",
        contract_type="MSA",
        change_of_control_clause_present=True,
        change_of_control_penalty_inr=1_000_000,
        change_of_control_quote=QuoteRef(
            source_quote="This exact sentence does not exist on page 1",
            page_number=1,
        ),
        termination_notice_days=60,
        termination_notice_quote=QuoteRef(
            source_quote="Sixty days notice is required for termination",
            page_number=2,
        ),
        exclusive_jurisdiction_city="Mumbai",
        extraction_confidence=0.80,
    )


@pytest.fixture
def extraction_with_invalid_page() -> ContractExtraction:
    """An extraction referencing a page number that does not exist."""
    return ContractExtraction(
        vendor_name="Ghost Pages Ltd",
        contract_type="MSA",
        change_of_control_clause_present=True,
        change_of_control_penalty_inr=500_000,
        change_of_control_quote=QuoteRef(
            source_quote="Change of control provision",
            page_number=99,  # Does not exist
        ),
        extraction_confidence=0.85,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Sample audit_job fixture
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_audit_job() -> AuditJob:
    """A standard audit job with a future closing date and Bengaluru hub."""
    return AuditJob(
        id=str(uuid.uuid4()),
        status="pending",
        created_by="analyst",
        closing_date=date(2026, 9, 15),
        client_hub_city="Bengaluru",
        created_at=datetime.utcnow(),
    )


@pytest.fixture
def audit_job_with_closing_conflict() -> AuditJob:
    """An audit job with a closing date that conflicts with notice periods."""
    return AuditJob(
        id=str(uuid.uuid4()),
        status="pending",
        created_by="analyst",
        closing_date=date(2026, 2, 1),  # Close deadline
        client_hub_city="Bengaluru",
        created_at=datetime.utcnow(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Page text lookup fixtures (for quote validation)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def clean_page_lookup() -> dict[int, str]:
    """Page text lookup matching sample_contract_clean.txt."""
    return {
        1: (
            "This Service Agreement (the \"Agreement\") is entered into on this 1st day of "
            "January, 2026, by and between: ABC Technologies Private Limited ... "
            "Either party may terminate this Agreement by giving not less than thirty (30) "
            "days prior written notice to the other party."
        ),
        2: (
            "The exclusive jurisdiction for any legal proceedings shall be the courts in "
            "Bengaluru. Each party agrees to indemnify and hold harmless the other party..."
        ),
        3: (
            "Entire Agreement: This Agreement constitutes the entire agreement between "
            "the parties."
        ),
    }


@pytest.fixture
def high_risk_page_lookup() -> dict[int, str]:
    """Page text lookup matching sample_contract_high_risk.txt."""
    return {
        1: (
            "Change of Control means (a) the acquisition of a party by another entity "
            "by way of merger, amalgamation, or consolidation... "
            "the Service Provider shall pay the Company a change of control penalty of "
            "INR 5,00,00,000 (Rupees Five Crores only) as liquidated damages."
        ),
        2: (
            "This MSA shall automatically renew for successive twelve-month periods... "
            "the Service Provider's fees shall automatically increase by twenty percent "
            "(20%) over the fees applicable during the preceding term. "
            "the Service Provider shall pay liquidated damages at the rate of INR 50,000 "
            "per day of delay, up to a maximum of 10% of the annual contract value. "
            "The Service Provider may terminate this MSA for convenience upon providing "
            "not less than one hundred twenty (120) days prior written notice."
        ),
        3: (
            "This MSA shall be governed by and construed in accordance with the laws of India. "
            "Any and all disputes shall be finally resolved by arbitration in New Delhi. "
            "The exclusive jurisdiction for all matters arising under this MSA shall vest "
            "solely with the courts in New Delhi, India. "
            "This MSA has been executed on stamp paper of INR 100."
        ),
        4: (
            "Neither party shall be liable to the other for any indirect, incidental, "
            "special, consequential, or punitive damages, including but not limited to "
            "loss of profits, loss of business, or loss of data."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Mock provider fixture
# ═══════════════════════════════════════════════════════════════════════════════


class MockProvider:
    """A controllable mock LLM provider for testing.

    Returns pre-configured JSON responses. Can simulate failures, invalid
    JSON, or low-confidence extractions.
    """

    def __init__(self, response_data: Optional[dict] = None) -> None:
        self.response_data = response_data or {}
        self.call_count = 0
        self.last_prompt: Optional[str] = None
        self.fail_mode: Optional[str] = None  # None, "invalid_json", "timeout", "exception"

    async def structured_extract(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type,
        timeout_s: int = 30,
    ):
        self.call_count += 1
        self.last_prompt = user_prompt

        if self.fail_mode == "invalid_json":
            return json.loads("not valid json")  # type: ignore[arg-type]

        if self.fail_mode == "exception":
            raise RuntimeError("Provider connection failed")

        if self.fail_mode == "timeout":
            raise TimeoutError("Provider request timed out")

        return response_schema(**self.response_data)


@pytest.fixture
def mock_provider() -> MockProvider:
    """Return a MockProvider with a default clean extraction response."""
    return MockProvider()


@pytest.fixture
def mock_provider_high_risk() -> MockProvider:
    """Return a MockProvider pre-loaded with high-risk extraction data."""
    from domain.schemas import ContractExtraction

    return MockProvider(
        response_data={
            "vendor_name": "DataServe India Private Limited",
            "contract_type": "MSA",
            "change_of_control_clause_present": True,
            "change_of_control_penalty_inr": 5_00_00_000,
            "automatic_renewal": True,
            "renewal_escalation_pct": 20.0,
            "arbitration_city": "New Delhi",
            "exclusive_jurisdiction_city": "New Delhi",
            "liquidated_damages_amount_inr": 50_000,
            "stamp_duty_amount_paid_inr": 100.0,
            "stamp_duty_state": "Karnataka",
            "extraction_confidence": 0.92,
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# FastAPI test client
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def api_client() -> AsyncClient:
    """Return an httpx.AsyncClient configured against the FastAPI test app.

    Requires apps/api/main.py to exist with a FastAPI 'app' instance.
    """
    if not _HAS_API:
        pytest.skip("FastAPI app not available (apps/api/main.py missing)")
    reset_store()
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest_asyncio.fixture
async def async_api_client() -> AsyncGenerator[AsyncClient, None]:
    """Async fixture yielding an httpx.AsyncClient for the FastAPI app."""
    if not _HAS_API:
        pytest.skip("FastAPI app not available")
    reset_store()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ═══════════════════════════════════════════════════════════════════════════════
# Async database fixtures (conditional — require testcontainers + SQLAlchemy)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest_asyncio.fixture
async def pg_session():
    """Provide an async PostgreSQL session via testcontainers.

    Skips if testcontainers or SQLAlchemy are not installed.
    """
    if not _HAS_TESTCONTAINERS:
        pytest.skip("testcontainers not installed")
    if not _HAS_SQLALCHEMY:
        pytest.skip("SQLAlchemy not installed")

    with PostgresContainer("postgres:16-alpine") as pg:
        engine = create_async_engine(pg.get_connection_url().replace("psycopg2", "asyncpg"))
        async with engine.begin() as conn:
            # Run migrations (in production, use Alembic)
            from pathlib import Path

            migrations_dir = Path(__file__).parent.parent / "infra" / "migrations"
            if migrations_dir.exists():
                for sql_file in sorted(migrations_dir.glob("*.sql")):
                    await conn.execute(sql_file.read_text())
        async with AsyncSession(engine) as session:
            yield session
        await engine.dispose()


@pytest_asyncio.fixture
async def redis_container():
    """Provide a Redis container via testcontainers.

    Skips if testcontainers not installed.
    """
    if not _HAS_TESTCONTAINERS:
        pytest.skip("testcontainers not installed")

    with RedisContainer("redis:7-alpine") as redis:
        yield redis.get_connection_url()


# ═══════════════════════════════════════════════════════════════════════════════
# Golden dataset fixtures (for evals — §22.4)
# ═══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def golden_dataset_path() -> Path:
    """Path to the golden dataset directory.

    Expected structure: evals/golden/{contract_name}/annotation.json
    """
    return Path(__file__).parent / "evals" / "golden"


@pytest.fixture
def sample_golden_entry() -> dict:
    """A single golden dataset entry for test purposes.

    Contains the expected annotation for a clean contract.
    """
    return {
        "contract_file": "sample_contract_clean.txt",
        "expected": {
            "contract_type": "MSA",
            "vendor_name": "XYZ Solutions Private Limited",
            "governing_law_city": "Bengaluru",
            "arbitration_city": "Bengaluru",
            "change_of_control_clause_present": False,
            "termination_notice_days": 30,
            "automatic_renewal": False,
            "exclusive_jurisdiction_city": "Bengaluru",
            "stamp_duty_amount_paid_inr": None,
            "liquidated_damages_amount_inr": None,
        },
        "expected_findings": [],
        "expected_risk_level": "INFO",
        "expected_total_score": 0,
    }
