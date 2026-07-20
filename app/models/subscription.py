"""Billing / subscription models.

MVP note: subscription history is not tracked — we keep one row per user and
update it on plan changes. Add a subscription_history table later if needed.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class SubscriptionPlan(BaseEntity):
    __tablename__ = "subscription_plans"

    plan_key: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    # Razorpay amounts are in paise (INR * 100). Null for business (custom / contact sales).
    price_inr: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Null = unlimited workspaces.
    workspace_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Null for free (no Razorpay object) and business (not self-serve).
    razorpay_plan_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    subscriptions = relationship("Subscription", back_populates="plan")


class Subscription(BaseEntity):
    """One row per user — updated in place on plan change (no history in MVP)."""

    __tablename__ = "subscriptions"
    __table_args__ = (UniqueConstraint("user_id", name="uq_subscriptions_user_id"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    plan_id: Mapped[UUID] = mapped_column(
        ForeignKey("subscription_plans.id"),
        nullable=False,
        index=True,
    )
    razorpay_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )
    # active | past_due | cancelled | expired | pending
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    plan = relationship("SubscriptionPlan", back_populates="subscriptions")
    user = relationship("User")


class PaymentEvent(BaseEntity):
    """Audit log of Razorpay webhook deliveries (idempotency + debugging)."""

    __tablename__ = "payment_events"

    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    razorpay_event_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        unique=True,
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
