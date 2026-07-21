from datetime import datetime

from sqlalchemy.orm import Session

from app.models.admin import Admin, AdminOTPCode


class AdminAuthRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_active_by_email(
        self,
        email: str,
        *,
        for_update: bool = False,
    ) -> Admin | None:
        query = self.db.query(Admin).filter(
            Admin.email == email,
            Admin.is_active.is_(True),
            Admin.is_deleted.is_(False),
        )
        if for_update:
            query = query.with_for_update()
        return query.first()

    def count_codes_since(self, admin_id, since: datetime) -> int:
        return (
            self.db.query(AdminOTPCode)
            .filter(
                AdminOTPCode.admin_id == admin_id,
                AdminOTPCode.created_at >= since,
            )
            .count()
        )

    def consume_active_codes(self, admin_id) -> None:
        (
            self.db.query(AdminOTPCode)
            .filter(
                AdminOTPCode.admin_id == admin_id,
                AdminOTPCode.consumed.is_(False),
            )
            .update({"consumed": True}, synchronize_session=False)
        )

    def add_code(self, otp: AdminOTPCode) -> None:
        self.db.add(otp)

    def get_latest_valid_code(
        self,
        admin_id,
        now: datetime,
    ) -> AdminOTPCode | None:
        return (
            self.db.query(AdminOTPCode)
            .filter(
                AdminOTPCode.admin_id == admin_id,
                AdminOTPCode.consumed.is_(False),
                AdminOTPCode.expires_at > now,
            )
            .order_by(AdminOTPCode.created_at.desc())
            .with_for_update()
            .first()
        )
