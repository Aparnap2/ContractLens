"""Audit job endpoints.

Spec section 13:
  POST   /audit-jobs                 — create job
  GET    /audit-jobs/{id}            — get job status
  GET    /audit-jobs/{id}/contracts  — list contracts
  POST   /audit-jobs/{id}/resume     — resume interrupted job
  GET    /audit-jobs/{id}/exports/{export_id} — download export
  POST   /audit-jobs/{id}/upload     — upload contract files (zip/multipart)
"""

import hashlib
import os
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import (
    AuditJob,
    AuditEvent,
    Contract,
    Export,
)
from app.schemas import (
    AuditJobCreate,
    AuditJobResponse,
    ContractResponse,
    ErrorResponse,
    ExportResponse,
    UploadResponse,
)

router = APIRouter(tags=["Audit Jobs"])

# Storage directory for uploaded files and exports
STORAGE_DIR = os.getenv("CONTRACTLENS_STORAGE", "/tmp/contractlens/storage")


# ─── POST /audit-jobs ────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=AuditJobResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Audit job created successfully"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def create_audit_job(
    payload: AuditJobCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new audit job.

    Accepts optional closing_date and client_hub_city for downstream
    deterministic legal checks (deadline breach, venue analysis).
    """
    job = AuditJob(
        status="created",
        created_by="system",  # Will be replaced with auth context in multi-tenant
        closing_date=payload.closing_date,
        client_hub_city=payload.client_hub_city,
    )
    db.add(job)
    await db.flush()

    # Log creation event
    event = AuditEvent(
        audit_job_id=job.id,
        event_type="job.created",
        event_json={
            "closing_date": str(payload.closing_date) if payload.closing_date else None,
            "client_hub_city": payload.client_hub_city,
            "ticket_system": payload.ticket_system,
            "email_enabled": payload.email_enabled,
        },
    )
    db.add(event)

    await db.commit()
    await db.refresh(job)
    return job


# ─── GET /audit-jobs/{id} ────────────────────────────────────────────────────

@router.get(
    "/{job_id}",
    response_model=AuditJobResponse,
    responses={
        200: {"description": "Job details"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def get_audit_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the current status and metadata of an audit job."""
    result = await db.execute(select(AuditJob).where(AuditJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "detail": f"Audit job {job_id} not found",
                "code": "JOB_NOT_FOUND",
            },
        )
    return job


# ─── GET /audit-jobs/{id}/contracts ──────────────────────────────────────────

@router.get(
    "/{job_id}/contracts",
    response_model=list[ContractResponse],
    responses={
        200: {"description": "List of contracts in the job"},
        404: {"model": ErrorResponse, "description": "Job not found"},
    },
)
async def list_contracts(
    job_id: uuid.UUID,
    status_filter: Optional[str] = Query(None, alias="status"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """List all contracts belonging to an audit job.

    Supports optional status filtering and pagination.
    """
    # Verify job exists
    job_check = await db.execute(
        select(sa_func.count()).select_from(AuditJob).where(AuditJob.id == job_id)
    )
    if job_check.scalar() == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "detail": f"Audit job {job_id} not found",
                "code": "JOB_NOT_FOUND",
            },
        )

    query = select(Contract).where(Contract.audit_job_id == job_id)
    if status_filter:
        query = query.where(Contract.status == status_filter)
    query = query.offset(offset).limit(limit).order_by(Contract.created_at)

    result = await db.execute(query)
    return result.scalars().all()


# ─── POST /audit-jobs/{id}/resume ───────────────────────────────────────────

