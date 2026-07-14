"""Add generation_lead_hours and last_generation_date to workspaces

Revision ID: a3c7e9f41b2d
Revises: f2a8d3e91c5b
Create Date: 2026-07-13 14:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a3c7e9f41b2d"
down_revision: Union[str, Sequence[str], None] = "f2a8d3e91c5b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workspaces",
        sa.Column(
            "generation_lead_hours",
            sa.Integer(),
            server_default="12",
            nullable=False,
        ),
    )
    op.add_column(
        "workspaces",
        sa.Column("last_generation_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("workspaces", "last_generation_date")
    op.drop_column("workspaces", "generation_lead_hours")
