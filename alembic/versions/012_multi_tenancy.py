"""Add multi-tenancy: Tenant table + tenant_id FK on parent tables.

Revision ID: 012
Revises: 011b
Create Date: 2026-04-08

Design notes:
- tenant_id is nullable on all tables — existing rows are treated as
  super-admin / unscoped data and remain accessible.
- Child tables (RaceEntry, GateRead, RaceResult, VetRecord, WorkoutRecord,
  CheckInRecord, TestBarnRecord, AuditLog, WebhookDelivery) do NOT get
  tenant_id — they inherit isolation via their parent.
- tenant slug must be unique and URL-safe.
"""

revision = "012"
down_revision = "011b"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # 1. Create tenants table
    op.create_table(
        "tenants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    # 2. Add nullable tenant_id FK to parent tables
    for table in ("venue_records", "horses", "races", "users",
                  "webhook_subscriptions", "api_keys"):
        op.add_column(
            table,
            sa.Column("tenant_id", sa.String(36),
                      sa.ForeignKey("tenants.id", ondelete="SET NULL"),
                      nullable=True),
        )


def downgrade() -> None:
    for table in ("venue_records", "horses", "races", "users",
                  "webhook_subscriptions", "api_keys"):
        op.drop_column(table, "tenant_id")
    op.drop_table("tenants")
