"""
ingestion.py — Data-source seam for Step 3 (real data, no hardware).

Today the app is populated by the demo seed. When real horses/operations arrive,
a real importer (CSV from a trainer/barn, or a public-data pull) becomes another
DataSource behind the same interface — the rest of the app doesn't change.

  - SeedDataSource       → the current provider (wraps scripts.seed).
  - CsvImportDataSource  → stub for importing real horses/entries/results from a
                           file a barn or owner provides.

Pick one with the DATA_SOURCE env var via get_data_source(); default is the seed.
"""
import os
from abc import ABC, abstractmethod


class DataSource(ABC):
    name = "base"

    @abstractmethod
    def populate(self, *, force: bool = False) -> None:
        """Load data into the database."""
        raise NotImplementedError


class SeedDataSource(DataSource):
    """Demo data — the canonical, realistic seed (scripts/seed.py)."""
    name = "seed"

    def populate(self, *, force: bool = False) -> None:
        from scripts import seed
        seed.run(force=force)


class CsvImportDataSource(DataSource):
    """Stub: import real horses / entries / results from a provided CSV bundle.

    Implement populate() when a barn or owner supplies real data — map their
    columns onto Horse / RaceEntry / RaceResult and reuse hisa_builder for the
    compliance payloads.
    """
    name = "csv"

    def __init__(self, path: str = None):
        self.path = path or os.getenv("IMPORT_PATH")

    def populate(self, *, force: bool = False) -> None:
        raise NotImplementedError("CSV import not implemented yet — supply real data to wire this up")


def get_data_source() -> DataSource:
    src = os.getenv("DATA_SOURCE", "seed").lower()
    if src == "csv":
        return CsvImportDataSource()
    return SeedDataSource()
