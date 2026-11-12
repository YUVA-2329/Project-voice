"""Profile updates and full account deletion."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.core.errors import Forbidden
from app.core.logging import get_logger
from app.core.security import verify_password
from app.db.models import User
from app.schemas.users import Preferences, UserPatch
from app.services import audit_service
from app.services.audit_service import AuditAction, RequestContext
from app.storage import StorageBackend, StorageError
from app.storage.keys import user_prefix

log = get_logger(__name__)


async def update_profile(session: AsyncSession, *, user: User, patch: UserPatch) -> User:
    if patch.display_name is not None:
        user.display_name = " ".join(patch.display_name.split()) or user.display_name
    if patch.preferences is not None:
        merged = {**Preferences().model_dump(), **(user.preferences or {})}
        merged.update(patch.preferences.model_dump(exclude_unset=True))
        user.preferences = Preferences.model_validate(merged).model_dump()
    await session.flush()
    return user


async def delete_account(
    session: AsyncSession,
    *,
    user: User,
    password: str,
    storage: StorageBackend,
    ctx: RequestContext,
) -> None:
    """Verify the password, then delete the user row (DB cascade) and every storage object."""
    if not verify_password(password, user.password_hash):
        raise Forbidden("Password is incorrect.", code="invalid_password")
    user_id = user.id
    audit_service.record(session, user_id=user_id, action=AuditAction.USER_DELETE, ctx=ctx)
    await session.flush()
    await session.delete(user)
    await session.flush()
    try:
        removed = await run_in_threadpool(storage.delete_prefix, user_prefix(user_id))
        log.info("account_deleted", user_id=str(user_id), objects_removed=removed)
    except StorageError as exc:
        log.error("account_storage_delete_failed", user_id=str(user_id), error=str(exc))
