# HID Bench Test — XOLORspace UHF Reader → TrackSense

Bench-test adapter that validates the full read pipeline using a real RF tag and
a real reader, without any of the production serial/LLRP plumbing.

```
Real RF tag → XOLORspace UHF reader (HID keyboard) → hid_bench_test.py → TrackSense → race state → webhook
```

## What this is

The **XOLORspace UHF Gen2** reader, plugged in over a USB-C adapter, enumerates
as a **USB HID keyboard**. When it reads a tag it "types" the tag's 24-character
hex EPC followed by **Enter** — e.g. `e280689420004035b7806108⏎`.

`scripts/hid_bench_test.py` captures those keystrokes and submits each EPC to a
running TrackSense backend via `POST /tags/submit`, exactly as a real serial
reader would. This proves out the whole chain end-to-end on the bench.

> **This is throwaway bench infrastructure.** The production hardware path is
> `hardware/reader.py` (sllurp / LLRP to an Impinj reader) and is **not** touched
> by this tool.

## Prerequisites

- **TrackSense running** locally (`./start.sh` → backend on `:8001`, UI on `:5173`).
- **`pynput` installed**: `pip install -r requirements.txt` (already pinned there).
- **XOLORspace reader plugged in** via the USB-C adapter and recognised as a
  keyboard. Test it by opening any text field and scanning a tag — you should see
  24 hex characters appear followed by a newline.
- **A tag** stuck to a piece of cardboard (so it stands off any metal and reads
  cleanly when waved past the antenna).

## macOS: grant Accessibility permission (required for global capture)

`pynput`'s global keyboard listener needs Accessibility access, or it will
**silently capture nothing**:

1. **System Settings → Privacy & Security → Accessibility**
2. Click **+** and add the app you'll run the script from — **Terminal** or
   **iTerm** (whichever you use). If you run it from an IDE, add that instead.
3. Toggle it **on**. Fully quit and reopen the terminal app so the grant takes
   effect.

No permission needed for the `--stdin` fallback (but that requires the terminal
to stay focused while scanning).

## How to run

```bash
python scripts/hid_bench_test.py
```

Optional flags / env:

```bash
# Force the stdin fallback (terminal must stay focused while scanning)
python scripts/hid_bench_test.py --stdin

# Print the banner/config and exit — no login, no capture (handy for a smoke check)
python scripts/hid_bench_test.py --dry-run

# Configuration (all optional; defaults shown)
TRACKSENSE_URL=http://localhost:8001 \
TRACKSENSE_USER=admin \
TRACKSENSE_PASS=tracksense \
READER_ID=GATE-FINISH \
python scripts/hid_bench_test.py
```

### ⚠️ READER_ID must match a gate in the armed race's venue

TrackSense routes every read by `reader_id`. If the `reader_id` isn't a gate in
the **armed race's venue**, the backend drops the read with
`{"ok": false, "reason": "unknown_gate"}` and **nothing happens**.

The default `READER_ID` is `bench-test-gate-1`, which does **not** exist in the
seeded venues. To exercise the full pipeline you have two options:

- **Easiest — point at the finish gate:** `export READER_ID=GATE-FINISH`. A scan
  then counts as the runner crossing the finish line, which assigns a finish
  position and (once all registered runners have finished) fires the webhook.
- **Or add a bench gate:** `POST /venues/{venue_id}/gates` with
  `{"reader_id": "bench-test-gate-1", "name": "Bench Gate", "distance_m": 0, "is_finish": true}`,
  then keep the default `READER_ID`.

Seeded venue gates are `GATE-START`, furlong markers, and `GATE-FINISH`.

## Expected output

On startup:

```
==============================================================
  TrackSense HID Bench Test Adapter
  XOLORspace UHF reader (HID keyboard) → POST /tags/submit
==============================================================
  Backend  : http://localhost:8001
  Reader ID: GATE-FINISH
  User     : admin
  Scan a tag (24-hex EPC + Enter). Press Ctrl+C to quit.
==============================================================
[auth] logged in OK
[mode] global HID capture via pynput — no terminal focus needed
```

On a successful scan (EPC registered as a runner, reader_id valid):

```
[14:22:07] scan e280689420004035b7806108 → reader=GATE-FINISH → HTTP 200 {'ok': True, 'duplicate': False, 'tag_id': 'E280689420004035B7806108', 'display_name': 'Test Horse', 'reader_id': 'GATE-FINISH', 'gate_name': 'Finish', 'is_finish': True, 'finish_position': 1, 'race_finished': True, ...}
```

