"""Add track_path_points table for broadcast-quality TrackMap geometry.

Revision ID: 013
Revises: 012
Create Date: 2026-04-09
"""

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "track_path_points",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("venue_id", sa.String, sa.ForeignKey("venue_records.venue_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("x", sa.Float, nullable=False),
        sa.Column("y", sa.Float, nullable=False),
        sa.UniqueConstraint("venue_id", "sequence"),
    )


def downgrade() -> None:
    op.drop_table("track_path_points")
