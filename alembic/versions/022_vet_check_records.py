"""Phase 4 — vet_check_records for training center structured barn checks.

Revision ID: 022
Revises: 021
Create Date: 2026-06-02
"""
revision = "022"
down_revision = "021"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table("vet_check_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("horse_chip_id", sa.String, sa.ForeignKey("horses.chip_id"), nullable=False, index=True),
        sa.Column("check_date", sa.String(10), nullable=False),
        sa.Column("check_type", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("vet_name", sa.String(128), nullable=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id"), nullable=True, index=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("vet_check_records")
