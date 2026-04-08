"""Add racing_api_horse_id column to horses table.

Revision ID: 008
Revises: 007
Create Date: 2026-04-08
"""

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("horses", sa.Column("racing_api_horse_id", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("horses", "racing_api_horse_id")
