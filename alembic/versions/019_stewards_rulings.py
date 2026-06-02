"""Phase 3 — stewards_rulings table for 48h HISA submission.

Revision ID: 019
Revises: 018
Create Date: 2026-06-02
"""
revision = "019"
down_revision = "018"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table("stewards_rulings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ruling_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id"), nullable=True, index=True),
        sa.Column("horse_chip_id", sa.String, sa.ForeignKey("horses.chip_id"), nullable=True, index=True),
        sa.Column("jockey_name", sa.String(128), nullable=True),
        sa.Column("rule_violated", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("penalty", sa.String(200), nullable=True),
        sa.Column("status", sa.String(32), server_default="draft", nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("stewards_rulings")
