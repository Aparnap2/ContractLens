# ContractLens API Specification

> **Document status:** Final  
> **Base URL (A):** `http://localhost:8000`  
> **Auth:** `X-API-Key` header (see §3)  
> **Content-Type:** `application/json` (unless multipart for upload)  
> **Source of truth:** ContractLens Master Blueprint §13

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Error Response Format](#2-error-response-format)
3. [Endpoints](#3-endpoints)
   - [3.1 Create Audit Job](#31-post-audit-jobs)
   - [3.2 Get Audit Job](#32-get-audit-jobsid)
   - [3.3 List Contracts in Job](#33-get-audit-jobsidcontracts)
   - [3.4 Get Contract Findings](#34-get-contractsidfindings)
   - [3.5 Resolve Human Review](#35-post-human-reviewsidresolve)
   - [3.6 Resume Audit Job](#36-post-audit-jobsidresume)
   - [3.7 Download Export](#37-get-audit-jobsidexportsexport_id)
4. [Async Job Polling Pattern](#4-async-job-polling-pattern)
5. [Human Review Resolution Flow](#5-human-review-resolution-flow)
6. [Schemas](#6-schemas)
7. [Rate Limiting](#7-rate-limiting)

---

## 1. Authentication

### 1.1 Architecture A

All API requests (except health check) require the `X-API-Key` header:

```
GET /audit-jobs/abc-123
X-API-Key: 550e8400-e29b-41d4-a716-446655440000
```

**Key format:** UUID v4, set via `API_KEY` environment variable.

**Validation:** Constant-time comparison against stored key. No bearer token, no session.

### 1.2 Response for Unauthenticated Requests

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "unauthorized",
  "message": "Invalid or missing API key. Provide via X-API-Key header.",
  "request_id": "req_uuid"
}
```

### 1.3 Architecture B (Upgrade)

Replace static key with OAuth2 + JWT:

- `POST /auth/token` — returns JWT (access + refresh)
- `Authorization: Bearer <jwt>` in all subsequent requests
- RBAC enforced per endpoint (analyst, senior_reviewer, admin roles)

---

## 2. Error Response Format

All error responses follow a consistent envelope:

```json
{
  "error": "error_code",
  "message": "Human-readable description of the problem.",
  "details": {},
  "request_id": "req_uuid"
}
```

### 2.1 Standard Error Codes

| HTTP Status | Error Code | When |
|-------------|-----------|------|
| 400 | `bad_request` | Invalid input payload (validation error) |
| 400 | `invalid_file` | Uploaded file is not a valid zip or contains unsupported types |
| 400 | `invalid_json` | Request body is not valid JSON |
| 401 | `unauthorized` | Missing or invalid API key |
| 404 | `not_found` | Resource (job, contract, review, export) not found |
| 409 | `conflict` | Job not in a resumable state (e.g., not interrupted) |
| 409 | `already_resolved` | Human review already resolved |
| 422 | `validation_error` | Request body fails schema validation (detailed per field) |
| 429 | `rate_limited` | Too many requests (see §7) |
| 500 | `internal_error` | Unexpected server error |
| 503 | `service_unavailable` | System in maintenance or overloaded |

### 2.2 Validation Error Details

```json
{
  "error": "validation_error",
  "message": "Request body failed validation.",
  "details": {
    "closing_date": ["field required"],
    "client_hub_city": ["field required"]
  },
  "request_id": "req_uuid"
}
```

### 2.3 Error Response for File Upload

```json
{
  "error": "invalid_file",
  "message": "Uploaded file is not a valid ZIP archive or contains unsupported file types.",
  "details": {
    "provided_type": "application/x-tar",
    "expected_types": ["application/zip", "application/x-zip-compressed"]
  },
  "request_id": "req_uuid"
}
```

---

## 3. Endpoints

### 3.1 POST /audit-jobs

Create a new audit job from an uploaded zip file.

**Endpoint:**
```
POST /audit-jobs
Content-Type: multipart/form-data
X-API-Key: <key>
```

**Request (multipart/form-data):**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file` | File | Yes | ZIP file containing contracts (.pdf files) |
| `closing_date` | string (date) | Yes | Acquisition closing date in ISO format (YYYY-MM-DD) |
| `client_hub_city` | string | Yes | Client's operational hub city for venue analysis |
| `ticket_system` | string | No | `"linear"` or `"jira"` (default: none) |
| `email_enabled` | boolean | No | Enable negotiation email drafting (default: false) |

**Example cURL:**
```bash
curl -X POST http://localhost:8000/audit-jobs \
  -H "X-API-Key: 550e8400-e29b-41d4-a716-446655440000" \
  -F "file=@contracts.zip" \
  -F "closing_date=2026-09-15" \
  -F "client_hub_city=Bengaluru" \
  -F "ticket_system=linear" \
  -F "email_enabled=true"
```

**Response 202 Accepted:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "pending",
  "total_contracts": 0,
  "message": "Audit job created. Files are being ingested.",
  "_links": {
    "self": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890" },
    "contracts": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/contracts" }
  }
}
```

**Validation Rules:**

| Rule | Error |
|------|-------|
| `closing_date` must be in the future | `closing_date must be today or later` |
| `client_hub_city` must be non-empty, max 200 chars | `client_hub_city: field required` or exceed length |
| ZIP must contain at least one `.pdf` file | `ZIP archive contains no PDF files` |
| Individual PDF file size limit | Max 50 MB per file (configurable) |
| Total upload size limit | Max 500 MB (configurable) |
| Filename sanitization | Strip path separators, replace non-alphanumeric characters, limit to 255 chars |

### 3.2 GET /audit-jobs/{id}

Retrieve audit job status and summary.

**Endpoint:**
```
GET /audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890
X-API-Key: <key>
```

**Response 200 OK:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "created_by": "analyst",
  "created_at": "2026-07-15T10:30:00Z",
  "completed_at": null,
  "closing_date": "2026-09-15",
  "client_hub_city": "Bengaluru",
  "total_contracts": 47,
  "processed_contracts": 23,
  "aggregate_exposure_inr": 12500000.00,
  "pending_reviews": 2,
  "summary_json": {
    "risk_level_counts": {
      "critical": 1,
      "high": 3,
      "medium": 8,
      "low": 11,
      "info": 0
    },
    "top_findings": [
      {
        "finding_code": "DEADLINE_BREACH",
        "contract_count": 2,
        "total_financial_impact_inr": 5000000.00
      },
      {
        "finding_code": "INSUFFICIENT_STAMP",
        "contract_count": 5,
        "total_financial_impact_inr": 0.00
      }
    ],
    "provider_summary": {
      "total_calls": 156,
      "failures": 3,
      "avg_confidence": 0.89
    }
  },
  "_links": {
    "self": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890" },
    "contracts": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/contracts" },
    "exports": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/exports" }
  }
}
```

**Status Lifecycle:**
```
pending → processing → review (if interrupt) → processing → completed
                                                      → failed (terminal)
```

| Status | Meaning |
|--------|---------|
| `pending` | Job created, files being ingested and queued |
| `processing` | Worker actively processing contracts |
| `review` | One or more contracts waiting for human review resolution |
| `completed` | All contracts processed, exports generated |
| `failed` | Fatal error (unrecoverable) |

### 3.3 GET /audit-jobs/{id}/contracts

List all contracts in an audit job with processing status.

**Endpoint:**
```
GET /audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/contracts
X-API-Key: <key>
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | (all) | Filter by status: `pending`, `ingested`, `processing`, `extracted`, `review`, `completed`, `failed` |
| `risk_level` | string | (all) | Filter by risk level: `info`, `low`, `medium`, `high`, `critical` |
| `page` | integer | 1 | Page number (1-indexed) |
| `per_page` | integer | 20 | Items per page (max 100) |

**Response 200 OK:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "contracts": [
    {
      "contract_id": "c1c2c3c4-e5f6-7890-abcd-ef1234567890",
      "file_name": "MSA_Acme_Corp.pdf",
      "status": "completed",
      "contract_type": "MSA",
      "vendor_name": "Acme Corp",
      "parser_used": "pymupdf",
      "parser_quality_score": 0.98,
      "risk_level": "high",
      "risk_score": 55.00,
      "exposure_inr": 5000000.00,
      "has_pending_review": false,
      "created_at": "2026-07-15T10:31:00Z"
    },
    {
      "contract_id": "d1d2d3d4-e5f6-7890-abcd-ef1234567890",
      "file_name": "Lease_Mumbai_Office.pdf",
      "status": "review",
      "contract_type": "LEASE",
      "vendor_name": null,
      "parser_used": "pymupdf",
      "parser_quality_score": 0.45,
      "risk_level": null,
      "risk_score": null,
      "exposure_inr": null,
      "has_pending_review": true,
      "created_at": "2026-07-15T10:31:05Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 47,
    "total_pages": 3
  },
  "_links": {
    "self": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/contracts?page=1&per_page=20" },
    "next": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/contracts?page=2&per_page=20" },
    "job": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890" }
  }
}
```

### 3.4 GET /contracts/{id}/findings

Retrieve all legal findings, risk scores, and extraction details for a single contract.

**Endpoint:**
```
GET /contracts/c1c2c3c4-e5f6-7890-abcd-ef1234567890/findings
X-API-Key: <key>
```

**Response 200 OK:**
```json
{
  "contract_id": "c1c2c3c4-e5f6-7890-abcd-ef1234567890",
  "file_name": "MSA_Acme_Corp.pdf",
  "contract_type": "MSA",
  "vendor_name": "Acme Corp",
  "status": "completed",
  "extraction": {
    "extraction_id": "e1e2e3e4-e5f6-7890-abcd-ef1234567890",
    "schema_version": "1.0",
    "provider_name": "groq",
    "model_name": "llama-3-70b",
    "confidence": 0.94,
    "extracted_fields": {
      "governing_law_city": "Bengaluru",
      "arbitration_city": "Mumbai",
      "change_of_control_clause_present": true,
      "change_of_control_penalty_inr": 5000000.00,
      "change_of_control_quote": {
        "source_quote": "In the event of a Change of Control, Company shall pay Vendor a penalty equal to 200% of the then-current Annual Fees.",
        "page_number": 8
      },
      "termination_notice_days": 90,
      "termination_notice_quote": {
        "source_quote": "Either party may terminate upon ninety (90) days prior written notice.",
        "page_number": 12
      },
      "automatic_renewal": true,
      "renewal_escalation_pct": 15.0,
      "renewal_quote": {
        "source_quote": "This Agreement shall automatically renew for successive one-year terms unless either party provides 90 days notice of non-renewal.",
        "page_number": 14
      },
      "liquidated_damages_amount_inr": 1000000.00,
      "liquidated_damages_quote": {
        "source_quote": "Vendor shall pay liquidated damages of INR 10,00,000 per day of delay.",
        "page_number": 22
      },
      "exclusive_jurisdiction_city": "Mumbai",
      "exclusive_jurisdiction_quote": {
        "source_quote": "The courts in Mumbai shall have exclusive jurisdiction over any disputes.",
        "page_number": 25
      },
      "indemnity_cap_inr": null,
      "consequential_damages_capped": false,
      "ambiguity_notes": []
    }
  },
  "risk_score": {
    "total_score": 55.00,
    "level": "high",
    "exposure_inr": 5000000.00,
    "scoring_breakdown": {
      "insufficient_stamp_flag": 0,
      "deadline_breach_flag": 0,
      "change_of_control_flag": 20,
      "high_ld_flag": 15,
      "auto_renew_escalation_flag": 10,
      "distant_venue_flag": 5,
      "uncapped_consequential_flag": 5
    }
  },
  "findings": [
    {
      "finding_id": "f1f2f3f4-e5f6-7890-abcd-ef1234567890",
      "finding_code": "CHANGE_OF_CONTROL_PENALTY",
      "severity": "high",
      "title": "Change of Control penalty of INR 50,00,000 triggered",
      "description": "Contract contains a Change of Control clause with a penalty of INR 5,000,000 (200% of Annual Fees). This represents a material financial obligation that would be triggered upon acquisition.",
      "statute_reference": null,
      "financial_impact_inr": 5000000.00,
      "deterministic": false,
      "evidence_json": {
        "source_quote": "In the event of a Change of Control, Company shall pay Vendor a penalty...",
        "page_number": 8,
        "extraction_confidence": 0.94
      }
    },
    {
      "finding_id": "f2f2f3f4-e5f6-7890-abcd-ef1234567890",
      "finding_code": "DEADLINE_BREACH",
      "severity": "critical",
      "title": "Termination notice period (90 days) exceeds time to closing",
      "description": "Termination requires 90 days notice but only 62 days remain until closing. Immediate renegotiation required.",
      "statute_reference": null,
      "financial_impact_inr": 0.00,
      "deterministic": true,
      "evidence_json": {
        "termination_notice_days": 90,
        "days_until_closing": 62,
        "closing_date": "2026-09-15",
        "current_date": "2026-07-15"
      }
    },
    {
      "finding_id": "f3f2f3f4-e5f6-7890-abcd-ef1234567890",
      "finding_code": "AUTO_RENEWAL_ESCALATION",
      "severity": "medium",
      "title": "Automatic renewal with 15% price escalation",
      "description": "Contract auto-renews annually with a 15% price escalation, which meets the configured threshold of 15%.",
      "statute_reference": null,
      "financial_impact_inr": 0.00,
      "deterministic": true,
      "evidence_json": {
        "escalation_pct": 15.0,
        "threshold_pct": 15.0
      }
    },
    {
      "finding_id": "f4f2f3f4-e5f6-7890-abcd-ef1234567890",
      "finding_code": "HIGH_LIQUIDATED_DAMAGES",
      "severity": "high",
      "title": "Liquidated damages of INR 10,00,000 per day — potential Section 74 issue",
      "description": "Liquidated damages clause specifies INR 1,000,000 per day of delay. Amount significantly exceeds configured threshold of INR 5,000,000 total. May be vulnerable as a penalty rather than genuine pre-estimate under Section 74, Indian Contract Act, 1872.",
      "statute_reference": "Indian Contract Act, 1872 — Section 74",
      "financial_impact_inr": 1000000.00,
      "deterministic": false,
      "evidence_json": {
        "source_quote": "Vendor shall pay liquidated damages of INR 10,00,000 per day of delay.",
        "page_number": 22,
        "ld_threshold_inr": 5000000.00
      }
    }
  ],
  "action_items": [
    {
      "action_id": "a1a2a3a4-e5f6-7890-abcd-ef1234567890",
      "action_type": "linear_ticket",
      "external_system": "linear",
      "status": "draft",
      "external_ref": null,
      "summary": "CRITICAL: Deadline breach in MSA_Acme_Corp.pdf — termination notice 90d exceeds 62d to closing",
      "created_at": "2026-07-15T10:35:00Z"
    }
  ],
  "_links": {
    "self": { "href": "/contracts/c1c2c3c4-e5f6-7890-abcd-ef1234567890/findings" },
    "contract_page": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/contracts" },
    "extraction_quotes": { "href": "/contracts/c1c2c3c4-e5f6-7890-abcd-ef1234567890/quotes" }
  }
}
```

### 3.5 POST /human-reviews/{id}/resolve

Submit a human review resolution to patch an extraction and resume the workflow.

**Endpoint:**
```
POST /human-reviews/r1r2r3r4-e5f6-7890-abcd-ef1234567890/resolve
Content-Type: application/json
X-API-Key: <key>
```

**Request Body:**
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
  "review_notes": "OCR merged 30 and 90 incorrectly. Correct value is 90 as read from page 12."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `approved` | boolean | Yes | Whether the extraction is approved (`true`) or rejected entirely (`false`) |
| `patched_extraction` | object | Conditionally | The corrected extraction fields. Required if `approved=true`. Only needs to contain fields being patched. |
| `review_notes` | string | No | Free-text notes explaining the resolution |

**Validation Rules:**

| Rule | Behavior |
|------|----------|
| `approved=true` without `patched_extraction` | Error 400: `patched_extraction required when approved is true` |
| `patched_extraction` field lacks `source_quote` | Error 400: `field X: source_quote required` |
| `patched_extraction` field lacks `page_number` | Error 400: `field X: page_number required` |
| Human review already resolved | Error 409: `already_resolved` |
| Human review ID not found | Error 404: `not_found` |
| `patched_extraction` includes field not in schema | Error 400: `unknown field: X` |

**Response 200 OK:**
```json
{
  "human_review_id": "r1r2r3r4-e5f6-7890-abcd-ef1234567890",
  "status": "resolved",
  "message": "Review resolved. Use POST /audit-jobs/{id}/resume to continue the workflow.",
  "_links": {
    "resume": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/resume" }
  }
}
```

### 3.6 POST /audit-jobs/{id}/resume

Resume a paused audit job after human review resolution. Triggers LangGraph to resume from the interrupted node.

**Endpoint:**
```
POST /audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/resume
Content-Type: application/json
X-API-Key: <key>
```

**Request Body:** Empty (no payload required).

**Response 200 OK:**
```json
{
  "job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "processing",
  "message": "Job resumed. Processing will continue from the last interrupted node.",
  "pending_reviews": 0,
  "_links": {
    "self": { "href": "/audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890" }
  }
}
```

**Error Conditions:**

| Condition | Status | Error |
|-----------|--------|-------|
| Job not in `review` status | 409 | `conflict: job is not in review status (current: processing)` |
| Unresolved human reviews exist | 409 | `conflict: 2 human reviews still unresolved` |
| Job ID not found | 404 | `not_found: audit job not found` |

### 3.7 GET /audit-jobs/{id}/exports/{export_id}

Download generated export package (CSV or XLSX).

**Endpoint:**
```
GET /audit-jobs/a1b2c3d4-e5f6-7890-abcd-ef1234567890/exports/x1x2x3x4-e5f6-7890-abcd-ef1234567890
X-API-Key: <key>
```

**Response:**

| Status | Content-Type | Body |
|--------|-------------|------|
| 200 | `text/csv` | CSV file download |
| 200 | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | XLSX file download |
| 404 | `application/json` | `{ "error": "not_found", "message": "Export not found" }` |

**Response Headers:**
```
Content-Disposition: attachment; filename="risk_register_2026-07-15.csv"
Content-Type: text/csv
Content-Length: 123456
```

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `format` | string | `csv` | Export format: `csv` or `xlsx` |

**Notes:**
- The export file is generated at job completion time by the `export_outputs` node.
- If the export has not been generated yet (job still processing), return 404.
- In Architecture A, the file is served from local encrypted filesystem.
- In Architecture B, the file is served from object storage via presigned URL redirect.

---

## 4. Async Job Polling Pattern

Since audit jobs are long-running (30s–5min for 100 contracts), all job creation is asynchronous.

### 4.1 Polling Protocol

```
1. POST /audit-jobs  ──▶  202 Accepted { job_id, status: "pending" }
2. GET /audit-jobs/{id} ──▶ 200 OK { status: "processing", processed_contracts: 5 }
3. Repeat step 2 every 2-3 seconds
4. GET /audit-jobs/{id} ──▶ 200 OK { status: "completed" }
```

### 4.2 Client Guidelines

| Behavior | Recommendation |
|----------|---------------|
| Poll interval | 2 seconds (exponential backoff not needed for local deployment) |
| Max polls before timeout | 150 (5 minutes at 2s interval) |
| On `status: review` | Alert user: "N contracts require human review" |
| On `status: failed` | Show error message, do not retry automatically |
| On `status: completed` | Redirect to findings view |

### 4.3 Server-Side Optimization

- `GET /audit-jobs/{id}` response is cached in Redis for 1 second to handle rapid polling.
- The `processed_contracts` and `aggregate_exposure_inr` fields update in near-real-time as each contract completes.

---

## 5. Human Review Resolution Flow

### 5.1 Step-by-Step

```
1. User polls GET /audit-jobs/{id} ──▶ status: "review"
2. User lists contracts: GET /audit-jobs/{id}/contracts?status=review
3. For each review-required contract:
   a. User views the contract's pending human_review
   b. User opens the review payload (prompt_json from human_reviews)
   c. User compares extracted value against quoted page text
   d. User either:
      - APPROVES: submits resolution with corrected extraction
      - REJECTS: submits resolution with approved=false
4. User submits: POST /human-reviews/{id}/resolve
5. User resumes job: POST /audit-jobs/{id}/resume
6. Graph continues with patched extraction
```

### 5.2 Retrieving Pending Reviews

There is no dedicated list endpoint for pending reviews. The UI derives pending reviews from:

1. `GET /audit-jobs/{id}` — `pending_reviews` count in the response
2. `GET /audit-jobs/{id}/contracts?status=review` — contracts awaiting review
3. `GET /contracts/{id}/findings` — view extraction + redacted page text

The `human_reviews` table can be queried directly for the review payload:

```sql
SELECT id, review_type, status, prompt_json
FROM human_reviews
WHERE contract_id = :contract_id AND status = 'pending';
```

### 5.3 Resolution Options

| Scenario | `approved` | `patched_extraction` | Effect |
|----------|-----------|---------------------|--------|
| Extraction correct | `true` | (empty or absent) | System uses existing extraction as-is |
| Extraction needs patch | `true` | Partial object with corrected fields | System merges patch over existing extraction |
| Extraction irrecoverable | `false` | (absent) | System treats extraction as failed, continues with informational findings only |

---

## 6. Schemas

### 6.1 AuditJobCreate

Used in `POST /audit-jobs` (as multipart form fields + file):

```json
{
  "closing_date": "2026-09-15",
  "client_hub_city": "Bengaluru",
  "ticket_system": "linear",
  "email_enabled": true
}
```

| Field | Type | Required | Default | Constraints |
|-------|------|----------|---------|-------------|
| `closing_date` | string (date) | Yes | — | Format `YYYY-MM-DD`, must be today or future |
| `client_hub_city` | string | Yes | — | 1–200 chars |
| `ticket_system` | string | No | `null` | Must be `"linear"`, `"jira"`, or `null` |
| `email_enabled` | boolean | No | `false` | — |

### 6.2 AuditJobResponse

Returned by `GET /audit-jobs/{id}`:

```json
{
  "job_id": "uuid",
  "status": "processing",
  "created_by": "analyst",
  "created_at": "2026-07-15T10:30:00Z",
  "completed_at": null,
  "closing_date": "2026-09-15",
  "client_hub_city": "Bengaluru",
  "total_contracts": 47,
  "processed_contracts": 23,
  "aggregate_exposure_inr": 12500000.00,
  "pending_reviews": 2,
  "summary_json": {}
}
```

### 6.3 HumanReviewResolve

Used in `POST /human-reviews/{id}/resolve`:

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

| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| `approved` | boolean | Yes | — |
| `patched_extraction` | object | No (but required if `approved=true`) | Must be a subset of `ContractExtraction` schema |
| `patched_extraction.*_quote` | object (QuoteRef) | Required per patched field | Must have `source_quote` (string) and `page_number` (int) |
| `review_notes` | string | No | Max 2000 chars |

### 6.4 ErrorResponse

```json
{
  "error": "error_code",
  "message": "Human-readable message",
  "details": {},
  "request_id": "req_uuid"
}
```

### 6.5 PaginatedResponse

```json
{
  "items": [],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 47,
    "total_pages": 3
  }
}
```

### 6.6 QuoteRef (Embedded)

```json
{
  "source_quote": "Exact text from the contract page.",
  "page_number": 12
}
```

---

## 7. Rate Limiting

| Limit | Scope | Architecture A | Architecture B |
|-------|-------|---------------|---------------|
| Requests per minute | Per IP | 100 | 1000 (per tenant) |
| Concurrent upload size | Global | 500 MB | 2 GB (per tenant) |
| Max contracts per job | Global | 500 | Configurable per tenant |

**Rate limit response:**
```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 60

{
  "error": "rate_limited",
  "message": "Rate limit exceeded. Retry after 60 seconds.",
  "details": {
    "limit": 100,
    "window_seconds": 60,
    "retry_after_seconds": 45
  },
  "request_id": "req_uuid"
}
```

---

> **End of API_SPEC.md**  
> This document defines exactly the endpoints from ContractLens Master Blueprint §13. No endpoints beyond those specified are defined. No fields beyond those specified are included.
