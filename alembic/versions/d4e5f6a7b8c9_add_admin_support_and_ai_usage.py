"""Add admin auth, support enquiries, AI usage and admin audit tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, Sequence[str], None] = "a9b1c2d3e4f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    ]


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        *_base_columns(),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_admins_email", "admins", ["email"], unique=True)

    op.create_table(
        "admin_otp_codes",
        sa.Column("admin_id", sa.UUID(), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "consumed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        *_base_columns(),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_admin_otp_codes_admin_id",
        "admin_otp_codes",
        ["admin_id"],
    )
    op.create_index(
        "ix_admin_otp_codes_expires_at",
        "admin_otp_codes",
        ["expires_at"],
    )

    op.create_table(
        "contact_enquiries",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("plan_interest", sa.String(length=20), nullable=True),
        sa.Column(
            "enquiry_type",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'sales'"),
        ),
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'new'"),
        ),
        sa.Column("admin_notes", sa.Text(), nullable=True),
        sa.Column("handled_by", sa.UUID(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(["handled_by"], ["admins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_contact_enquiries_email",
        "contact_enquiries",
        ["email"],
    )
    op.create_index(
        "ix_contact_enquiries_enquiry_type",
        "contact_enquiries",
        ["enquiry_type"],
    )
    op.create_index(
        "ix_contact_enquiries_user_id",
        "contact_enquiries",
        ["user_id"],
    )
    op.create_index(
        "ix_contact_enquiries_status",
        "contact_enquiries",
        ["status"],
    )
    op.create_index(
        "ix_contact_enquiries_handled_by",
        "contact_enquiries",
        ["handled_by"],
    )

    op.create_table(
        "ai_usage_logs",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("generated_post_id", sa.UUID(), nullable=True),
        sa.Column("agent_purpose", sa.String(length=30), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("estimated_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(
            ["generated_post_id"],
            ["generated_posts.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"],
            ["workspaces.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_ai_usage_logs_workspace_id",
        "ai_usage_logs",
        ["workspace_id"],
    )
    op.create_index(
        "ix_ai_usage_logs_generated_post_id",
        "ai_usage_logs",
        ["generated_post_id"],
    )
    op.create_index(
        "ix_ai_usage_logs_agent_purpose",
        "ai_usage_logs",
        ["agent_purpose"],
    )
    op.create_index(
        "ix_ai_usage_logs_provider",
        "ai_usage_logs",
        ["provider"],
    )

    op.create_table(
        "admin_action_logs",
        sa.Column("admin_id", sa.UUID(), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("payload_snapshot", postgresql.JSONB(), nullable=True),
        *_base_columns(),
        sa.ForeignKeyConstraint(
            ["admin_id"],
            ["admins.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_admin_action_logs_admin_id",
        "admin_action_logs",
        ["admin_id"],
    )
    op.create_index(
        "ix_admin_action_logs_action_type",
        "admin_action_logs",
        ["action_type"],
    )
    op.create_index(
        "ix_admin_action_logs_target_type",
        "admin_action_logs",
        ["target_type"],
    )
    op.create_index(
        "ix_admin_action_logs_target_id",
        "admin_action_logs",
        ["target_id"],
    )


def downgrade() -> None:
    op.drop_table("admin_action_logs")
    op.drop_table("ai_usage_logs")
    op.drop_table("contact_enquiries")
    op.drop_table("admin_otp_codes")
    op.drop_table("admins")
