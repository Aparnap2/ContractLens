# ContractLens Master Blueprint

Below is the **single-file master blueprint** for **ContractLens** optimized for **A → B**:

- **A:** local-first, single-tenant, portfolio-grade build.
- **B:** clean upgrade path to production multi-tenant scale.

It is intentionally compact in wording but **complete in coverage** so a coding agent gets one canonical source and does not need incremental context stitching.

Every factual claim tied to current external behavior is cited inline. OpenRouter free models use `:free` SKUs and are rate-limited on the free plan; current public docs/pricing indicate free-model limits and pricing constraints, though exact limits can change and must be externalized in config rather than hardcoded. Groq provides OpenAI-compatible APIs via `https://api.groq.com/openai/v1`, which is useful for shared client abstractions and provider fallback. LangGraph `interrupt` requires a checkpointer and resumes by re-executing the interrupted node, which materially affects HITL node design.[^1][^2][^3][^4][^5][^6][^7]

***

## ContractLens Master Blueprint

### 1. Product

**Name:** ContractLens
**Category:** Legal AI for M\&A/vendor due diligence
**Primary user:** junior corporate lawyer or legal ops analyst
**Core job:** upload a folder/zip of Indian commercial contracts; extract poison-pill clauses; compute deterministic legal and financial risk; populate a risk register; create remediation actions.

### 1.1 Problem

Lawyers manually review hundreds of PDFs to find:

- change-of-control penalties,
- automatic renewals and escalation traps,
- notice-period conflicts with closing date,
- liquidated damages that may be vulnerable under Section 74,
- insufficient stamping risk under Section 35,
- distant arbitration/jurisdiction clauses,
- indemnity asymmetry,
- lock-in periods,
- uncapped consequential damages.

Manual review is slow, inconsistent, hard to audit, and weak at portfolio aggregation.

### 1.2 Product promise

“Drop 50–100 contracts. Get a contract-by-contract, page-cited, auditable risk register in minutes.”

### 1.3 Scope

**In scope**

- Indian Lease Deeds, MSAs, SaaS agreements, NDAs, employment contracts.
- PDF ingestion.
- OCR fallback.
- Clause extraction into typed schema.
- Deterministic legal checks.
- Risk scoring and exposure aggregation.
- CSV/XLSX export.
- Jira/Linear ticket creation.
- negotiation-email drafting.
- human review for ambiguous extractions.

**Out of scope, v1**

- redlining,
- e-sign,
- non-PDF ingestion,
- multilingual contracts,
- external legal research generation,
- legal advice replacement.


### 1.4 Deployment strategy

- **A:** local-first single-tenant with Docker Compose.
- **B:** multi-tenant cloud deployment with the same service boundaries, tenancy controls, and queueing abstraction.

***

## 2. User roles

| Role | Goal | Permissions |
| :-- | :-- | :-- |
| Analyst | run audit, inspect findings | upload, review, export |
| Senior reviewer | approve high-risk actions | analyst + approve/reject |
| Admin | configure thresholds/providers | all |
| System | autonomous processing | internal only |


***

## 3. End-to-end workflow

1. User uploads zip/folder manifest.
2. System creates `audit_job`.
3. Files are hashed, deduped, stored, and queued.
4. Each contract is processed independently.
5. PDF text is extracted page by page.
6. Paragraphs/chunks are created with page anchors.
7. Deterministic router selects candidate paragraphs by clause family.
8. LLM extraction converts only routed paragraphs into typed objects.
9. Validation checks completeness, quote fidelity, numeric parsing, and confidence.
10. If ambiguous, graph interrupts for HITL.
11. Deterministic law engine runs.
12. Risk score and financial exposure are calculated.
13. Risk register rows are written.
14. Action agent drafts tickets/emails.
15. Export package is generated.
16. Job closes with summary metrics.

### 3.1 Unhappy path workflow

