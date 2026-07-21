from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common.messages import AdminErrorMessages, ErrorMessages
from app.core.enums import GeneratedPostStatus, PublishingJobStatus, WorkspaceStatus
from app.models.admin_action_log import AdminActionLog
from app.models.ai_usage_log import AIUsageLog
from app.models.subscription import Subscription
from app.models.user import User
from app.repositories.admin_operations import AdminOperationsRepository
from app.services.admin_action_service import log_admin_action
from app.services.billing_service import sync_workspace_entitlement


def serialize_usage(row: AIUsageLog) -> dict:
    return {
        "id": row.id,
        "workspace_id": row.workspace_id,
        "generated_post_id": row.generated_post_id,
        "agent_purpose": row.agent_purpose,
        "provider": row.provider,
        "model": row.model,
        "prompt_tokens": row.prompt_tokens,
        "completion_tokens": row.completion_tokens,
        "total_tokens": row.total_tokens,
        "estimated_cost_usd": row.estimated_cost_usd,
        "latency_ms": row.latency_ms,
        "created_at": row.created_at,
    }


class AdminOperationsService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = AdminOperationsRepository(db)

    def list_ai_usage(
        self,
        *,
        workspace_id: UUID | None,
        agent_purpose: str | None,
        provider: str | None,
        from_date: datetime | None,
        to_date: datetime | None,
        limit: int,
        offset: int,
    ) -> dict:
        query = self.repository.ai_usage_query(
            workspace_id=workspace_id,
            agent_purpose=agent_purpose,
            provider=provider,
            from_date=from_date,
            to_date=to_date,
        )
        total = query.count()
        rows = (
            query.order_by(AIUsageLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "items": [serialize_usage(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_ai_usage_summary(self, period: str) -> dict:
        days = 7 if period == "7d" else 30
        since = datetime.now(timezone.utc) - timedelta(days=days)
        totals = self.repository.usage_totals(since)
        by_provider = self.repository.usage_by_provider(since)
        by_purpose = self.repository.usage_by_purpose(since)
        return {
            "period": period,
            "from_date": since,
            "totals": {
                "prompt_tokens": totals[0],
                "completion_tokens": totals[1],
                "total_tokens": totals[2],
                "estimated_cost_usd": totals[3],
                "calls": totals[4],
            },
            "by_provider": [
                {
                    "provider": row[0],
                    "total_tokens": row[1],
                    "estimated_cost_usd": row[2],
                    "calls": row[3],
                }
                for row in by_provider
            ],
            "by_agent_purpose": [
                {
                    "agent_purpose": row[0],
                    "total_tokens": row[1],
                    "estimated_cost_usd": row[2],
                    "calls": row[3],
                }
                for row in by_purpose
            ],
        }

    def list_users(self, search: str | None, limit: int, offset: int) -> dict:
        query = self.repository.users_query(search)
        total = query.count()
        users = (
            query.order_by(User.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        workspace_counts = self.repository.workspace_counts_by_user(
            [user.id for user in users]
        )
        return {
            "items": [
                {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "status": user.status.value,
                    "workspace_count": workspace_counts.get(user.id, 0),
                    "email_verified_at": user.email_verified_at,
                    "last_login_at": user.last_login_at,
                    "created_at": user.created_at,
                }
                for user in users
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_user_detail(self, user_id: UUID) -> dict:
        user = self.repository.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
        workspaces = self.repository.get_user_workspaces(user.id)
        subscription = self.repository.get_user_subscription(user.id)
        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "status": user.status.value,
                "email_verified_at": user.email_verified_at,
                "last_login_at": user.last_login_at,
                "created_at": user.created_at,
            },
            "workspaces": [
                {
                    "id": ws.id,
                    "name": ws.name,
                    "status": ws.status,
                    "onboarding_status": ws.onboarding_status,
                    "timezone": ws.timezone,
                    "created_at": ws.created_at,
                }
                for ws in workspaces
            ],
            "subscription": (
                {
                    "id": subscription.id,
                    "status": subscription.status,
                    "plan_key": subscription.plan.plan_key,
                    "plan_name": subscription.plan.name,
                    "workspace_limit": subscription.plan.workspace_limit,
                    "razorpay_subscription_id": subscription.razorpay_subscription_id,
                    "current_period_end": subscription.current_period_end,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                }
                if subscription and subscription.plan
                else None
            ),
        }

    def get_workspace_detail(self, workspace_id: UUID) -> dict:
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=ErrorMessages.WORKSPACE_NOT_FOUND,
            )
        profile = self.repository.get_business_profile(workspace.id)
        ai_config = self.repository.get_ai_configuration(workspace.id)
        documents = self.repository.get_knowledge_documents(workspace.id)
        posts = self.repository.get_recent_posts(workspace.id)
        jobs = self.repository.get_recent_jobs(workspace.id)
        accounts = self.repository.get_connected_accounts(workspace.id)
        usage = self.repository.get_recent_usage(workspace.id)
        return {
            "workspace": {
                "id": workspace.id,
                "owner_id": workspace.owner_id,
                "name": workspace.name,
                "slug": workspace.slug,
                "status": workspace.status,
                "onboarding_status": workspace.onboarding_status,
                "timezone": workspace.timezone,
                "preferred_post_time": workspace.preferred_post_time,
                "generation_lead_hours": workspace.generation_lead_hours,
                "last_generation_date": workspace.last_generation_date,
                "created_at": workspace.created_at,
            },
            "business_profile": (
                {
                    "business_name": profile.business_name,
                    "industry": profile.industry,
                    "description": profile.description,
                    "target_audience": profile.target_audience,
                    "brand_voice": profile.brand_voice,
                    "prohibited_words": profile.prohibited_words,
                    "required_keywords": profile.required_keywords,
                    "website_url": profile.website_url,
                }
                if profile
                else None
            ),
            "ai_configuration": (
                {
                    "content_style": ai_config.content_style,
                    "caption_length": ai_config.caption_length,
                    "hashtag_count": ai_config.hashtag_count,
                    "emoji_usage": ai_config.emoji_usage,
                    "cta_style": ai_config.cta_style,
                    "custom_instructions": ai_config.custom_instructions,
                }
                if ai_config
                else None
            ),
            "knowledge_documents": {
                "count": len(documents),
                "by_status": {
                    value: sum(1 for doc in documents if doc.status == value)
                    for value in sorted({doc.status for doc in documents})
                },
            },
            "recent_generated_posts": [
                {
                    "id": post.id,
                    "generation_cycle_id": post.generation_cycle_id,
                    "content_type": post.content_type,
                    "status": post.status.value,
                    "reviewer_score": post.reviewer_score,
                    "regenerate_count": post.regenerate_count,
                    "scheduled_for": post.scheduled_for,
                    "created_at": post.created_at,
                }
                for post in posts
            ],
            "recent_publishing_jobs": [
                {
                    "id": job.id,
                    "post_id": job.post_id,
                    "status": job.status.value,
                    "attempt_count": job.attempt_count,
                    "last_error": job.last_error,
                    "published_at": job.published_at,
                    "created_at": job.created_at,
                }
                for job in jobs
            ],
            "instagram_connections": [
                {
                    "id": account.id,
                    "provider": account.provider,
                    "provider_username": account.provider_username,
                    "display_name": account.display_name,
                    "status": account.status,
                    "expires_at": account.expires_at,
                    "connected_at": account.connected_at,
                    "last_sync_at": account.last_sync_at,
                }
                for account in accounts
            ],
            "recent_ai_usage": [serialize_usage(row) for row in usage],
        }

    def get_generation_runs(self, workspace_id: UUID, limit: int) -> dict:
        if not self.repository.get_workspace(workspace_id):
            raise HTTPException(
                status_code=404,
                detail=ErrorMessages.WORKSPACE_NOT_FOUND,
            )
        posts = self.repository.get_recent_posts(workspace_id, limit)
        return {
            "items": [
                {
                    "generation_cycle_id": post.generation_cycle_id,
                    "post_id": post.id,
                    "status": post.status.value,
                    "reviewer_score": post.reviewer_score,
                    "reviewer_notes": post.reviewer_notes,
                    "regenerate_count": post.regenerate_count,
                    "created_at": post.created_at,
                    "updated_at": post.updated_at,
                }
                for post in posts
            ]
        }

    def set_user_plan(
        self,
        user_id: UUID,
        plan_key: str,
        reason: str,
        admin_id: UUID,
    ) -> dict:
        user = self.repository.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
        plan = self.repository.get_plan(plan_key.strip().lower())
        if not plan:
            raise HTTPException(
                status_code=404,
                detail=AdminErrorMessages.PLAN_NOT_FOUND,
            )
        subscription = self.repository.get_user_subscription(user.id)
        before = None
        if subscription:
            before = {
                "plan_id": str(subscription.plan_id),
                "status": subscription.status,
                "razorpay_subscription_id": subscription.razorpay_subscription_id,
            }
            subscription.plan_id = plan.id
            subscription.status = "active"
            subscription.razorpay_subscription_id = None
            subscription.current_period_end = None
            subscription.cancel_at_period_end = False
        else:
            subscription = Subscription(
                user_id=user.id,
                plan_id=plan.id,
                status="active",
                cancel_at_period_end=False,
            )
            self.repository.add(subscription)
        self.db.flush()
        sync_result = sync_workspace_entitlement(self.db, user.id, notify=False)
        log_admin_action(
            self.db,
            admin_id=admin_id,
            action_type="set_plan",
            target_type="user",
            target_id=user.id,
            reason=reason,
            payload_snapshot={
                "before": before,
                "after": {"plan_key": plan.plan_key, "status": "active"},
                "workspace_sync": sync_result,
            },
        )
        self.db.commit()
        self.db.refresh(subscription)
        return {
            "subscription_id": subscription.id,
            "plan_key": plan.plan_key,
            "status": subscription.status,
            "workspace_sync": sync_result,
        }

    def force_subscription_status(
        self,
        subscription_id: UUID,
        status: str,
        reason: str,
        admin_id: UUID,
    ) -> dict:
        subscription = self.repository.get_subscription(subscription_id)
        if not subscription:
            raise HTTPException(
                status_code=404,
                detail=AdminErrorMessages.SUBSCRIPTION_NOT_FOUND,
            )
        previous_status = subscription.status
        subscription.status = status
        self.db.flush()
        sync_result = sync_workspace_entitlement(
            self.db,
            subscription.user_id,
            notify=False,
        )
        log_admin_action(
            self.db,
            admin_id=admin_id,
            action_type="force_subscription_status",
            target_type="subscription",
            target_id=subscription.id,
            reason=reason,
            payload_snapshot={
                "before": {"status": previous_status},
                "after": {"status": status},
                "workspace_sync": sync_result,
            },
        )
        self.db.commit()
        return {
            "subscription_id": subscription.id,
            "status": subscription.status,
            "workspace_sync": sync_result,
        }

    def unlock_workspace(
        self,
        workspace_id: UUID,
        reason: str,
        admin_id: UUID,
    ) -> dict:
        workspace = self.repository.get_workspace(workspace_id)
        if not workspace:
            raise HTTPException(
                status_code=404,
                detail=ErrorMessages.WORKSPACE_NOT_FOUND,
            )
        previous_status = workspace.status
        workspace.status = WorkspaceStatus.ACTIVE.value
        log_admin_action(
            self.db,
            admin_id=admin_id,
            action_type="unlock_workspace",
            target_type="workspace",
            target_id=workspace.id,
            reason=reason,
            payload_snapshot={
                "before": {"status": previous_status},
                "after": {"status": workspace.status},
                "bypassed_plan_limit": True,
            },
        )
        self.db.commit()
        return {"workspace_id": workspace.id, "status": workspace.status}

    def prepare_publish_retry(
        self,
        job_id: UUID,
        reason: str,
        admin_id: UUID,
    ) -> dict:
        job = self.repository.get_publishing_job(job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail=AdminErrorMessages.PUBLISHING_JOB_NOT_FOUND,
            )
        if job.status not in {
            PublishingJobStatus.FAILED,
            PublishingJobStatus.RETRYING,
        }:
            raise HTTPException(
                status_code=400,
                detail=AdminErrorMessages.PUBLISH_JOB_NOT_RETRYABLE,
            )
        post = self.repository.get_post_for_update(job.post_id)
        if not post or post.is_deleted:
            raise HTTPException(
                status_code=404,
                detail=AdminErrorMessages.GENERATED_POST_NOT_FOUND,
            )
        workspace = self.repository.get_workspace(post.workspace_id)
        if not workspace or workspace.status != WorkspaceStatus.ACTIVE.value:
            raise HTTPException(
                status_code=400,
                detail=AdminErrorMessages.WORKSPACE_MUST_BE_ACTIVE,
            )
        if self.repository.get_active_publish_job(post.id, job.id):
            raise HTTPException(
                status_code=409,
                detail=AdminErrorMessages.PUBLISH_ALREADY_ACTIVE,
            )
        if post.status == GeneratedPostStatus.PUBLISHED:
            raise HTTPException(
                status_code=409,
                detail=AdminErrorMessages.POST_ALREADY_PUBLISHED,
            )
        previous_post_status = post.status.value
        post.status = GeneratedPostStatus.APPROVED
        log_admin_action(
            self.db,
            admin_id=admin_id,
            action_type="retry_publishing_job",
            target_type="publishing_job",
            target_id=job.id,
            reason=reason,
            payload_snapshot={
                "job_status": job.status.value,
                "job_attempt_count": job.attempt_count,
                "post_id": str(post.id),
                "previous_post_status": previous_post_status,
            },
        )
        self.db.commit()
        return {"job_id": job.id, "post_id": post.id, "status": "queued"}

    def list_action_logs(
        self,
        action_type: str | None,
        target_type: str | None,
        limit: int,
        offset: int,
    ) -> dict:
        query = self.repository.action_logs_query(action_type, target_type)
        total = query.count()
        rows = (
            query.order_by(AdminActionLog.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return {
            "items": [
                {
                    "id": row.id,
                    "admin_id": row.admin_id,
                    "action_type": row.action_type,
                    "target_type": row.target_type,
                    "target_id": row.target_id,
                    "reason": row.reason,
                    "payload_snapshot": row.payload_snapshot,
                    "created_at": row.created_at,
                }
                for row in rows
            ],
            "total": total,
            "limit": limit,
            "offset": offset,
        }
