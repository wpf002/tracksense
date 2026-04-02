# TrackSense

RFID-based horse race finish-line engine. Backend-first. Hardware-ready.

## What it does

Ingests RFID tag reads from a finish-line antenna gate and records horse finish order with millisecond-accurate split times. Currently runs with a mock reader. Designed to swap in real UHF RFID hardware with no backend changes.

## Project Structure

```text
tracksense/
├── app/
│   ├── server.py         FastAPI app instance
│   ├── routes.py         REST API endpoints
│   └── race_state.py     Thread-safe race engine (the core)
├── scripts/
│   └── mock_reader.py    Simulated RFID reader (20 horses, realistic timing)
├── hardware/
│   └── reader.py         Real reader integration (serial + TCP/IP)
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
├── docs/
│   └── HARDWARE.md       Full hardware spec: readers, antennas, tags, wiring
├── tests/
│   └── test_race_state.py
├── main.py               Startup orchestrator
└── requirements.txt
```

## Quick Start

```bash
pip install -r requirements.txt
python main.py
```

The backend starts on `localhost:8000`, the mock reader fires 20 horses through the finish line with realistic timing and duplicate reads, results print to terminal.

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness check |
| POST | `/race/register` | Register horse field |
| POST | `/race/arm` | Arm race (keep horses, clear results) |
| POST | `/race/reset` | Full wipe |
| POST | `/tags/submit` | Submit tag read (hot path) |
| GET | `/race/status` | Quick status |
| GET | `/race/finish-order` | Full results with splits |

## Hardware Mode

```bash
# Serial/USB reader
RFID_PORT=/dev/ttyUSB0 RFID_BAUD=115200 python main.py --hardware serial

# TCP/IP reader (Impinj etc.)
RFID_HOST=192.168.1.100 RFID_PORT=5084 python main.py --hardware tcp
```

See `docs/HARDWARE.md` for full hardware selection, antenna placement, and tag guidance.

## Docker

```bash
cd docker
docker-compose up --build
```

## Tests

```bash
pytest tests/
```

## Key Design Decisions

- **Thread-safe core:** Mock reader and hardware readers run in threads. All state access is locked.
- **Duplicate fold:** Real UHF readers see each tag 2–10 times per pass. Duplicates are counted but don't re-record finish position.
- **Unknown tag rejection:** Stray reads from adjacent paddock/maintenance tags are silently dropped. Backend doesn't crash or miscount.
- **Re-armable:** Same horse field can be raced multiple times with `/race/arm`. No need to re-register between heats.
- **Hardware-swappable:** `mock_reader.py` and `hardware/reader.py` both POST to the same `/tags/submit` endpoint. Backend never knows the difference.
