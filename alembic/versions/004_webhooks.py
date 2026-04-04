"""Webhook subscriptions table.

Revision ID: 004
Revises: 003
Create Date: 2026-04-04
"""

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "webhook_subscriptions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("url", sa.String(512), nullable=False),
        sa.Column("secret", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False, server_default="race.finished"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("webhook_subscriptions")