- unreadable PDF → OCR fallback
- OCR poor quality → mark parser quality low, continue with warning
- no relevant clauses found → create informational row, not failure
- LLM invalid JSON → retry provider/model; if still invalid, human review
- missing exact quote → fail extraction validation
- third-party API limit hit → store deferred action item, do not fail audit
- graph crash mid-job → resume from checkpoint
- duplicate contract file → reuse prior extraction if policy allows

***

## 4. System architecture

### 4.1 Local-first architecture A

- **Web UI:** Next.js
- **API Gateway:** Go or FastAPI gateway; for A, FastAPI-only is acceptable to reduce complexity
- **Agent Service:** Python + LangGraph
- **DB:** PostgreSQL
- **Cache/Queue:** Redis
- **Vector store:** Qdrant optional in A, enabled when semantic routing outgrows regex
- **Observability:** Langfuse
- **File storage:** local encrypted filesystem
- **Exports:** local filesystem/object-like abstraction


### 4.2 Upgrade path B

- add object storage,
- split API gateway and agent worker,
- introduce durable queue abstraction,
- enable multi-tenant row isolation,
- separate compute pools for OCR and extraction,
- add background export worker,
- add per-tenant provider budgets.


### 4.3 Why this split

Python is best for LangGraph/Pydantic/legal rules. Groq’s OpenAI-compatible API and OpenRouter-compatible model routing reduce provider-specific code paths if wrapped behind a single provider interface. LangGraph interrupt semantics demand persisted checkpoints, so the workflow engine must be stateful rather than stateless request chaining.[^3][^4][^1]

***

## 5. Models and provider strategy

### 5.1 Provider policy

Use free-tier providers only.

**Providers**

- OpenRouter free models[^5][^7]
- Groq free-tier/OpenAI-compatible API[^1][^3]
- Poolside as separate provider where direct free access exists in your chosen implementation path; also allow routed Poolside fallback where necessary[^8][^9][^10]


### 5.2 Provider abstraction

Define one internal interface:

```python
class LLMProvider(Protocol):
    async def structured_extract(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: type[BaseModel],
        timeout_s: int,
    ) -> BaseModel: ...
```

No node may call vendor SDKs directly. All calls go through `provider_router.py`.

### 5.3 Routing policy

Priority:

1. Poolside direct free model for structured extraction when available/configured.
2. Groq for speed and batch throughput.
3. OpenRouter free `:free` models for fallback.
4. Human review if structured output remains invalid.

### 5.4 Anti-hallucination provider rules

- temperature near zero,
- strict JSON schema,
- no narrative output accepted,
- response rejected if any field is outside schema,
- numbers must be reparsed deterministically from source quote,
- no field may be populated without `source_quote` and `source_page`,
- absent clause must be `null/false`, never inferred.

***

## 6. LangGraph workflow design

### 6.1 Graph nodes

- `create_job`
- `ingest_contract`
- `extract_pages`
- `chunk_contract`
- `route_clauses`
- `extract_structured_risks`
- `validate_extraction`
- `human_review_interrupt`
- `run_law_engine`
- `score_contract`
- `persist_results`
- `create_actions`
- `export_outputs`
- `finalize_job`


### 6.2 Interrupt design

Use `interrupt()` only in nodes explicitly designed for replay-safe execution because interrupted nodes re-run from the start when resumed.[^4]

### 6.3 Replay-safe node rule

Any node that can interrupt:

- must not perform irreversible side effects before interrupt,
- must write proposed actions as drafts first,
- must use idempotency keys for later side effects,
- must separate “compute” from “commit”.


### 6.4 Graph state

Keep state small. Store references, not full contract text.

```python
class AuditState(TypedDict):
    audit_job_id: str
    contract_id: str | None
    contract_ids: list[str]
    current_step: str
    review_required: bool
    review_payload_id: str | None
    provider_attempts: list[dict]
    extraction_result_id: str | None
    findings_ids: list[str]
    action_ids: list[str]
    errors: list[str]
```


***

## 7. Data model

### 7.1 Core entities

