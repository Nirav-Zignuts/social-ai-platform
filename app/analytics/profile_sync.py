"""Daily Instagram profile metrics snapshot sync."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, time, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx

from app.core.enums import ConnectedAccountStatus, SocialProvider, WorkspaceStatus
from app.db.session import SessionLocal
from app.generation.scheduler import get_workspace_local_now
from app.integrations.meta.exceptions import InstagramTokenExpiredError, MetaIntegrationError
from app.integrations.meta.service import MetaService
from app.models.connected_account import ConnectedAccount
from app.models.profile_metric_snapshot import ProfileMetricSnapshot
from app.models.workspace import Workspace
from app.publishing.token import get_valid_token

logger = logging.getLogger(__name__)


def _workspace_day_bounds(workspace: Workspace, local_today) -> tuple[datetime, datetime]:
    tz = ZoneInfo(workspace.timezone or "UTC")
    start_local = datetime.combine(local_today, time.min, tzinfo=tz)
    end_local = datetime.combine(local_today, time.max, tzinfo=tz)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


def _get_snapshot_for_local_day(db, workspace: Workspace, local_today):
    """Return today's snapshot row if one already exists (workspace-local day)."""
    start_utc, end_utc = _workspace_day_bounds(workspace, local_today)
    return (
        db.query(ProfileMetricSnapshot)
        .filter(
            ProfileMetricSnapshot.workspace_id == workspace.id,
            ProfileMetricSnapshot.recorded_at >= start_utc,
            ProfileMetricSnapshot.recorded_at <= end_utc,
        )
        .order_by(ProfileMetricSnapshot.recorded_at.desc())
        .first()
    )


def upsert_today_profile_snapshot(
    db,
    workspace: Workspace,
    *,
    followers_count: int,
    follows_count: int,
    media_count: int,
    account: ConnectedAccount | None = None,
    source: str = "cron",
) -> tuple[ProfileMetricSnapshot, str]:
    """
    Create or update today's profile snapshot (one row per workspace-local day).
    Does not commit — caller owns the transaction.
    """
    local_today = get_workspace_local_now(workspace).date()
    existing = _get_snapshot_for_local_day(db, workspace, local_today)
    now = datetime.now(timezone.utc)
    followers = int(followers_count or 0)
    follows = int(follows_count or 0)
    media = int(media_count or 0)

    if existing:
        old_followers = existing.followers_count
        existing.followers_count = followers
        existing.follows_count = follows
        existing.media_count = media
        existing.recorded_at = now
        db.add(existing)
        action = "updated"
        snapshot = existing
    else:
        snapshot = ProfileMetricSnapshot(
            workspace_id=workspace.id,
            followers_count=followers,
            follows_count=follows,
            media_count=media,
            recorded_at=now,
        )
        db.add(snapshot)
        action = "created"

    if account is not None:
        account.last_sync_at = now
        db.add(account)

    return snapshot, action


async def _sync_profile_metrics_async(workspace_id: str) -> dict:
    db = SessionLocal()
    meta_service = MetaService()
    try:
        wid = UUID(workspace_id)
        workspace = (
            db.query(Workspace)
            .filter(
                Workspace.id == wid,
                Workspace.is_deleted.is_(False),
                Workspace.status == WorkspaceStatus.ACTIVE.value,
            )
            .first()
        )
        if not workspace:
            return {"status": "skipped", "reason": "workspace_not_found"}

        local_today = get_workspace_local_now(workspace).date()
        existing = _get_snapshot_for_local_day(db, workspace, local_today)

        try:
            account = get_valid_token(db, wid)
        except InstagramTokenExpiredError as exc:
            logger.warning("profile_sync skip workspace=%s: %s", workspace_id, exc)
            return {"status": "skipped", "reason": "token_invalid"}

        try:
            profile = await meta_service.get_instagram_profile(
                account.instagram_business_account_id,
                account.access_token,
            )
        except MetaIntegrationError as exc:
            logger.warning("profile_sync failed workspace=%s: %s", workspace_id, exc)
            return {"status": "failed", "reason": str(exc)}
        except httpx.HTTPError as exc:
            logger.warning(
                "profile_sync network error workspace=%s: %r",
                workspace_id,
                exc,
            )
            return {"status": "failed", "reason": f"network_error: {type(exc).__name__}"}

        snapshot, action = upsert_today_profile_snapshot(
            db,
            workspace,
            followers_count=int(profile.followers_count or 0),
            follows_count=int(profile.follows_count or 0),
            media_count=int(profile.media_count or 0),
            account=account,
            source="cron",
        )
        db.commit()
        logger.info(
            "profile_sync ok workspace=%s action=%s followers=%s",
            workspace_id,
            action,
            snapshot.followers_count,
        )
        return {
            "status": "synced",
            "action": action,
            "followers_count": snapshot.followers_count,
        }
    except Exception as exc:
        logger.exception("profile_sync unexpected error workspace=%s", workspace_id)
        return {"status": "failed", "reason": str(exc) or type(exc).__name__}
    finally:
        db.close()


def sync_profile_metrics_for_workspace(workspace_id: str) -> dict:
    """Sync entry point for BackgroundTasks (sync wrapper)."""
    try:
        return asyncio.run(_sync_profile_metrics_async(workspace_id))
    except Exception as exc:
        logger.exception("profile_sync crashed workspace=%s", workspace_id)
        return {"status": "failed", "reason": str(exc) or type(exc).__name__}


def poll_profile_sync() -> dict:
    """
    Find active workspaces with connected Instagram accounts.

    Caller should schedule sync_profile_metrics_for_workspace per workspace id.
    """
    db = SessionLocal()
    try:
        rows = (
            db.query(Workspace.id)
            .join(ConnectedAccount, ConnectedAccount.workspace_id == Workspace.id)
            .filter(
                Workspace.status == WorkspaceStatus.ACTIVE.value,
                Workspace.is_deleted.is_(False),
                ConnectedAccount.provider == SocialProvider.INSTAGRAM.value,
                ConnectedAccount.status == ConnectedAccountStatus.CONNECTED.value,
                ConnectedAccount.is_deleted.is_(False),
            )
            .distinct()
            .all()
        )
        workspace_ids = [str(row[0]) for row in rows]
        logger.info("poll_profile_sync found %s workspaces", len(workspace_ids))
        return {"enqueued": len(workspace_ids), "workspace_ids": workspace_ids}
    finally:
        db.close()
