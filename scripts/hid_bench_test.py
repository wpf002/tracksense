#!/usr/bin/env python3
"""
hid_bench_test.py — XOLORspace UHF reader (HID keyboard mode) → TrackSense adapter.

BENCH-TEST INFRASTRUCTURE ONLY. This is throwaway test tooling, not the
production hardware path (that is hardware/reader.py, which talks LLRP/sllurp to
an Impinj reader and stays untouched).

The XOLORspace UHF Gen2 reader, plugged in over USB-C, enumerates as a USB HID
keyboard. When it reads a tag it "types" the 24-character hex EPC followed by
Enter. This adapter captures those keystrokes and submits each EPC to a running
TrackSense backend via POST /tags/submit — exactly as a real serial reader does —
so you can validate the full pipeline:

    Real RF → Reader (HID) → this adapter → TrackSense → race state → webhook

Capture modes:
  - pynput global listener (default): captures keystrokes with no terminal focus.
  - stdin fallback: used automatically if pynput can't start (e.g. headless/CI).
    Requires THIS terminal to be focused while scanning.

Config via environment variables (sensible defaults):
    TRACKSENSE_URL   default http://localhost:8001
    TRACKSENSE_USER  default admin
    TRACKSENSE_PASS  default tracksense
    READER_ID        default bench-test-gate-1

NOTE on READER_ID: the backend drops a read with reason "unknown_gate" unless the
reader_id matches a gate configured in the armed race's venue. Seeded venues use
GATE-START / GATE-FINISH / furlong markers, so to exercise the full pipeline set
READER_ID=GATE-FINISH (a scan then = crossing the finish line) or add a gate named
bench-test-gate-1 via POST /venues/{venue_id}/gates. See docs/HID_BENCH_TEST.md.
"""

import argparse
import os
import re
import sys
import time

import requests

URL = os.getenv("TRACKSENSE_URL", "http://localhost:8001").rstrip("/")
USER = os.getenv("TRACKSENSE_USER", "admin")
PASS = os.getenv("TRACKSENSE_PASS", "tracksense")
READER_ID = os.getenv("READER_ID", "bench-test-gate-1")

# A valid EPC is exactly 24 hex characters (case-insensitive).
EPC_RE = re.compile(r"^[0-9a-fA-F]{24}$")

_token = None


def login():
    """Authenticate to TrackSense and cache the JWT. Raises on failure."""
    global _token
    r = requests.post(f"{URL}/auth/login", json={"username": USER, "password": PASS}, timeout=10)
    r.raise_for_status()
    _token = r.json()["access_token"]
    return _token


def submit(epc):
    """
    POST one EPC as a tag read. The backend expects {tag_id, reader_id} and
    stamps the read time itself (no client timestamp field). Re-auths once on a
    401 and retries. Returns (status_code, body).
    """
    global _token
    payload = {"tag_id": epc, "reader_id": READER_ID}
    for attempt in (1, 2):
        headers = {"Authorization": f"Bearer {_token}"}
        r = requests.post(f"{URL}/tags/submit", json=payload, headers=headers, timeout=10)
        if r.status_code == 401 and attempt == 1:
            print("[auth] token rejected (401) — re-authenticating…")
            login()
            continue
        break
    try:
        body = r.json()
    except ValueError:
        body = r.text
    return r.status_code, body


def handle_line(buf):
    """Validate a captured line and, if it's an EPC, submit it as a tag read."""
    raw = buf.strip()
    if not EPC_RE.match(raw):
        if raw:
            print(f"[skip] not a 24-hex EPC ({len(raw)} chars): {raw!r}")
        return
    epc = raw.lower()
    ts = time.strftime("%H:%M:%S")
    try:
        status, body = submit(epc)
        print(f"[{ts}] scan {epc} → reader={READER_ID} → HTTP {status} {body}")
    except Exception as exc:  # noqa: BLE001 — bench tool: never die on one bad scan
        print(f"[{ts}] scan {epc} → ERROR {exc}")


def run_pynput():
    """Global keyboard capture — no terminal focus required."""
    from pynput import keyboard
    from pynput.keyboard import Key, KeyCode

    buf = []

    def on_press(key):
        if key == Key.enter:
            handle_line("".join(buf))
            buf.clear()
        elif isinstance(key, KeyCode) and key.char is not None:
            buf.append(key.char)
        # all other keys (shift, ctrl, etc.) are ignored

    print("[mode] global HID capture via pynput — no terminal focus needed")
    with keyboard.Listener(on_press=on_press) as listener:
        listener.join()


def run_stdin():
    """Fallback: read newline-terminated EPCs from stdin (terminal must be focused)."""
    print("[mode] stdin fallback — keep THIS terminal focused while scanning")
    for line in sys.stdin:
        handle_line(line)


def banner():
    print("=" * 62)
    print("  TrackSense HID Bench Test Adapter")
    print("  XOLORspace UHF reader (HID keyboard) → POST /tags/submit")
    print("=" * 62)
    print(f"  Backend  : {URL}")
    print(f"  Reader ID: {READER_ID}")
    print(f"  User     : {USER}")
    print("  Scan a tag (24-hex EPC + Enter). Press Ctrl+C to quit.")
    print("=" * 62)


def main():
    parser = argparse.ArgumentParser(description="HID-to-TrackSense bench test adapter.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the banner/config and exit (no login, no capture).")
    parser.add_argument("--stdin", action="store_true",
                        help="Force stdin capture instead of the pynput global listener.")
    args = parser.parse_args()

    banner()
    if args.dry_run:
        print("[dry-run] not logging in or starting capture — exiting.")
        return

    try:
        login()
        print("[auth] logged in OK")
    except Exception as exc:  # noqa: BLE001
        print(f"[auth] login FAILED: {exc}")
        print("       Is TrackSense running at the configured TRACKSENSE_URL?")
        sys.exit(1)

    try:
        if args.stdin:
            run_stdin()
        else:
            try:
                run_pynput()
            except Exception as exc:  # noqa: BLE001 — pynput can't start (headless/no perms)
                print(f"[mode] pynput unavailable ({exc}) — falling back to stdin")
                run_stdin()
    except KeyboardInterrupt:
        print("\n[exit] stopped.")


if __name__ == "__main__":
    main()
