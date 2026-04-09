# TrackSense Hardware Installation Guide

Field installation reference for RFID gate readers at race venues.
Covers site preparation, reader mounting, network configuration, and
system validation before a live race meeting.

---

## Contents

1. [Prerequisites](#1-prerequisites)
2. [Site Survey](#2-site-survey)
3. [Reader Hardware Overview](#3-reader-hardware-overview)
4. [Antenna Placement](#4-antenna-placement)
5. [Power and Cabling](#5-power-and-cabling)
6. [Network Configuration](#6-network-configuration)
7. [LLRP Reader Setup](#7-llrp-reader-setup)
8. [TrackSense Gate Registration](#8-tracksense-gate-registration)
9. [End-to-End Validation](#9-end-to-end-validation)
10. [Troubleshooting](#10-troubleshooting)
11. [Tear-Down and Pack-Up](#11-tear-down-and-pack-up)

---

## 1. Prerequisites

### Personnel
- Two installers (one for cabling, one for positioning)
- TrackSense system administrator (can be remote)

### Equipment checklist
| Item | Qty | Notes |
|------|-----|-------|
| LLRP UHF RFID reader | 1–8 | One per gate position |
| Circular-polarised panel antenna | 2 per reader | Left/right track coverage |
| LMR-400 coax cable (5 m sections) | As required | Keep runs under 10 m |
| SMA–N-type adaptors | Per antenna | Match reader port type |
| Weatherproof enclosure (IP65) | 1 per reader | For outdoor readers |
| 802.3af PoE switch or injector | 1 per reader | 15.4 W minimum |
| CAT6 outdoor cable | Per run | UV-rated jacket |
| Laptop running TrackSense CLI | 1 | For registration/validation |
| Test tag (implant chip on bench mount) | 2 | One per antenna side |
| Tape measure and chalk line | 1 set | Gate marking |

### Software
- TrackSense server reachable on the venue LAN (default port 8000)
- Admin JWT or API key for gate registration
- Reader manufacturer firmware at the required version (see [docs/HARDWARE.md](HARDWARE.md))

---

## 2. Site Survey

Complete a site survey **at least one week before** the race meeting.

### Track walk
1. Walk the track with the race steward to confirm:
   - Start line position
   - Furlong / quarter-mile marker positions
   - Finish line position
   - Any temporary fencing that blocks antenna line-of-sight
2. Record GPS coordinates (±1 m accuracy) for each gate position.
   These become the `position_x` / `position_y` values in TrackSense
   after normalising to the 0.0–1.0 coordinate range.

### Distance verification
- Measure distances from start to each gate using a surveyor's wheel.
- Cross-reference with the official track plan supplied by the venue.
- Record as `distance_m` for each gate record.

### Network survey
- Identify the nearest network cabinet or junction box to each gate.
- Measure cable run lengths; add 20% margin for routing.
- Confirm PoE switch capacity (one 15.4 W port per reader).
- If Wi-Fi bridging is required, survey for 5 GHz coverage at each gate.

---

## 3. Reader Hardware Overview

TrackSense uses LLRP-compatible UHF RFID readers operating at 865–928 MHz
(region-specific). Current validated hardware:

| Model | Antenna ports | Max power | Protocol |
|-------|--------------|-----------|----------|
| Impinj Speedway R420 | 4 | 30 dBm | LLRP 1.1 |
| Zebra FX9600 | 8 | 30 dBm | LLRP 1.1 |
| Jadak ThingMagic M6e | 1–4 | 27 dBm | LLRP 1.0 |

> **Note**: Always use the LLRP interface. Proprietary SDK modes are not supported.

---

## 4. Antenna Placement

### Goal
Each antenna must cover the full track width (typically 20–30 m) with
sufficient gain to read an implanted chip at gallop speed (~60 km/h).

### Recommended geometry

```
         TRACK
  ←────── 25 m ──────→
  |                   |
  [Ant L]         [Ant R]
     ↑ 1.5 m          ↑ 1.5 m
     │ height          │
  [Reader]          [Reader]
  (inside rail)  (inside rail)
```

- Mount antennas 1.2–1.8 m above ground level.
- Angle antenna face 10–15° downward toward the track centreline.
- For straight gates: antennas on both sides of the track, facing inward.
- For curved sections: verify coverage with a walk-through test before racing.

### Finish line
- Use **four** antennas (two per side) staggered 0.5 m apart along the rail
  to ensure every horse is read regardless of position across the track.

### Separation between gates
- Maintain at least 30 m between adjacent reader antennas to avoid
  cross-reads (a horse at gate 2 triggering gate 3's reader).
- If gates must be closer, reduce power on the nearer antenna.

---

## 5. Power and Cabling

### PoE installation
1. Run CAT6 from the PoE switch to each reader location.
2. Keep each cable run under **100 m** (Ethernet PoE limit).
3. Label each cable at both ends: `GATE-[name]-[reader serial]`.
4. Use outdoor-rated conduit for any exposed surface run.

### Antenna coax
1. Dress coax away from mains power cables (minimum 150 mm separation).
2. Secure coax every 500 mm with UV-stable cable ties.
3. Seal all connectors with self-amalgamating tape after torquing to spec.
4. Document coax run length — every metre of LMR-400 adds ~0.2 dB loss.

### Grounding
- Bond reader enclosure ground lug to venue earth stake.
- Do **not** rely solely on signal-ground through the coax.

---

## 6. Network Configuration

### Reader IP assignment
Assign a static IP to each reader. Use the venue's dedicated IoT VLAN.

| Gate | Reader | Suggested IP |
|------|--------|-------------|
| Start | Reader-01 | 192.168.10.11 |
| 1F | Reader-02 | 192.168.10.12 |
| 2F | Reader-03 | 192.168.10.13 |
| Finish | Reader-04 | 192.168.10.14 |

Adjust the last octet for additional gates.

### Firewall rules
- TrackSense server must be reachable on port **8000** (HTTP API) and
  port **5084** (LLRP inbound, if readers connect outbound).
- Readers connect **outbound** to TrackSense — no inbound firewall rules
  are required on the reader side.

### DNS / hosts
Add entries to the venue router's local DNS:
```
tracksense.local  →  <TrackSense server IP>
```

Or configure each reader with the server IP directly.

---

## 7. LLRP Reader Setup

### Step-by-step (Impinj Speedway R420 example)

1. Open the reader's web management interface at its IP address.
2. Navigate to **Antenna Configuration**:
   - Enable antenna ports 1 and 2.
   - Set TX power to 27 dBm (reduce if interference observed).
   - Set Receiver Sensitivity: –70 dBm.
3. Navigate to **LLRP Settings**:
   - Mode: **Initiator** (reader connects to TrackSense).
   - Server host: `tracksense.local` or IP.
   - Server port: `5084`.
   - Reconnect on disconnect: **Yes**.
4. Under **Reader Operation**:
   - Session: 1 (to re-read tags after they pass).
   - Tag Population: Low (single file of horses).
   - Enable **Tag Report** with EPC, Antenna ID, and Timestamp fields.
5. Save and reboot the reader.
6. Confirm the reader appears in the TrackSense gate registry
   within 30 seconds of boot.

For other reader models, consult their LLRP configuration guide and
map settings to the above parameters equivalently.

---

## 8. TrackSense Gate Registration

Register each gate via the TrackSense API before the race meeting.

### 1. Create the venue (if not already registered)

```bash
curl -X POST http://tracksense.local:8000/venues \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "venue_id": "FLEMINGTON",
    "name": "Flemington Racecourse",
    "total_distance_m": 2400.0
  }'
```

### 2. Register each gate

```bash
curl -X POST http://tracksense.local:8000/venues/FLEMINGTON/gates \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "reader_id": "GATE-START",
    "name": "Start",
    "distance_m": 0.0,
    "is_finish": false,
    "position_x": 0.05,
    "position_y": 0.5
  }'
```

Repeat for each gate, increasing `distance_m` and updating `position_x`/`position_y`
based on the normalised GPS coordinates from your site survey.

### 3. Verify geometry

```bash
curl http://tracksense.local:8000/venues/FLEMINGTON/geometry
```

Confirm all expected gates appear with correct `distance_m` values.

---

## 9. End-to-End Validation

Run this checklist before the first race of the meeting.

### Hardware check
- [ ] All readers powered on and showing green status LED
- [ ] All antennas connected and sealed
- [ ] PoE injector/switch showing correct power draw per port

### Network check
- [ ] Ping each reader IP from the TrackSense server
- [ ] `GET /venues/{id}/geometry` returns all registered gates
- [ ] LLRP connection log shows all readers connected

### Tag read test
1. Walk a test chip (bench-mounted implant chip) through each gate.
2. Confirm a gate read event appears in TrackSense within 500 ms.
3. Repeat for both antenna sides (left rail and right rail) at each gate.

```bash
# Watch live gate reads
curl http://tracksense.local:8000/race/status
```

### Full end-to-end
1. Register a test race via `POST /races`.
2. Start the race tracker via `POST /race/start`.
3. Walk test chips through each gate in distance order.
4. Verify `GET /race/state` shows each horse advancing.
5. Walk chips through finish gate.
6. Verify `GET /race/finish-order` returns correct finish positions.
7. Persist results via `POST /races/{id}/persist` and verify the export
   endpoints return valid data.

---

## 10. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| Reader not appearing in registry | LLRP connection not established | Check firewall port 5084; check reader LLRP config |
| Tag reads missing for one side | Antenna cable fault or wrong port | Swap antenna ports; check SMA connectors |
| Cross-reads between adjacent gates | Readers too close or power too high | Reduce TX power; add directional null between gates |
| Read rate drops during race | Tag population mode mismatch | Set Session=1; clear tag population after finish |
| High latency (>1 s) on reads | Network congestion | Dedicate a VLAN for readers; check switch queue depth |
| Reader reboots unexpectedly | PoE power budget exceeded | Check switch total PoE budget; use separate injectors |
| Position on TrackMap is wrong | Incorrect `position_x`/`position_y` | Re-normalise GPS coordinates; update gate via API |

---

## 11. Tear-Down and Pack-Up

After the race meeting:

1. Persist all race results to the database before powering down readers.
2. Back up the TrackSense database file (`tracksense.db`) to an off-site location.
3. Power down readers in reverse order (finish gate last).
4. Label and coil all coax cables (minimum bend radius 100 mm for LMR-400).
5. Return gate records to pending state via the admin dashboard or API.
6. File a post-meeting installation report including:
   - Any cross-reads or missed reads
   - Reader firmware versions in use
   - Environmental conditions (temperature, rain)
   - Suggested geometry improvements for next meeting

---

*Document version: 1.0 — 2026-04-08*
*Owner: TrackSense Platform Team*
