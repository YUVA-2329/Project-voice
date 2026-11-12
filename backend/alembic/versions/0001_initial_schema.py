"""initial schema

Revision ID: 0001
Revises: —
Create Date: 2026-11-09 10:59:40.757309+00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('model_registry',
    sa.Column('engine_id', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('version', sa.String(length=64), nullable=False),
    sa.Column('licence', sa.String(length=128), nullable=False),
    sa.Column('weight_licence', sa.String(length=128), nullable=False),
    sa.Column('available', sa.Boolean(), nullable=False),
    sa.Column('unavailable_reason', sa.Text(), nullable=True),
    sa.Column('loaded', sa.Boolean(), nullable=False),
    sa.Column('device', sa.String(length=8), nullable=True),
    sa.Column('tts_languages', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('cloning_languages', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('cross_lingual', sa.Boolean(), nullable=False),
    sa.Column('requires_reference_text', sa.Boolean(), nullable=False),
    sa.Column('sample_rate', sa.Integer(), nullable=False),
    sa.Column('resource', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('worker_name', sa.String(length=128), nullable=True),
    sa.Column('refreshed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_model_registry')),
    sa.UniqueConstraint('engine_id', name=op.f('uq_model_registry_engine_id'))
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=320), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=False),
    sa.Column('display_name', sa.String(length=80), nullable=False),
    sa.Column('preferences', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
    sa.UniqueConstraint('email', name=op.f('uq_users_email'))
    )
    op.create_table('api_keys',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('prefix', sa.String(length=24), nullable=False),
    sa.Column('key_hash', sa.String(length=64), nullable=False),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_api_keys_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_api_keys')),
    sa.UniqueConstraint('key_hash', name=op.f('uq_api_keys_key_hash'))
    )
    op.create_index(op.f('ix_api_keys_user_id'), 'api_keys', ['user_id'], unique=False)
    op.create_table('audit_events',
    sa.Column('user_id', sa.Uuid(), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('resource_type', sa.String(length=32), nullable=True),
    sa.Column('resource_id', sa.Uuid(), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_audit_events_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_events'))
    )
    op.create_index(op.f('ix_audit_events_action'), 'audit_events', ['action'], unique=False)
    op.create_index(op.f('ix_audit_events_created_at'), 'audit_events', ['created_at'], unique=False)
    op.create_index('ix_audit_events_user_id_created_at', 'audit_events', ['user_id', 'created_at'], unique=False)
    op.create_table('idempotency_keys',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('key', sa.String(length=128), nullable=False),
    sa.Column('request_hash', sa.String(length=64), nullable=False),
    sa.Column('resource_type', sa.String(length=32), nullable=False),
    sa.Column('resource_id', sa.Uuid(), nullable=False),
    sa.Column('status_code', sa.Integer(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_idempotency_keys_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_idempotency_keys')),
    sa.UniqueConstraint('user_id', 'key', name='uq_idempotency_keys_user_id_key')
    )
    op.create_index('ix_idempotency_keys_expires_at', 'idempotency_keys', ['expires_at'], unique=False)
    op.create_table('processing_jobs',
    sa.Column('owner_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('queue', sa.String(length=32), nullable=False),
    sa.Column('rq_job_id', sa.String(length=64), nullable=True),
    sa.Column('resource_type', sa.String(length=32), nullable=True),
    sa.Column('resource_id', sa.Uuid(), nullable=True),
    sa.Column('progress', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('attempts', sa.Integer(), nullable=False),
    sa.Column('worker_name', sa.String(length=128), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_processing_jobs_owner_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_processing_jobs'))
    )
    op.create_index(op.f('ix_processing_jobs_owner_id'), 'processing_jobs', ['owner_id'], unique=False)
    op.create_index('ix_processing_jobs_resource', 'processing_jobs', ['resource_type', 'resource_id'], unique=False)
    op.create_index('ix_processing_jobs_status_created_at', 'processing_jobs', ['status', 'created_at'], unique=False)
    op.create_table('user_sessions',
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('refresh_token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rotated_from_hash', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_user_sessions_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user_sessions')),
    sa.UniqueConstraint('refresh_token_hash', name=op.f('uq_user_sessions_refresh_token_hash'))
    )
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_index('ix_user_sessions_user_id_expires_at', 'user_sessions', ['user_id', 'expires_at'], unique=False)
    op.create_table('voice_profiles',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=60), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('language_hint', sa.String(length=8), nullable=True),
    sa.Column('language', sa.String(length=8), nullable=True),
    sa.Column('detected_language', sa.String(length=8), nullable=True),
    sa.Column('engine_id', sa.String(length=64), nullable=True),
    sa.Column('transcript', sa.Text(), nullable=True),
    sa.Column('transcript_source', sa.String(length=8), nullable=True),
    sa.Column('user_transcript', sa.Text(), nullable=True),
    sa.Column('quality', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('fingerprint', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('warnings', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('preview_generation_id', sa.Uuid(), nullable=True),
    sa.Column('job_id', sa.Uuid(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delete_after', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_voice_profiles_owner_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_voice_profiles'))
    )
    op.create_index('ix_voice_profiles_delete_after', 'voice_profiles', ['delete_after'], unique=False)
    op.create_index(op.f('ix_voice_profiles_owner_id'), 'voice_profiles', ['owner_id'], unique=False)
    op.create_index('ix_voice_profiles_owner_id_created_at', 'voice_profiles', ['owner_id', 'created_at'], unique=False)
    op.create_index('ix_voice_profiles_status', 'voice_profiles', ['status'], unique=False)
    op.create_table('generations',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('voice_id', sa.Uuid(), nullable=True),
    sa.Column('voice_name', sa.String(length=60), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('text_hash', sa.String(length=64), nullable=False),
    sa.Column('text_chars', sa.Integer(), nullable=False),
    sa.Column('requested_language', sa.String(length=8), nullable=False),
    sa.Column('language', sa.String(length=8), nullable=True),
    sa.Column('requested_engine_id', sa.String(length=64), nullable=True),
    sa.Column('engine_id', sa.String(length=64), nullable=True),
    sa.Column('speed', sa.Float(), nullable=False),
    sa.Column('quality', sa.String(length=16), nullable=False),
    sa.Column('output_format', sa.String(length=8), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('progress', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('error', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('output', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('metrics', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('job_id', sa.Uuid(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('delete_after', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], name=op.f('fk_generations_owner_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['voice_id'], ['voice_profiles.id'], name=op.f('fk_generations_voice_id_voice_profiles'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_generations'))
    )
    op.create_index('ix_generations_delete_after', 'generations', ['delete_after'], unique=False)
    op.create_index(op.f('ix_generations_owner_id'), 'generations', ['owner_id'], unique=False)
    op.create_index('ix_generations_owner_id_created_at', 'generations', ['owner_id', 'created_at'], unique=False)
    op.create_index('ix_generations_status', 'generations', ['status'], unique=False)
    op.create_index(op.f('ix_generations_voice_id'), 'generations', ['voice_id'], unique=False)
    op.create_table('voice_consents',
    sa.Column('voice_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('consent_type', sa.String(length=32), nullable=False),
    sa.Column('text_version', sa.String(length=32), nullable=False),
    sa.Column('ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('given_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_voice_consents_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['voice_id'], ['voice_profiles.id'], name=op.f('fk_voice_consents_voice_id_voice_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_voice_consents'))
    )
    op.create_index(op.f('ix_voice_consents_user_id'), 'voice_consents', ['user_id'], unique=False)
    op.create_index(op.f('ix_voice_consents_voice_id'), 'voice_consents', ['voice_id'], unique=False)
    op.create_table('voice_reference_files',
    sa.Column('voice_id', sa.Uuid(), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=True),
    sa.Column('format', sa.String(length=16), nullable=False),
    sa.Column('codec', sa.String(length=32), nullable=True),
    sa.Column('content_type', sa.String(length=64), nullable=False),
    sa.Column('duration_seconds', sa.Float(), nullable=False),
    sa.Column('sample_rate', sa.Integer(), nullable=False),
    sa.Column('channels', sa.Integer(), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('speech_seconds', sa.Float(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['voice_id'], ['voice_profiles.id'], name=op.f('fk_voice_reference_files_voice_id_voice_profiles'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_voice_reference_files')),
    sa.UniqueConstraint('voice_id', 'role', name='uq_voice_reference_files_voice_id_role')
    )
    op.create_index(op.f('ix_voice_reference_files_voice_id'), 'voice_reference_files', ['voice_id'], unique=False)
    op.create_table('generation_files',
    sa.Column('generation_id', sa.Uuid(), nullable=False),
    sa.Column('storage_key', sa.String(length=512), nullable=False),
    sa.Column('format', sa.String(length=8), nullable=False),
    sa.Column('content_type', sa.String(length=64), nullable=False),
    sa.Column('duration_seconds', sa.Float(), nullable=False),
    sa.Column('sample_rate', sa.Integer(), nullable=False),
    sa.Column('channels', sa.Integer(), nullable=False),
    sa.Column('size_bytes', sa.BigInteger(), nullable=False),
    sa.Column('sha256', sa.String(length=64), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['generation_id'], ['generations.id'], name=op.f('fk_generation_files_generation_id_generations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_generation_files')),
    sa.UniqueConstraint('generation_id', name=op.f('uq_generation_files_generation_id'))
    )
    # Circular / deferred foreign keys (use_alter=True in the models) are created once every
    # table exists.
    op.create_foreign_key('fk_voice_profiles_job', 'voice_profiles', 'processing_jobs', ['job_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_voice_profiles_preview_generation', 'voice_profiles', 'generations', ['preview_generation_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_generations_job', 'generations', 'processing_jobs', ['job_id'], ['id'], ondelete='SET NULL')
    # ### end Alembic commands ###


def downgrade() -> None:
    op.drop_constraint('fk_generations_job', 'generations', type_='foreignkey')
    op.drop_constraint('fk_voice_profiles_preview_generation', 'voice_profiles', type_='foreignkey')
    op.drop_constraint('fk_voice_profiles_job', 'voice_profiles', type_='foreignkey')
    op.drop_table('generation_files')
    op.drop_index(op.f('ix_voice_reference_files_voice_id'), table_name='voice_reference_files')
    op.drop_table('voice_reference_files')
    op.drop_index(op.f('ix_voice_consents_voice_id'), table_name='voice_consents')
    op.drop_index(op.f('ix_voice_consents_user_id'), table_name='voice_consents')
    op.drop_table('voice_consents')
    op.drop_index(op.f('ix_generations_voice_id'), table_name='generations')
    op.drop_index('ix_generations_status', table_name='generations')
    op.drop_index('ix_generations_owner_id_created_at', table_name='generations')
    op.drop_index(op.f('ix_generations_owner_id'), table_name='generations')
    op.drop_index('ix_generations_delete_after', table_name='generations')
    op.drop_table('generations')
    op.drop_index('ix_voice_profiles_status', table_name='voice_profiles')
    op.drop_index('ix_voice_profiles_owner_id_created_at', table_name='voice_profiles')
    op.drop_index(op.f('ix_voice_profiles_owner_id'), table_name='voice_profiles')
    op.drop_index('ix_voice_profiles_delete_after', table_name='voice_profiles')
    op.drop_table('voice_profiles')
    op.drop_index('ix_user_sessions_user_id_expires_at', table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index('ix_processing_jobs_status_created_at', table_name='processing_jobs')
    op.drop_index('ix_processing_jobs_resource', table_name='processing_jobs')
    op.drop_index(op.f('ix_processing_jobs_owner_id'), table_name='processing_jobs')
    op.drop_table('processing_jobs')
    op.drop_index('ix_idempotency_keys_expires_at', table_name='idempotency_keys')
    op.drop_table('idempotency_keys')
    op.drop_index('ix_audit_events_user_id_created_at', table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_created_at'), table_name='audit_events')
    op.drop_index(op.f('ix_audit_events_action'), table_name='audit_events')
    op.drop_table('audit_events')
    op.drop_index(op.f('ix_api_keys_user_id'), table_name='api_keys')
    op.drop_table('api_keys')
    op.drop_table('users')
    op.drop_table('model_registry')
    # ### end Alembic commands ###
