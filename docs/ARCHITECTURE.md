# ContractLens System Architecture

> **Document status:** Final  
> **Applies to:** Architecture A (local-first single-tenant) with B upgrade paths annotated  
> **Source of truth:** ContractLens Master Blueprint (master_spec.md)

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Service Boundaries](#2-service-boundaries)
3. [Data Flow](#3-data-flow)
4. [Component Interaction Patterns](#4-component-interaction-patterns)
5. [LangGraph Workflow Topology](#5-langgraph-workflow-topology)
6. [Interrupt / Human-in-the-Loop Design](#6-interrupt--human-in-the-loop-design)
7. [Provider Routing Architecture](#7-provider-routing-architecture)
8. [Storage Architecture](#8-storage-architecture)
9. [Security Architecture](#9-security-architecture)
10. [Multi-Tenant Upgrade Path (A → B)](#10-multi-tenant-upgrade-path-a--b)
11. [Observability](#11-observability)

---

## 1. Architecture Overview

### Architecture A (Local-First Single-Tenant)

```
┌──────────────────────────────────────────────────────────┐
│                    Docker Compose                          │
│                                                           │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐              │
│  │  Web UI  │──▶│   API    │──▶│  Worker   │              │
│  │ Next.js  │   │ FastAPI  │   │ Python + │              │
│  │  :3000   │   │  :8000   │   │ LangGraph │              │
│  └──────────┘   └────┬─────┘   └─────┬─────┘              │
│                       │               │                    │
│                       ▼               ▼                    │
│                ┌──────────┐   ┌──────────┐                │
│                │   DB     │   │  Redis   │                │
│                │PostgreSQL│   │ Queue    │                │
│                │  :5432   │   │  :6379   │                │
│                └──────────┘   └──────────┘                │
│                       │               │                    │
│                       ▼               ▼                    │
│                ┌──────────┐   ┌──────────┐                │
│                │ Langfuse │   │  Local   │                │
│                │ Tracing  │   │ Encrypted │               │
│                │          │   │   FS     │                │
│                └──────────┘   └──────────┘                │
│                                                           │
│  ┌─────────────────────────────────────────────┐          │
│  │          Provider Adapter Layer              │          │
│  │  OpenRouter │ Groq │ Poolside               │          │
│  └─────────────────────────────────────────────┘          │
└──────────────────────────────────────────────────────────┘
```

**Key characteristic:** Single-process worker runs all workflow nodes sequentially per contract. Concurrency is bounded by configurable parallelism within the worker. No queue abstraction — API writes directly to DB, worker polls or is invoked.

### Architecture B (Multi-Tenant Cloud)

```
┌─────────────────────────────────────────────────────────────┐
│                      Production Cluster                      │
│                                                              │
│  ┌──────────┐   ┌──────────┐   ┌────────────┐               │
│  │  Web UI  │──▶│  Auth/   │──▶│  Upload    │               │
│  │ Next.js  │   │  Gateway │   │  Service   │               │
│  └──────────┘   └──────────┘   └─────┬──────┘               │
│                                       │                      │
│                                       ▼                      │
│                              ┌────────────────┐             │
│                              │   Durable       │             │
│                              │   Queue (SQS/   │             │
│                              │   Redis Streams)│             │
│                              └───┬───┬───┬─────┘             │
│                                  │   │   │                   │
│                    ┌─────────────┘   │   └─────────────┐     │
│                    ▼                 ▼                 ▼     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  │  OCR Worker Pool │  │ Extraction Worker│  │  Export Worker   │
│  │   (parallel)     │  │   Pool (parallel)│  │                  │
│  └──────────────────┘  └────────┬─────────┘  └──────────────────┘
│                                  │                              │
│  ┌──────────────────┐  ┌────────▼─────────┐  ┌──────────────────┐
│  │  Action Worker   │  │   PostgreSQL      │  │   Object Store   │
│  │  (tickets/email)  │  │   + Citus/Read   │  │   S3/MinIO      │
│  └──────────────────┘  │   Replicas       │  └──────────────────┘
│                        └──────────────────┘                     │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  │  Tenant Config   │  │   Qdrant         │  │   Redis Cluster  │
│  │  Service         │  │   (semantic)     │  │                  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘
└─────────────────────────────────────────────────────────────┘
```

**Key characteristic:** Worker pool splits by concern. Durable queue provides backpressure. Object store replaces local FS. Tenant isolation via row-level + service-level controls.

---

## 2. Service Boundaries

### 2.1 Web UI (`apps/web/`)

| Attribute | Value |
|-----------|-------|
| Framework | Next.js |
| Port (A) | `:3000` |
| Role | Upload interface, progress monitoring, findings review, resolution submission, export download |
| Auth (A) | Session-based or static API key stored in env |
| Auth (B) | OAuth2 / SSO with role-based access |
| Dependencies | API Gateway (`:8000`) |

**Responsibilities:**
- Accept zip/manifest upload via multipart form
- Poll job status via `GET /audit-jobs/{id}`
- Display contract-level findings with page citations
- Render human review prompt interface
- Submit review resolutions
- Trigger exports and download results

**Non-responsibilities:**
- No direct DB access
- No workflow orchestration
- No file processing

### 2.2 API Gateway (`apps/api/`)

| Attribute | Value |
|-----------|-------|
| Framework | FastAPI (A); can split to Go gateway in B |
| Port (A) | `:8000` |
| Role | HTTP API surface, auth enforcement, request validation, job creation, status queries |
| Auth (A) | `X-API-Key` header matched against `API_KEY` env |

**Responsibilities:**
- `POST /audit-jobs` — create job, store files, enqueue
- `GET /audit-jobs/{id}` — return job status and summary
- `GET /audit-jobs/{id}/contracts` — list contracts in job
- `GET /contracts/{id}/findings` — return legal findings for a contract
- `POST /human-reviews/{id}/resolve` — submit human review resolution
- `POST /audit-jobs/{id}/resume` — resume paused graph
- `GET /audit-jobs/{id}/exports/{export_id}` — download export package
- Validate input schemas before writing to DB
- Sanitize filenames on upload

**Non-responsibilities:**
- No workflow execution
- No LLM provider calls
- No export file generation (triggers worker)

### 2.3 Worker (`apps/worker/`)

| Attribute | Value |
|-----------|-------|
| Runtime | Python + LangGraph |
| Role | Execute audit workflow via stateful graph with checkpointer |
| Concurrency (A) | `asyncio` bounded concurrency (default: 3 parallel contracts) |
| Concurrency (B) | Horizontal pod scaling, separate OCR/extraction pools |

**Responsibilities:**
- Execute all 13 LangGraph nodes
- Manage provider fallback and retry
- Orchestrate human-in-the-loop interrupts
- Run deterministic law engine
- Calculate risk scores
- Draft action items (tickets/emails) as deferred side effects
- Generate export packages
- Write audit events

**Non-responsibilities:**
- No HTTP API surface
- No file upload handling

### 2.4 Supporting Services

| Service | Role | A | B |
|---------|------|----|----|
| PostgreSQL | Persistent storage for all entities | Docker container | Managed RDS + read replicas |
| Redis | Job queue, result cache, rate-limit counters | Docker container | Redis Cluster / ElastiCache |
| Langfuse | LLM tracing, prompt versioning, eval | Docker container or cloud | Cloud tier |
| Qdrant | Semantic clause routing (optional) | Not deployed (A) | Separate container / cloud |
| Object Store | File/export persistence | Local encrypted FS | MinIO / S3 |
| Export Worker | Generate CSV/XLSX in background | Inline in worker | Separate pool |

---

## 3. Data Flow

### 3.1 Primary Flow: End-to-End Audit

```
User                    API                   Worker                  DB/Redis
 │                       │                      │                       │
 │  POST /audit-jobs     │                      │                       │
 │  (zip + config)       │                      │                       │
 ├──────────────────────▶│                      │                       │
 │                       │  Hash files,         │                       │
 │                       │  store to FS,        │                       │
 │                       │  create audit_job    │                       │
 │                       │  INSERT contracts    │──────────────────────▶│
 │                       │                      │                       │
 │                       │  Enqueue job         │                       │
 │                       │──────────────────────│──▶ Redis Queue        │
 │                       │                      │                       │
 │  202 Accepted         │                      │                       │
 │◀──────────────────────┤                      │                       │
 │                       │                      │                       │
 │                       │                      │  Dequeue contract     │
 │                       │                      │◀── Redis Queue ──────│
 │                       │                      │                       │
 │                       │                      │  ┌─────────────────┐  │
 │                       │                      │  │ LangGraph       │  │
 │                       │                      │  │ Workflow        │  │
 │                       │                      │  │                 │  │
 │                       │                      │  │ create_job      │  │
 │                       │                      │  │ ingest_contract │  │
 │                       │                      │  │ extract_pages   │  │
 │                       │                      │  │ chunk_contract  │  │
 │                       │                      │  │ route_clauses   │──│──▶ Provider
 │                       │                      │  │ extract_...     │──│──▶ Provider
 │                       │                      │  │ validate_...    │  │
 │                       │                      │  │ human_review... │──│──▶ Redis (interrupt wait)
 │                       │                      │  │ run_law_engine  │  │
 │                       │                      │  │ score_contract  │  │
 │                       │                      │  │ persist_results │──│──▶ DB
 │                       │                      │  │ create_actions  │──│──▶ Linear/Jira
 │                       │                      │  │ export_outputs  │  │
 │                       │                      │  │ finalize_job    │──│──▶ DB
 │                       │                      │  └─────────────────┘  │
 │                       │                      │                       │
 │  GET /audit-jobs/{id}  │                      │                       │
 ├──────────────────────▶│                      │                       │
 │◀──────────────────────┤                      │                       │
 │  {status, summary}    │                      │                       │
 │                       │                      │                       │
 │  GET /contracts/{id}  │                      │                       │
 │  /findings            │                      │                       │
 ├──────────────────────▶│                      │                       │
 │◀──────────────────────┤                      │                       │
 │  [legal_findings]     │                      │                       │
 │                       │                      │                       │
```

### 3.2 Human Review Flow

```
Worker (interrupted)      API                  User
 │                       │                      │
 │  interrupt() with     │                      │
 │  review_payload       │                      │
 │  Graph pauses         │                      │
 │                       │                      │
 │                       │  GET /audit-jobs/{id}│
 │                       │◀─────────────────────┤
 │                       │  status: review      │
 │                       │─────────────────────▶│
 │                       │                      │
 │                       │  POST /human-reviews │
 │                       │  /{id}/resolve       │
 │                       │◀─────────────────────┤
 │                       │                      │
 │  Resume graph with    │                      │
 │  resolution           │                      │
 │  apply_resolution()   │                      │
 │  Continue workflow    │                      │
 │                       │                      │
```

### 3.3 Provider Fallback Flow

```
extract_structured_risks node
         │
         ▼
  Try Poolside (priority 1)
         │
    ┌────┴────┐
    │ Success │  Fail (exception / invalid JSON)
    └────┬────┘         │
         │              ▼
         │       Try Groq (priority 2)
         │              │
         │         ┌────┴────┐
         │         │ Success │  Fail
         │         └────┬────┘     │
         │              │          ▼
         │              │   Try OpenRouter (priority 3)
         │              │          │
         │              │     ┌────┴────┐
         │              │     │ Success │  Fail
         │              │     └────┬────┘     │
         │              │          │          │
         │              │          │    Create human_review
         │              │          │    Mark provider_attempts
         │              │          │    interrupt() for manual fix
         │              │          │          │
         ◀──────────────┴──────────┴──────────┘
         │
         ▼
  return extraction result
```

### 3.4 Unhappy Paths

| Scenario | Flow |
|----------|------|
| Unreadable PDF | → OCR fallback in `extract_pages` → if OCR poor quality → mark `parser_quality_score` low, add audit event, continue |
| No relevant clauses | → `route_clauses` returns empty → `extract_structured_risks` returns null fields → `run_law_engine` creates informational finding → not a failure |
| LLM invalid JSON | → retry with next provider/model up to `max_provider_retries` → if all fail → create `human_review` with raw output, interrupt |
| Missing exact quote | → `validate_extraction` fails → log error, increment provider attempt → retry or interrupt |
| Third-party API limit | → capture error code → store deferred action item → do not fail audit |
| Graph crash mid-job | → LangGraph checkpointer resumes from last completed node → no data loss |
| Duplicate contract | → `file_hash` unique index per job → skip insertion → reuse prior extraction if config allows |

---

## 4. Component Interaction Patterns

### 4.1 API → Worker Handoff

**Architecture A (direct):**
```
POST /audit-jobs
  │
  ├── API validates request
  ├── API stores files to encrypted FS
  ├── API inserts audit_job + contracts rows
  ├── API enqueues job_id to Redis list (LPUSH)
  └── Returns 202 { job_id }
         │
  Worker polls Redis (BRPOP) or listens via pub/sub
  Worker dequeues contract_id one at a time
  Worker executes LangGraph workflow per contract
```

**Architecture B (durable queue):**
```
POST /audit-jobs
  │
  ├── Upload Service receives files
  ├── Upload Service stores to S3/MinIO
  ├── Publishes message to SQS / Redis Streams
  └── Returns 202 { job_id }

  Worker pool consumes from queue with visibility timeout
  Failed messages return to queue after timeout (max 3 retries)
  Dead-letter queue captures permanent failures
```

### 4.2 Worker ↔ DB Interaction

- All DB writes go through the `packages/domain` repository layer
- Worker reads contract config and page text for processing
- Worker writes extraction results, findings, risk scores
- Worker reads human review resolution on resume
- All writes are idempotent where possible (action item idempotency keys)

### 4.3 Worker ↔ External Integrations

```
Worker ──▶ Provider Adapter ──▶ OpenRouter / Groq / Poolside
Worker ──▶ Action Adapter  ──▶ Linear API / Jira API
Worker ──▶ Email Adapter   ──▶ SendGrid API
Worker ──▶ Langfuse SDK    ──▶ Langfuse (tracing)
```

**Rules (from spec §12.2):**
- All integrations behind adapters in `packages/integrations/`
- Draft then commit: no external side effect before approval for critical findings
- Idempotency key required for all ticket/email creation
- Retries only for transient failures (5xx, timeout)
- No ticket/email creation before reviewer approval if severity is critical (score >= 70)

### 4.4 Worker ↔ Human (Interrupt)

```
Worker node hits interrupt()
  │
  ├── State persisted to checkpointer (PostgreSQL or SQLite)
  ├── interrupt() returns control to orchestrator
  ├── Status set to "review" on audit_job
  │
  User resolves via API
  │
  ├── POST /human-reviews/{id}/resolve
  ├── Resolution stored in human_reviews.resolution_json
  │
  API resumes graph
  │
  ├── POST /audit-jobs/{id}/resume
  ├── LangGraph resumes from interrupted node
  ├── Node reads resolution, applies patch
  └── Workflow continues
```

---

## 5. LangGraph Workflow Topology

### 5.1 Node Registry

All 13 nodes as defined in Master Blueprint §6.1:

| # | Node Name | Input State Keys | Output State Keys | Side Effects | Interrupt-Safe |
|---|-----------|-----------------|------------------|-------------|---------------|
| 1 | `create_job` | (initial) | `audit_job_id`, `current_step` | DB: set status to `processing` | N/A (first node) |
| 2 | `ingest_contract` | `audit_job_id`, `contract_ids` | `contract_id` | DB: update contract status to `ingested` | No |
| 3 | `extract_pages` | `contract_id` | (none) | DB: write `contract_pages` rows; file read | No |
| 4 | `chunk_contract` | `contract_id` | (none) | DB: write `contract_chunks` rows | No |
| 5 | `route_clauses` | `contract_id` | (none) | DB: update `contract_chunks.selected`, `clause_family`, `router_score` | No |
| 6 | `extract_structured_risks` | `contract_id` | `extraction_result_id`, `provider_attempts` | DB: write `extractions`, `extraction_quotes`; external: LLM provider calls | No |
| 7 | `validate_extraction` | `extraction_result_id` | `review_required`, `review_payload_id` | DB: update extraction status | No (but precede interrupts) |
| 8 | `human_review_interrupt` | `review_payload_id`, `review_required` | `review_required` | DB: write `human_reviews` prompt; **interrupt()** | **YES** |
| 9 | `run_law_engine` | `contract_id`, optional human review patched data | (none) | DB: write `legal_findings` rows | No |
| 10 | `score_contract` | `contract_id` | `findings_ids` | DB: write `risk_scores` row | No |
| 11 | `persist_results` | `contract_id`, `findings_ids` | (none) | DB: update `audit_jobs.processed_contracts`, `aggregate_exposure_inr` | No |
| 12 | `create_actions` | `contract_id`, `findings_ids` | `action_ids` | External: Linear/Jira tickets, SendGrid emails (if approved) | Yes (only drafts before approval) |
| 13 | `export_outputs` | `audit_job_id` | (none) | FS: write CSV/XLSX; DB: create `exports` row | No |
| — | `finalize_job` | `audit_job_id` | (none) | DB: set `audit_jobs.status` to `completed`, `completed_at`; generate `summary_json` | No |

> **Note:** `finalize_job` is listed as a separate step in the spec §6.1 (item 16). It is not numbered in the 13-node list but is the terminal step. The workflow includes it as an implicit final node.

### 5.2 Graph Topology

```
                                    ┌─────────────┐
                                    │  START       │
                                    │              │
                                    │ create_job   │
                                    └──────┬───────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │              │
                                    │ For each     │
                                    │ contract_id  │
                                    │ in           │
                                    │ contract_ids │
                                    └──────┬───────┘
                                           │
                              ┌────────────▼────────────┐
                              │                         │
                              │  2. ingest_contract     │
                              │  (hash, dedupe, store)  │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │  3. extract_pages        │
                              │  (PDF→text per page,    │
                              │   OCR fallback)          │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │  4. chunk_contract       │
                              │  (paragraph split,      │
                              │   page anchors)          │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │  5. route_clauses        │
                              │  (regex keywords →      │
                              │   selected chunks)       │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │  6. extract_structured_  │
                              │     risks                │
                              │  (provider router →     │
                              │   typed schema)          │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │  7. validate_extraction  │
                              │  (quote fidelity,       │
                              │   numeric parse,         │
                              │   confidence)            │
                              └────────────┬────────────┘
                                           │
                            ┌──────────────┴──────────────┐
                            │                              │
                          OK │                         LOW_CONFIDENCE
                            │                              │
                            ▼                              ▼
                    ┌──────────────┐          ┌──────────────────────┐
                    │              │          │  8. human_review_    │
                    │  (skip 8)    │          │     interrupt        │
                    │              │          │  (interrupt() call)  │
                    └──────┬───────┘          └──────────┬───────────┘
                           │                             │
                           │                     HITL RESOLVED
                           │                             │
                           └──────────────┬──────────────┘
                                          │
                                          ▼
                              ┌─────────────────────────┐
                              │  9. run_law_engine       │
                              │  (Sec 35, Sec 74,       │
                              │   deadline, venue, CoC)  │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │ 10. score_contract       │
                              │  (weighted score,       │
                              │   risk_level, exposure)  │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │ 11. persist_results      │
                              │  (update job aggregates) │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │ 12. create_actions       │
                              │  (draft tickets/emails, │
                              │   skip if critical +    │
                              │   not approved)          │
                              └────────────┬────────────┘
                                           │
                                           ▼
                              ┌─────────────────────────┐
                              │ 13. export_outputs       │
                              │  (generate CSV/XLSX)     │
                              └────────────┬────────────┘
                                           │
                                           ▼
                                    ┌─────────────┐
                                    │ finalize_job │
                                    │              │
                                    │ END          │
                                    └─────────────┘
```

### 5.3 Edge Conditions

| Transition | Condition | Behavior |
|-----------|-----------|----------|
| `validate_extraction` → `human_review_interrupt` | Confidence < threshold OR quote validation failed | Interrupt for human patch |
| `validate_extraction` → skip to `run_law_engine` | Confidence >= threshold AND all quotes valid | Continue automatically |
| `extract_structured_risks` → retry | Invalid JSON or provider exception | Move to next provider in priority list |
| `extract_structured_risks` → `human_review_interrupt` | All providers exhausted | Interrupt with raw provider output |
| `ingest_contract` → skip contract | Duplicate hash and reuse policy allows skip | Log event, update counts, move to next contract |
| `extract_pages` → warning path | OCR quality low | Set `parser_quality_score` low, continue with audit event |
| `route_clauses` → empty result | No clause keywords matched | Extraction returns null fields; informational finding created later |
| `create_actions` → skip | Critical finding without reviewer approval | Store draft, do not send, log deferred action |

### 5.4 State Schema

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

**State design rules (from spec §6.4):**
- Store references (UUIDs), not full document text
- `contract_ids` drives the per-contract loop
- `review_required` + `review_payload_id` controls the HITL interrupt
- `provider_attempts` logs each provider attempt for observability
- `errors` accumulates non-fatal errors; fatal errors halt the contract

---

## 6. Interrupt / Human-in-the-Loop Design

### 6.1 Interrupt Semantics

LangGraph's `interrupt()` function pauses graph execution and persists state to the checkpointer. When resumed, the **entire interrupted node re-runs from the start**, not from the interrupt point. This is a critical constraint (§6.2, §6.3).

### 6.2 Replay-Safe Node Pattern

The `human_review_interrupt` node follows this pattern:

```
human_review_interrupt(state):
  1. LOAD review_payload from DB by state["review_payload_id"]
     (safe: read-only, idempotent)

  2. CHECK if resolution already exists in human_reviews table
     (safe: read-only, idempotent)

  3. IF resolution exists:
       APPLY resolution (patch extraction data)
       RETURN {"review_required": False}
       (safe: idempotent if apply is idempotent)

  4. ELSE:
       CALL interrupt({"type": "HUMAN_REVIEW", "payload": review_payload})
       (safe: no side effects before this point)

       AFTER RESUME:
       Read resolution from interrupt() return value
       STORE resolution in human_reviews.resolution_json
       APPLY resolution patch
       RETURN {"review_required": False}
```

**Safety rules applied:**
- No irreversible side effects before interrupt
- Proposed actions written as drafts first (in `human_reviews.prompt_json`)
- Idempotency keys for later external side effects (in `action_items`)
- Separation of "compute" (read state + build payload) from "commit" (apply resolution)

### 6.3 Trigger Conditions

The workflow enters `human_review_interrupt` when:

1. **Low confidence extraction** — `confidence < 0.78` (from `tenant_settings.confidence_threshold`)
2. **Quote validation failure** — `source_quote` not found in page text after all provider retries
3. **All providers failed** — All 3 provider tiers returned errors or invalid JSON
4. **Critical severity finding** — Optional pre-approval gate (config `allow_auto_ticket_creation`)

### 6.4 Review Payload Structure

```json
{
  "type": "HUMAN_REVIEW",
  "payload": {
    "human_review_id": "uuid",
    "contract_id": "uuid",
    "contract_file_name": "MSA_Acme_Corp.pdf",
    "page_number": 12,
    "field_name": "termination_notice_days",
    "extracted_value": 30,
    "source_quote": "Either party may terminate upon thirty (30) days notice.",
    "page_text_snippet": "...party may terminate upon thirty (30) days prior written notice...",
    "ambiguity_notes": [
      "OCR may have merged 'thirty' and '30' as duplicate"
    ],
    "all_provider_attempts": [
      {"provider": "groq", "model": "llama-3-70b", "success": false, "error": "invalid_json"},
      {"provider": "openrouter", "model": "gemini-2.0-flash:free", "success": true, "confidence": 0.45}
    ]
  }
}
```

### 6.5 Resolution Structure

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
  "review_notes": "OCR merged 30 and 90 incorrectly. Correct value is 90."
}
```

### 6.6 Resume Flow

```
1. User submits POST /human-reviews/{id}/resolve
2. API writes resolution_json to human_reviews row, sets status='resolved'
3. User calls POST /audit-jobs/{id}/resume
4. API /resume triggers LangGraph to resume the interrupted graph
5. LangGraph checkpointer retrieves last checkpoint
6. human_review_interrupt node re-runs from start
7. Node reads resolution from human_reviews (step 2 in pattern above)
8. Since resolution exists, node applies patch and returns
9. Workflow continues to run_law_engine with patched data
```

---

## 7. Provider Routing Architecture

### 7.1 Provider Abstraction Interface

```python
# packages/providers/provider_router.py

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

**No node may call vendor SDKs directly.** All provider calls go through `provider_router.py`.

### 7.2 Router Implementation

```python
class ProviderRouter:
    def __init__(self, providers: dict[str, LLMProvider], policy: RoutingPolicy):
        self.providers = providers
        self.policy = policy

    async def structured_extract(self, request: ExtractionRequest):
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
                # Log successful call to provider_calls table
                return result, candidate
            except Exception as e:
                last_error = e
                # Log failed call to provider_calls table
                continue
        raise RuntimeError(f"all providers failed: {last_error}")
```

### 7.3 Routing Policy (Priority)

| Priority | Provider | When | Models |
|----------|----------|------|--------|
| 1 | Poolside | When configured and available for structured extraction | Poolside Laguna M.1 free tier |
| 2 | Groq | Default for speed and batch throughput | Llama 3 70B, Mixtral 8x7B (free tier) |
| 3 | OpenRouter | Fallback when Groq unavailable | `:free` models (Gemini 2.0 Flash, etc.) |
| 4 | Human review | All providers exhausted | Manual entry via UI |

### 7.4 Anti-Hallucination Enforcement

All provider calls enforce at the adapter level:

| Rule | Enforcement |
|------|-------------|
| Temperature near zero | Set in adapter before API call |
| Strict JSON schema | `response_schema` param enforced by provider SDK or post-hoc Pydantic parse |
| No narrative output | Reject if response is not valid JSON matching schema |
| Out-of-schema fields | Pydantic `extra="forbid"` on schema |
| Numbers reparsed from quote | `validate_extraction` node checks numeric fields against `source_quote` |
| Quote + page required | Schema-level validation: no populated material field without `QuoteRef` |
| Absent clause = null/false | System prompt rule, validated in post-extraction check |
| `source_quote` must be substring of page text | `validate_quote()` function |

### 7.5 Provider Call Logging

Every provider call is logged to `provider_calls` table regardless of success/failure:

```sql
INSERT INTO provider_calls (
  id, audit_job_id, contract_id, provider_name, model_name,
  prompt_hash, response_hash, latency_ms, success, tokens_in, tokens_out, error_code
) VALUES (...);
```

This enables per-provider failure rate dashboards and cost tracking.

---

## 8. Storage Architecture

### 8.1 PostgreSQL

**Purpose:** All persistent domain data.

**Connection (A):** Single connection pool via asyncpg/SQLAlchemy async.

**Connection (B):** Read replicas for queries, writer node for mutations + Citus for sharding.

**Schema summary** (14 tables — see [DATA_MODEL.md](./DATA_MODEL.md) for full detail):

| Table | Purpose | Est. Row Size | Growth |
|-------|---------|---------------|--------|
| `audit_jobs` | Job-level metadata | ~500 B | 1 per audit |
| `contracts` | Per-contract metadata | ~1 KB | 10–100 per job |
| `contract_pages` | Extracted page text | ~10 KB | ~50 pages × contracts |
| `contract_chunks` | Paragraph chunks with routing scores | ~2 KB | ~30 chunks × pages |
| `extractions` | LLM extraction attempts | ~5 KB | ~3 per contract (retries) |
| `extraction_quotes` | Quote-level evidence | ~500 B | ~15 per extraction |
| `legal_findings` | Deterministic rule outputs | ~1 KB | ~10 per contract |
| `risk_scores` | Aggregated risk per contract | ~2 KB | 1 per contract |
| `action_items` | Ticket/email drafts | ~2 KB | ~3 per high-risk contract |
| `human_reviews` | HITL prompts and resolutions | ~5 KB | ~2 per contract |
| `provider_calls` | Provider telemetry | ~500 B | ~6 per contract |
| `exports` | Export metadata | ~500 B | 1–3 per job |
| `audit_events` | Immutable workflow log | ~1 KB | ~30 per job |
| `tenant_settings` | Config and thresholds | ~500 B | 1 row (A); N rows (B) |

### 8.2 Redis

**Purpose (A):** Job queue, result cache, rate-limit counters.

| Use | Data Structure | TTL | Details |
|-----|---------------|-----|---------|
| Job queue | List (`LPUSH` / `BRPOP`) | N/A (persistent until consumed) | Contract IDs pending processing |
| Provider rate limit | String (`INCR` + EXPIRE) | 1 second | Tracks API calls per second per provider |
| In-flight tracking | Set | N/A | Contract IDs currently being processed (crash recovery) |
| Result cache | String | 1 hour | Cached extraction results for duplicate contracts |

**Architecture B upgrade:** Replace List with Redis Streams or SQS for durable messaging with visibility timeout, dead-letter queue, and consumer groups.

### 8.3 File Storage

**Architecture A:**
- **Path:** `STORAGE_PATH` env var (default: `./data/storage/`)
- **Structure:**
  ```
  data/storage/
    uploads/
      {audit_job_id}/
        {contract_id}_{file_hash}.pdf
    exports/
      {audit_job_id}/
        risk_register_{export_id}.csv
        risk_register_{export_id}.xlsx
    temp/
      {session_id}/  (cleaned after processing)
  ```
- **Encryption:** AES-256-GCM at rest if `ENCRYPT_STORAGE=true` (env config)
- **Sanitization:** Filenames sanitized on upload (strip path traversal, replace special chars)

**Architecture B:**
- Object storage (MinIO / S3) with same path structure
- Server-side encryption (SSE-S3 or SSE-KMS)
- Presigned URLs for export download
- Lifecycle policies for temp data

---

## 9. Security Architecture

### 9.1 Architecture A Security

| Layer | Control | Implementation |
|-------|---------|---------------|
| API | API Key auth | `X-API-Key` header compared to `API_KEY` env var (constant-time compare) |
| API | Request validation | Pydantic models on all input endpoints |
| API | Rate limiting | Redis-based per-IP rate limiter (100 req/min default) |
| Upload | Filename sanitization | Strip directory separators, replace non-alphanumeric chars, limit length |
| Upload | AV scan | Optional (`CLAMAV_ENABLED` env), skip in A by default |
| Storage | Encryption | AES-256-GCM on stored files when `ENCRYPT_STORAGE=true` |
| Storage | Least-privilege | Worker and API use separate DB roles (API: read-write on most tables; worker: full) |
| Secrets | Management | All credentials via environment variables, never in code |
| DB | Connection encryption | PostgreSQL SSL/TLS enforced |
| Network | Internal | Docker compose network — only API port exposed to host |
| Audit | Immutability | `audit_events` table: insert-only for normal workflows (no UPDATE/DELETE by app users) |
| PII | Redaction | Prompt construction redacts unnecessary PII (names not relevant to clause) |

### 9.2 Authentication Design (A)

```
Request ──▶ FastAPI middleware
              │
              ▼
         Extract X-API-Key header
              │
              ▼
         Constant-time compare with API_KEY env
              │
         ┌────┴────┐
         │ Match   │  No match
         └────┬────┘     │
              │          ▼
         Continue    401 Unauthorized
                      { "error": "unauthorized", "message": "Invalid API key" }
```

**API Key format:** UUID v4 (generated once, stored in `.env`).

### 9.3 Architecture B Security Upgrades

| Control | A | B |
|---------|---|----|
| Auth | Static API key | OAuth2 + JWT + RBAC |
| User isolation | N/A (single user) | Row-level security (RLS) on all tables |
| Encryption at rest | Optional env toggle | Mandatory SSE-KMS |
| Audit | App-level event log | Immutable audit + database audit logs |
| Network | Single compose network | VPC + private subnets + API gateway |
| Secrets | `.env` file | Vault / AWS Secrets Manager |
| File scanning | Optional | Mandatory (ClamAV or commercial AV) |

### 9.4 Secrets Model

```yaml
# .env (local) / secrets manager (B)
API_KEY=uuid-v4
DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/contractlens
REDIS_URL=redis://redis:6379/0
ENCRYPTION_KEY=base64-256-bit-key  # for file storage encryption

OPENROUTER_API_KEY=sk-or-...
GROQ_API_KEY=gsk_...
POOLSIDE_API_KEY=ps_...

LINEAR_API_KEY=lin_...
SENDGRID_API_KEY=SG....
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
```

---

## 10. Multi-Tenant Upgrade Path (A → B)

### 10.1 Upgrade Dimensions

| Dimension | A (Local-First) | B (Multi-Tenant) | Migration Strategy |
|-----------|-----------------|------------------|-------------------|
| **Deployment** | Docker Compose, single host | Kubernetes, auto-scaling | Kustomize or Helm charts; container images unchanged |
| **API** | FastAPI monolith | FastAPI + Go auth gateway | Extract auth middleware into gateway; keep FastAPI for business routes |
| **Worker** | Single Python process | Worker pool (OCR, extraction, action, export) | Split `apps/worker/` into separate entrypoints with shared `packages/` |
| **Queue** | Redis List | Redis Streams / SQS | Adapter pattern: `QueueInterface` with `RedisListQueue` and `SQSQueue` implementations |
| **File Storage** | Local encrypted FS | S3/MinIO | Adapter pattern: `StorageInterface` with `LocalStorage` and `S3Storage` |
| **Tenancy** | Single row in `tenant_settings` | `tenant_id` column on every table + RLS | Add `tenant_id` UUID NOT NULL to all entity tables; backfill for existing data with single tenant ID |
| **Auth** | Static API key | OAuth2 / JWT with RBAC | Replace middleware; map API key to tenant in B |
| **Provider Budgets** | N/A | Per-tenant monthly caps | Add `tenant_provider_budgets` table; check in `ProviderRouter` |
| **Semantic Routing** | Disabled (`allow_semantic_routing: false`) | Enabled with Qdrant | Config toggle; add Qdrant container; embed chunks at chunk time |
| **OCR Pool** | Inline in worker | Separate OCR pool with GPU | Extract OCR to standalone service; queue OCR jobs separately |

### 10.2 Code-Level Migration Strategy

**Phase B1 steps (from spec §26 Phase B1):**

1. **Add tenancy model:**
   - Add `tenant_id` column to `audit_jobs`, `contracts`, all child tables
   - Create `tenants` table with billing/plan info
   - Add RLS policies for PostgreSQL Row-Level Security
   - Seed default tenant for existing single-tenant data

2. **Object storage adapter:**
   ```python
   # packages/domain/storage.py
   class StorageBackend(Protocol):
       async def store(self, path: str, content: bytes) -> str: ...
       async def retrieve(self, uri: str) -> bytes: ...
       async def delete(self, uri: str) -> None: ...

   class LocalEncryptedFS(StorageBackend): ...
   class S3Storage(StorageBackend): ...
   ```

3. **Durable queue abstraction:**
   ```python
   # packages/domain/queue.py
   class QueueBackend(Protocol):
       async def enqueue(self, queue: str, payload: dict) -> None: ...
       async def dequeue(self, queue: str, timeout_s: int) -> dict | None: ...
       async def acknowledge(self, queue: str, receipt: str) -> None: ...
       async def requeue_dead_letter(self, queue: str, payload: dict) -> None: ...

   class RedisListQueue(QueueBackend): ...    # A
   class RedisStreamQueue(QueueBackend): ...  # B
   class SQSQueue(QueueBackend): ...          # B
   ```

4. **Worker pool split:**
   ```
   apps/worker/
     main.py              # Entrypoint: reads QUEUE_NAME env, starts appropriate loop
     ocr_worker.py        # B only: processes PDF→text
     extraction_worker.py # B only: runs LangGraph extraction subgraph
     action_worker.py     # B only: executes approved actions
     export_worker.py     # B only: generates export files
   ```

### 10.3 Database Migration Path

No breaking schema changes. All B migrations add nullable columns or new tables:

```
Migration A1:   (14 tables as defined in spec §7.2)
Migration B1a:  CREATE TABLE tenants (...);  ALTER TABLE audit_jobs ADD tenant_id UUID REFERENCES tenants;  ...
Migration B1b:  CREATE TABLE tenant_provider_budgets (...)
Migration B1c:  CREATE INDEX idx_*_tenant_id ON * (tenant_id);
```

### 10.4 Configuration Migration

```
# A: single tenant_settings row
tenant_settings:
  client_hub_city: Bengaluru
  closing_date: 2026-09-15
  ...

# B: settings per tenant, stored in tenant_configs table or config service
tenant_configs:
  tenant_abc123:
    client_hub_city: Bengaluru
    closing_date: 2026-09-15
    monthly_provider_budget_usd: 50.00
    ...
  tenant_def456:
    client_hub_city: Mumbai
    closing_date: 2026-12-01
    monthly_provider_budget_usd: 200.00
    ...
```

---

## 11. Observability

### 11.1 Langfuse Tracing

Every LLM provider call is traced via Langfuse:

| Trace Event | Data |
|-------------|------|
| `provider.extract` | Model name, prompt hash, response hash, latency, token counts, success/failure |
| `node.*` | Node name, contract_id, audit_job_id, duration |
| `workflow.audit_job` | Job-level span encompassing all contracts |

### 11.2 Provider Call Table

The `provider_calls` table provides self-hosted observability independent of Langfuse:

```sql
-- Per-provider failure rate
SELECT provider_name,
       COUNT(*) FILTER(WHERE success = false) AS failures,
       COUNT(*) AS total,
       ROUND(100.0 * COUNT(*) FILTER(WHERE success = false) / COUNT(*), 1) AS fail_pct
FROM provider_calls
WHERE audit_job_id = :job_id
GROUP BY provider_name;
```

### 11.3 Audit Events

Every meaningful workflow transition emits an `audit_events` row:

```sql
INSERT INTO audit_events (audit_job_id, contract_id, event_type, event_json)
VALUES (
  :job_id,
  :contract_id,
  'extraction_completed',
  '{"extraction_id": "...", "confidence": 0.92, "provider": "groq", "model": "llama-3-70b"}'
);
```

**Event types:**
`job_created`, `contract_ingested`, `pages_extracted`, `chunks_created`, `clauses_routed`, `extraction_attempted`, `extraction_completed`, `extraction_failed`, `validation_passed`, `validation_failed`, `human_review_created`, `human_review_resolved`, `law_engine_run`, `risk_scored`, `action_drafted`, `action_sent`, `export_generated`, `job_completed`, `job_failed`, `provider_fallback`, `ocr_fallback`, `duplicate_skipped`.

### 11.4 Key Metrics (Dashboard)

| Metric | Source | Purpose |
|--------|--------|---------|
| Contracts processed / sec | `audit_events` + timing | Throughput monitoring |
| Provider failure rate | `provider_calls` | Provider health |
| Human review rate | `human_reviews` | Extraction quality |
| Invalid JSON rate | `provider_calls` + `audit_events` | Model quality |
| Avg confidence score | `extractions` | Extraction quality |
| P50/P95 latency per node | Langfuse + logs | Performance optimization |
| Active jobs | `audit_jobs` | Queue depth |
| Export generation lag | `exports` + logs | Export throughput |

---

> **End of ARCHITECTURE.md**  
> This document is derived from ContractLens Master Blueprint. Any deviation from the spec is a bug.
