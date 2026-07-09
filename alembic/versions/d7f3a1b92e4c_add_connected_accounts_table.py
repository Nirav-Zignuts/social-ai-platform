"""Add connected_accounts table

Revision ID: d7f3a1b92e4c
Revises: c4a8e2f91b3d
Create Date: 2026-07-09 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "d7f3a1b92e4c"
down_revision: Union[str, Sequence[str], None] = "c4a8e2f91b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connected_accounts",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("provider_username", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("access_token", sa.String(), nullable=False),
        sa.Column("refresh_token", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("page_id", sa.String(length=255), nullable=True),
        sa.Column("instagram_business_account_id", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workspace_id", "provider", name="uq_connected_accounts_workspace_provider"),
    )
    op.create_index(
        op.f("ix_connected_accounts_provider"), "connected_accounts", ["provider"], unique=False
    )
    op.create_index(
        op.f("ix_connected_accounts_status"), "connected_accounts", ["status"], unique=False
    )
    op.create_index(
        op.f("ix_connected_accounts_workspace_id"),
        "connected_accounts",
        ["workspace_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_connected_accounts_workspace_id"), table_name="connected_accounts")
    op.drop_index(op.f("ix_connected_accounts_status"), table_name="connected_accounts")
    op.drop_index(op.f("ix_connected_accounts_provider"), table_name="connected_accounts")
    op.drop_table("connected_accounts")
