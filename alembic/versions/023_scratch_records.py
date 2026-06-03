"""Phase 5 — scratch_records for race-day scratch management.

Revision ID: 023
Revises: 022
Create Date: 2026-06-02
"""
revision = "023"
down_revision = "022"
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table("scratch_records",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id"), nullable=False, index=True),
        sa.Column("horse_chip_id", sa.String, sa.ForeignKey("horses.chip_id"), nullable=False, index=True),
        sa.Column("scratch_type", sa.String(32), nullable=False),
        sa.Column("declared_by", sa.String(128), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("declared_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("race_id", "horse_chip_id"),
    )

def downgrade():
    op.drop_table("scratch_records")