- `audit_jobs`
- `contracts`
- `contract_pages`
- `contract_chunks`
- `extractions`
- `extraction_quotes`
- `legal_findings`
- `risk_scores`
- `action_items`
- `human_reviews`
- `provider_calls`
- `exports`
- `audit_events`
- `tenant_settings` (single-tenant in A, real tenant table in B)


### 7.2 SQL-ish schema

```sql
CREATE TABLE audit_jobs (
  id UUID PRIMARY KEY,
  status TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ,
  closing_date DATE,
  client_hub_city TEXT,
  total_contracts INT NOT NULL DEFAULT 0,
  processed_contracts INT NOT NULL DEFAULT 0,
  aggregate_exposure_inr NUMERIC(18,2) NOT NULL DEFAULT 0,
  summary_json JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE contracts (
  id UUID PRIMARY KEY,
  audit_job_id UUID NOT NULL REFERENCES audit_jobs(id),
  file_name TEXT NOT NULL,
  file_hash TEXT NOT NULL,
  storage_uri TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  parser_used TEXT,
  parser_quality_score NUMERIC(5,2),
  contract_type TEXT,
  vendor_name TEXT,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX uq_contract_filehash_per_job ON contracts(audit_job_id, file_hash);

CREATE TABLE contract_pages (
  id UUID PRIMARY KEY,
  contract_id UUID NOT NULL REFERENCES contracts(id),
  page_number INT NOT NULL,
  extracted_text TEXT NOT NULL,
  ocr_used BOOLEAN NOT NULL DEFAULT FALSE,
  text_hash TEXT NOT NULL
);

CREATE TABLE contract_chunks (
  id UUID PRIMARY KEY,
  contract_id UUID NOT NULL REFERENCES contracts(id),
  page_number INT NOT NULL,
  chunk_index INT NOT NULL,
  clause_family TEXT,
  chunk_text TEXT NOT NULL,
  chunk_hash TEXT NOT NULL,
  router_score NUMERIC(5,2),
  selected BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE extractions (
  id UUID PRIMARY KEY,
  contract_id UUID NOT NULL REFERENCES contracts(id),
  schema_version TEXT NOT NULL,
  provider_name TEXT NOT NULL,
  model_name TEXT NOT NULL,
  attempt_no INT NOT NULL,
  confidence NUMERIC(5,2),
  structured_json JSONB NOT NULL,
  status TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE extraction_quotes (
  id UUID PRIMARY KEY,
  extraction_id UUID NOT NULL REFERENCES extractions(id),
  field_name TEXT NOT NULL,
  source_quote TEXT NOT NULL,
  page_number INT NOT NULL,
  start_char INT,
  end_char INT
);

CREATE TABLE legal_findings (
  id UUID PRIMARY KEY,
  contract_id UUID NOT NULL REFERENCES contracts(id),
  finding_code TEXT NOT NULL,
  severity TEXT NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  statute_reference TEXT,
  financial_impact_inr NUMERIC(18,2),
  deterministic BOOLEAN NOT NULL DEFAULT TRUE,
  evidence_json JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE risk_scores (
  id UUID PRIMARY KEY,
  contract_id UUID NOT NULL REFERENCES contracts(id),
  total_score NUMERIC(6,2) NOT NULL,
  level TEXT NOT NULL,
  exposure_inr NUMERIC(18,2) NOT NULL DEFAULT 0,
  scoring_breakdown JSONB NOT NULL
);

CREATE TABLE action_items (
  id UUID PRIMARY KEY,
  contract_id UUID NOT NULL REFERENCES contracts(id),
  action_type TEXT NOT NULL,
  external_system TEXT,
  idempotency_key TEXT NOT NULL,
  payload_json JSONB NOT NULL,
  status TEXT NOT NULL,
  external_ref TEXT,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE human_reviews (
  id UUID PRIMARY KEY,
  contract_id UUID NOT NULL REFERENCES contracts(id),
  review_type TEXT NOT NULL,
  status TEXT NOT NULL,
  prompt_json JSONB NOT NULL,
  resolution_json JSONB,
  reviewer_id TEXT,
  created_at TIMESTAMPTZ NOT NULL,
  resolved_at TIMESTAMPTZ
);

CREATE TABLE provider_calls (
  id UUID PRIMARY KEY,
  audit_job_id UUID NOT NULL REFERENCES audit_jobs(id),
  contract_id UUID REFERENCES contracts(id),
  provider_name TEXT NOT NULL,
  model_name TEXT NOT NULL,
  prompt_hash TEXT NOT NULL,
  response_hash TEXT,
  latency_ms INT,
  success BOOLEAN NOT NULL,
  tokens_in INT,
  tokens_out INT,
  error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE audit_events (
  id UUID PRIMARY KEY,
  audit_job_id UUID NOT NULL REFERENCES audit_jobs(id),
  contract_id UUID,
  event_type TEXT NOT NULL,
  event_json JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL
);
```


