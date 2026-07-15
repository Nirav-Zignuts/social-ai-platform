"""Add page_name and profile_picture_url to connected_accounts

Revision ID: e8c4b2a70d1f
Revises: c7e2a91b4d5f
Create Date: 2026-07-15 16:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e8c4b2a70d1f"
down_revision: Union[str, Sequence[str], None] = "c7e2a91b4d5f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "connected_accounts",
        sa.Column("page_name", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "connected_accounts",
        sa.Column("profile_picture_url", sa.String(length=1000), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("connected_accounts", "profile_picture_url")
    op.drop_column("connected_accounts", "page_name")
