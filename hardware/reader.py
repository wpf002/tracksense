"""
hardware_reader.py

Real RFID reader integration for TrackSense.

This replaces mock_reader.py when physical hardware is connected.

Supported reader types:
  - Serial/RS-232/RS-485 readers (most industrial UHF readers)
  - USB-CDC readers (appear as /dev/ttyUSB0 or COM port)
  - TCP/IP socket readers (networked readers with Ethernet)

Hardware recommendations for horse racing:
  - Impinj R420 or R220 (enterprise UHF, excellent multi-tag performance)
  - ThingMagic M6 or Nano (solid mid-range)
  - Zebra FX9600 (rugged, outdoor-rated)
  - Budget option: CHAFON or similar 902-928 MHz UHF with serial output

Tag recommendations:
  - UHF Gen2 (ISO 18000-6C) — best read range (3–8m), handles speed well
  - For horses: attach to the saddle girth, breastplate, or racing number
    board. NOT on the bridle — too much movement noise.
  - ISO 11784/11785 LF chips (standard horse microchip) have only 10–15cm
    range — NOT suitable for finish-line detection at race speed.
    You need a separate UHF race tag, not the vet microchip.

Antenna placement:
  - Two antennas in a gate configuration either side of the track
  - Polarization: circular polarized (RHCP) for orientation-independent reads
  - Mount at girth height (~1.2m) pointing inward
  - Minimum 2 antennas to handle horses on both rails simultaneously

This module handles:
  1. Serial reader (most common)
  2. TCP/IP reader (Impinj and others)
  3. A parser for common ASCII output formats
"""

import serial
import socket
import time
import threading
import requests
import re
from typing import Optional, Callable
from enum import Enum

BACKEND_URL = "http://localhost:8000"
SUBMIT_URL = f"{BACKEND_URL}/tags/submit"

# ------------------------------------------------------------------ #
# Tag ID normalisation
# ------------------------------------------------------------------ #

# Most readers output EPC in hex, e.g. "E200 6811 B802 0167 1234 ABCD"
# We strip spaces and uppercase. The backend stores it as-is.
def normalise_tag_id(raw: str) -> str:
    return raw.strip().replace(" ", "").upper()


# ------------------------------------------------------------------ #
# Serial Reader
# ------------------------------------------------------------------ #