***

## 8. Canonical extraction schema

```python
from pydantic import BaseModel, Field
from typing import Optional, Literal

class QuoteRef(BaseModel):
    source_quote: str
    page_number: int

class ContractExtraction(BaseModel):
    vendor_name: Optional[str] = None
    contract_type: Optional[Literal["LEASE","MSA","NDA","EMPLOYMENT","SAAS","OTHER"]] = None
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
```


### 8.1 Hard validation rules

- if `*_present == True`, matching quote must exist.
- all money fields require quote.
- all duration fields require quote.
- quote page must map to real page.
- `source_quote` must be substring of extracted page text.
- if not substring, extraction invalid.
- confidence below threshold never auto-commits as final.

***

## 9. Clause routing logic

### 9.1 Deterministic router first

Use regex + keyword families:

- change of control,
- assignability,
- termination,
- notice,
- automatic renewal,
- price escalation,
- liquidated damages,
- penalty,
- stamp duty,
- arbitration,
- jurisdiction,
- indemnity,
- consequential damages,
- lock-in.


### 9.2 Semantic router second

Optional in A, enabled in B or after baseline:

- embed chunks,
- query by clause family prompt,
- union deterministic + semantic candidates,
- cap top-k per family.


### 9.3 Why

This constrains LLM context and reduces hallucination surface area by only exposing relevant text.

***

## 10. Business logic

### 10.1 Section 35 logic

If stamp duty missing or insufficient according to configured state rule table, mark risk. Public legal references describe instruments not duly stamped as inadmissible in evidence under Section 35, so this should be expressed as a risk/compliance finding, not as final legal advice.[^11][^12][^13]

### 10.2 Section 74 logic

Flag large LD amounts and suspicious penalty patterns as potential enforceability/commercial-risk issues, not definitive court outcomes. Section 74 analysis must be framed as screening logic, not legal conclusion.[^14]

### 10.3 Deadline breach logic

If `termination_notice_days > days_until_closing`, mark immediate action required.

### 10.4 Automatic renewal logic

If auto-renewal is true and escalation exceeds configured threshold, mark medium/high risk.

### 10.5 Venue logic

If arbitration/jurisdiction city differs from client hub city/state, mark operational burden risk.

### 10.6 CoC exposure formula

Aggregate exposure = sum of all change-of-control penalty amounts plus deterministic immediate stamp/other monetary liabilities where applicable.

### 10.7 Risk score formula

```text
score =
  30 * insufficient_stamp_flag +
  25 * deadline_breach_flag +
  20 * change_of_control_flag +
  15 * high_ld_flag +
  10 * auto_renew_escalation_flag +
   5 * distant_venue_flag +
   5 * uncapped_consequential_flag

risk_level:
  0-9   INFO
  10-29 LOW
  30-49 MEDIUM
  50-69 HIGH
  70+   CRITICAL
```

All weights must be config-driven.

***

## 11. Configuration model

```yaml
tenant_settings:
  client_hub_city: Bengaluru
  closing_date: 2026-09-15
  ld_high_threshold_inr: 5000000
  renewal_escalation_threshold_pct: 15
  confidence_threshold: 0.78
  max_provider_retries: 3
  allow_semantic_routing: false
  allow_auto_ticket_creation: true
  allow_auto_email_drafts: true
  stamp_rule_source: seed_table_v1
```

