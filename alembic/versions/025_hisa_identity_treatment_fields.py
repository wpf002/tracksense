"""HISA Covered-Horse identity fields + Rule 2251(b) treatment fields.

Adds horse identity columns (dam_name, covered_since) and the additional
veterinary-treatment columns required by ADMC Rule 2251(b).

Revision ID: 025
Revises: 024
Create Date: 2026-06-07
"""
revision = "025"
down_revision = "024"
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa


def upgrade():
    # horses — HISA Covered-Horse identity
    op.add_column("horses", sa.Column("dam_name", sa.String(128), nullable=True))
    op.add_column("horses", sa.Column("covered_since", sa.String(10), nullable=True))

    # treatment_records — Rule 2251(b) fields
    op.add_column("treatment_records", sa.Column("treatment_time", sa.String(8), nullable=True))
    op.add_column("treatment_records", sa.Column("frequency", sa.String(64), nullable=True))
    op.add_column("treatment_records", sa.Column("duration", sa.String(64), nullable=True))
    op.add_column("treatment_records", sa.Column("diagnosis", sa.Text, nullable=True))
    op.add_column("treatment_records", sa.Column("condition_treated", sa.String(200), nullable=True))
    op.add_column("treatment_records", sa.Column("procedure", sa.Text, nullable=True))
    op.add_column("treatment_records", sa.Column("vet_phone", sa.String(32), nullable=True))
    op.add_column("treatment_records", sa.Column("vet_email", sa.String(128), nullable=True))


def downgrade():
    for col in ("vet_email", "vet_phone", "procedure", "condition_treated",
                "diagnosis", "duration", "frequency", "treatment_time"):
        op.drop_column("treatment_records", col)
    op.drop_column("horses", "covered_since")
    op.drop_column("horses", "dam_name")
