"""Create audit_log table.

Revision ID: 009
Revises: 008
Create Date: 2026-04-08
"""

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("username", sa.String(128), nullable=False),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target_type", sa.String(64), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
        sa.Column("occurred_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
