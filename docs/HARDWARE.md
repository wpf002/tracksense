# TrackSense Hardware Reference

## Overview

TrackSense needs to detect **which horse crossed the finish line, in what order, at race speed**.

A thoroughbred covers the finish line at approximately **60–70 km/h (37–43 mph)**. The system has roughly **50–150ms** to read each tag as the horse transits the antenna field. Every hardware decision flows from this constraint.

---

## Why NOT the Standard Horse Microchip

Every registered horse has an ISO 11784/11785 LF (134.2 kHz) microchip implanted in the nuchal ligament of the neck. **This chip cannot be used for finish-line detection.** Reasons:

- Read range: 10–15 cm maximum
- Requires reader to be essentially in contact with the horse
- LF cannot read through tissue and movement at speed
- No realistic antenna geometry covers a full race track width

**The vet microchip is for identification only.** TrackSense uses a separate UHF tag that is physically attached to the horse's racing equipment for each race.

---

## Tag Standard: UHF Gen2 (EPC Class 1 Gen 2 / ISO 18000-6C)

| Property | Value |
|---|---|
| Frequency | 902–928 MHz (US) / 865–868 MHz (EU) |
| Read range | 3–8 metres (passive, no battery) |
| Read speed | <1ms per tag |
| Multi-tag | 100s of tags/second (anti-collision built in) |
| Tag cost | $0.10–$2.00 depending on form factor |

This is the correct standard. It is used in logistics, livestock tracking, and official RFID race timing systems (e.g. ChronoTrack, MyLaps RFID).

### Tag Form Factor Selection

For horse racing, the tag needs to survive sweat, contact, and movement. Options:

| Form Factor | Mount Location | Notes |
|---|---|---|
| **Flexible wet inlay** | Laminated into race number bib | Most common in official systems. Hidden from view. |
| **Hard ABS enclosure** | Girth strap loop or breastplate D-ring | Survives washing, reusable, easy to swap per race |
| **Adhesive label inlay** | Inside back of saddle cloth | Low cost, single-use |
| **Cable-tie mount** | Fetlock boot or tendon boot | Lower priority — leg movement increases read variance |

**Recommendation: Flexible inlay laminated into the saddle cloth number.** This is how major RFID race timing systems operate. The tag is at ~1.0–1.2m height, centred on the horse, and presents broad face to the antenna.

---

## Reader Hardware

### Recommended: Impinj R220 or R420

| Spec | R220 | R420 |
|---|---|---|
| Antennas | 2 ports | 4 ports |
| Read rate | 150 tags/sec | 1100 tags/sec |
| Interface | Ethernet (LLRP) | Ethernet (LLRP) |
| IP rating | IP52 | IP52 |
| Power | PoE or 12V DC | PoE or 12V DC |

The R220 is sufficient for a finish line with 2 antennas. The R420 is better if you want 4 antenna ports for redundancy.

