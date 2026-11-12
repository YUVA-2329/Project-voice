"""Operator CLI: ``python -m app.cli <command>``.

Commands: ``create-user``, ``reset-password``, ``cleanup``.  Uses the synchronous session so it
works anywhere the worker works (no event loop, no asyncpg).
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.security import hash_password
from app.db.models import User
from app.db.models.user import default_preferences
from app.db.sync_session import sync_session_scope
from app.services.auth_service import normalise_email


def _read_password(provided: str | None) -> str:
    settings = get_settings()
    password = provided or getpass.getpass("Password: ")
    if not settings.PASSWORD_MIN_LENGTH <= len(password) <= settings.PASSWORD_MAX_LENGTH:
        raise SystemExit(
            "password must be between "
            f"{settings.PASSWORD_MIN_LENGTH} and {settings.PASSWORD_MAX_LENGTH} characters"
        )
    return password


def cmd_create_user(args: argparse.Namespace) -> int:
    email = normalise_email(args.email)
    password = _read_password(args.password)
    with sync_session_scope() as session:
        if session.scalar(select(User.id).where(User.email == email)) is not None:
            print(f"error: a user with email {email} already exists", file=sys.stderr)
            return 1
        user = User(
            email=email,
            password_hash=hash_password(password),
            display_name=args.display_name or email.split("@")[0],
            preferences=default_preferences(),
        )
        session.add(user)
        session.flush()
        print(f"created user {user.id} <{email}>")
    return 0


def cmd_reset_password(args: argparse.Namespace) -> int:
    email = normalise_email(args.email)
    password = _read_password(args.password)
    with sync_session_scope() as session:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"error: no user with email {email}", file=sys.stderr)
            return 1
        user.password_hash = hash_password(password)
        if args.revoke_sessions:
            from datetime import UTC, datetime

            for user_session in user.sessions:
                if user_session.revoked_at is None:
                    user_session.revoked_at = datetime.now(UTC)
        print(
            f"password updated for {email}"
            + (" (sessions revoked)" if args.revoke_sessions else "")
        )
    return 0


def cmd_cleanup(_: argparse.Namespace) -> int:
    from app.jobs.maintenance import cleanup_job

    stats = cleanup_job()
    for key, value in stats.items():
        print(f"{key}: {value}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pv", description="PROJECT VOICE operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-user", help="create a user account")
    create.add_argument("email")
    create.add_argument("--password", help="password (prompted when omitted)")
    create.add_argument("--display-name", dest="display_name", default=None)
    create.set_defaults(func=cmd_create_user)

    reset = sub.add_parser("reset-password", help="set a new password for a user")
    reset.add_argument("email")
    reset.add_argument("--password", help="new password (prompted when omitted)")
    reset.add_argument(
        "--revoke-sessions", action="store_true", help="also sign the user out everywhere"
    )
    reset.set_defaults(func=cmd_reset_password)

    cleanup = sub.add_parser("cleanup", help="run the maintenance cleanup job now")
    cleanup.set_defaults(func=cmd_cleanup)
    return parser


def main(argv: list[str] | None = None) -> int:
    configure_logging(get_settings())
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