No business threshold may be hardcoded in node code.

***

## 12. Third-party integrations

### 12.1 Allowed in A

- Linear or Jira for tickets
- SendGrid or equivalent free-tier email API for drafts/send
- OpenRouter
- Groq
- Poolside
- Langfuse


### 12.2 Integration rules

- all integrations behind adapters,
- draft then commit,
- idempotency key required,
- retries only for transient failures,
- no ticket/email creation before reviewer approval if severity is critical.

***

## 13. API design

### 13.1 External API

- `POST /audit-jobs`
- `GET /audit-jobs/{id}`
- `GET /audit-jobs/{id}/contracts`
- `GET /contracts/{id}/findings`
- `POST /human-reviews/{id}/resolve`
- `POST /audit-jobs/{id}/resume`
- `GET /audit-jobs/{id}/exports/{export_id}`


### 13.2 Example create job

```json
{
  "closing_date": "2026-09-15",
  "client_hub_city": "Bengaluru",
  "ticket_system": "linear",
  "email_enabled": true
}
```


### 13.3 Example human review resolution

```json
{
  "approved": true,
  "patched_extraction": {
    "termination_notice_days": 90,
    "termination_notice_quote": {
      "source_quote": "Either party may terminate upon ninety (90) days prior written notice.",
      "page_number": 12
    }
  },
  "review_notes": "OCR merged 30 and 90 incorrectly."
}
```


***

## 14. File and folder structure

```text
contractlens/
  apps/
    api/
    worker/
    web/
  packages/
    domain/
    providers/
    workflows/
    rules/
    exports/
    integrations/
  infra/
    docker/
    migrations/
    seed/
  tests/
    unit/
    integration/
    e2e/
    evals/
    fixtures/
  docs/
    master_spec.md
```


***

## 15. Service boundaries

### A

- one API service,
- one worker,
- postgres,
- redis,
- langfuse,
- optional qdrant.


### B

- upload service,
- workflow worker,
- OCR worker pool,
- extraction worker pool,
- action worker,
- export worker,
- auth/gateway,
- tenant config service.

***

## 16. SOPs

### 16.1 SOP: run audit

1. Verify provider keys and quotas.
2. Upload zip.
3. Set closing date and client hub city.
4. Start job.
5. Monitor progress.
6. Resolve any human reviews.
7. Review critical findings.
8. Approve actions.
9. Download export.
10. Archive job.

### 16.2 SOP: human review

1. Open flagged field.
2. Compare extracted value with page text.
3. Patch only fields evidenced by quote.
4. Approve or reject.
5. Resume graph.

### 16.3 SOP: provider outage

1. Mark failing provider unhealthy.
2. Route to next provider.
3. Requeue only failed extraction tasks.
4. Keep audit job open.
5. Notify user only if all providers fail.

### 16.4 SOP: stamp rule update

1. Update seed/config table.
2. Run regression tests on rule engine.
3. Bump `stamp_rule_source`.
4. Log audit event.

***

## 17. Checklists

### 17.1 Build checklist

- schema defined
- DB migrations written
- provider abstraction written
- all nodes typed
- interrupt-safe HITL implemented
- deterministic law engine implemented
- idempotent actions implemented
- exports implemented
- tests written
- golden eval fixtures created
- docs packaged as single master spec


### 17.2 Release checklist

- unit tests green
- integration tests green
- e2e sample job green
- eval thresholds met
- provider fallback verified
- exports verified
- human review replay verified
- crash recovery verified
- no secret in repo
- docker compose boots on 16GB RAM target


### 17.3 Review checklist

- every finding has quote
- every quote has page
- every number has deterministic parse
- every external action has approval path
- every side effect has idempotency key
- every threshold is config-based
- every prompt is versioned
- every schema is versioned

***

## 18. ADRs

### ADR-001

