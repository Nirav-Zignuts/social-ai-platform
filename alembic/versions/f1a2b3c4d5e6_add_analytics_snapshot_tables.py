"""Add profile_metric_snapshots and post_insight_snapshots tables."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "e8c4b2a70d1f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "profile_metric_snapshots",
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("followers_count", sa.Integer(), nullable=False),
        sa.Column("follows_count", sa.Integer(), nullable=False),
        sa.Column("media_count", sa.Integer(), nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
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
    )
    op.create_index(
        "ix_profile_metric_snapshots_workspace_recorded",
        "profile_metric_snapshots",
        ["workspace_id", "recorded_at"],
    )
    op.create_index(
        op.f("ix_profile_metric_snapshots_workspace_id"),
        "profile_metric_snapshots",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_profile_metric_snapshots_recorded_at"),
        "profile_metric_snapshots",
        ["recorded_at"],
    )

    op.create_table(
        "post_insight_snapshots",
        sa.Column("post_id", sa.UUID(), nullable=False),
        sa.Column("workspace_id", sa.UUID(), nullable=False),
        sa.Column("like_count", sa.Integer(), nullable=True),
        sa.Column("comments_count", sa.Integer(), nullable=True),
        sa.Column("saved_count", sa.Integer(), nullable=True),
        sa.Column("shares_count", sa.Integer(), nullable=True),
        sa.Column("reach", sa.Integer(), nullable=True),
        sa.Column("views", sa.Integer(), nullable=True),
        sa.Column("total_interactions", sa.Integer(), nullable=True),
        sa.Column("profile_visits", sa.Integer(), nullable=True),
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
    )
    op.create_index(
        "ix_post_insight_snapshots_post_fetched",
        "post_insight_snapshots",
        ["post_id", "fetched_at"],
    )
    op.create_index(
        "ix_post_insight_snapshots_workspace_fetched",
        "post_insight_snapshots",
        ["workspace_id", "fetched_at"],
    )
    op.create_index(
        op.f("ix_post_insight_snapshots_post_id"),
        "post_insight_snapshots",
        ["post_id"],
    )
    op.create_index(
        op.f("ix_post_insight_snapshots_workspace_id"),
        "post_insight_snapshots",
        ["workspace_id"],
    )
    op.create_index(
        op.f("ix_post_insight_snapshots_fetched_at"),
        "post_insight_snapshots",
        ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_post_insight_snapshots_fetched_at"),
        table_name="post_insight_snapshots",
    )
    op.drop_index(
        op.f("ix_post_insight_snapshots_workspace_id"),
        table_name="post_insight_snapshots",
    )
    op.drop_index(
        op.f("ix_post_insight_snapshots_post_id"),
        table_name="post_insight_snapshots",
    )
    op.drop_index(
        "ix_post_insight_snapshots_workspace_fetched",
        table_name="post_insight_snapshots",
    )
    op.drop_index(
        "ix_post_insight_snapshots_post_fetched",
        table_name="post_insight_snapshots",
    )
    op.drop_table("post_insight_snapshots")

    op.drop_index(
        op.f("ix_profile_metric_snapshots_recorded_at"),
        table_name="profile_metric_snapshots",
    )
    op.drop_index(
        op.f("ix_profile_metric_snapshots_workspace_id"),
        table_name="profile_metric_snapshots",
    )
    op.drop_index(
        "ix_profile_metric_snapshots_workspace_recorded",
        table_name="profile_metric_snapshots",
    )
    op.drop_table("profile_metric_snapshots")