@router.post(
    "/{job_id}/resume",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Job resumed successfully"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        409: {"model": ErrorResponse, "description": "Job not in resumable state"},
    },
)
async def resume_job(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Resume an interrupted audit job.

    For use after a human review has been resolved or after a crash recovery.
    The job status must be 'interrupted' or 'paused' to be resumed.
    """
    result = await db.execute(select(AuditJob).where(AuditJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "detail": f"Audit job {job_id} not found",
                "code": "JOB_NOT_FOUND",
            },
        )

    if job.status not in ("interrupted", "paused", "human_review"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "invalid_state",
                "detail": f"Cannot resume job in status '{job.status}'. "
                          f"Must be 'interrupted', 'paused', or 'human_review'.",
                "code": "JOB_NOT_RESUMABLE",
            },
        )

    job.status = "queued"
    event = AuditEvent(
        audit_job_id=job.id,
        event_type="job.resumed",
        event_json={"previous_status": job.status} if hasattr(job, 'status') else {},
    )
    db.add(event)
    await db.commit()
    await db.refresh(job)
    return {
        "message": "Job resumed successfully",
        "job_id": str(job.id),
        "status": job.status,
    }


# ─── POST /audit-jobs/{id}/upload ────────────────────────────────────────────

@router.post(
    "/{job_id}/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {"description": "Files uploaded and contracts created"},
        404: {"model": ErrorResponse, "description": "Job not found"},
        400: {"model": ErrorResponse, "description": "Invalid file"},
    },
)
async def upload_files(
    job_id: uuid.UUID,
    file: UploadFile,
    db: AsyncSession = Depends(get_db),
):
    """Upload contract files (zip or individual PDF) to an audit job.

    Accepts multipart file upload. Files are:
    1. Validated for type and size
    2. Hashed for deduplication
    3. Stored to local filesystem
    4. Registered as contract records
    """
    # Verify job exists
    result = await db.execute(select(AuditJob).where(AuditJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "detail": f"Audit job {job_id} not found",
                "code": "JOB_NOT_FOUND",
            },
        )

    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file",
                "detail": "No filename provided",
                "code": "INVALID_FILE",
            },
        )

    # Determine MIME type
    mime_type = file.content_type or "application/octet-stream"

    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "empty_file",
                "detail": "Uploaded file is empty",
                "code": "EMPTY_FILE",
            },
        )

    # Compute hash for deduplication
    file_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicate within same job
    dup_check = await db.execute(
        select(Contract).where(
            Contract.audit_job_id == job_id,
            Contract.file_hash == file_hash,
        )
    )
    existing = dup_check.scalar_one_or_none()
    if existing:
        return UploadResponse(
            contract_ids=[existing.id],
            file_names=[file.filename],
            duplicates_skipped=1,
        )

    # Store file
    os.makedirs(STORAGE_DIR, exist_ok=True)
    storage_filename = f"{job_id}_{file_hash}_{file.filename}"
    storage_path = os.path.join(STORAGE_DIR, storage_filename)
    with open(storage_path, "wb") as f:
        f.write(content)

    # Create contract record
    contract = Contract(
        audit_job_id=job_id,
        file_name=file.filename,
        file_hash=file_hash,
        storage_uri=storage_path,
        mime_type=mime_type,
        status="uploaded",
    )
    db.add(contract)
    await db.flush()

    # Update job counters
    job.total_contracts += 1

    # Log event
    event = AuditEvent(
        audit_job_id=job_id,
        contract_id=contract.id,
        event_type="contract.uploaded",
        event_json={
            "file_name": file.filename,
            "file_hash": file_hash,
            "mime_type": mime_type,
            "file_size_bytes": len(content),
        },
    )
    db.add(event)

    await db.commit()
    await db.refresh(contract)

    return UploadResponse(
        contract_ids=[contract.id],
        file_names=[file.filename],
        duplicates_skipped=0,
    )


# ─── GET /audit-jobs/{id}/exports/{export_id} ────────────────────────────────

@router.get(
    "/{job_id}/exports/{export_id}",
    responses={
        200: {"description": "Export file download"},
        404: {"model": ErrorResponse, "description": "Export not found"},
    },
)
async def download_export(
    job_id: uuid.UUID,
    export_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download a generated export file for an audit job.

    Returns the export metadata and file contents as a streaming response.
    """
    result = await db.execute(
        select(Export).where(
            Export.id == export_id,
            Export.audit_job_id == job_id,
        )
    )
    export = result.scalar_one_or_none()
    if not export:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "detail": f"Export {export_id} not found for job {job_id}",
                "code": "EXPORT_NOT_FOUND",
            },
        )

    if export.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "export_not_ready",
                "detail": f"Export status is '{export.status}', not yet ready for download",
                "code": "EXPORT_NOT_READY",
            },
        )

    if not os.path.exists(export.storage_uri):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "file_missing",
                "detail": "Export file not found on storage",
                "code": "EXPORT_FILE_MISSING",
            },
        )

    media_type_map = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    media_type = media_type_map.get(export.format, "application/octet-stream")
    filename = f"contractlens_export_{export_id}.{export.format}"

    return FileResponse(
        path=export.storage_uri,
        media_type=media_type,
        filename=filename,
    )