Use LangGraph for orchestration because resumable interrupts and checkpointers fit legal HITL flows better than stateless chains.[^6][^4]

### ADR-002

Separate non-deterministic extraction from deterministic legal rules to reduce hallucination and improve auditability.

### ADR-003

Use provider abstraction rather than provider-specific code in nodes.

### ADR-004

Use local-first single-tenant deployment first; preserve boundaries for multi-tenant scale later.

### ADR-005

Keep graph state reference-based, not document-text-based, to control memory.

### ADR-006

No side effects before human approval on critical actions.

### ADR-007

Use strict typed schemas and reject free-text model outputs.

### ADR-008

All legal outputs are risk signals and workflow aids, not legal advice.

***

## 19. Prompting strategy

### 19.1 System prompt rules for extraction

- You are an extraction engine, not a legal advisor.
- Extract only explicit facts from supplied text.
- Never infer absent clauses.
- If unclear, return null and add ambiguity note.
- Every populated material field must include exact quote and page.
- Return JSON only.


### 19.2 User prompt template

```text
Contract metadata:
- contract_id: {contract_id}
- contract_type_hint: {contract_type_hint}

Candidate paragraphs:
{clauses_with_page_numbers}

Task:
Extract the schema exactly.
Rules:
1. Use only supplied text.
2. No assumptions.
3. Null if absent.
4. Every populated field requires exact quote and page.
5. JSON only.
```


***

## 20. Anti-hallucination coding-agent rules

This is the most important section.

### 20.1 Coding-agent operating rules

The coding agent must:

- implement only entities, APIs, tables, fields, and workflows explicitly defined in this master spec;
- never invent fields, statuses, or endpoints;
- never rename schema fields unless updating all references and reporting it;
- ask for clarification if required data is missing instead of guessing;
- fail closed on ambiguity;
- preserve deterministic rule boundaries;
- preserve interrupt/checkpointer semantics;
- preserve idempotency and approval flows;
- never “simplify” by removing evidence capture, quote storage, or audit logs.


### 20.2 Coding-agent output contract

For every task it performs, it must return:

- files changed,
- spec sections implemented,
- schema or migration changes,
- tests added/updated,
- commands run,
- result summary,
- assumptions made,
- deviations from spec,
- rollback notes.


### 20.3 Forbidden shortcuts

- no replacing structured schema with dicts,
- no skipping quote validation,
- no full-document prompts for convenience,
- no business thresholds hardcoded in logic,
- no provider SDK calls inside business logic nodes,
- no direct irreversible external side effects before approval,
- no mocking all LLM behavior and claiming production readiness,
- no storing entire document blobs inside LangGraph state,
- no hidden global mutable state.

***

## 21. Code snippets

### 21.1 Provider router

```python
class ProviderRouter:
    def __init__(self, providers, policy):
        self.providers = providers
        self.policy = policy

    async def structured_extract(self, request):
        last_error = None
        for candidate in self.policy.candidates(request):
            provider = self.providers[candidate.provider_name]
            try:
                result = await provider.structured_extract(
                    model=candidate.model,
                    system_prompt=request.system_prompt,
                    user_prompt=request.user_prompt,
                    response_schema=request.response_schema,
                    timeout_s=request.timeout_s,
                )
                return result, candidate
            except Exception as e:
                last_error = e
                continue
        raise RuntimeError(f"all providers failed: {last_error}")
```


### 21.2 Quote validation

```python
def validate_quote(page_text: str, quote: str) -> bool:
    return quote.strip() in page_text

def validate_extraction_quotes(extraction: ContractExtraction, page_lookup: dict[int, str]) -> list[str]:
    errors = []
    for field_name, value in extraction.model_dump().items():
        if field_name.endswith("_quote") and value:
            page = value["page_number"]
            quote = value["source_quote"]
            if page not in page_lookup:
                errors.append(f"{field_name}: invalid page")
            elif not validate_quote(page_lookup[page], quote):
                errors.append(f"{field_name}: quote not found in page text")
    return errors
```


### 21.3 Interrupt-safe review node

