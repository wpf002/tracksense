"""Add jockey column to race_entries table.

Revision ID: 011b
Revises: 011
Create Date: 2026-04-09
"""

revision = "011b"
down_revision = "011"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("race_entries", sa.Column("jockey", sa.String(128), nullable=True))


def downgrade() -> None:
    op.drop_column("race_entries", "jockey")
