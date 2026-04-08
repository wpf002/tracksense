"""Add name column to races table.

Revision ID: 007
Revises: 006
Create Date: 2026-04-08
"""

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("races", sa.Column("name", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("races", "name")
