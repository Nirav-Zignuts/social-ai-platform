from uuid import UUID

from sqlalchemy.orm import Query, Session

from app.models.contact_enquiry import ContactEnquiry
from app.repositories.base import BaseRepository


class ContactEnquiryRepository(BaseRepository[ContactEnquiry]):
    model = ContactEnquiry

    def list_query(
        self,
        *,
        status: str | None = None,
        enquiry_type: str | None = None,
    ) -> Query:
        query = self.db.query(self.model).filter(
            self.model.is_deleted.is_(False)
        )
        if status:
            query = query.filter(self.model.status == status)
        if enquiry_type:
            query = query.filter(self.model.enquiry_type == enquiry_type)
        return query

    def get_active_by_id(self, enquiry_id: UUID) -> ContactEnquiry | None:
        return (
            self.db.query(self.model)
            .filter(
                self.model.id == enquiry_id,
                self.model.is_deleted.is_(False),
            )
            .first()
        )

    def add(self, enquiry: ContactEnquiry) -> ContactEnquiry:
        self.db.add(enquiry)
        return enquiry

    def remove(self, enquiry: ContactEnquiry) -> None:
        self.db.delete(enquiry)
