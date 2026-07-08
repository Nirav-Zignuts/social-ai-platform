from typing import Optional
from sqlalchemy import String, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid import UUID

from app.common.models import BaseEntity
from app.core.enums import PostReviewAction

class PostReview(BaseEntity):
    __tablename__ = "post_reviews"
    
    # We do not need updated_at for an append-only log. 
    # But since it's inherited from BaseEntity, let's keep it but it won't change.
    # Alternatively, we could override updated_at to be ignored, but BaseEntity 
    # enforces it. That's fine, we will just not update it.
    # The prompt says: "no updated_at needed since this is append-only — override BaseEntity if it forces updated_at, or just ignore that column for this table".
    # I will ignore it.

    post_id: Mapped[UUID] = mapped_column(
        ForeignKey("generated_posts.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    reviewed_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True
    )
    
    action: Mapped[PostReviewAction] = mapped_column(
        SQLEnum(PostReviewAction, name="post_review_action"),
        nullable=False
    )
    feedback: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    edited_caption: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Relationships
    post = relationship("GeneratedPost", back_populates="reviews")
    # belongs to User (no back-reference needed on User)
    user = relationship("User")
