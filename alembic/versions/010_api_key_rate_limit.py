"""Add rate_limit_per_minute column to api_keys table.

Revision ID: 010
Revises: 009
Create Date: 2026-04-08
"""

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.add_column("api_keys", sa.Column("rate_limit_per_minute", sa.Integer, nullable=True))


def downgrade() -> None:
    op.drop_column("api_keys", "rate_limit_per_minute")
