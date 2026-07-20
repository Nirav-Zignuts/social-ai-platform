"""Account-level billing: checkout, cancel, webhooks, workspace entitlement."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session, joinedload

from app.core.config import settings
from app.core.enums import NotificationChannel, NotificationType, WorkspaceStatus
from app.models.subscription import PaymentEvent, Subscription, SubscriptionPlan
from app.models.user import User
from app.models.workspace import Workspace
from app.payments.razorpay_client import get_razorpay_client
from app.services.notification_service import create_notification, send_email_notification

logger = logging.getLogger(__name__)

# Statuses that still entitle the user to their paid plan's workspace limit.
# past_due keeps access while payment recovery is in progress (do not silent-downgrade).
ENTITLED_STATUSES = frozenset({"active", "past_due"})

# Razorpay requires total_count even for "indefinite" renewals.
# 120 ≈ 10 years of monthly cycles — practical stand-in until cancelled.
RAZORPAY_SUBSCRIPTION_TOTAL_COUNT = 120

SELF_SERVE_PLAN_KEYS = frozenset({"pro"})


def get_free_plan(db: Session) -> SubscriptionPlan:
    plan = (
        db.query(SubscriptionPlan)
        .filter(
            SubscriptionPlan.plan_key == "free",
            SubscriptionPlan.is_deleted.is_(False),
        )
        .first()
    )
    if not plan:
        raise HTTPException(status_code=500, detail="Free plan is not configured.")
    return plan


def get_user_subscription(db: Session, user_id: UUID) -> Subscription | None:
    return (
        db.query(Subscription)
        .options(joinedload(Subscription.plan))
        .filter(
            Subscription.user_id == user_id,
            Subscription.is_deleted.is_(False),
        )
        .first()
    )


def get_effective_entitlement(
    db: Session,
    user_id: UUID,
) -> tuple[SubscriptionPlan, Subscription | None]:
    """
    Resolve the plan that currently governs workspace limits.

    - No subscription row → Free plan (default state, not an error).
    - active / past_due → that plan (past_due keeps access during payment recovery).
    - cancelled / expired / pending → Free plan for limits (locks apply after cancel webhook).
    """
    free = get_free_plan(db)
    sub = get_user_subscription(db, user_id)
    if not sub or not sub.plan:
        return free, None

    if sub.status in ENTITLED_STATUSES:
        return sub.plan, sub

    return free, sub


def get_user_workspace_limit(user_id: UUID, db: Session) -> int | None:
    """Return workspace_limit for the user (None = unlimited)."""
    plan, _ = get_effective_entitlement(db, user_id)
    return plan.workspace_limit


def count_user_workspaces(db: Session, user_id: UUID) -> int:
    return (
        db.query(Workspace)
        .filter(
            Workspace.owner_id == user_id,
            Workspace.is_deleted.is_(False),
            Workspace.status != WorkspaceStatus.DELETED.value,
        )
        .count()
    )


def _list_user_workspaces(db: Session, user_id: UUID) -> list[Workspace]:
    return (
        db.query(Workspace)
        .filter(
            Workspace.owner_id == user_id,
            Workspace.is_deleted.is_(False),
            Workspace.status != WorkspaceStatus.DELETED.value,
        )
        .order_by(Workspace.created_at.desc())
        .all()
    )


def sync_workspace_entitlement(
    db: Session,
    user_id: UUID,
    *,
    notify: bool = True,
) -> dict:
    """
    Align workspace statuses with the user's effective plan limit.

    - Unlimited plan → unlock all locked_over_limit workspaces.
    - Finite limit → keep up to `limit` workspaces active (newest first if auto),
      lock the rest as locked_over_limit.
    """
    plan, _sub = get_effective_entitlement(db, user_id)
    limit = plan.workspace_limit
    workspaces = _list_user_workspaces(db, user_id)

    if limit is None:
        unlocked = 0
        for ws in workspaces:
            if ws.status == WorkspaceStatus.LOCKED_OVER_LIMIT.value:
                ws.status = WorkspaceStatus.ACTIVE.value
                db.add(ws)
                unlocked += 1
        if unlocked:
            db.flush()
        return {
            "action": "unlocked_all",
            "active": len(workspaces),
            "locked": 0,
            "limit": None,
        }

    # Prefer keeping already-active workspaces; fill remaining slots with newest locked ones.
    active = [w for w in workspaces if w.status == WorkspaceStatus.ACTIVE.value]
    locked = [w for w in workspaces if w.status == WorkspaceStatus.LOCKED_OVER_LIMIT.value]
    other = [
        w
        for w in workspaces
        if w.status
        not in (
            WorkspaceStatus.ACTIVE.value,
            WorkspaceStatus.LOCKED_OVER_LIMIT.value,
        )
    ]

    keep: list[Workspace] = []
    # Newest-first among currently active.
    active_sorted = sorted(active, key=lambda w: w.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    keep.extend(active_sorted[:limit])
    if len(keep) < limit:
        locked_sorted = sorted(
            locked,
            key=lambda w: w.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        for w in locked_sorted:
            if len(keep) >= limit:
                break
            keep.append(w)
    if len(keep) < limit:
        for w in other:
            if len(keep) >= limit:
                break
            keep.append(w)

    keep_ids = {w.id for w in keep}
    newly_locked = 0
    for ws in workspaces:
        if ws.id in keep_ids:
            if ws.status != WorkspaceStatus.ACTIVE.value:
                ws.status = WorkspaceStatus.ACTIVE.value
                db.add(ws)
        else:
            if ws.status != WorkspaceStatus.LOCKED_OVER_LIMIT.value:
                ws.status = WorkspaceStatus.LOCKED_OVER_LIMIT.value
                db.add(ws)
                newly_locked += 1

    db.flush()

    locked_count = sum(
        1 for w in workspaces if w.status == WorkspaceStatus.LOCKED_OVER_LIMIT.value
    )
    active_count = sum(1 for w in workspaces if w.status == WorkspaceStatus.ACTIVE.value)

    if notify and newly_locked > 0:
        _notify_workspaces_locked(db, user_id, newly_locked=newly_locked, limit=limit)

    return {
        "action": "synced",
        "active": active_count,
        "locked": locked_count,
        "limit": limit,
        "newly_locked": newly_locked,
    }


def assert_can_create_workspace(db: Session, user_id: UUID) -> None:
    limit = get_user_workspace_limit(user_id, db)
    if limit is None:
        return
    current = count_user_workspaces(db, user_id)
    if current >= limit:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Workspace limit reached ({current}/{limit}). "
                "Upgrade your plan or delete a workspace to create more."
            ),
        )


class BillingService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _get_user(self, user_id: UUID) -> User:
        user = (
            self.db.query(User)
            .filter(User.id == user_id, User.is_deleted.is_(False))
            .first()
        )
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    def get_status(self, user_id: UUID) -> dict:
        plan, sub = get_effective_entitlement(self.db, user_id)
        workspaces = _list_user_workspaces(self.db, user_id)
        workspace_count = len(workspaces)
        active_count = sum(
            1 for w in workspaces if w.status == WorkspaceStatus.ACTIVE.value
        )
        locked_count = sum(
            1 for w in workspaces if w.status == WorkspaceStatus.LOCKED_OVER_LIMIT.value
        )
        period_end = None
        if sub and sub.current_period_end:
            period_end = sub.current_period_end.isoformat()

        limit = plan.workspace_limit
        needs_selection = bool(
            limit is not None and (locked_count > 0 or active_count > limit)
        )

        return {
            "plan": {
                "plan_key": plan.plan_key,
                "name": plan.name,
                "price_inr": plan.price_inr,
                "workspace_limit": plan.workspace_limit,
            },
            "status": sub.status if sub else "active",
            "current_period_end": period_end,
            "cancel_at_period_end": bool(sub.cancel_at_period_end) if sub else False,
            "workspace_count": workspace_count,
            "workspace_limit": plan.workspace_limit,
            "active_workspace_count": active_count,
            "locked_workspace_count": locked_count,
            "needs_workspace_selection": needs_selection,
            "razorpay_subscription_id": (
                sub.razorpay_subscription_id if sub else None
            ),
        }

    def select_active_workspaces(
        self,
        user_id: UUID,
        workspace_ids: list[UUID],
    ) -> dict:
        """
        FE: user picks which workspaces stay active under the current plan limit.
        All other owned workspaces become locked_over_limit.
        """
        plan, _sub = get_effective_entitlement(self.db, user_id)
        limit = plan.workspace_limit
        if limit is None:
            # Unlimited — just unlock everything.
            result = sync_workspace_entitlement(self.db, user_id, notify=False)
            self.db.commit()
            return {
                "active_workspace_ids": [str(w.id) for w in _list_user_workspaces(self.db, user_id)],
                "locked_workspace_ids": [],
                **result,
            }

        # Dedupe while preserving order
        seen: set[UUID] = set()
        unique_ids: list[UUID] = []
        for wid in workspace_ids:
            if wid not in seen:
                seen.add(wid)
                unique_ids.append(wid)

        if len(unique_ids) < 1:
            raise HTTPException(
                status_code=400,
                detail="Select at least one workspace to keep active.",
            )
        if len(unique_ids) > limit:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"You can keep at most {limit} workspace(s) active on the "
                    f"{plan.name} plan. Received {len(unique_ids)}."
                ),
            )

        owned = _list_user_workspaces(self.db, user_id)
        owned_by_id = {w.id: w for w in owned}
        missing = [str(i) for i in unique_ids if i not in owned_by_id]
        if missing:
            raise HTTPException(
                status_code=404,
                detail=f"Workspace(s) not found or not owned: {', '.join(missing)}",
            )

        keep_ids = set(unique_ids)
        for ws in owned:
            if ws.id in keep_ids:
                ws.status = WorkspaceStatus.ACTIVE.value
            else:
                ws.status = WorkspaceStatus.LOCKED_OVER_LIMIT.value
            self.db.add(ws)

        self.db.commit()

        return {
            "active_workspace_ids": [str(i) for i in unique_ids],
            "locked_workspace_ids": [
                str(w.id) for w in owned if w.id not in keep_ids
            ],
            "active": len(unique_ids),
            "locked": len(owned) - len(unique_ids),
            "limit": limit,
        }

    def create_checkout(self, user_id: UUID, plan_key: str) -> dict:
        key = (plan_key or "").strip().lower()
        if key == "free":
            raise HTTPException(
                status_code=400,
                detail="Free plan does not require payment. It is the default.",
            )
        if key == "business":
            raise HTTPException(
                status_code=400,
                detail="Business plan is contact-sales only and cannot be purchased via checkout.",
            )
        if key not in SELF_SERVE_PLAN_KEYS:
            raise HTTPException(status_code=400, detail=f"Unknown plan_key '{plan_key}'.")

        plan = (
            self.db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.plan_key == key,
                SubscriptionPlan.is_deleted.is_(False),
                SubscriptionPlan.is_active.is_(True),
            )
            .first()
        )
        if not plan:
            raise HTTPException(status_code=404, detail="Plan not found")
        if not plan.razorpay_plan_id:
            raise HTTPException(
                status_code=503,
                detail=(
                    "This plan is not linked to Razorpay yet. "
                    "Set subscription_plans.razorpay_plan_id for Pro after creating the plan "
                    "in the Razorpay dashboard."
                ),
            )

        user = self._get_user(user_id)
        existing = get_user_subscription(self.db, user_id)
        if (
            existing
            and existing.status in ENTITLED_STATUSES
            and existing.plan
            and existing.plan.plan_key == key
            and not existing.cancel_at_period_end
        ):
            raise HTTPException(
                status_code=400,
                detail="You are already subscribed to this plan.",
            )

        client = get_razorpay_client()
        # total_count: Razorpay requires a finite cycle count; 120 ≈ 10 years monthly.
        rz_payload = {
            "plan_id": plan.razorpay_plan_id,
            "total_count": RAZORPAY_SUBSCRIPTION_TOTAL_COUNT,
            "customer_notify": 1,
            "notes": {
                "user_id": str(user_id),
                "plan_key": key,
            },
        }
        try:
            rz_sub = client.subscription.create(rz_payload)
        except Exception as exc:
            logger.exception("Razorpay subscription.create failed user=%s", user_id)
            raise HTTPException(
                status_code=502,
                detail="Failed to create Razorpay subscription.",
            ) from exc

        rz_sub_id = rz_sub.get("id")
        if not rz_sub_id:
            raise HTTPException(status_code=502, detail="Razorpay returned no subscription id.")

        # Do NOT mark active here — wait for subscription.activated webhook.
        if existing:
            existing.plan_id = plan.id
            existing.razorpay_subscription_id = rz_sub_id
            existing.status = "pending"
            existing.cancel_at_period_end = False
            existing.current_period_end = None
            self.db.add(existing)
        else:
            existing = Subscription(
                user_id=user_id,
                plan_id=plan.id,
                razorpay_subscription_id=rz_sub_id,
                status="pending",
                cancel_at_period_end=False,
            )
            self.db.add(existing)

        self.db.commit()
        self.db.refresh(existing)

        return {
            "subscription_id": rz_sub_id,
            "key_id": settings.RAZORPAY_KEY_ID,
            "plan_key": plan.plan_key,
            "plan_name": plan.name,
            "prefill": {
                "name": user.full_name,
                "email": user.email,
            },
        }

    def cancel_subscription(self, user_id: UUID, *, immediate: bool = False) -> dict:
        sub = get_user_subscription(self.db, user_id)
        if not sub or not sub.razorpay_subscription_id:
            raise HTTPException(status_code=400, detail="No cancellable paid subscription found.")
        if sub.status in ("cancelled", "expired"):
            raise HTTPException(status_code=400, detail="Subscription is already cancelled.")
        if sub.plan and sub.plan.plan_key == "free":
            raise HTTPException(status_code=400, detail="Free plan cannot be cancelled.")

        client = get_razorpay_client()
        try:
            # Default: cancel_at_cycle_end — keep access through paid period.
            client.subscription.cancel(
                sub.razorpay_subscription_id,
                {"cancel_at_cycle_end": 0 if immediate else 1},
            )
        except Exception as exc:
            logger.exception(
                "Razorpay subscription.cancel failed user=%s sub=%s",
                user_id,
                sub.razorpay_subscription_id,
            )
            raise HTTPException(
                status_code=502,
                detail="Failed to cancel Razorpay subscription.",
            ) from exc

        if immediate:
            sub.status = "cancelled"
            sub.cancel_at_period_end = False
            # Period ended / immediate — apply free-plan workspace locks now.
            sync_workspace_entitlement(self.db, user_id, notify=True)
        else:
            sub.cancel_at_period_end = True
            # status stays active/past_due until webhook confirms at period end

        self.db.add(sub)
        self.db.commit()
        self.db.refresh(sub)

        return {
            "status": sub.status,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "current_period_end": (
                sub.current_period_end.isoformat() if sub.current_period_end else None
            ),
        }

    # ── Webhooks ──────────────────────────────────────────────────────────

    def verify_and_handle_webhook(
        self,
        *,
        raw_body: bytes,
        signature: str | None,
        event_id_header: str | None,
    ) -> dict:
        """
        Verify signature, persist audit row, process known events idempotently.
        Always designed so the route can return 200 after this returns (or on soft failure).
        """
        secret = (settings.RAZORPAY_WEBHOOK_SECRET or "").strip()
        if not secret:
            logger.error("RAZORPAY_WEBHOOK_SECRET is not configured")
            raise HTTPException(status_code=503, detail="Webhook secret is not configured")

        if not signature:
            raise HTTPException(status_code=400, detail="Missing X-Razorpay-Signature")

        body_text = raw_body.decode("utf-8")
        client = get_razorpay_client()
        try:
            client.utility.verify_webhook_signature(body_text, signature, secret)
        except Exception:
            logger.warning("Razorpay webhook signature verification failed")
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

        import json

        try:
            payload = json.loads(body_text)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON body") from exc

        event_type = str(payload.get("event") or "unknown")
        razorpay_event_id = (event_id_header or "").strip() or None
        if not razorpay_event_id:
            # Fallback idempotency key when header is absent.
            created_at = payload.get("created_at")
            sub_entity = _subscription_entity(payload)
            sub_id = (sub_entity or {}).get("id")
            if created_at and sub_id:
                razorpay_event_id = f"{event_type}:{sub_id}:{created_at}"

        if razorpay_event_id:
            existing = (
                self.db.query(PaymentEvent)
                .filter(PaymentEvent.razorpay_event_id == razorpay_event_id)
                .first()
            )
            if existing and existing.processed_at is not None:
                return {"status": "duplicate", "event": event_type}
            if existing and existing.processed_at is None:
                # Already inserted but not finished — retry processing safely.
                event_row = existing
            else:
                event_row = None
        else:
            event_row = None

        sub_entity = _subscription_entity(payload)
        user_id = _resolve_user_id(self.db, sub_entity, payload)

        if event_row is None:
            event_row = PaymentEvent(
                user_id=user_id,
                razorpay_event_id=razorpay_event_id,
                event_type=event_type,
                raw_payload=payload,
            )
            self.db.add(event_row)
            try:
                self.db.commit()
                self.db.refresh(event_row)
            except Exception:
                self.db.rollback()
                # Race on unique razorpay_event_id — treat as duplicate.
                if razorpay_event_id:
                    dup = (
                        self.db.query(PaymentEvent)
                        .filter(PaymentEvent.razorpay_event_id == razorpay_event_id)
                        .first()
                    )
                    if dup and dup.processed_at is not None:
                        return {"status": "duplicate", "event": event_type}
                    if dup:
                        event_row = dup
                    else:
                        raise
                else:
                    raise

        try:
            self._process_event(event_type, sub_entity, user_id, payload)
            event_row.processed_at = datetime.now(timezone.utc)
            if user_id and event_row.user_id is None:
                event_row.user_id = user_id
            self.db.add(event_row)
            self.db.commit()
        except Exception:
            self.db.rollback()
            logger.exception(
                "Webhook processing failed event=%s event_id=%s",
                event_type,
                razorpay_event_id,
            )
            # Still return success to caller so route can 200 — Razorpay retries otherwise.
            return {"status": "accepted_with_error", "event": event_type}

        return {"status": "processed", "event": event_type}

    def _process_event(
        self,
        event_type: str,
        sub_entity: dict | None,
        user_id: UUID | None,
        payload: dict,
    ) -> None:
        if event_type not in {
            "subscription.activated",
            "subscription.charged",
            "subscription.pending",
            "subscription.halted",
            "subscription.cancelled",
            "subscription.completed",
        }:
            logger.info("Ignoring unhandled Razorpay event type=%s", event_type)
            return

        if not sub_entity or not sub_entity.get("id"):
            logger.warning("Webhook %s missing subscription entity", event_type)
            return

        rz_sub_id = sub_entity["id"]
        sub = (
            self.db.query(Subscription)
            .options(joinedload(Subscription.plan))
            .filter(Subscription.razorpay_subscription_id == rz_sub_id)
            .first()
        )
        if not sub:
            # Try notes.user_id create/update path
            if user_id:
                sub = get_user_subscription(self.db, user_id)
            if not sub:
                logger.warning(
                    "No local subscription for razorpay_subscription_id=%s",
                    rz_sub_id,
                )
                return
            sub.razorpay_subscription_id = rz_sub_id

        period_end = _period_end_from_entity(sub_entity)

        if event_type == "subscription.activated":
            sub.status = "active"
            sub.cancel_at_period_end = False
            if period_end:
                sub.current_period_end = period_end
            self.db.add(sub)
            self.db.flush()
            # Paid plan restored — unlock any locked_over_limit workspaces.
            sync_workspace_entitlement(self.db, sub.user_id, notify=False)
        elif event_type == "subscription.charged":
            if sub.status not in ("cancelled", "expired"):
                sub.status = "active"
            if period_end:
                sub.current_period_end = period_end
            self.db.add(sub)
            self.db.flush()
            sync_workspace_entitlement(self.db, sub.user_id, notify=False)
        elif event_type in ("subscription.pending", "subscription.halted"):
            sub.status = "past_due"
            self.db.add(sub)
            self.db.flush()
            _notify_payment_failed(self.db, sub.user_id)
        elif event_type == "subscription.cancelled":
            sub.status = "cancelled"
            sub.cancel_at_period_end = False
            if period_end:
                sub.current_period_end = period_end
            self.db.add(sub)
            self.db.flush()
            # Downgrade to free entitlement → lock excess workspaces.
            sync_workspace_entitlement(self.db, sub.user_id, notify=True)
        elif event_type == "subscription.completed":
            # All billed cycles finished — treat like expiry.
            sub.status = "expired"
            sub.cancel_at_period_end = False
            self.db.add(sub)
            self.db.flush()
            sync_workspace_entitlement(self.db, sub.user_id, notify=True)

    def list_payment_events(
        self,
        *,
        user_id: UUID | None = None,
        event_types: list[str] | None = None,
        processed: bool | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        page: int = 1,
        page_size: int = 25,
    ) -> dict:
        """Return paginated payment events with optional filters.

        Filters are ANDed. Pagination uses 1-based `page` and `page_size`.
        """
        q = self.db.query(PaymentEvent)

        if user_id is not None:
            q = q.filter(PaymentEvent.user_id == user_id)
        if event_types:
            q = q.filter(PaymentEvent.event_type.in_(event_types))
        if processed is True:
            q = q.filter(PaymentEvent.processed_at.isnot(None))
        elif processed is False:
            q = q.filter(PaymentEvent.processed_at.is_(None))
        if date_from is not None:
            q = q.filter(PaymentEvent.created_at >= date_from)
        if date_to is not None:
            q = q.filter(PaymentEvent.created_at <= date_to)

        total = q.count()
        if page < 1:
            page = 1
        if page_size < 1:
            page_size = 25
        offset = (page - 1) * page_size

        items = (
            q.order_by(PaymentEvent.created_at.desc())
            .offset(offset)
            .limit(page_size)
            .all()
        )

        def serialize(ev: PaymentEvent) -> dict:
            payload = ev.raw_payload or {}

            def find_dict_with_keys(obj: object, keys: set[str]) -> dict | None:
                """Recursively find a dict that contains any of the keys in `keys`.

                Returns the first matching dict found, or None.
                """
                if isinstance(obj, dict):
                    if keys.intersection(obj.keys()):
                        return obj
                    for v in obj.values():
                        found = find_dict_with_keys(v, keys)
                        if found:
                            return found
                elif isinstance(obj, list):
                    for item in obj:
                        found = find_dict_with_keys(item, keys)
                        if found:
                            return found
                return None

            # potential locations
            sub_entity = find_dict_with_keys(payload.get("payload", {}), {"subscription"})
            if isinstance(sub_entity, dict):
                # subscription entity may be nested under 'subscription'->'entity'
                sub_entity = sub_entity.get("subscription", {}).get("entity") or sub_entity.get("entity") or sub_entity

            pay_entity = find_dict_with_keys(payload.get("payload", {}), {"payment", "payment_method", "payment_entity", "payment_details"})
            if isinstance(pay_entity, dict):
                # normalize to entity dict if present
                pay_entity = pay_entity.get("payment", {}).get("entity") or pay_entity.get("entity") or pay_entity

            name = None
            status = None
            entity = None
            payment_method = None
            amount = None
            currency = None

            if isinstance(sub_entity, dict):
                entity = {k: v for k, v in sub_entity.items() if k in ("id", "current_end", "end_at", "status", "notes")}
                notes = sub_entity.get("notes") if isinstance(sub_entity.get("notes"), dict) else {}
                name = notes.get("plan_key") or notes.get("plan_name")
                status = sub_entity.get("status")

            # Try many places for payment/card info
            card_obj = None
            # common direct payment entity
            if isinstance(pay_entity, dict):
                card_obj = pay_entity.get("card") or pay_entity.get("method_details") or pay_entity.get("payment_method") or pay_entity

            # fallback: subscription entity may embed payment info (e.g., last_payment)
            if not card_obj and isinstance(sub_entity, dict):
                card_obj = sub_entity.get("last_payment") or sub_entity.get("last_invoice") or sub_entity.get("payment")

            # deep search for any dict that looks like a card (contains keys like last4, issuer, network)
            if not card_obj:
                card_obj = find_dict_with_keys(payload, {"last4", "last4_digits", "issuer", "network", "card", "method"})

            if isinstance(card_obj, dict):
                payment_method = {}
                # method may be top-level key
                if card_obj.get("method"):
                    payment_method["method"] = card_obj.get("method")
                # card-specific fields
                last4 = (
                    card_obj.get("last4")
                    or card_obj.get("last4_digits")
                    or card_obj.get("last4digits")
                    or card_obj.get("last4digit")
                )
                if last4:
                    payment_method["number"] = f"**** **** **** {str(last4)}"
                elif card_obj.get("number"):
                    payment_method["number"] = card_obj.get("number")
                for k in ("type", "issuer", "network"):
                    if card_obj.get(k):
                        payment_method[k] = card_obj.get(k)

                # also capture any masked number formats seen in some payloads
                if not payment_method.get("number"):
                    masked = card_obj.get("masked") or card_obj.get("masked_card")
                    if masked:
                        payment_method["number"] = masked

                # amount/currency may be present on the card/payment object
                if amount is None:
                    for ak in ("amount", "amount_paid", "amount_due", "amount_paid_in_paise", "amount_in_paise", "paid_amount"):
                        if card_obj.get(ak) is not None:
                            amount = card_obj.get(ak)
                            break
                if currency is None:
                    currency = card_obj.get("currency") or card_obj.get("currency_code")

            # If still missing, search anywhere in payload for amount/currency keys
            if amount is None or currency is None:
                found_amt = find_dict_with_keys(payload, {"amount", "amount_paid", "amount_due", "amount_in_paise", "paid_amount", "currency", "currency_code"})
                if isinstance(found_amt, dict):
                    if amount is None:
                        for ak in ("amount", "amount_paid", "amount_due", "amount_paid_in_paise", "amount_in_paise", "paid_amount"):
                            if found_amt.get(ak) is not None:
                                amount = found_amt.get(ak)
                                break
                    if currency is None:
                        currency = found_amt.get("currency") or found_amt.get("currency_code")

            # final fallbacks for name/status
            if not name:
                try:
                    notes = (
                        payload.get("payload", {}).get("subscription", {}).get("entity", {}).get("notes", {})
                    )
                    if isinstance(notes, dict):
                        name = notes.get("plan_key") or notes.get("plan_name")
                except Exception:
                    pass
            if not status:
                status = ev.event_type

            return {
                "id": str(ev.id),
                "user_id": str(ev.user_id) if ev.user_id else None,
                "razorpay_event_id": ev.razorpay_event_id,
                "event_type": ev.event_type,
                "name": name,
                "status": status,
                "entity": entity,
                "payment_method": payment_method,
                "amount": amount,
                "currency": currency,
                "processed_at": (ev.processed_at.isoformat() if ev.processed_at else None),
                "created_at": (ev.created_at.isoformat() if ev.created_at else None),
                "raw_payload": None,
            }

        total_pages = (total + page_size - 1) // page_size if page_size else 1

        return {
            "items": [serialize(i) for i in items],
            "total_items": total,
            "current_page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }


def _subscription_entity(payload: dict) -> dict | None:
    try:
        entity = payload["payload"]["subscription"]["entity"]
        return entity if isinstance(entity, dict) else None
    except (KeyError, TypeError):
        return None


def _resolve_user_id(
    db: Session,
    sub_entity: dict | None,
    payload: dict,
) -> UUID | None:
    notes = {}
    if sub_entity and isinstance(sub_entity.get("notes"), dict):
        notes = sub_entity["notes"]
    raw = notes.get("user_id")
    if raw:
        try:
            return UUID(str(raw))
        except (TypeError, ValueError):
            pass

    rz_sub_id = (sub_entity or {}).get("id")
    if rz_sub_id:
        sub = (
            db.query(Subscription)
            .filter(Subscription.razorpay_subscription_id == rz_sub_id)
            .first()
        )
        if sub:
            return sub.user_id
    return None


def _period_end_from_entity(entity: dict) -> datetime | None:
    # Razorpay uses unix seconds in current_end / charge_at / end_at depending on event.
    for key in ("current_end", "end_at", "charge_at"):
        raw = entity.get(key)
        if raw is None:
            continue
        try:
            ts = int(raw)
            if ts > 0:
                return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            continue
    return None


def _notify_payment_failed(db: Session, user_id: UUID) -> None:
    """Best-effort in-app + email warning; never raise into webhook path."""
    try:
        workspace = (
            db.query(Workspace)
            .filter(
                Workspace.owner_id == user_id,
                Workspace.is_deleted.is_(False),
            )
            .order_by(Workspace.created_at.asc())
            .first()
        )
        if not workspace:
            logger.info(
                "payment_failed notify skipped — user=%s has no workspace",
                user_id,
            )
            return

        create_notification(
            user_id=user_id,
            workspace_id=workspace.id,
            post_id=None,
            notification_type=NotificationType.BILLING_PAYMENT_FAILED,
            channel=NotificationChannel.IN_APP,
            db=db,
        )
        email_notification = create_notification(
            user_id=user_id,
            workspace_id=workspace.id,
            post_id=None,
            notification_type=NotificationType.BILLING_PAYMENT_FAILED,
            channel=NotificationChannel.EMAIL,
            db=db,
        )
        send_email_notification(email_notification, db=db)
    except Exception:
        logger.exception("Failed to send billing payment-failed notification user=%s", user_id)


def _notify_workspaces_locked(
    db: Session,
    user_id: UUID,
    *,
    newly_locked: int,
    limit: int,
) -> None:
    try:
        workspace = (
            db.query(Workspace)
            .filter(
                Workspace.owner_id == user_id,
                Workspace.is_deleted.is_(False),
            )
            .order_by(Workspace.created_at.asc())
            .first()
        )
        if not workspace:
            return
        extra = {
            "newly_locked": newly_locked,
            "workspace_limit": limit,
            "message": (
                f"{newly_locked} workspace(s) were locked because your plan allows "
                f"only {limit} active workspace(s). Choose which to keep active in Billing."
            ),
        }
        create_notification(
            user_id=user_id,
            workspace_id=workspace.id,
            post_id=None,
            notification_type=NotificationType.BILLING_WORKSPACES_LOCKED,
            channel=NotificationChannel.IN_APP,
            db=db,
            extra_payload=extra,
        )
        email_notification = create_notification(
            user_id=user_id,
            workspace_id=workspace.id,
            post_id=None,
            notification_type=NotificationType.BILLING_WORKSPACES_LOCKED,
            channel=NotificationChannel.EMAIL,
            db=db,
            extra_payload=extra,
        )
        send_email_notification(email_notification, db=db)
    except Exception:
        logger.exception("Failed to send workspaces-locked notification user=%s", user_id)
