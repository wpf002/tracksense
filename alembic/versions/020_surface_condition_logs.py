"""Phase 3 — surface_condition_logs for HISA Rule 2151/2154.

Revision ID: 020
Revises: 019
Create Date: 2026-06-02
"""
revision = "020"
down_revision = "019"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table("surface_condition_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("venue_id", sa.String, sa.ForeignKey("venue_records.venue_id"), nullable=False, index=True),
        sa.Column("logged_date", sa.String(10), nullable=False),
        sa.Column("surface_type", sa.String(32), nullable=False),
        sa.Column("going_description", sa.String(64), nullable=False),
        sa.Column("moisture_pct", sa.Float, nullable=True),
        sa.Column("temperature_c", sa.Float, nullable=True),
        sa.Column("maintenance_notes", sa.Text, nullable=True),
        sa.Column("logged_by", sa.String(128), nullable=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("venue_id", "logged_date"),
    )

def downgrade():
    op.drop_table("surface_condition_logs")
