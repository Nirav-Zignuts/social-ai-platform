"""Add subscription_plans, subscriptions, payment_events + seed plans."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "a9b1c2d3e4f5"
down_revision: Union[str, Sequence[str], None] = "f1a2b3c4d5e6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscription_plans",
        sa.Column("plan_key", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("price_inr", sa.Integer(), nullable=True),
        sa.Column("workspace_limit", sa.Integer(), nullable=True),
        sa.Column("razorpay_plan_id", sa.String(length=100), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plan_key"),
    )
    op.create_index(
        op.f("ix_subscription_plans_plan_key"),
        "subscription_plans",
        ["plan_key"],
        unique=False,
    )

    op.create_table(
        "subscriptions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("razorpay_subscription_id", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cancel_at_period_end",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.ForeignKeyConstraint(["plan_id"], ["subscription_plans.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_subscriptions_user_id"),
        sa.UniqueConstraint("razorpay_subscription_id"),
    )
    op.create_index(op.f("ix_subscriptions_user_id"), "subscriptions", ["user_id"], unique=False)
    op.create_index(op.f("ix_subscriptions_plan_id"), "subscriptions", ["plan_id"], unique=False)
    op.create_index(
        op.f("ix_subscriptions_razorpay_subscription_id"),
        "subscriptions",
        ["razorpay_subscription_id"],
        unique=False,
    )

    op.create_table(
        "payment_events",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("razorpay_event_id", sa.String(length=100), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("razorpay_event_id"),
    )
    op.create_index(op.f("ix_payment_events_user_id"), "payment_events", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_payment_events_razorpay_event_id"),
        "payment_events",
        ["razorpay_event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_payment_events_event_type"),
        "payment_events",
        ["event_type"],
        unique=False,
    )

    # Data seed — backend source of truth for Free / Pro / Business.
    # razorpay_plan_id for Pro is filled later via env/ops after creating the plan in Razorpay.
    op.execute(
        sa.text(
            """
            INSERT INTO subscription_plans (
                id, plan_key, name, price_inr, workspace_limit, razorpay_plan_id,
                is_active, is_deleted, created_at, updated_at
            ) VALUES
            (
                gen_random_uuid(), 'free', 'Free', 0, 2, NULL,
                true, false, now(), now()
            ),
            (
                gen_random_uuid(), 'pro', 'Pro', 99900, 10, NULL,
                true, false, now(), now()
            ),
            (
                gen_random_uuid(), 'business', 'Business', NULL, NULL, NULL,
                true, false, now(), now()
            )
            """
        )
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_payment_events_event_type"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_razorpay_event_id"), table_name="payment_events")
    op.drop_index(op.f("ix_payment_events_user_id"), table_name="payment_events")
    op.drop_table("payment_events")

    op.drop_index(op.f("ix_subscriptions_razorpay_subscription_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_plan_id"), table_name="subscriptions")
    op.drop_index(op.f("ix_subscriptions_user_id"), table_name="subscriptions")
    op.drop_table("subscriptions")

    op.drop_index(op.f("ix_subscription_plans_plan_key"), table_name="subscription_plans")
    op.drop_table("subscription_plans")
