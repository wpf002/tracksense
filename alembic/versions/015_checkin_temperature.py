"""Add temperature_c to checkin_records for thermal chip scanning.

Revision ID: 015
Revises: 014
Create Date: 2026-04-09
"""

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column(
        "checkin_records",
        sa.Column("temperature_c", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("checkin_records", "temperature_c")