**Software interface:** Use [sllurp](https://github.com/ransford/sllurp) — open source Python LLRP client. Replace the `TCPReader` class in `hardware/reader.py` with an sllurp-based reader when moving to Impinj.

### Budget Alternative: CHAFON CF-RU5202 or similar

- Serial/USB output, ASCII protocol
- Works with `SerialReader` in `hardware/reader.py` as-is
- Typical output: `EPC: E200681100000000AABBCCDD\r\n`
- Read range is shorter (2–4m) but adequate with close antenna placement
- ~$150–300 USD

---

## Antenna Configuration

### Geometry: Gate Setup

Place two antennas in a **gate configuration** straddling the track at the finish line.

```
TRACK WIDTH (~15–25m)
|←————————————————————————————→|

[ANT-L]                    [ANT-R]
  │         HORSE →          │
  │    ←——antenna field——→   │
  │                           │

Post/Rail                Post/Rail
~1.2m height             ~1.2m height
Aimed inward             Aimed inward
```

- Each antenna covers half the track width
- For wider tracks (>15m) use 4 antennas (2 per side, staggered)
- Mount height: **1.0–1.3m** — targets the saddle cloth / girth area
- Aim: **15–20° downward tilt** toward the track centre line

### Antenna Specs

| Property | Requirement |
|---|---|
| Polarisation | **Circular (RHCP)** — handles tag orientation variation |
| Gain | 6–9 dBiC |
| Frequency | Must match reader band (902–928 MHz US) |
| Cable | LMR-400 or equivalent low-loss coax |
| Max cable run | 10m with LMR-400 before meaningful loss |
| Connector | RP-TNC or N-type (match reader port) |

**Do not use linear polarised antennas.** Tag read rate drops significantly when tag and antenna polarisation are misaligned, and you cannot control tag angle on a moving horse.

### Recommended Antennas

- **Laird S9028PCR** — 8.5 dBiC circular, outdoor rated, $150–200
- **Times-7 A6028-RA** — excellent pattern, rain cover available
- **Budget:** MTI MT-242020/TRH — adequate for testing

---

## Power and Weatherproofing

| Item | Spec |
|---|---|
| Reader power | PoE (802.3af) preferred — single cable, no separate PSU |
| PoE injector/switch | Any 802.3af capable switch |
| Cable runs to antennas | LMR-400, weatherproof N-type connectors |
| Reader enclosure | NEMA 4 rated box if outdoors (IP52 reader in IP65 box) |
| Antenna connectors | Seal with self-amalgamating tape at the antenna port |
| Operating temp | Most UHF readers: -20°C to +55°C |

If the reader is inside a timing tower or judges' booth, only the antenna cables need to run outdoors.

---

## Connecting to TrackSense

### With Impinj (LLRP/TCP)

```python
# In hardware/reader.py, replace TCPReader with:
# pip install sllurp

from sllurp.llrp import LLRPClient

# sllurp fires a callback on each tag read
# In the callback, call emit_tag(epc) → POST to /tags/submit
```

The EPC (Electronic Product Code) from the reader IS the tag_id. Register horses in TrackSense with their EPC as the horse_id.

### With Serial/USB Reader

```bash
# Identify device
ls /dev/ttyUSB* /dev/ttyACM*

# Check baud rate in reader config (usually printed on reader or in manual)
# Common: 115200, 57600, 9600

# Run TrackSense in hardware mode
python main.py --hardware serial

# Or set env vars:
RFID_PORT=/dev/ttyUSB0 RFID_BAUD=115200 python main.py --hardware serial
```

---

## EPC / Tag ID Management

EPC codes from UHF tags are 12-byte (96-bit) hex strings like:
```
E200 6811 0000 0000 AABB CCDD
```

**Two approaches for horse-to-EPC mapping:**

1. **Pre-programmed tags:** Write a simple ID (e.g. "TAG-001") into the EPC field when you program the tag. Register horses in TrackSense with that ID.

2. **Read factory EPC, then register:** Read each tag's factory EPC, then use `/race/register` to map that EPC to a horse name. More robust — no programming equipment needed.

Approach 2 is recommended for field use. You can read EPCs with any UHF reader and a laptop before the race.

---

## Validation Before Live Use

1. **Static read test:** Mount antennas, place a tagged saddle cloth at the finish line, confirm reads appear at `/race/finish-order`
2. **Walk-speed test:** Walk a person through the gate carrying the tag. Confirm read.
3. **Trot test:** Trot a horse through. Confirm read. Check duplicate count — should be 3–10 reads per pass.
4. **Full-speed test:** Gallop a horse through. If read rate drops below 2 per pass, adjust antenna aim or increase reader power level.
5. **Multi-horse test:** Send 2–3 horses through simultaneously. Confirm all are recorded in correct order.

---

## Known Limitations and Mitigations

| Issue | Cause | Mitigation |
|---|---|---|
| Missed read | Tag obscured by jockey leg, sweat, foil on saddle | Place 2nd tag at different location on same horse (breastplate) |
| Wrong order | Two horses nose-to-nose within 50ms | Acceptable in practice — photo finish decides < 1 length margins |
| Duplicate tag IDs | Two tags with same EPC | Check EPC uniqueness before race. Factory EPCs are globally unique. |
| Reader reboot mid-race | Power interruption | PoE + UPS on the PoE switch. 10-minute battery covers any race. |
| RF interference | Other 900MHz devices near finish line | Coordinate with venue. Race-day comms often use 460MHz or 800MHz — usually fine. |