class SerialReader:
    """
    Reads tag data from a serial/USB RFID reader.

    Most readers output one tag per line in formats like:
      - EPC hex:          "E200681100000000AABBCCDD"
      - CSV with RSSI:    "E200681100000000AABBCCDD,-65,2024-01-01T12:00:00"
      - Prefix format:    "TAG: E200681100000000AABBCCDD"

    Adjust `parse_line()` to match your reader's actual output format.

    Common serial settings for UHF readers:
      - Baud: 115200 (sometimes 9600 or 57600 — check reader docs)
      - Data bits: 8, Stop bits: 1, Parity: None
      - Flow control: None
    """

    def __init__(
        self,
        port: str,
        baud: int = 115200,
        on_tag: Optional[Callable[[str], None]] = None,
        reader_id: str = "SERIAL-READER-1",
    ):
        self.port = port
        self.baud = baud
        self.on_tag = on_tag or self._default_submit
        self.reader_id = reader_id
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def parse_line(self, line: str) -> Optional[str]:
        """
        Parse a line of reader output into a tag ID.

        This is the function to customise for your reader.
        Returns None if the line doesn't contain a tag.
        """
        line = line.strip()
        if not line:
            return None

        # Format: bare 24-hex-char EPC
        if re.fullmatch(r"[0-9A-Fa-f]{24}", line):
            return normalise_tag_id(line)

        # Format: "TAG: <epc>"
        m = re.match(r"TAG:\s*([0-9A-Fa-f\s]{20,})", line, re.IGNORECASE)
        if m:
            return normalise_tag_id(m.group(1))

        # Format: CSV first field is EPC
        parts = line.split(",")
        if parts and re.fullmatch(r"[0-9A-Fa-f\s]{20,}", parts[0]):
            return normalise_tag_id(parts[0])

        return None

    def _default_submit(self, tag_id: str):
        """Default callback: submit to TrackSense backend."""
        try:
            r = requests.post(
                SUBMIT_URL,
                json={"tag_id": tag_id, "reader_id": self.reader_id},
                timeout=2,
            )
            result = r.json()
            if result.get("ok") and not result.get("duplicate"):
                print(f"[hw-serial] Tag: {tag_id} → Position {result.get('position')}")
            elif result.get("duplicate"):
                pass  # Suppress duplicate noise in output
            else:
                print(f"[hw-serial] Rejected: {tag_id} — {result.get('reason')}")
        except Exception as e:
            print(f"[hw-serial] Submit error: {e}")

    def start(self):
        """Start reading in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        print(f"[hw-serial] Listening on {self.port} at {self.baud} baud...")

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3)

    def _read_loop(self):
        while self._running:
            try:
                with serial.Serial(
                    self.port,
                    baudrate=self.baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=1,
                ) as ser:
                    print(f"[hw-serial] Port {self.port} opened.")
                    while self._running:
                        line = ser.readline().decode("ascii", errors="ignore")
                        tag_id = self.parse_line(line)
                        if tag_id:
                            self.on_tag(tag_id)
            except serial.SerialException as e:
                print(f"[hw-serial] Serial error: {e}. Retrying in 3s...")
                time.sleep(3)
            except Exception as e:
                print(f"[hw-serial] Unexpected error: {e}. Retrying in 3s...")
                time.sleep(3)


# ------------------------------------------------------------------ #
# TCP/IP Reader (Impinj, Zebra, others with network interface)
# ------------------------------------------------------------------ #

class TCPReader:
    """
    Reads tag data from a networked RFID reader via TCP socket.

    Common for:
    - Impinj R420 (port 5084 default, LLRP protocol — see below)
    - Readers with raw TCP output mode (check reader config)

    NOTE on LLRP:
    Impinj and many enterprise readers use LLRP (Low Level Reader Protocol)
    which is binary. For production use with Impinj, use the official
    Impinj OctaneSdk or sllurp (open source Python LLRP library).
    This implementation handles simple ASCII-over-TCP readers.
    For LLRP, swap this class for an sllurp-based reader.
    """

    def __init__(
        self,
        host: str,
        port: int,
        on_tag: Optional[Callable[[str], None]] = None,
        reader_id: str = "TCP-READER-1",
    ):
        self.host = host
        self.port = port
        self.on_tag = on_tag or self._default_submit
        self.reader_id = reader_id
        self._running = False

    def _default_submit(self, tag_id: str):
        try:
            r = requests.post(
                SUBMIT_URL,
                json={"tag_id": tag_id, "reader_id": self.reader_id},
                timeout=2,
            )
            result = r.json()
            if result.get("ok") and not result.get("duplicate"):
                print(f"[hw-tcp] Tag: {tag_id} → Position {result.get('position')}")
        except Exception as e:
            print(f"[hw-tcp] Submit error: {e}")

    def start(self):
        self._running = True
        threading.Thread(target=self._read_loop, daemon=True).start()
        print(f"[hw-tcp] Connecting to {self.host}:{self.port}...")

    def stop(self):
        self._running = False

    def _read_loop(self):
        while self._running:
            try:
                with socket.create_connection((self.host, self.port), timeout=10) as sock:
                    print(f"[hw-tcp] Connected to {self.host}:{self.port}")
                    buf = ""
                    while self._running:
                        chunk = sock.recv(1024).decode("ascii", errors="ignore")
                        if not chunk:
                            break
                        buf += chunk
                        while "\n" in buf:
                            line, buf = buf.split("\n", 1)
                            # Reuse serial parser logic
                            tag_id = SerialReader("dummy").parse_line(line)
                            if tag_id:
                                self.on_tag(tag_id)
            except (socket.timeout, ConnectionRefusedError) as e:
                print(f"[hw-tcp] Connection error: {e}. Retrying in 5s...")
                time.sleep(5)
            except Exception as e:
                print(f"[hw-tcp] Error: {e}. Retrying in 5s...")
                time.sleep(5)


# ------------------------------------------------------------------ #
# LLRP Reader (Impinj R220 / R420 and compatible readers)
# ------------------------------------------------------------------ #

class LLRPReader:
    """
    Reads tag data from an Impinj R220/R420 (or any LLRP-compliant) reader.

    Uses the sllurp library for LLRP protocol support.
    Install with: pip install sllurp

    Calls the same on_tag(tag_id: str) callback interface as SerialReader
    and TCPReader, so the rest of the system is unaware of which reader
    type is in use.

    Tag reports are delivered asynchronously by sllurp via a callback;
    this class bridges them into the TrackSense callback interface.
    """

    def __init__(
        self,
        host: str,
        port: int = 5084,
        on_tag: Optional[Callable[[str], None]] = None,
        reader_id: str = "LLRP-READER-1",
    ):
        try:
            from sllurp import llrp as _sllurp_llrp  # noqa: PLC0415
            self._sllurp_llrp = _sllurp_llrp
        except ImportError as exc:
            raise ImportError(
                "sllurp is required for LLRP reader support (Impinj R220/R420). "
                "Install it with: pip install sllurp"
            ) from exc

        self.host = host
        self.port = port
        self.on_tag = on_tag or self._default_submit
        self.reader_id = reader_id
        self._client = None
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _handle_tags(self, reader, tags):
        """
        Called by sllurp on each tag report batch.
        Extracts EPC-96 from each tag and forwards to on_tag callback.
        """
        for tag in tags:
            epc_bytes = tag.get("EPC-96", b"")
            if isinstance(epc_bytes, bytes):
                epc = epc_bytes.hex().upper()
            else:
                epc = normalise_tag_id(str(epc_bytes))
            if epc:
                self.on_tag(epc)

    def _make_client(self):
        """
        Create and connect a sllurp LLRPClient.
        Raises on connection failure — caller handles retry logic.
        """
        config = self._sllurp_llrp.LLRPReaderConfig({})
        client = self._sllurp_llrp.LLRPClient(self.host, self.port, config)
        client.add_tag_report_handler(self._handle_tags)
        client.connect()
        return client

    def _run_loop(self):
        while self._running:
            try:
                print(f"[hw-llrp] Connecting to {self.host}:{self.port}...")
                self._client = self._make_client()
                print(f"[hw-llrp] Connected to {self.host}:{self.port}")
                # Block here while the reader is active; sllurp fires callbacks
                # from its own internal thread as tags are read.
                while self._running:
                    time.sleep(0.1)
            except Exception as exc:
                print(f"[hw-llrp] Connection error: {exc}. Retrying in 5s...")
                if self._running:
                    time.sleep(5)

    def start(self):
        """Start the LLRP reader in a background thread."""
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the LLRP reader and disconnect cleanly."""
        self._running = False
        if self._client:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None
        if self._thread:
            self._thread.join(timeout=3)
        print("[hw-llrp] Stopped.")

    def _default_submit(self, tag_id: str):
        """Default callback: submit tag to TrackSense backend."""
        try:
            r = requests.post(
                SUBMIT_URL,
                json={"tag_id": tag_id, "reader_id": self.reader_id},
                timeout=2,
            )
            result = r.json()
            if result.get("ok") and not result.get("duplicate"):
                print(f"[hw-llrp] Tag: {tag_id} → Position {result.get('position')}")
            elif result.get("duplicate"):
                pass
            else:
                print(f"[hw-llrp] Rejected: {tag_id} — {result.get('reason')}")
        except Exception as e:
            print(f"[hw-llrp] Submit error: {e}")


# ------------------------------------------------------------------ #
# Entry point for hardware mode
# ------------------------------------------------------------------ #

def run_serial(port: str = "/dev/ttyUSB0", baud: int = 115200):
    """Start a serial hardware reader and block until interrupted."""
    reader = SerialReader(port=port, baud=baud)
    reader.start()
    print("[hw] Hardware reader running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        reader.stop()
        print("[hw] Stopped.")


def run_tcp(host: str = "192.168.1.100", port: int = 5084):
    """Start a TCP hardware reader and block until interrupted."""
    reader = TCPReader(host=host, port=port)
    reader.start()
    print("[hw] Hardware TCP reader running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        reader.stop()
        print("[hw] Stopped.")


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "serial"
    if mode == "tcp":
        run_tcp()
    else:
        run_serial()
