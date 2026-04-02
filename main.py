"""
main.py

TrackSense startup orchestrator.

Startup sequence:
  1. Kill anything on port 8000
  2. Start FastAPI backend (subprocess)
  3. Wait for backend health check
  4. Run mock reader (or hardware reader if --hardware flag passed)
  5. Monitor for race completion
  6. Print results and exit cleanly

Usage:
  python main.py                    # Run with mock reader
  python main.py --hardware serial  # Run with serial RFID reader
  python main.py --hardware tcp     # Run with TCP RFID reader
"""

import subprocess
import sys
import os
import time
import signal
import requests
import argparse

BACKEND_URL = "http://localhost:8000"


def kill_port_8000():
    """Kill any process already using port 8000."""
    try:
        result = subprocess.run(
            ["lsof", "-ti", ":8000"],
            capture_output=True, text=True
        )
        pids = result.stdout.strip().split()
        for pid in pids:
            if pid:
                os.kill(int(pid), signal.SIGTERM)
                print(f"[main] Killed existing process on port 8000 (PID {pid})")
        if pids:
            time.sleep(1)
    except Exception:
        pass  # lsof not available or no process — fine


def clean_pycache():
    """Remove __pycache__ dirs to avoid stale bytecode issues."""
    import shutil
    for root, dirs, _ in os.walk("."):
        for d in dirs:
            if d == "__pycache__":
                shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def start_backend() -> subprocess.Popen:
    """Start the FastAPI backend as a subprocess."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "warning"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    print(f"[main] Backend started (PID {proc.pid})")
    return proc


def wait_for_backend(retries: int = 20, delay: float = 0.5) -> bool:
    for i in range(retries):
        try:
            r = requests.get(f"{BACKEND_URL}/health", timeout=2)
            if r.status_code == 200:
                print("[main] Backend healthy.")
                return True
        except Exception:
            pass
        time.sleep(delay)
    return False


def run_mock():
    """Import and run the mock reader inline (same process, blocking)."""
    from scripts.mock_reader import run
    run()


def run_hardware(mode: str):
    """Start the hardware reader."""
    if mode == "serial":
        from hardware.reader import run_serial
        port = os.environ.get("RFID_PORT", "/dev/ttyUSB0")
        baud = int(os.environ.get("RFID_BAUD", "115200"))
        run_serial(port=port, baud=baud)
    elif mode == "tcp":
        from hardware.reader import run_tcp
        host = os.environ.get("RFID_HOST", "192.168.1.100")
        port = int(os.environ.get("RFID_PORT", "5084"))
        run_tcp(host=host, port=port)
    else:
        print(f"[main] Unknown hardware mode: {mode}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="TrackSense Race Engine")
    parser.add_argument(
        "--hardware",
        choices=["serial", "tcp"],
        default=None,
        help="Run with real hardware reader instead of mock (serial or tcp)"
    )
    args = parser.parse_args()

    print("\n========================================")
    print("  TRACKSENSE — RFID Race Engine")
    print("========================================\n")

    clean_pycache()
    kill_port_8000()

    backend_proc = start_backend()
    time.sleep(0.5)

    if not wait_for_backend():
        print("[main] ERROR: Backend failed to start.")
        backend_proc.terminate()
        sys.exit(1)

    try:
        if args.hardware:
            print(f"[main] Hardware mode: {args.hardware}")
            print("[main] Register horses via POST /race/register before tagging.")
            run_hardware(args.hardware)
        else:
            run_mock()
    except KeyboardInterrupt:
        print("\n[main] Interrupted.")
    finally:
        print("[main] Shutting down backend...")
        backend_proc.terminate()
        try:
            backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            backend_proc.kill()
        print("[main] Done.")


if __name__ == "__main__":
    main()
