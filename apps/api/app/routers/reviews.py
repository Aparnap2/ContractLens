"""Human review resolution endpoints.

Spec section 13:
  POST /human-reviews/{id}/resolve — resolve a human-in-the-loop review
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AuditEvent, HumanReview
from app.schemas import ErrorResponse, ReviewResolution

router = APIRouter(tags=["Human Reviews"])


# ─── POST /human-reviews/{id}/resolve ────────────────────────────────────────

@router.post(
    "/{review_id}/resolve",
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Review resolved successfully"},
        404: {"model": ErrorResponse, "description": "Review not found"},
        409: {"model": ErrorResponse, "description": "Review already resolved"},
    },
)
async def resolve_human_review(
    review_id: uuid.UUID,
    resolution: ReviewResolution,
    db: AsyncSession = Depends(get_db),
):
    """Resolve a human-in-the-loop review.

    Accepts reviewer decision (approved/rejected) with optional patched
    extraction values and notes.

    Spec section 13.3 example:
    ```json
    {
      "approved": true,
      "patched_extraction": {
        "termination_notice_days": 90,
        ...
      },
      "review_notes": "OCR merged 30 and 90 incorrectly."
    }
    ```

    After resolution, the workflow can be resumed via POST /audit-jobs/{id}/resume.
    """
    # Fetch review
    result = await db.execute(select(HumanReview).where(HumanReview.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "detail": f"Human review {review_id} not found",
                "code": "REVIEW_NOT_FOUND",
            },
        )

    if review.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "error": "already_resolved",
                "detail": f"Human review {review_id} is already resolved",
                "code": "REVIEW_ALREADY_RESOLVED",
            },
        )

    # Apply resolution (idempotent per spec section 6.3 replay-safe rule)
    resolution_data = resolution.model_dump()
    review.status = "resolved" if resolution.approved else "rejected"
    review.resolution_json = resolution_data
    review.resolved_at = datetime.now(timezone.utc)

    # Log event
    event = AuditEvent(
        audit_job_id=None,  # Will be updated when workflow links reviews to jobs
        contract_id=review.contract_id,
        event_type="human_review.resolved",
        event_json={
            "review_id": str(review.id),
            "approved": resolution.approved,
            "has_patches": resolution.patched_extraction is not None,
            "review_notes": resolution.review_notes,
        },
    )
    db.add(event)

    await db.commit()
    await db.refresh(review)

    return {
        "message": "Review resolved successfully",
        "review_id": str(review.id),
        "status": review.status,
        "approved": resolution.approved,
    }
