"""Phase 3 — hisa_submissions compliance dashboard backbone.

Revision ID: 021
Revises: 020
Create Date: 2026-06-02
"""
revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table("hisa_submissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("rule_category", sa.String(64), nullable=False, index=True),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False, index=True),
        sa.Column("source_record_type", sa.String(64), nullable=False),
        sa.Column("source_record_id", sa.Integer, nullable=False),
        sa.Column("horse_chip_id", sa.String, nullable=True, index=True),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=True, index=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload_json", sa.Text, nullable=True),
        sa.Column("response_json", sa.Text, nullable=True),
        sa.Column("submitted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("tenant_id", sa.String(36), sa.ForeignKey("tenants.id"), nullable=True, index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

def downgrade():
    op.drop_table("hisa_submissions")
