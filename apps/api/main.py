"""ContractLens — FastAPI application entry point (Master Spec §13)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from domain.schemas import AuditJob, HumanReview

app = FastAPI(title="ContractLens", version="0.1.0")

# In-memory store for test isolation
_jobs: dict[str, AuditJob] = {}
_contracts: dict[str, list[dict]] = {}
_findings: dict[str, list[dict]] = {}
_reviews: dict[str, HumanReview] = {}


# ── Request / response models ───────────────────────────────────────────────


class CreateJobRequest(BaseModel):
    closing_date: Optional[date] = None
    client_hub_city: Optional[str] = None
    ticket_system: Optional[str] = None
    email_enabled: bool = False


class UploadContractRequest(BaseModel):
    file_name: str
    content: str  # base64 or text content for tests


class ResolveReviewRequest(BaseModel):
    approved: bool
    patched_extraction: Optional[dict] = None
    review_notes: Optional[str] = None


# ── Endpoints (Master Spec §13.1) ───────────────────────────────────────────


@app.post("/audit-jobs", status_code=201)
async def create_audit_job(req: CreateJobRequest):
    job = AuditJob(
        id=str(uuid.uuid4()),
        status="pending",
        created_by="analyst",
        closing_date=req.closing_date,
        client_hub_city=req.client_hub_city,
    )
    _jobs[job.id] = job
    _contracts[job.id] = []
    return {"id": job.id, "status": job.status, "created_at": job.created_at.isoformat()}


@app.get("/audit-jobs/{job_id}")
async def get_audit_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.model_dump()


@app.get("/audit-jobs/{job_id}/contracts")
async def list_contracts(job_id: str):
    if job_id not in _jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return _contracts.get(job_id, [])


@app.get("/contracts/{contract_id}/findings")
async def get_findings(contract_id: str):
    return _findings.get(contract_id, [])


@app.post("/human-reviews/{review_id}/resolve")
async def resolve_review(review_id: str, req: ResolveReviewRequest):
    review = _reviews.get(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.status = "resolved" if req.approved else "rejected"
    review.resolution_json = req.model_dump()
    return {"status": review.status}


@app.post("/audit-jobs/{job_id}/resume")
async def resume_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": "resumed"}


# ── Helpers for tests ───────────────────────────────────────────────────────


def reset_store():
    """Clear in-memory store (for test isolation)."""
    _jobs.clear()
    _contracts.clear()
    _findings.clear()
    _reviews.clear()
