"""
hardware/reader.py — Device adapter seams for Step 4 (real hardware).

Everything in the app today runs on seeded/mock data. These interfaces are the
single place real devices plug in later, so the rest of the codebase stays
device-agnostic:

  - MicrochipReader   → reads an ISO 11784/11785 microchip at paddock check-in.
                        MockMicrochipReader returns canned values; a real reader
                        (SerialMicrochipReader) talks to a USB/serial wand.
  - ResultsSource     → ingests official finish order. ManualResultsSource is the
                        current path; FinishLynx/MYLAPS adapters slot in here.

Select an implementation with env vars (READER_MODE, RESULTS_SOURCE) via the
factory functions; default is always the mock so nothing breaks without hardware.
"""
import os
from abc import ABC, abstractmethod
from typing import Optional


# ─── Microchip reader (paddock check-in) ──────────────────────────────────────
class MicrochipReader(ABC):
    @abstractmethod
    def read_chip(self) -> Optional[str]:
        """Block until a chip is read; return the chip id (or None on timeout)."""
        raise NotImplementedError


class MockMicrochipReader(MicrochipReader):
    """Returns preconfigured chip ids — used for demos and tests."""
    def __init__(self, queue=None):
        self._queue = list(queue or [])

    def read_chip(self) -> Optional[str]:
        return self._queue.pop(0) if self._queue else None


class SerialMicrochipReader(MicrochipReader):
    """Stub for a real USB/serial RFID wand (e.g. pyserial + ISO 11784/11785
    FDX-B decode). Implement read_chip() when the hardware is on hand."""
    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate

    def read_chip(self) -> Optional[str]:
        raise NotImplementedError("SerialMicrochipReader not implemented — connect a reader first")


def get_microchip_reader() -> MicrochipReader:
    mode = os.getenv("READER_MODE", "mock").lower()
    if mode == "serial":
        return SerialMicrochipReader(port=os.getenv("READER_PORT", "/dev/ttyUSB0"))
    return MockMicrochipReader()


# ─── Results source (official finish order) ───────────────────────────────────
class ResultsSource(ABC):
    @abstractmethod
    def fetch_results(self, race_id: int):
        """Return a list of {finish_position, chip_id|saddle_cloth, elapsed_ms}."""
        raise NotImplementedError


class ManualResultsSource(ResultsSource):
    """Current path — results are entered by hand / posted to the ingest API."""
    def fetch_results(self, race_id: int):
        return []


class FinishLynxResultsSource(ResultsSource):
    """Stub for FinishLynx/MYLAPS timing export ingestion (Step 4)."""
    def __init__(self, export_path: Optional[str] = None):
        self.export_path = export_path

    def fetch_results(self, race_id: int):
        raise NotImplementedError("FinishLynx/MYLAPS ingestion not implemented yet")


def get_results_source() -> ResultsSource:
    src = os.getenv("RESULTS_SOURCE", "manual").lower()
    if src in ("finishlynx", "mylaps"):
        return FinishLynxResultsSource(export_path=os.getenv("RESULTS_EXPORT_PATH"))
    return ManualResultsSource()
