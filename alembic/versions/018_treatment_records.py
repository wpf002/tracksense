"""Phase 3 — treatment_records table for ADMC medication records.

Revision ID: 018
Revises: 017
Create Date: 2026-06-02
"""
revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table("treatment_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("horse_chip_id", sa.String, sa.ForeignKey("horses.chip_id"), nullable=False, index=True),
        sa.Column("treatment_date", sa.String(10), nullable=False),
        sa.Column("substance", sa.String(200), nullable=False),
        sa.Column("dose", sa.String(100), nullable=True),
        sa.Column("route", sa.String(100), nullable=True),
        sa.Column("withdrawal_time_hours", sa.Integer, nullable=True),
        sa.Column("prescribed_by", sa.String(128), nullable=True),
        sa.Column("administered_by", sa.String(128), nullable=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id"), nullable=True, index=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("is_prohibited", sa.Boolean, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("treatment_records")
