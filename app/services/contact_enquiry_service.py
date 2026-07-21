from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.common.messages import AdminErrorMessages, ErrorMessages
from app.models.contact_enquiry import ContactEnquiry
from app.repositories.contact_enquiry import ContactEnquiryRepository
from app.repositories.user import UserRepository


def serialize_enquiry(row: ContactEnquiry) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "email": row.email,
        "company_name": row.company_name,
        "message": row.message,
        "plan_interest": row.plan_interest,
        "enquiry_type": row.enquiry_type,
        "user_id": row.user_id,
        "status": row.status,
        "admin_notes": row.admin_notes,
        "handled_by": row.handled_by,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


class ContactEnquiryService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = ContactEnquiryRepository(db)
        self.user_repository = UserRepository(db)

    def submit_sales_enquiry(self, payload) -> None:
        self.repository.add(
            ContactEnquiry(
                name=payload.name.strip(),
                email=str(payload.email).strip().lower(),
                company_name=(
                    payload.company_name.strip() if payload.company_name else None
                ),
                message=payload.message.strip(),
                plan_interest=payload.plan_interest,
                enquiry_type="sales",
            )
        )
        self.db.commit()

    def submit_support_issue(self, user_id: UUID, message: str) -> None:
        user = self.user_repository.get_by_id(user_id)
        if not user or user.is_deleted:
            raise HTTPException(status_code=404, detail=ErrorMessages.USER_NOT_FOUND)
        self.repository.add(
            ContactEnquiry(
                name=user.full_name,
                email=user.email.strip().lower(),
                message=message.strip(),
                enquiry_type="support",
                user_id=user.id,
            )
        )
        self.db.commit()

    def list_enquiries(
        self,
        *,
        status: str | None,
        enquiry_type: str | None,
        sort_order: str,
        limit: int,
        offset: int,
    ) -> dict:
        query = self.repository.list_query(
            status=status,
            enquiry_type=enquiry_type,
        )
        total = query.count()
        ordering = (
            ContactEnquiry.created_at.asc()
            if sort_order == "asc"
            else ContactEnquiry.created_at.desc()
        )
        rows = query.order_by(ordering).offset(offset).limit(limit).all()
        return {
            "items": [serialize_enquiry(row) for row in rows],
            "total": total,
            "limit": limit,
            "offset": offset,
        }

    def get_enquiry(self, enquiry_id: UUID) -> dict:
        row = self.repository.get_active_by_id(enquiry_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail=AdminErrorMessages.ENQUIRY_NOT_FOUND,
            )
        return serialize_enquiry(row)

    def update_enquiry(self, enquiry_id: UUID, payload, admin_id: UUID) -> dict:
        row = self.repository.get_active_by_id(enquiry_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail=AdminErrorMessages.ENQUIRY_NOT_FOUND,
            )
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(row, key, value)
        row.handled_by = admin_id
        self.db.commit()
        self.db.refresh(row)
        return serialize_enquiry(row)

    def delete_enquiry(self, enquiry_id: UUID) -> None:
        row = self.repository.get_active_by_id(enquiry_id)
        if not row:
            raise HTTPException(
                status_code=404,
                detail=AdminErrorMessages.ENQUIRY_NOT_FOUND,
            )
        self.repository.remove(row)
        self.db.commit()
