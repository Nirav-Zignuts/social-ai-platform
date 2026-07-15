from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class ConnectedAccount(BaseEntity):
    __tablename__ = "connected_accounts"
    __table_args__ = (
        UniqueConstraint("workspace_id", "provider", name="uq_connected_accounts_workspace_provider"),
    )

    workspace_id: Mapped[UUID] = mapped_column(
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    provider_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    page_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    page_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    instagram_business_account_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    profile_picture_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="connected", index=True)
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    workspace = relationship("Workspace", back_populates="connected_accounts")
