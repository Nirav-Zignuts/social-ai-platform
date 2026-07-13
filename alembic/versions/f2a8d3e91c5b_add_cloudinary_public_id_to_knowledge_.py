"""Add cloudinary_public_id to knowledge_documents

Revision ID: f2a8d3e91c5b
Revises: e1b9c4d82f6a
Create Date: 2026-07-09 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f2a8d3e91c5b"
down_revision: Union[str, Sequence[str], None] = "e1b9c4d82f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "knowledge_documents",
        sa.Column("cloudinary_public_id", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("knowledge_documents", "cloudinary_public_id")
