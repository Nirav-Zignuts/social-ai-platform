"""Add post_insights table for Instagram engagement metrics

Revision ID: b4d8f0a52c3e
Revises: a3c7e9f41b2d
Create Date: 2026-07-13 15:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "b4d8f0a52c3e"
down_revision: Union[str, Sequence[str], None] = "a3c7e9f41b2d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_insights",
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("ig_media_id", sa.String(length=255), nullable=False),
        sa.Column("permalink", sa.String(length=1000), nullable=True),
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("saved_count", sa.Integer(), nullable=True),
        sa.Column("shares_count", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("total_interactions", sa.Integer(), nullable=True),
        sa.Column("profile_visits", sa.Integer(), nullable=True),
        sa.Column("raw_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["post_id"], ["generated_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id"),
    )
    op.create_index(op.f("ix_post_insights_ig_media_id"), "post_insights", ["ig_media_id"])
    op.create_index(op.f("ix_post_insights_post_id"), "post_insights", ["post_id"])
    op.create_index(op.f("ix_post_insights_workspace_id"), "post_insights", ["workspace_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_post_insights_workspace_id"), table_name="post_insights")
    op.drop_index(op.f("ix_post_insights_post_id"), table_name="post_insights")
    op.drop_index(op.f("ix_post_insights_ig_media_id"), table_name="post_insights")
    op.drop_table("post_insights")
