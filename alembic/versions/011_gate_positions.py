"""Add position_x and position_y columns to gate_records table.

Revision ID: 011
Revises: 010
Create Date: 2026-04-08
"""

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # position_x and position_y: normalised 0.0–1.0 coordinates for TrackMap rendering
    op.add_column("gate_records", sa.Column("position_x", sa.Float, nullable=True))
    op.add_column("gate_records", sa.Column("position_y", sa.Float, nullable=True))


def downgrade() -> None:
    op.drop_column("gate_records", "position_y")
    op.drop_column("gate_records", "position_x")