Reads that are filtered show why, on one line each:

```
[14:23:10] scan e280689420004035b7806108 → reader=GATE-FINISH → HTTP 200 {'ok': False, 'reason': 'unknown_tag', ...}   # EPC not a registered runner
[14:23:18] scan e280689420004035b7806108 → reader=bench-test-gate-1 → HTTP 200 {'ok': False, 'reason': 'unknown_gate', ...}   # reader_id not a venue gate
[skip] not a 24-hex EPC (5 chars): 'hello'   # stray manual typing, ignored
```

## Full bench test walkthrough

1. **Start TrackSense**
   ```bash
   ./start.sh
   ```

2. **Register a horse with your tag's EPC.** Use the EPC your reader actually
   prints (scan once into a text field to read it off). Log in to get a token,
   then:
   ```bash
   TOKEN=$(curl -s -X POST http://localhost:8001/auth/login \
     -H 'Content-Type: application/json' \
     -d '{"username":"admin","password":"tracksense"}' | python -c "import sys,json;print(json.load(sys.stdin)['access_token'])")

   curl -s -X POST http://localhost:8001/horses \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"epc":"e280689420004035b7806108","name":"Bench Test Horse"}'
   ```
   (EPC case doesn't matter — the backend upper-cases it.)

3. **Register a race field with that horse and arm it.** Pick a seeded venue
   (e.g. `CHURCHILL`):
   ```bash
   curl -s -X POST http://localhost:8001/race/register \
     -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
     -d '{"venue_id":"CHURCHILL","horses":[{"horse_id":"e280689420004035b7806108","display_name":"Bench Test Horse","saddle_cloth":"1"}]}'

   curl -s -X POST http://localhost:8001/race/arm -H "Authorization: Bearer $TOKEN"
   ```
   (You can also build a field in the UI's Race Builder → **Advanced**.)

4. **Run the adapter**, pointed at the finish gate so a scan completes the race:
   ```bash
   READER_ID=GATE-FINISH python scripts/hid_bench_test.py
   ```

5. **Wave the tag past the reader.** You should see a `scan … HTTP 200 {'ok': True … 'finish_position': 1 …}` line.

6. **Confirm race state updates in the UI** at <http://localhost:5173> — the Live
   Race view should show the runner crossing the finish and the race going to
   `finished`.

7. **Confirm the webhook fires.** When all registered runners have finished, the
   backend fires the `race.finished` webhook to every active subscriber; watch
   the backend log for lines beginning with `[webhook]`. To deliver to the
   GateSmart endpoint specifically, configure it as a subscription (or set the
   `GATESMART_WEBHOOK_URL` + `TRACKSENSE_WEBHOOK_SECRET` env vars and call
   `POST /races/{id}/persist`); the target is:
   ```
   https://backend-production-15e941.up.railway.app/api/tracksense/webhook
   ```
   You'll see `[webhook] OK → … HTTP 200` (or `[gatesmart] …`) in the backend log.

## Troubleshooting

| Symptom | Likely cause / fix |
| --- | --- |
| **No keystrokes captured** (nothing logs when you scan) | macOS Accessibility permission not granted to your terminal app. See the grant steps above, then fully quit & reopen the terminal. Or run with `--stdin` and keep the terminal focused. |
| **`401` on submit** | Token expired or invalid. The script auto re-authenticates once per scan; if it persists, restart the script. Check `TRACKSENSE_USER` / `TRACKSENSE_PASS`. |
| **`{"ok": false, "reason": "unknown_gate"}`** | `READER_ID` isn't a gate in the armed race's venue. Set `READER_ID=GATE-FINISH` or add a `bench-test-gate-1` gate (see the READER_ID note above). |
| **`{"ok": false, "reason": "unknown_tag"}`** | The scanned EPC isn't a registered runner in the active race. Register the horse and add it to the armed field (walkthrough steps 2–3). |
| **`{"ok": false, "reason": "no_active_race"}`** | No race is registered/armed. Do steps 3–4. |
| **EPC ignored / `[skip] not a 24-hex EPC`** | Keystrokes were interrupted (another app grabbed focus mid-scan) or stray manual typing landed in the buffer. With global capture, avoid typing elsewhere while scanning; with `--stdin`, keep this terminal focused. |
| **`login FAILED` on startup** | TrackSense isn't running, or `TRACKSENSE_URL` is wrong. Start it with `./start.sh`. |
