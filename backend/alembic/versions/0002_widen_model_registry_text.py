"""widen model_registry licence/version columns

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-09 12:25:00+00:00

The engine registry reports full licence notes (e.g. the ZipVoice weight licence explains the
Emilia dataset terms in ~190 characters) and composite version strings; the original
``VARCHAR(128)``/``VARCHAR(64)`` columns truncated the worker's upsert and the registry was never
written.  Text columns remove the limit.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "model_registry", "name", type_=sa.Text(), existing_type=sa.String(length=128)
    )
    op.alter_column(
        "model_registry", "version", type_=sa.Text(), existing_type=sa.String(length=64)
    )
    op.alter_column(
        "model_registry", "licence", type_=sa.Text(), existing_type=sa.String(length=128)
    )
    op.alter_column(
        "model_registry",
        "weight_licence",
        type_=sa.Text(),
        existing_type=sa.String(length=128),
    )


def downgrade() -> None:
    # Values longer than the old limits are truncated on downgrade.
    op.execute("UPDATE model_registry SET weight_licence = LEFT(weight_licence, 128)")
    op.execute("UPDATE model_registry SET licence = LEFT(licence, 128)")
    op.execute("UPDATE model_registry SET version = LEFT(version, 64)")
    op.execute("UPDATE model_registry SET name = LEFT(name, 128)")
    op.alter_column(
        "model_registry", "weight_licence", type_=sa.String(length=128), existing_type=sa.Text()
    )
    op.alter_column(
        "model_registry", "licence", type_=sa.String(length=128), existing_type=sa.Text()
    )
    op.alter_column(
        "model_registry", "version", type_=sa.String(length=64), existing_type=sa.Text()
    )
    op.alter_column(
        "model_registry", "name", type_=sa.String(length=128), existing_type=sa.Text()
    )
