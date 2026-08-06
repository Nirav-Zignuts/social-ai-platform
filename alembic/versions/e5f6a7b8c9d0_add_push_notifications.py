"""Add device tokens, notification broadcasts, nullable workspace_id

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-08-06 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token", sa.String(length=512), nullable=False),
        sa.Column("platform", sa.String(length=20), nullable=False),
        sa.Column("device_id", sa.String(length=255), nullable=True),
        sa.Column("app_version", sa.String(length=100), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", name="uq_device_tokens_token"),
    )
    op.create_index(
        op.f("ix_device_tokens_user_id"), "device_tokens", ["user_id"], unique=False
    )
    op.create_index(
        "ix_device_tokens_user_active",
        "device_tokens",
        ["user_id", "is_active"],
        unique=False,
    )

    op.create_table(
        "notification_broadcasts",
        sa.Column("admin_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=2000), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("deep_link", sa.String(length=1000), nullable=True),
        sa.Column("target", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("in_app_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("push_success", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("push_failure", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_notification_broadcasts_admin_id"),
        "notification_broadcasts",
        ["admin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_notification_broadcasts_status"),
        "notification_broadcasts",
        ["status"],
        unique=False,
    )

    op.alter_column(
        "notifications",
        "workspace_id",
        existing_type=sa.UUID(),
        nullable=True,
    )
    op.alter_column(
        "notifications",
        "type",
        existing_type=sa.String(length=30),
        type_=sa.String(length=50),
        existing_nullable=False,
    )

    # Backfill device_tokens from active sessions that already have an FCM token.
    op.execute(
        """
        INSERT INTO device_tokens (
            id, user_id, token, platform, device_id, app_version,
            last_seen_at, is_active, is_deleted, created_at, updated_at
        )
        SELECT DISTINCT ON (us.fcm_token)
            gen_random_uuid(),
            us.user_id,
            us.fcm_token,
            COALESCE(NULLIF(LOWER(us.platform), ''), 'web'),
            us.device_id,
            us.app_version,
            NOW(),
            true,
            false,
            NOW(),
            NOW()
        FROM user_sessions us
        WHERE us.fcm_token IS NOT NULL
          AND us.fcm_token <> ''
          AND us.is_active = true
          AND us.is_deleted = false
        ORDER BY us.fcm_token, us.updated_at DESC
        ON CONFLICT (token) DO NOTHING
        """
    )


def downgrade() -> None:
    op.alter_column(
        "notifications",
        "type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=30),
        existing_nullable=False,
    )
    op.alter_column(
        "notifications",
        "workspace_id",
        existing_type=sa.UUID(),
        nullable=False,
    )
    op.drop_index(
        op.f("ix_notification_broadcasts_status"),
        table_name="notification_broadcasts",
    )
    op.drop_index(
        op.f("ix_notification_broadcasts_admin_id"),
        table_name="notification_broadcasts",
    )
    op.drop_table("notification_broadcasts")
    op.drop_index("ix_device_tokens_user_active", table_name="device_tokens")
    op.drop_index(op.f("ix_device_tokens_user_id"), table_name="device_tokens")
    op.drop_table("device_tokens")
