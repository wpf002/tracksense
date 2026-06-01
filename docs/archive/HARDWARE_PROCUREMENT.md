
# TrackSense — Hardware Procurement Spec
## Field Test v1 — Single Finish-Line Gate

### Objective
Prove that a UHF Gen2 lip implant chip can be reliably read at race speed
through a single finish-line antenna gate before investing in multi-gate
track infrastructure.

---

## Component 1 — UHF RFID Reader

### Recommended: Impinj Speedway R220 (2-port)
- Part number: `IPJ-REV-R220-USA2M`
- Price: ~$1,315 new / ~$400–600 refurbished (eBay)
- Interface: Ethernet, PoE 802.3af powered
- RF Sensitivity: -84 dBm
- Protocol: LLRP — works with `sllurp` library already in codebase
- Where to buy: atlasrfidstore.com or eBay refurbished

### Budget Alternative: CHAFON CF-RU5202
- Price: ~$200
- Interface: USB/serial, ASCII output
- Works immediately with `SerialReader` in `hardware/reader.py` — no sllurp needed
- Good for bench testing before committing to Impinj hardware

### Recommendation
Buy one refurbished R220 (~$500) for field deployment and one CHAFON (~$200)
for bench testing. Use the CHAFON to validate the software pipeline first.

---

## Component 2 — Antennas

