"""Job status endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession
from app.core.errors import NotFound
from app.core.ids import parse_uuid
from app.schemas.jobs import JobOut
from app.services import jobs_service
from app.services.serializers import job_to_out

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobOut)
async def get_job(job_id: str, auth: CurrentUser, session: DbSession) -> JobOut:
    parsed = parse_uuid(job_id)
    if parsed is None:
        raise NotFound("Job not found.", code="job_not_found")
    job = await jobs_service.get_owned(session, owner_id=auth.user_id, job_id=parsed)
    return job_to_out(job)