```python
from langgraph.types import interrupt

def human_review_node(state):
    review_payload = load_review_payload(state["review_payload_id"])
    resolution = interrupt({
        "type": "HUMAN_REVIEW",
        "payload": review_payload,
    })
    apply_review_resolution(state["contract_id"], resolution)
    return {"review_required": False}
```

This node is only safe if `apply_review_resolution` is idempotent and no side effects occur before the interrupt, because interrupted nodes replay from the start on resume.[^4]

### 21.4 Deterministic deadline breach

```python
from datetime import date

def deadline_breach(termination_notice_days: int | None, closing_date: date | None) -> bool:
    if termination_notice_days is None or closing_date is None:
        return False
    return termination_notice_days > (closing_date - date.today()).days
```


***

## 22. Tests

### 22.1 Unit tests

- regex router matches representative clause variants
- quote validator rejects non-substring quote
- numeric parser extracts INR values correctly
- deadline breach logic
- risk score logic
- stamp table lookup logic
- config loading
- idempotency key generation
- action gating by severity


### 22.2 Integration tests

- upload zip → job created
- worker processes 3 sample contracts
- invalid JSON from provider retries to fallback
- low-confidence extraction triggers human review
- review resolution resumes graph
- approved critical finding creates draft action
- export generated successfully


### 22.3 End-to-end tests

- one clean contract returns low/no risk
- one high-risk MSA yields CoC + renewal + venue findings
- one lease with insufficient stamping yields stamp finding
- one closing-date conflict yields deadline-breach finding


### 22.4 Eval tests

Golden dataset of annotated contracts:

- field precision
- field recall
- quote fidelity
- page-number accuracy
- risk classification agreement
- action recommendation consistency


### 22.5 Test gates

- unit: 100% pass
- integration: 100% pass
- e2e: 100% pass
- eval: configurable thresholds, e.g. precision ≥ 0.95, recall ≥ 0.90, quote fidelity = 1.00

***

## 23. Observability

- Langfuse for prompt/response tracing and evals
- provider call table for per-provider failures
- audit events for workflow transitions
- exportable job timeline
- counters: processed contracts, review interrupts, provider fallbacks, invalid JSON rate

***

## 24. Security

- encrypted file storage in A if feasible; mandatory in B
- secrets via env, never code
- least-privilege integration tokens
- audit logs immutable by normal app users
- sanitize filenames
- AV scan optional in A, stronger in B
- redact unnecessary PII from prompts where possible

***

## 25. Performance constraints

For A:

- optimize for correctness first,
- contract-level parallelism bounded,
- no full-doc prompts,
- only routed chunks sent to provider.

For B:

- add worker pools and queue backpressure,
- separate OCR from extraction throughput pools.

***

## 26. Delivery plan

### Phase A1

- migrations
- schema
- PDF extraction
- regex router
- one provider
- typed extraction
- deterministic rules
- CSV export
- core tests


### Phase A2

- provider fallback
- human review
- ticket/email drafts
- XLSX export
- Langfuse evals


### Phase B1

- tenancy model
- object storage
- queue split
- semantic routing
- stronger auth
- multi-worker scaling


### Phase B2

- full multi-tenant governance
- per-tenant budgets
- policy engine
- more integrations

***

## 27. Final coding-agent master prompt

Use this as the single source prompt for your coding agent.