### Recommended: Times-7 A5010 SlimLine Circular Polarized
- Part number: `A5010-60001-FG` (FCC 902–928 MHz)
- Gain: 8.3 dBiC circular polarized
- Size: 250mm × 250mm × 14mm (10" square, very slim)
- IP67 rated — permanent outdoor use
- Price: ~$150–200 each
- Connector: SMA female
  Requires RPTNC-Male to SMA-Male adapter cable to connect to Impinj R220

### Quantity
2 antennas per gate (one each side of the track width)

### Why Circular Polarized
The chip orientation in the horse's lip is unpredictable as the horse
moves at speed. Circular polarization reads the tag regardless of angle.
Linear polarized antennas will drop reads when the chip is perpendicular
to the antenna beam.

### Mounting
- Height: 0.5–0.7m (lip/nose height at full gallop — head drops and extends)
- Tilt: 10° upward toward track centre line
- Position: One antenna each side of the track, aimed inward

---

## Component 3 — The Chip

**Critical: you need a UHF Gen2 (ISO 18000-6C) injectable glass capsule.
This is NOT the standard LF 134.2 kHz vet microchip. Standard vet chips
have 10–15cm read range and cannot be used for finish-line detection.**

### Option A — Destron Fearing UHF Glass Transponder
- The established name in equine implants
- UHF Gen2, glass capsule, 23mm × 3.85mm
- Distributed by Merck Animal Health
- Contact Merck Animal Health to order

### Option B — Lip Chip (lipchipllc.com)
- Already selling into the equine market with established vet relationships
- ISO compliant, already used in horses at scale
- Can supply chips + syringes separately from their software platform
- Phone: (325) 866-3146
- Fastest path to getting chips in hand

### Option C — Direct manufacturer
- Sites like rfid-life.com and ID Tech Solutions sell injectable UHF glass capsules
- Cheaper per unit but requires more independent validation
- Only recommended once chip spec is confirmed working

### Recommendation
Contact Lip Chip directly first — fastest path, established equine track record.
Order 10 chips + syringes for the first test batch.

---

## Component 4 — Injection Equipment

- 12-gauge sterile needle injector (ships with chips from most suppliers)
- Alcohol swabs, sterile gloves, gauze
- Licensed equine veterinarian to perform injection (legally required)

### Post-Injection Protocol
- Do NOT race within 72 hours of injection
- Verify chip reads with handheld UHF reader immediately post-injection
- Check for migration at each subsequent scan before racing
- Log implant date, vet name, and chip EPC in TrackSense horse profile

---

## Component 5 — Cabling and Power

| Item | Spec | Approx Cost |
|---|---|---|
| PoE injector or switch | 802.3af — powers the R220 | $30–50 |
| LMR-400 coax cable | 2 × 3m runs, antenna to reader | $20–40 each |
| RPTNC-Male to SMA-Male adapter | Connects R220 ports to Times-7 antennas | $15–25 each |
| Antenna mounting brackets | Mount at 0.6m height on posts | $20–40 |
| Weatherproof reader enclosure | NEMA 4 rated box | $40–80 |

---

## Component 6 — Field Computer

Any laptop running macOS or Linux:
- Python 3.12 with TrackSense repo cloned and dependencies installed
- Connected to R220 via Ethernet (direct or through PoE switch)
- Running: `make dev` or `uvicorn app.server:app --port 8001`

---

## Budget Summary — Field Test v1

| Item | Estimated Cost |
|---|---|
| Impinj R220 (refurbished) | ~$500 |
| CHAFON CF-RU5202 (bench test) | ~$200 |
| 2× Times-7 A5010 antennas | ~$350 |
| Cables, PoE injector, enclosure, mounts | ~$200 |
| 10× UHF glass capsule chips + syringes | ~$100–300 |
| Licensed vet injection fee | ~$100–200 |
| **Total** | **~$1,450–1,650** |

---

## Field Test Protocol

### Week 1 — Bench Test (no horse required)
1. Connect CHAFON reader to laptop via USB
2. Run: `python main.py --hardware serial`
3. Wave a UHF chip in front of the reader
4. Confirm reads appear in the backend at `localhost:8001/race/state`
5. Register a horse with that EPC, arm a race, confirm the full flow works
6. Verify the UI shows the horse at the correct gate

### Week 2 — Static Gate Test (no horse required)
1. Mount both antennas at 0.6m height on posts ~15m apart
2. Connect R220 via Ethernet, configure power level via sllurp
3. Tape a chip to a stick at lip height — walk it through the gate at different angles
4. Confirm reads at all angles (circular polarization should handle this)
5. Check duplicate count — should be 4–8 reads per pass at walking speed
6. Adjust antenna aim and power level until consistent

### Week 3 — Horse Test (vet required)
1. Vet injects UHF chip into horse's lower lip
2. Record EPC, log implant in TrackSense horse profile
3. Wait 72 hours minimum
4. Verify chip reads with handheld reader post-healing
5. Walk horse through gate — confirm read, check read count
6. Trot horse through gate — confirm read, count should drop to 3–5
7. Gallop horse through gate — minimum 2 reads per pass required
8. If dropping to 1 read at gallop, adjust antenna aim or increase reader power

### Week 4 — Full Race Test
1. Chip and register 3–5 horses in TrackSense
2. Build a race in Race Builder, arm it
3. Run horses through the finish gate in sequence
4. Confirm finish order appears correctly in the Live Race and Results views
5. Confirm webhook fires to a test endpoint (use httpbin.org/post)
6. Check Horse Profile — verify race result appears in career history

---

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| No reads at gallop | Antenna too high or wrong angle | Lower to 0.5m, increase upward tilt |
| Only 1 read per pass | Reader power too low | Increase transmit power in reader config |
| Reads from wrong horse | Adjacent horse chip in range | Reduce reader power, narrow beam |
| Chip not found post-injection | Migration or deep placement | Handheld scan around entire lip area |
| Backend not receiving reads | sllurp connection issue | Check Ethernet, verify reader IP config |

---

## Software Integration

Once the R220 is connected, replace the mock reader with hardware mode:
```bash
RFID_HOST=192.168.1.100 python main.py --hardware tcp
```

The backend receives reads through the same `/tags/submit` endpoint used
by the mock reader. No backend changes required.

For sllurp-based LLRP integration, replace `TCPReader` in
`hardware/reader.py` with an sllurp client. See `docs/HARDWARE.md`
for the sllurp integration notes.

---

*Last updated: April 2026*
*Status: Pre-procurement — awaiting hardware sourcing decision*
