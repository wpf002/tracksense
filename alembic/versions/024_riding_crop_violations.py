"""Phase 5 — riding_crop_violations for HISA Rule 2280/2281.

Revision ID: 024
Revises: 023
Create Date: 2026-06-02
"""
revision = "024"
down_revision = "023"
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table("riding_crop_violations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("races.id"), nullable=False, index=True),
        sa.Column("horse_chip_id", sa.String, sa.ForeignKey("horses.chip_id"), nullable=True, index=True),
        sa.Column("jockey_name", sa.String(128), nullable=False),
        sa.Column("crop_count", sa.Integer, nullable=False),
        sa.Column("violation_determined", sa.Boolean, server_default=sa.false()),
        sa.Column("penalty", sa.String(200), nullable=True),
        sa.Column("official_name", sa.String(128), nullable=True),
        sa.Column("race_date", sa.String(10), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("riding_crop_violations")
