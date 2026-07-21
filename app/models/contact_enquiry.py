from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.models import BaseEntity


class ContactEnquiry(BaseEntity):
    __tablename__ = "contact_enquiries"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    plan_interest: Mapped[str | None] = mapped_column(String(20), nullable=True)
    enquiry_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="sales",
        server_default=text("'sales'"),
        index=True,
    )
    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="new",
        server_default=text("'new'"),
        index=True,
    )
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    handled_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("admins.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    handler = relationship("Admin")
    user = relationship("User")
