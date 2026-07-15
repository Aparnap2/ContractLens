# ContractLens Data Model

> **Document status:** Final  
> **Engine:** PostgreSQL 15+  
> **Migration tool:** Alembic  
> **Source of truth:** ContractLens Master Blueprint §7

---

## Table of Contents

1. [Entity Relationship Summary](#1-entity-relationship-summary)
2. [Table Definitions](#2-table-definitions)
3. [Relationship Cardinalities](#3-relationship-cardinalities)
4. [Indexing Strategy](#4-indexing-strategy)
5. [Migration Ordering](#5-migration-ordering)
6. [Migration Ordering Diagram](#6-migration-ordering-diagram)
7. [Design Decisions](#7-design-decisions)

---

## 1. Entity Relationship Summary

The ContractLens data model consists of **14 tables** organized into 5 logical groups:

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TENANCY GROUP                                 │
│  ┌────────────────┐                                                   │
│  │ tenant_settings │  (1 row in A; N rows in B)                      │
│  └────────────────┘                                                   │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                        AUDIT GROUP                                    │
│  ┌────────────┐       ┌──────────────┐       ┌──────────────┐        │
│  │ audit_jobs │──1:N──│  contracts   │──1:N──│ audit_events │        │
│  └────────────┘       └──────────────┘       └──────────────┘        │
│                              │                                        │
└──────────────────────────────┼────────────────────────────────────────┘
                               │
          ┌────────────────────┼───────────────────────────┐
          │                    │                           │
          ▼                    ▼                           ▼
┌─────────────────┐  ┌──────────────────┐  ┌───────────────────┐
│  CONTRACT DATA  │  │  EXTRACTION      │  │  RISK & ACTION    │
│  GROUP          │  │  GROUP           │  │  GROUP            │
│                 │  │                  │  │                   │
│ contract_pages  │  │ extractions      │  │ legal_findings    │
│   (1:N)         │  │   (1:N)          │  │   (1:N)           │
│ contract_chunks │  │ extraction_quotes│  │ risk_scores       │
│   (1:N)         │  │   (1:1 extract)  │  │   (1:1)           │
│                 │  │ provider_calls   │  │ action_items      │
│                 │  │   (N:1 contract) │  │   (1:N)           │
│                 │  │ human_reviews    │  │                   │
│                 │  │   (N:1 contract) │  └───────────────────┘
└─────────────────┘  └──────────────────┘
```

### Entity Counts per Audit Job (Typical)

| Entity | Per Job (100 contracts) |
|--------|------------------------|
| `audit_jobs` | 1 |
| `contracts` | 100 |
| `contract_pages` | 5,000 (50 pages × 100 contracts) |
| `contract_chunks` | 150,000 (30 chunks × 50 pages × 100 contracts) |
| `extractions` | 300 (3 attempts × 100 contracts) |
| `extraction_quotes` | 4,500 (15 quotes × 300 extractions) |
| `legal_findings` | 1,000 (10 findings × 100 contracts) |
| `risk_scores` | 100 |
| `action_items` | 150 (1.5 per high-risk contract) |
| `human_reviews` | 200 (2 per low-confidence contract) |
| `provider_calls` | 600 (6 per contract avg) |
| `exports` | 2 |
| `audit_events` | 3,000 (30 events per contract) |
| `tenant_settings` | 1 |

---

## 2. Table Definitions

### 2.1 `audit_jobs`

Job-level metadata. One row per audit execution.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique job identifier |
| `status` | TEXT | NOT NULL, CHECK(status IN ('pending','processing','review','completed','failed')) | Current job status |
| `created_by` | TEXT | NOT NULL | User identifier (static "analyst" in A) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Job creation timestamp |
| `completed_at` | TIMESTAMPTZ | nullable | Job completion/failure timestamp |
| `closing_date` | DATE | nullable | Acquisition closing date for deadline breach checks |
| `client_hub_city` | TEXT | nullable | Client's operational hub city for venue analysis |
| `total_contracts` | INT | NOT NULL, DEFAULT 0 | Number of contracts in the zip |
| `processed_contracts` | INT | NOT NULL, DEFAULT 0 | Number of contracts fully processed |
| `aggregate_exposure_inr` | NUMERIC(18,2) | NOT NULL, DEFAULT 0 | Sum of all financial exposures across contracts |
| `summary_json` | JSONB | NOT NULL, DEFAULT '{}' | Job summary with risk counts, top findings, provider stats |

**Status machine:** `pending → processing → review ⇄ processing → completed | failed`

### 2.2 `contracts`

Per-contract metadata and processing status.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique contract identifier |
| `audit_job_id` | UUID | NOT NULL, FK → audit_jobs(id) | Parent audit job |
| `file_name` | TEXT | NOT NULL | Original filename (sanitized) |
| `file_hash` | TEXT | NOT NULL | SHA-256 hash of file content for dedup |
| `storage_uri` | TEXT | NOT NULL | Path or URI to stored file |
| `mime_type` | TEXT | NOT NULL | MIME type (always `application/pdf`) |
| `parser_used` | TEXT | nullable | PDF parser (`pymupdf`, `ocr`) |
| `parser_quality_score` | NUMERIC(5,2) | nullable | 0.00–1.00 quality score from parser |
| `contract_type` | TEXT | nullable | Classified type (`LEASE`, `MSA`, `NDA`, `EMPLOYMENT`, `SAAS`, `OTHER`) |
| `vendor_name` | TEXT | nullable | Extracted vendor/counterparty name |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' | Processing status |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation timestamp |

**Unique constraint:** `(audit_job_id, file_hash)` — prevents duplicate uploads within a job.

**Status values:** `pending`, `queued`, `ingested`, `processing`, `extracted`, `review`, `completed`, `failed`.

### 2.3 `contract_pages`

Extracted text per page, with OCR metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique page identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id) | Parent contract |
| `page_number` | INT | NOT NULL | 1-indexed page number |
| `extracted_text` | TEXT | NOT NULL | Full text extracted from this page |
| `ocr_used` | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether OCR was used |
| `text_hash` | TEXT | NOT NULL | SHA-256 of extracted text (for change detection) |

**Unique constraint:** `(contract_id, page_number)` — one row per page per contract.

### 2.4 `contract_chunks`

Paragraph-level chunks with clause routing scores.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique chunk identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id) | Parent contract |
| `page_number` | INT | NOT NULL | Source page number |
| `chunk_index` | INT | NOT NULL | Sequential chunk position on page |
| `clause_family` | TEXT | nullable | Assigned clause family from routing |
| `chunk_text` | TEXT | NOT NULL | Text content of this chunk |
| `chunk_hash` | TEXT | NOT NULL | SHA-256 of chunk_text |
| `router_score` | NUMERIC(5,2) | nullable | Relevance score from router (0.00–1.00) |
| `selected` | BOOLEAN | NOT NULL, DEFAULT FALSE | Whether this chunk was selected for LLM extraction |

**Unique constraint:** `(contract_id, page_number, chunk_index)`.

**Purpose:** Chunks are the unit of routing. Only chunks with `selected=true` are sent to the LLM provider.

### 2.5 `extractions`

LLM extraction attempts with provider metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique extraction identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id) | Parent contract |
| `schema_version` | TEXT | NOT NULL | Version of extraction schema used |
| `provider_name` | TEXT | NOT NULL | Provider that performed extraction |
| `model_name` | TEXT | NOT NULL | Model that performed extraction |
| `attempt_no` | INT | NOT NULL | Attempt number (1-based) |
| `confidence` | NUMERIC(5,2) | nullable | Extraction confidence score (0.00–1.00) |
| `structured_json` | JSONB | NOT NULL | Full extraction output as JSON |
| `status` | TEXT | NOT NULL, DEFAULT 'completed' | Status (`completed`, `failed`, `low_confidence`) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation timestamp |

**Index:** `(contract_id, attempt_no)` for retry tracking.

### 2.6 `extraction_quotes`

Page-level evidence backing extraction fields.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique quote identifier |
| `extraction_id` | UUID | NOT NULL, FK → extractions(id) | Parent extraction |
| `field_name` | TEXT | NOT NULL | Extraction field this quote supports |
| `source_quote` | TEXT | NOT NULL | Exact text from the page |
| `page_number` | INT | NOT NULL | Source page number |
| `start_char` | INT | nullable | Start character offset in page text |
| `end_char` | INT | nullable | End character offset in page text |

**Purpose:** Enables quote fidelity validation — every material extraction field must have a corresponding quote row, and `source_quote` must be a substring of the page's `extracted_text`.

### 2.7 `legal_findings`

Outputs from the deterministic law engine and LLM-based analysis.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique finding identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id) | Parent contract |
| `finding_code` | TEXT | NOT NULL | Identifier: `CHANGE_OF_CONTROL_PENALTY`, `INSUFFICIENT_STAMP`, `DEADLINE_BREACH`, `AUTO_RENEWAL_ESCALATION`, `HIGH_LIQUIDATED_DAMAGES`, `DISTANT_VENUE`, `UNCAP_PENALTY`, `VENUE_MISMATCH`, `TERMINATION_NOTICE`, `LOCK_IN_PERIOD`, `INDEMNITY_ASYMMETRY`, `INFO_NO_CLAUSES` |
| `severity` | TEXT | NOT NULL, CHECK(severity IN ('info','low','medium','high','critical')) | Risk severity |
| `title` | TEXT | NOT NULL | Human-readable short title |
| `description` | TEXT | NOT NULL | Detailed finding description |
| `statute_reference` | TEXT | nullable | Statute citation (e.g., "Indian Contract Act, 1872 — Section 74") |
| `financial_impact_inr` | NUMERIC(18,2) | nullable | Quantitative financial exposure |
| `deterministic` | BOOLEAN | NOT NULL, DEFAULT TRUE | Whether finding is from deterministic rule (true) or LLM-derived (false) |
| `evidence_json` | JSONB | NOT NULL, DEFAULT '{}' | Supporting evidence with quotes, page numbers, and computed values |

**Finding codes** are the canonical enumeration. No finding is created without a code from the above list.

### 2.8 `risk_scores`

Aggregated risk score per contract.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique risk score identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id), UNIQUE | One score per contract |
| `total_score` | NUMERIC(6,2) | NOT NULL | 0.00–100.00 weighted score |
| `level` | TEXT | NOT NULL, CHECK(level IN ('info','low','medium','high','critical')) | Classified risk level |
| `exposure_inr` | NUMERIC(18,2) | NOT NULL, DEFAULT 0 | Total financial exposure for this contract |
| `scoring_breakdown` | JSONB | NOT NULL | Per-rule breakdown of score components |

**Score formula** (from Master Blueprint §10.7):

```
score =
   30 * insufficient_stamp_flag +
   25 * deadline_breach_flag +
   20 * change_of_control_flag +
   15 * high_ld_flag +
   10 * auto_renew_escalation_flag +
    5 * distant_venue_flag +
    5 * uncapped_consequential_flag

risk_level:
   0-9    INFO
   10-29  LOW
   30-49  MEDIUM
   50-69  HIGH
   70+    CRITICAL
```

**All weights must be config-driven** (stored in `tenant_settings` or config file), not hardcoded.

### 2.9 `action_items`

Deferred external actions (tickets, emails) with idempotency keys.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique action identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id) | Parent contract |
| `action_type` | TEXT | NOT NULL | `linear_ticket`, `jira_ticket`, `negotiation_email` |
| `external_system` | TEXT | nullable | System name (`linear`, `jira`, `sendgrid`) |
| `idempotency_key` | TEXT | NOT NULL, UNIQUE | Prevents duplicate external creation |
| `payload_json` | JSONB | NOT NULL | Full payload for external system |
| `status` | TEXT | NOT NULL, DEFAULT 'draft' | `draft`, `pending_approval`, `approved`, `sent`, `failed` |
| `external_ref` | TEXT | nullable | External system reference (ticket ID, email ID) |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation timestamp |

**Architecture A behavior:** All critical-severity action items remain in `draft` status. No external creation occurs without prior human approval.

**Idempotency key format:** `{action_type}/{contract_id}/{finding_code}/{timestamp_ms}`

### 2.10 `human_reviews`

Human-in-the-loop review prompts and resolutions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique review identifier |
| `contract_id` | UUID | NOT NULL, FK → contracts(id) | Parent contract |
| `review_type` | TEXT | NOT NULL | `low_confidence`, `validation_failure`, `provider_exhausted` |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' | `pending`, `resolved` |
| `prompt_json` | JSONB | NOT NULL | The review payload (contract context, extracted value, ambiguity notes) |
| `resolution_json` | JSONB | nullable | The resolution submitted by the reviewer |
| `reviewer_id` | TEXT | nullable | Who resolved it |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation timestamp |
| `resolved_at` | TIMESTAMPTZ | nullable | Resolution timestamp |

### 2.11 `provider_calls`

Telemetry for every LLM provider invocation.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique call identifier |
| `audit_job_id` | UUID | NOT NULL, FK → audit_jobs(id) | Parent audit job |
| `contract_id` | UUID | nullable, FK → contracts(id) | Related contract (nullable for job-level calls) |
| `provider_name` | TEXT | NOT NULL | `openrouter`, `groq`, `poolside` |
| `model_name` | TEXT | NOT NULL | Model identifier |
| `prompt_hash` | TEXT | NOT NULL | SHA-256 of the full prompt sent |
| `response_hash` | TEXT | nullable | SHA-256 of the response received |
| `latency_ms` | INT | nullable | Total round-trip time |
| `success` | BOOLEAN | NOT NULL | Whether the call returned a usable response |
| `tokens_in` | INT | nullable | Input token count |
| `tokens_out` | INT | nullable | Output token count |
| `error_code` | TEXT | nullable | Error code on failure |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation timestamp |

### 2.12 `exports`

Generated export package metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique export identifier |
| `audit_job_id` | UUID | NOT NULL, FK → audit_jobs(id) | Parent audit job |
| `format` | TEXT | NOT NULL | `csv` or `xlsx` |
| `storage_uri` | TEXT | NOT NULL | Path or object storage URI |
| `file_size_bytes` | BIGINT | nullable | File size |
| `status` | TEXT | NOT NULL, DEFAULT 'pending' | `pending`, `generating`, `ready`, `failed` |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Request timestamp |
| `completed_at` | TIMESTAMPTZ | nullable | Generation completion timestamp |

### 2.13 `audit_events`

Immutable workflow audit trail.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique event identifier |
| `audit_job_id` | UUID | NOT NULL, FK → audit_jobs(id) | Parent audit job |
| `contract_id` | UUID | nullable, FK → contracts(id) | Related contract (nullable for job-level events) |
| `event_type` | TEXT | NOT NULL | See event type enumeration below |
| `event_json` | JSONB | NOT NULL | Event payload with context |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Event timestamp |

**Event type enumeration:** `job_created`, `contract_ingested`, `pages_extracted`, `chunks_created`, `clauses_routed`, `extraction_attempted`, `extraction_completed`, `extraction_failed`, `validation_passed`, `validation_failed`, `human_review_created`, `human_review_resolved`, `law_engine_run`, `risk_scored`, `action_drafted`, `action_sent`, `export_generated`, `job_completed`, `job_failed`, `provider_fallback`, `ocr_fallback`, `duplicate_skipped`.

**Immutability:** Application code only INSERTs into this table. No UPDATE or DELETE by normal app flows.

### 2.14 `tenant_settings`

Configuration and threshold storage. Single row in Architecture A; one row per tenant in B.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PK, DEFAULT gen_random_uuid() | Unique config identifier |
| `client_hub_city` | TEXT | NOT NULL, DEFAULT 'Bengaluru' | Default client hub city |
| `closing_date` | DATE | nullable | Default closing date |
| `ld_high_threshold_inr` | NUMERIC(18,2) | NOT NULL, DEFAULT 5000000 | Liquidated damages threshold |
| `renewal_escalation_threshold_pct` | NUMERIC(5,2) | NOT NULL, DEFAULT 15 | Escalation % threshold |
| `confidence_threshold` | NUMERIC(5,2) | NOT NULL, DEFAULT 0.78 | Minimum confidence for auto-commit |
| `max_provider_retries` | INT | NOT NULL, DEFAULT 3 | Max retries across providers |
| `allow_semantic_routing` | BOOLEAN | NOT NULL, DEFAULT FALSE | Enable Qdrant routing |
| `allow_auto_ticket_creation` | BOOLEAN | NOT NULL, DEFAULT TRUE | Auto-create tickets from findings |
| `allow_auto_email_drafts` | BOOLEAN | NOT NULL, DEFAULT TRUE | Auto-draft negotiation emails |
| `stamp_rule_source` | TEXT | NOT NULL, DEFAULT 'seed_table_v1' | Version of stamp duty rules |
| `created_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Row creation timestamp |
| `updated_at` | TIMESTAMPTZ | NOT NULL, DEFAULT now() | Last update timestamp |

**B upgrade:** Add `tenant_id` column, and migrate to a `tenants` table with `tenant_configs` as a child.

---

## 3. Relationship Cardinalities

```
audit_jobs  ──1:N──▶  contracts
audit_jobs  ──1:N──▶  audit_events
audit_jobs  ──1:N──▶  provider_calls
audit_jobs  ──1:N──▶  exports

contracts   ──1:N──▶  contract_pages
contracts   ──1:N──▶  contract_chunks
contracts   ──1:N──▶  extractions
contracts   ──1:N──▶  legal_findings
contracts   ──1:1──▶  risk_scores          (UNIQUE constraint on contract_id)
contracts   ──1:N──▶  action_items
contracts   ──1:N──▶  human_reviews
contracts   ──1:N──▶  audit_events          (nullable FK)

extractions ──1:N──▶  extraction_quotes

provider_calls ──N:1▶ contracts             (nullable FK)
provider_calls ──N:1▶ audit_jobs            (non-nullable FK)

human_reviews ──N:1▶ contracts

audit_events ──N:1▶  audit_jobs             (non-nullable FK)
audit_events ──N:1▶  contracts              (nullable FK)

tenant_settings     (standalone; single row in A)
```

### Cardinality Diagram (Text)

```
audit_jobs
    │
    ├──1:N── contracts
    │          ├──1:N── contract_pages
    │          ├──1:N── contract_chunks
    │          ├──1:N── extractions
    │          │          └──1:N── extraction_quotes
    │          ├──1:N── legal_findings
    │          ├──1:1── risk_scores
    │          ├──1:N── action_items
    │          ├──1:N── human_reviews
    │          └──1:N── audit_events (nullable)
    │
    ├──1:N── audit_events
    ├──1:N── provider_calls (nullable contract)
    └──1:N── exports
```

---

## 4. Indexing Strategy

### 4.1 Primary Keys

All 14 tables use UUID primary keys with `DEFAULT gen_random_uuid()`. Clustered by PK (default PostgreSQL behavior).

### 4.2 Foreign Key Indexes

Required for all FK columns to avoid sequential scans on joins:

| Index Name | Table | Column(s) | Type | Rationale |
|-----------|-------|-----------|------|-----------|
| `idx_contracts_audit_job_id` | `contracts` | `audit_job_id` | B-tree | Lookup all contracts in a job |
| `idx_contract_pages_contract_id` | `contract_pages` | `contract_id` | B-tree | Lookup all pages for a contract |
| `idx_contract_chunks_contract_id` | `contract_chunks` | `contract_id` | B-tree | Lookup all chunks for a contract |
| `idx_extractions_contract_id` | `extractions` | `contract_id` | B-tree | Lookup all extraction attempts for a contract |
| `idx_extraction_quotes_extraction_id` | `extraction_quotes` | `extraction_id` | B-tree | Lookup all quotes for an extraction |
| `idx_legal_findings_contract_id` | `legal_findings` | `contract_id` | B-tree | Lookup all findings for a contract |
| `idx_risk_scores_contract_id` | `risk_scores` | `contract_id` | UNIQUE B-tree | One score per contract |
| `idx_action_items_contract_id` | `action_items` | `contract_id` | B-tree | Lookup all actions for a contract |
| `idx_human_reviews_contract_id` | `human_reviews` | `contract_id` | B-tree | Lookup pending reviews for a contract |
| `idx_provider_calls_audit_job_id` | `provider_calls` | `audit_job_id` | B-tree | Lookup all provider calls for a job |
| `idx_provider_calls_contract_id` | `provider_calls` | `contract_id` | B-tree | Lookup provider calls for a contract |
| `idx_audit_events_audit_job_id` | `audit_events` | `audit_job_id` | B-tree | Lookup all events for a job |
| `idx_exports_audit_job_id` | `exports` | `audit_job_id` | B-tree | Lookup exports for a job |
| `idx_contract_chunks_selected` | `contract_chunks` | `selected` | Partial B-tree | `WHERE selected = true` — filter routed chunks |

### 4.3 Unique Constraints

| Constraint Name | Table | Column(s) | Purpose |
|----------------|-------|-----------|---------|
| `uq_contract_filehash_per_job` | `contracts` | `(audit_job_id, file_hash)` | Prevent duplicate file uploads within a job |
| `uq_contract_page` | `contract_pages` | `(contract_id, page_number)` | One row per page |
| `uq_contract_chunk` | `contract_chunks` | `(contract_id, page_number, chunk_index)` | Unique chunk position |
| `uq_risk_score_contract` | `risk_scores` | `contract_id` | One risk score per contract |
| `uq_action_idempotency` | `action_items` | `idempotency_key` | Prevent duplicate external actions |

### 4.4 Query Pattern Indexes

Optimized for the most common query patterns:

| Pattern | Query | Index Used |
|---------|-------|-----------|
| Job status polling | `SELECT * FROM audit_jobs WHERE id = :id` | PK lookup |
| Contracts by job | `SELECT * FROM contracts WHERE audit_job_id = :job_id` | `idx_contracts_audit_job_id` |
| Contracts filtered by status | `SELECT * FROM contracts WHERE audit_job_id = :job_id AND status = :status` | Composite: `idx_contracts_audit_job_id` + `status` |
| Pending reviews count | `SELECT count(*) FROM human_reviews WHERE contract_id IN (:ids) AND status = 'pending'` | `idx_human_reviews_contract_id` |
| Findings for contract | `SELECT * FROM legal_findings WHERE contract_id = :id ORDER BY severity DESC` | `idx_legal_findings_contract_id` |
| Selected chunks for extraction | `SELECT * FROM contract_chunks WHERE contract_id = :id AND selected = true` | `idx_contract_chunks_selected` partial index |
| Provider stats for job | `SELECT provider_name, success, count(*) FROM provider_calls WHERE audit_job_id = :job_id GROUP BY provider_name, success` | `idx_provider_calls_audit_job_id` |
| Active extraction attempts | `SELECT * FROM extractions WHERE contract_id = :id ORDER BY attempt_no DESC` | `idx_extractions_contract_id` |
| Action items by status | `SELECT * FROM action_items WHERE contract_id = :id AND status = :status` | `idx_action_items_contract_id` |
| Find chunks by clause family (B semantic routing) | `SELECT * FROM contract_chunks WHERE contract_id = :id AND clause_family = :family AND selected = true` | Consider adding: `idx_chunks_clause_family` |

### 4.5 Additional Recommended Indexes

| Index | Table | Columns | Rationale |
|-------|-------|---------|-----------|
| `idx_audit_jobs_status` | `audit_jobs` | `status` | Filter active/review/completed jobs — low cardinality but useful for dashboards |
| `idx_legal_findings_severity` | `legal_findings` | `(contract_id, severity)` | Order findings by severity for display |
| `idx_contracts_status` | `contracts` | `(audit_job_id, status)` | Filter contracts by status within a job |

### 4.6 Full-Text Search (Optional, B)

If free-text search across findings is needed in B:

```sql
ALTER TABLE legal_findings ADD COLUMN search_vector tsvector
  GENERATED ALWAYS AS (to_tsvector('english', title || ' ' || description)) STORED;

CREATE INDEX idx_findings_search ON legal_findings USING GIN (search_vector);
```

---

## 5. Migration Ordering

### 5.1 Dependency Graph

Migrations must respect FK dependencies — referenced tables must exist before referencing tables.

```
Layer 0 (no dependencies):
  tenant_settings

Layer 1 (depends on nothing):
  audit_jobs

Layer 2 (depends on audit_jobs):
  contracts

Layer 3 (depends on contracts):
  contract_pages
  contract_chunks
  extractions
  legal_findings
  risk_scores
  action_items
  human_reviews

Layer 4 (depends on extractions):
  extraction_quotes

Layer 5 (depends on audit_jobs + optionally contracts):
  provider_calls   (FK to audit_jobs required, FK to contracts nullable)
  audit_events     (FK to audit_jobs required, FK to contracts nullable)
  exports          (FK to audit_jobs)
```

### 5.2 Ordered Migration List

Execute in this exact order:

| # | Migration | Table(s) | Dependencies | Rollback |
|---|-----------|----------|-------------|----------|
| 001 | Create `tenant_settings` | `tenant_settings` | None | DROP TABLE |
| 002 | Create `audit_jobs` | `audit_jobs` | None | DROP TABLE |
| 003 | Create `contracts` | `contracts` | 002 | DROP TABLE (CASCADE) |
| 004 | Create `contract_pages` | `contract_pages` | 003 | DROP TABLE |
| 005 | Create `contract_chunks` | `contract_chunks` | 003 | DROP TABLE |
| 006 | Create `extractions` | `extractions` | 003 | DROP TABLE |
| 007 | Create `extraction_quotes` | `extraction_quotes` | 006 | DROP TABLE |
| 008 | Create `legal_findings` | `legal_findings` | 003 | DROP TABLE |
| 009 | Create `risk_scores` | `risk_scores` | 003 | DROP TABLE |
| 010 | Create `action_items` | `action_items` | 003 | DROP TABLE |
| 011 | Create `human_reviews` | `human_reviews` | 003 | DROP TABLE |
| 012 | Create `provider_calls` | `provider_calls` | 002, 003 | DROP TABLE |
| 013 | Create `audit_events` | `audit_events` | 002, 003 | DROP TABLE |
| 014 | Create `exports` | `exports` | 002 | DROP TABLE |
| 015 | Create indexes | All tables | 001–014 | DROP INDEX (per index) |
| 016 | Insert seed `tenant_settings` | `tenant_settings` | 001 | DELETE |

### 5.3 Seed Data

Migration 016 inserts the default `tenant_settings` row:

```sql
INSERT INTO tenant_settings (
  id,
  client_hub_city,
  closing_date,
  ld_high_threshold_inr,
  renewal_escalation_threshold_pct,
  confidence_threshold,
  max_provider_retries,
  allow_semantic_routing,
  allow_auto_ticket_creation,
  allow_auto_email_drafts,
  stamp_rule_source
) VALUES (
  gen_random_uuid(),
  'Bengaluru',
  NULL,
  5000000.00,
  15.00,
  0.78,
  3,
  FALSE,
  TRUE,
  TRUE,
  'seed_table_v1'
);
```

### 5.4 Architecture B Migration Additions

After Architecture A migrations are deployed, B adds:

| # | Migration | Change |
|---|-----------|--------|
| 017 | Create `tenants` table | New table for multi-tenant identity |
| 018 | Add `tenant_id` to `audit_jobs` | `ALTER TABLE audit_jobs ADD COLUMN tenant_id UUID REFERENCES tenants(id)` |
| 019 | Add `tenant_id` to all child tables | `ALTER TABLE contracts ADD COLUMN tenant_id UUID` |
| 020 | Backfill `tenant_id` for existing data | Single default tenant ID |
| 021 | Set `tenant_id` NOT NULL on all tables | Required after backfill |
| 022 | Add RLS policies | `ALTER TABLE ... ENABLE ROW LEVEL SECURITY` + policy creation |
| 023 | Create `tenant_provider_budgets` | Per-tenant monthly budget tracking |
| 024 | Create indexes on `tenant_id` | `CREATE INDEX idx_*_tenant_id ON * (tenant_id)` for all tables |

---

## 6. Migration Ordering Diagram

```
       ┌──────────────────┐
       │  tenant_settings │   (001 — standalone)
       └──────────────────┘

       ┌──────────────────┐
       │   audit_jobs     │   (002 — root entity)
       └────────┬─────────┘
                │
                ▼
       ┌──────────────────┐
       │    contracts     │   (003 — child of audit_jobs)
       └────┬────┬────┬───┘
            │    │    │
    ┌───────┘    │    └────────────┐
    ▼            ▼                 ▼
┌──────────┐ ┌──────────┐  ┌──────────────┐
│contract_ │ │contract_ │  │ extractions  │  (006)
│pages     │ │chunks    │  └──────┬───────┘
│(004)     │ │(005)     │         │
└──────────┘ └──────────┘         ▼
                          ┌──────────────┐
                          │extraction_   │
                          │quotes        │  (007)
                          └──────────────┘

    ┌──────────┐ ┌──────────┐ ┌──────────┐
    │ legal_   │ │ risk_    │ │ action_  │
    │ findings │ │ scores   │ │ items    │
    │ (008)    │ │ (009)    │ │ (010)    │
    └──────────┘ └──────────┘ └──────────┘

    ┌──────────────┐
    │human_reviews │  (011)
    └──────────────┘

    ┌──────────────┐ ┌──────────────┐ ┌──────────┐
    │provider_     │ │audit_events  │ │ exports  │
    │calls (012)   │ │(013)         │ │(014)     │
    └──────────────┘ └──────────────┘ └──────────┘

    ┌─────────────────────────────────────────────┐
    │  Indexes on all tables              (015)   │
    │  Seed data                           (016)  │
    └─────────────────────────────────────────────┘
```

---

## 7. Design Decisions

### 7.1 Why JSONB for variable-schema fields?

`structured_json` in `extractions`, `evidence_json` in `legal_findings`, `payload_json` in `action_items`, `prompt_json`/`resolution_json` in `human_reviews`, `event_json` in `audit_events`, and `summary_json`/`scoring_breakdown` in `audit_jobs`/`risk_scores` are JSONB because:

- Extraction schema is versioned — JSONB accommodates version drift without column DDL
- Evidence and scoring breakdown have variable shape per finding code
- External action payloads differ per system (Linear vs Jira)
- JSONB supports indexing with GIN if query performance becomes necessary

### 7.2 Why separate `extraction_quotes` from `extractions.structured_json`?

Quote validation is a hard requirement (spec §8.1). Separating quotes into their own table:

- Enforces the invariant that every quote-backed field has a DB row
- Enables deterministic quote-fidelity checks via SQL (`SELECT ... WHERE source_quote NOT IN page_text`)
- Avoids parsing JSONB to validate quotes on every access
- Provides a clear audit trail for which quote supported which field

### 7.3 Why NOT NULL on `provider_calls.audit_job_id` but nullable on `provider_calls.contract_id`?

Some provider calls happen at the job level (e.g., classification before per-contract routing). The job FK is always known. The contract FK is nullable for those job-level calls.

### 7.4 Why `tenant_settings` as a table instead of a config file?

- Enables runtime updates without restart
- Provides upgrade path to multi-tenant (one row per tenant)
- Allows audit trail of config changes (via `updated_at`)
- Consistent with the spec's "all thresholds must be config-driven" rule

### 7.5 Why `risk_scores` has a UNIQUE constraint on `contract_id`?

One contract produces exactly one aggregate risk score. The scoring logic (spec §10.7) is deterministic given the findings, so multiple rows would represent a bug.

### 7.6 Why UUID primary keys instead of auto-increment?

- Prevents information leakage (sequential IDs leak job count)
- Safe for multi-worker environments (no contention on sequence)
- Simplifies B migration (no ID conflicts when merging databases)
- Supports distributed ID generation in B

---

> **End of DATA_MODEL.md**  
> This document defines exactly the 14 tables from ContractLens Master Blueprint §7. No tables, columns, or constraints beyond those specified are defined.