```text
You are implementing ContractLens from the provided master blueprint.
Your job is to build exactly what the spec defines and nothing that it does not define.

NON-NEGOTIABLE RULES
1. Treat the master blueprint as the canonical source of truth.
2. Do not invent fields, endpoints, statuses, tables, or workflows.
3. If required information is missing, stop and explicitly report the missing item instead of guessing.
4. Preserve the separation between:
   - non-deterministic extraction,
   - deterministic legal/business rules,
   - external side effects.
5. Every material extracted field must be backed by exact quote + page.
6. Never replace typed Pydantic schemas with free-form dicts in domain logic.
7. Never send full contract text to the LLM/provider unless the spec explicitly allows it.
8. Keep LangGraph state lightweight; store IDs/references, not entire contract texts.
9. Any human-review node using interrupt must be replay-safe and side-effect-safe.
10. No irreversible external side effects before approval for critical findings.
11. All thresholds must come from config, never hardcoded.
12. All provider calls must go through a provider abstraction layer.
13. All changes must include tests.
14. If you deviate from spec, explicitly explain why and mark it as a deviation.

IMPLEMENTATION ORDER
1. Create repo structure.
2. Create DB migrations for all tables in the spec.
3. Implement domain schemas and config loading.
4. Implement PDF page extraction and chunking.
5. Implement deterministic clause router.
6. Implement provider abstraction and one provider integration.
7. Implement structured extraction with strict schema validation.
8. Implement quote/page validation.
9. Implement deterministic law engine.
10. Implement risk scoring.
11. Implement LangGraph workflow with checkpointing and interrupt-based HITL.
12. Implement action adapters.
13. Implement exports.
14. Implement tests and eval fixtures.
15. Implement fallback providers.
16. Implement UI/API surfaces.

FOR EACH TASK RETURN
- files created/changed
- spec sections covered
- migrations added
- tests added
- commands to run
- assumptions
- deviations
- next recommended task

FORBIDDEN
- hidden assumptions
- silent schema changes
- skipping tests
- replacing interrupt semantics with ad-hoc pauses
- hardcoding thresholds
- writing ambiguous legal claims as definitive legal advice
- collapsing all logic into one script
- removing auditability to save time

SUCCESS CONDITION
The resulting system must be buildable from the spec alone without requiring unstated context.
```


## Packaging

The best next move is to save the content above as your **single canonical spec file**, then give that exact file to the coding agent as the only governing document. That will reduce drift far more than feeding it partial docs over time.

Would you like me to now convert this into a **clean markdown artifact format** with headings, code fences, and copy-paste-ready sections for direct use as `ContractLens_Master_Blueprint.md`?
<span style="display:none">[^15][^16][^17][^18][^19][^20][^21][^22]</span>

<div align="center">⁂</div>

[^1]: https://console.groq.com/docs/openai

[^2]: https://openrouter.ai/docs/faq

[^3]: https://console.groq.com/docs/overview

[^4]: https://reference.langchain.com/python/langgraph/types/interrupt

[^5]: https://buldrr.com/openrouter-free-api-keys-free-models-simple-guide/

[^6]: https://docs.langchain.com/oss/python/langgraph/interrupts

[^7]: https://openrouter.ai/pricing

[^8]: https://theaidude.net/tools/laguna-xs2

[^9]: https://openrouter.ai/poolside

[^10]: https://freellm.net/models/openrouter/poolside-laguna-m.1

[^11]: https://www.indiacode.nic.in/show-data?actid=AC_JK_69_654_00013_00013_1614057674561\&sectionId=54937\&sectionno=35\&orderno=45

[^12]: https://indianlawlive.net/2023/03/04/law-on-insufficiently-stamped-documents/

[^13]: https://www.supremecourtcases.com/vijay-v-union-of-india-and-others/

[^14]: https://academic.oup.com/cjcl/article/6/1/103/4994994

[^15]: https://medium.com/@sitabjapal03/langgraph-part-4-human-in-the-loop-for-reliable-ai-workflows-aa4cc175bce4

[^16]: https://dev.to/jamesbmour/interrupts-and-commands-in-langgraph-building-human-in-the-loop-workflows-4ngl

[^17]: https://checkthat.ai/brands/openrouter/pricing

[^18]: https://langchain-ai.github.io/langgraph/tutorials/get-started/4-human-in-the-loop/

[^19]: https://www.youtube.com/watch?v=6t7YJcEFUIY

[^20]: https://apiscout.dev/guides/openrouter-api-unified-llm-gateway-2026

[^21]: https://www.remoteopenclaw.com/blog/best-free-openrouter-models-for-ai-coding-agents

[^22]: https://freellm.net/providers/openrouter/

