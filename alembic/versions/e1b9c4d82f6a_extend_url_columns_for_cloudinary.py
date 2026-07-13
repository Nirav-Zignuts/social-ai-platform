"""Extend file_path and image_url for Cloudinary URLs

Revision ID: e1b9c4d82f6a
Revises: d7f3a1b92e4c
Create Date: 2026-07-09 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "e1b9c4d82f6a"
down_revision: Union[str, Sequence[str], None] = "d7f3a1b92e4c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "knowledge_documents",
        "file_path",
        existing_type=sa.String(length=500),
        type_=sa.String(length=1000),
        existing_nullable=False,
    )
    op.alter_column(
        "generated_posts",
        "image_url",
        existing_type=sa.String(length=500),
        type_=sa.String(length=1000),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "generated_posts",
        "image_url",
        existing_type=sa.String(length=1000),
        type_=sa.String(length=500),
        existing_nullable=True,
    )
    op.alter_column(
        "knowledge_documents",
        "file_path",
        existing_type=sa.String(length=1000),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
