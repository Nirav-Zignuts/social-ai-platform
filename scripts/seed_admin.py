"""One-off admin seed. Usage: python scripts/seed_admin.py EMAIL [FULL_NAME]."""

import sys

from email_validator import validate_email

from app.db.session import SessionLocal
from app.models.admin import Admin


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: python scripts/seed_admin.py EMAIL [FULL_NAME]")
    email = validate_email(sys.argv[1], check_deliverability=False).normalized.lower()
    full_name = sys.argv[2].strip() if len(sys.argv) > 2 else None

    with SessionLocal() as db:
        existing = db.query(Admin).filter(Admin.email == email).first()
        if existing:
            existing.full_name = full_name or existing.full_name
            existing.is_active = True
            existing.is_deleted = False
            db.commit()
            print(f"Reactivated existing admin: {email}")
            return
        db.add(Admin(email=email, full_name=full_name))
        db.commit()
        print(f"Created admin: {email}")


if __name__ == "__main__":
    main()
