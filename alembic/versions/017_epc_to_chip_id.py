"""Phase 2 — rename horse identity from UHF epc to Jockey Club LF chip_id.

horses.epc -> horses.chip_id (PK); every child table's horse_epc -> horse_chip_id.

Note: the dev path is SQLite + create_all on a fresh DB + reseed, so this migration
is primarily for Postgres/prod. On Postgres, renaming horses.epc keeps dependent FK
constraints valid automatically; the child-column renames are independent.

Revision ID: 017
Revises: 016
Create Date: 2026-06-02
"""

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None

from alembic import op

_CHILD_TABLES = [
    "owners", "trainers", "vet_records", "race_entries", "race_results",
    "workout_records", "checkin_records", "test_barn_records", "biosensor_readings",
]


def upgrade() -> None:
    op.alter_column("horses", "epc", new_column_name="chip_id")
    for table in _CHILD_TABLES:
        op.alter_column(table, "horse_epc", new_column_name="horse_chip_id")


def downgrade() -> None:
    for table in _CHILD_TABLES:
        op.alter_column(table, "horse_chip_id", new_column_name="horse_epc")
    op.alter_column("horses", "chip_id", new_column_name="epc")
