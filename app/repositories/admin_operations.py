from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.enums import PublishingJobStatus
from app.models.admin_action_log import AdminActionLog
from app.models.ai_configuration import AIConfiguration
from app.models.ai_usage_log import AIUsageLog
from app.models.business_profile import BusinessProfile
from app.models.connected_account import ConnectedAccount
from app.models.generated_post import GeneratedPost
from app.models.knowledge_document import KnowledgeDocument
from app.models.publishing_job import PublishingJob
from app.models.subscription import Subscription, SubscriptionPlan
from app.models.user import User
from app.models.workspace import Workspace


class AdminOperationsRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, entity) -> None:
        self.db.add(entity)

    def ai_usage_query(
        self,
        *,
        workspace_id: UUID | None,
        agent_purpose: str | None,
        provider: str | None,
        from_date: datetime | None,
        to_date: datetime | None,
    ):
        query = self.db.query(AIUsageLog).filter(AIUsageLog.is_deleted.is_(False))
        if workspace_id:
            query = query.filter(AIUsageLog.workspace_id == workspace_id)
        if agent_purpose:
            query = query.filter(AIUsageLog.agent_purpose == agent_purpose)
        if provider:
            query = query.filter(AIUsageLog.provider == provider)
        if from_date:
            query = query.filter(AIUsageLog.created_at >= from_date)
        if to_date:
            query = query.filter(AIUsageLog.created_at <= to_date)
        return query

    def usage_totals(self, since: datetime):
        return (
            self.db.query(
                func.coalesce(func.sum(AIUsageLog.prompt_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.completion_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.total_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0),
                func.count(AIUsageLog.id),
            )
            .filter(
                AIUsageLog.created_at >= since,
                AIUsageLog.is_deleted.is_(False),
            )
            .one()
        )

    def usage_by_provider(self, since: datetime):
        return (
            self.db.query(
                AIUsageLog.provider,
                func.coalesce(func.sum(AIUsageLog.total_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0),
                func.count(AIUsageLog.id),
            )
            .filter(
                AIUsageLog.created_at >= since,
                AIUsageLog.is_deleted.is_(False),
            )
            .group_by(AIUsageLog.provider)
            .all()
        )

    def usage_by_purpose(self, since: datetime):
        return (
            self.db.query(
                AIUsageLog.agent_purpose,
                func.coalesce(func.sum(AIUsageLog.total_tokens), 0),
                func.coalesce(func.sum(AIUsageLog.estimated_cost_usd), 0),
                func.count(AIUsageLog.id),
            )
            .filter(
                AIUsageLog.created_at >= since,
                AIUsageLog.is_deleted.is_(False),
            )
            .group_by(AIUsageLog.agent_purpose)
            .all()
        )

    def users_query(self, search: str | None = None):
        query = self.db.query(User).filter(User.is_deleted.is_(False))
        if search:
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(User.email.ilike(term), User.full_name.ilike(term))
            )
        return query

    def workspace_counts_by_user(self, user_ids: list[UUID]) -> dict[UUID, int]:
        if not user_ids:
            return {}
        rows = (
            self.db.query(Workspace.owner_id, func.count(Workspace.id))
            .filter(
                Workspace.owner_id.in_(user_ids),
                Workspace.is_deleted.is_(False),
            )
            .group_by(Workspace.owner_id)
            .all()
        )
        return {owner_id: count for owner_id, count in rows}

    def get_user(self, user_id: UUID) -> User | None:
        return (
            self.db.query(User)
            .filter(User.id == user_id, User.is_deleted.is_(False))
            .first()
        )

    def get_user_workspaces(self, user_id: UUID) -> list[Workspace]:
        return (
            self.db.query(Workspace)
            .filter(
                Workspace.owner_id == user_id,
                Workspace.is_deleted.is_(False),
            )
            .order_by(Workspace.created_at.desc())
            .all()
        )

    def get_user_subscription(self, user_id: UUID) -> Subscription | None:
        return (
            self.db.query(Subscription)
            .options(joinedload(Subscription.plan))
            .filter(
                Subscription.user_id == user_id,
                Subscription.is_deleted.is_(False),
            )
            .first()
        )

    def get_workspace(self, workspace_id: UUID) -> Workspace | None:
        return (
            self.db.query(Workspace)
            .filter(
                Workspace.id == workspace_id,
                Workspace.is_deleted.is_(False),
            )
            .first()
        )

    def get_business_profile(self, workspace_id: UUID) -> BusinessProfile | None:
        return (
            self.db.query(BusinessProfile)
            .filter(BusinessProfile.workspace_id == workspace_id)
            .first()
        )

    def get_ai_configuration(self, workspace_id: UUID) -> AIConfiguration | None:
        return (
            self.db.query(AIConfiguration)
            .filter(AIConfiguration.workspace_id == workspace_id)
            .first()
        )

    def get_knowledge_documents(self, workspace_id: UUID):
        return (
            self.db.query(KnowledgeDocument)
            .filter(
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.is_deleted.is_(False),
            )
            .all()
        )

    def get_recent_posts(self, workspace_id: UUID, limit: int = 20):
        return (
            self.db.query(GeneratedPost)
            .filter(
                GeneratedPost.workspace_id == workspace_id,
                GeneratedPost.is_deleted.is_(False),
            )
            .order_by(GeneratedPost.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_recent_jobs(self, workspace_id: UUID, limit: int = 20):
        return (
            self.db.query(PublishingJob)
            .filter(
                PublishingJob.workspace_id == workspace_id,
                PublishingJob.is_deleted.is_(False),
            )
            .order_by(PublishingJob.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_connected_accounts(self, workspace_id: UUID):
        return (
            self.db.query(ConnectedAccount)
            .filter(
                ConnectedAccount.workspace_id == workspace_id,
                ConnectedAccount.is_deleted.is_(False),
            )
            .all()
        )

    def get_recent_usage(self, workspace_id: UUID, limit: int = 20):
        return (
            self.db.query(AIUsageLog)
            .filter(
                AIUsageLog.workspace_id == workspace_id,
                AIUsageLog.is_deleted.is_(False),
            )
            .order_by(AIUsageLog.created_at.desc())
            .limit(limit)
            .all()
        )

    def get_plan(self, plan_key: str) -> SubscriptionPlan | None:
        return (
            self.db.query(SubscriptionPlan)
            .filter(
                SubscriptionPlan.plan_key == plan_key,
                SubscriptionPlan.is_active.is_(True),
                SubscriptionPlan.is_deleted.is_(False),
            )
            .first()
        )

    def get_subscription(self, subscription_id: UUID) -> Subscription | None:
        subscription = self.db.get(Subscription, subscription_id)
        return subscription if subscription and not subscription.is_deleted else None

    def get_publishing_job(self, job_id: UUID) -> PublishingJob | None:
        job = self.db.get(PublishingJob, job_id)
        return job if job and not job.is_deleted else None

    def get_post_for_update(self, post_id: UUID) -> GeneratedPost | None:
        return (
            self.db.query(GeneratedPost)
            .filter(GeneratedPost.id == post_id)
            .with_for_update()
            .first()
        )

    def get_active_publish_job(
        self,
        post_id: UUID,
        excluded_job_id: UUID,
    ) -> PublishingJob | None:
        return (
            self.db.query(PublishingJob)
            .filter(
                PublishingJob.post_id == post_id,
                PublishingJob.id != excluded_job_id,
                PublishingJob.status.in_(
                    [
                        PublishingJobStatus.PROCESSING,
                        PublishingJobStatus.PUBLISHED,
                    ]
                ),
            )
            .first()
        )

    def action_logs_query(
        self,
        action_type: str | None,
        target_type: str | None,
    ):
        query = self.db.query(AdminActionLog).filter(
            AdminActionLog.is_deleted.is_(False)
        )
        if action_type:
            query = query.filter(AdminActionLog.action_type == action_type)
        if target_type:
            query = query.filter(AdminActionLog.target_type == target_type)
        return query
