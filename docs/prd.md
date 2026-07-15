# ContractLens — Indian Corporate Poison Pill Auto-Extractor
## Production-Grade Specification Document

> **Project Codename:** ContractLens  
> **Domain:** Legal AI / M&A Due Diligence  
> **Target Users:** Corporate lawyers, legal ops teams, M&A associates at Indian law firms and in-house corporate legal departments  
> **Core Promise:** Upload a folder of Indian commercial contracts → get an audited risk register with page-level citations, statutory compliance flags, and auto-generated remediation tickets in seconds  

---

## Table of Contents

1. [Product Requirements Document (PRD)](#1-product-requirements-document-prd)
2. [End-to-End Workflow](#2-end-to-end-workflow)
3. [Technical Architecture & System Design](#3-technical-architecture--system-design)
4. [Agent Design](#4-agent-design)
5. [Database Model](#5-database-model)
6. [Architecture Decision Records (ADRs)](#6-architecture-decision-records-adrs)
7. [Standard Operating Procedure (SOP)](#7-standard-operating-procedure-sop)
8. [Checklists](#8-checklists)
9. [Coding Agent Master Prompt](#9-coding-agent-master-prompt)

---

## 1. Product Requirements Document (PRD)

### 1.1 Problem Statement

During Indian M&A transactions and vendor audits, junior corporate lawyers spend 3–6 weeks inside virtual data rooms manually reading hundreds of commercial agreements — Lease Deeds, Master Service Agreements (MSAs), Employment Contracts, NDAs, and SaaS Terms of Service. They are hunting for "poison pills" — hidden clauses that could financially damage an acquisition:

- **Change of Control penalties** — triggered automatically when ownership changes hands
- **Unconscionable liquidated damages** — penalties disguised as genuine pre-estimates of loss (invalid under Section 74, Indian Contract Act, 1872) [web:5]
- **Insufficiently stamped documents** — contracts inadmissible as evidence under Section 35 of the Indian Stamp Act [web:8][page:1]
- **Distant arbitration venues** — governing law set to a city far from the client's operational hub, increasing litigation overhead
- **Automatic renewal traps** — contracts that auto-renew with 15%+ price escalations
- **Lock-in periods** — employment or service contracts with unreasonable lock-in durations
- **Exclusive jurisdiction clauses** — venue-locking that forces litigation in unfavorable courts

The current manual process suffers from **context rot** (forgetting clause details across hundreds of documents), **inconsistent risk scoring** (different lawyers flag different severity levels), and **no deterministic statutory compliance checking** against Indian law.

### 1.2 Target Users

| Persona | Role | Pain Point |
|---------|------|------------|
| Junior Associate | Reads contracts, logs risks | Context rot after 50+ documents; misses subtle clauses |
| Senior Partner | Reviews risk register | Cannot trust junior findings; re-reads critical contracts |
| Legal Ops Manager | Coordinates due diligence | No aggregate financial exposure view; manual spreadsheet tracking |
| In-House Counsel | Vendor audit compliance | Needs statutory compliance checks (Stamp Act, Contract Act) |

### 1.3 User Stories

**US-1: Portfolio Audit**
> As a junior associate, I want to upload a zip folder of 100+ Indian commercial contracts and receive an audited risk register, so that I can focus my manual review on only the highest-risk contracts instead of reading every document from page 1.

**US-2: Statutory Compliance Flag**
> As an in-house counsel, I want the system to automatically flag contracts that are insufficiently stamped under the Indian Stamp Act, so that I know which contracts are inadmissible as evidence before entering litigation.

**US-3: Financial Exposure Calculation**
> As a legal ops manager, I want to see the aggregate financial exposure across all contracts with Change of Control penalties, so that I can report the total contingent liability to the deal team.

**US-4: Negotiation Email Drafting**
> As a senior partner, I want the system to draft negotiation emails to counterparties pointing out exact clause updates required, so that I can send them with minimal editing.

**US-5: Remediation Ticket Generation**
> As a legal ops manager, I want the system to create tracking tickets in Linear/Jira for each contract requiring manual renegotiation, so that no flagged risk falls through the cracks.

**US-6: Deadline Breach Alert**
> As a deal team member, I want the system to flag contracts where the termination notice period exceeds the time remaining before the acquisition closing date, so that I can prioritize immediate renegotiation.

### 1.4 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-1 | Ingest multi-page PDF contracts (scanned and digital) from a zip folder or directory | P0 |
| FR-2 | Extract text with page-level and section-level citation tracking | P0 |
| FR-3 | Semantic routing to identify target paragraphs (assignability, termination, change of control, indemnification, liquidated damages, stamp duty, arbitration) | P0 |
| FR-4 | LLM-based structured extraction into Pydantic models with exact source quotes | P0 |
| FR-5 | Deterministic Indian law compliance engine (Section 74 Contract Act, Section 35 Stamp Act, Arbitration Act) | P0 |
| FR-6 | Aggregate financial risk exposure calculation across portfolio | P0 |
| FR-7 | Deadline breach detection (termination notice vs. closing date) | P1 |
| FR-8 | Auto-generate Linear/Jira tickets with source quote and page reference | P1 |
| FR-9 | Auto-draft negotiation emails via SendGrid API | P1 |
| FR-10 | Export risk register as CSV/Excel for deal team | P1 |
| FR-11 | Multi-contract comparison view (same clause across vendors) | P2 |
| FR-12 | Historical audit trail of all extractions and rule evaluations | P0 |

### 1.5 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR-1 | Processing time for 100 contracts | < 5 minutes (parallelized) |
| NFR-2 | Extraction accuracy (clause presence/absence) | > 95% precision, > 90% recall |
| NFR-3 | Source quote fidelity (exact text match) | 100% (no paraphrasing) |
| NFR-4 | System runs locally on 16GB RAM | Docker Compose total < 6GB RAM |
| NFR-5 | LLM cost per 100-contract audit | < $2 USD (using cheap models via OpenRouter) |
| NFR-6 | Zero hallucination on financial figures | Pydantic validation + deterministic re-check |
| NFR-7 | All risk evaluations are auditable and reproducible | Full trace in Langfuse + PostgreSQL |
| NFR-8 | API response time for status polling | < 200ms |

### 1.6 Scope

**In Scope:**
- Indian commercial contracts: Lease Deeds, MSAs, Employment Contracts, NDAs, SaaS Terms
- Indian statutory law checks: Contract Act Section 74, Stamp Act Section 35, Arbitration Act venue analysis
- Single-tenant deployment (one law firm / one deal team)
- PDF input only (Phase 1)

**Out of Scope (Phase 1):**
- Non-Indian jurisdiction contracts
- Real-time collaboration between multiple users
- Contract authoring or redlining
- Court filing integration
- OCR for handwritten annotations on scanned documents (Phase 2)
- Multi-language contract support (Hindi, Bengali, etc.) (Phase 2)

### 1.7 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time reduction vs. manual review | 90% (from 3 weeks to 2 days) | Deal completion time tracking |
| Risk recall (poison pills found / total poison pills) | > 90% | Legal team spot audit on 10% sample |
| False positive rate (flagged but not actual risk) | < 10% | Legal team review of flagged items |
| Statutory compliance accuracy | 100% (deterministic rules) | Automated test suite |
| User adoption (contracts audited via system vs. manual) | > 80% within 3 months | Usage analytics |
