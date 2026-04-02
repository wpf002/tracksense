# TrackSense Hardware Reference

## Lip-Implant UHF RFID Finish-Line System

---

## Why Lip Implant, Not Saddle Cloth

The standard approach in commercial RFID race timing (MyLaps, ChronoTrack) uses tags attached to racing equipment. TrackSense takes a different approach: a **permanent UHF glass capsule implant in the horse's lower lip**.

Advantages:

- Permanent identification — no pre-race tagging ritual, no tag left on the rail
- Cannot be lost, forgotten, or placed on the wrong horse
- Lip tissue is thin → better RF signal transmission than neck or hindquarter implant sites
- Horse's head leads the body at the finish line → chip enters the antenna field before the body mass obstructs signal

---

## Why NOT the Standard Vet Microchip

Every registered horse already has an ISO 11784/11785 **LF (134.2 kHz)** chip in the nuchal ligament of the neck. This chip **cannot be used for finish-line detection**:

- Maximum read range: 10–15 cm in open air, ~8–12 cm through tissue
- At 65 km/h, a horse's lip transits a fixed point in ~8ms
- The antenna would need to be essentially in contact with the horse
- LF chips have no anti-collision — multiple horses simultaneously = unreadable

**The vet microchip is for identity verification only.** TrackSense requires a separate UHF chip.

---

## Recommended Chip: UHF Gen2 Glass Capsule

| Property | Value |
| --- | --- |
| Standard | EPC Class 1 Gen 2 / ISO 18000-6C |
| Frequency | 902–928 MHz (US) / 865–868 MHz (EU) |
| Form factor | Glass capsule, 23mm × 3.85mm |
| Injection | Standard 12-gauge implant gun — same procedure as vet microchip |
| Open-air read range | 3–8m |
| Through-tissue (lip) read range | 60–100cm |
| Read time at 65 km/h | ~8ms transit window, 2–4 reads per pass |
| Anti-collision | Yes — multiple horses simultaneously readable |
| EPC programmable | Yes — write horse ID before injection |

### Specific Products

- **Destron Fearing UHF Glass Transponder** — well-established livestock implant, UHF Gen2
- **Allflex UHF Injectable Transponder** — widely available, ISO 18000-6C compliant
- **Pit Tag UHF 23mm** — commonly used in fish/wildlife tagging, suitable for equine lip

All of the above use the same 12-gauge needle injector. The procedure is identical to a standard microchip implant.

---

## Injection Site: Lower Lip

**Anatomy:** The lower lip (labium inferius) has a thin layer of submucous tissue over the orbicularis oris muscle. This is thinner than the nuchal ligament site used for the standard vet chip — meaning better RF signal transmission.

**Procedure:**

1. Clean the injection site with antiseptic
2. Tent the lip tissue with thumb and forefinger
3. Insert the 12-gauge needle parallel to the lip surface, bevel up
4. Deposit the capsule into the submucous layer, not the muscle
5. Withdraw needle, apply light pressure for 10 seconds
6. Verify implant with handheld UHF reader immediately post-injection
7. Log the EPC against the horse's registered identity

**Aftercare:** No special aftercare required. The glass capsule is inert. The injection site heals within 48–72 hours.

**Orientation:** The capsule will settle parallel to the lip surface. This is acceptable — circular polarised antennas handle any tag orientation.

**Vet sign-off:** This is a minor veterinary procedure. Must be performed or supervised by a licensed veterinarian.

---

## Reader Hardware

### Recommended: Impinj R220

| Spec | Value |
| --- | --- |
| Antenna ports | 2 |
| Read rate | 150 tags/sec |
| Interface | Ethernet (LLRP protocol) |
| Power | PoE (802.3af) |
| IP rating | IP52 (put in NEMA 4 box outdoors) |
| Range | Configured via power level — set to cover 80–100cm |

For LLRP integration with TrackSense, use [sllurp](https://github.com/ransford/sllurp) (open source Python LLRP client) and replace the `TCPReader` class in `hardware/reader.py`.

### Budget Alternative: CHAFON CF-RU5202

- USB/serial output, ASCII protocol
- Works with `SerialReader` in `hardware/reader.py` out of the box
- Read range 2–4m (more than enough at 60–100cm implant range)
- ~$200 USD

---

## Antenna Configuration for Lip-Height Reading

The lip implant changes antenna geometry significantly compared to a saddle cloth system. The horse's nose is at **0.5–0.8m** at full gallop (head drops and extends forward).

### Gate Layout

```text
TRACK WIDTH (~15–25m)
|←————————————————————————————→|

[ANT-L]  ←— 0.5–0.7m height —→  [ANT-R]
   │                               │
   │      ← antenna field →        │
   │   HEAD leads body at finish   │
   │                               │
Post                             Post
aimed inward + 10° upward tilt
```

- Antenna height: **0.5–0.7m** — targets nose/lip height at race speed
- Tilt: **10° upward** — the horse's head is extended forward and slightly down; aiming slightly up centres the field on the lip
- For track widths >12m: use 4 antennas (2 per side), overlapping fields in the centre
- Gate depth (front to back): 0.5–1.0m — enough for 2–4 reads at race speed

### Antenna Specs

| Property | Requirement |
| --- | --- |
| Polarisation | **Circular (RHCP)** — tag orientation in lip varies, linear will miss reads |
| Gain | 6–8 dBiC |
| Frequency | Match reader band exactly |
| Cable | LMR-400, max 10m run |
| Connector | N-type or RP-TNC (match reader port) |

**Recommended:** Laird S9028PCR or Times-7 A6028-RA. Both are outdoor-rated, circular polarised, and well-suited to this geometry.

---

## EPC Programming and Horse Registration

Each chip is programmed with a unique EPC before injection. Recommended format:

```text
E200 6811 0000 0001 XXXX XXXX
                    ↑ unique horse ID (hex)
```

**Workflow:**

1. Program EPC onto chip with a desktop UHF programmer before injection
2. Record EPC → horse name mapping in your horse registry
3. Before each race, POST to `/race/register` with each horse's EPC as `horse_id`
4. ARM the race — backend is ready to receive finish-line reads

Alternatively: inject factory-EPC chips, read the EPC post-injection with a handheld reader, and register that EPC to the horse. No programmer needed.

---

## Power and Weatherproofing

| Item | Spec |
| --- | --- |
| Reader power | PoE 802.3af — single cable, no separate PSU at the rail |
| PoE switch/injector | Any 802.3af switch in the timing booth |
| Backup power | Small UPS on the PoE switch — 10 min covers any race |
| Reader enclosure | IP52 reader in IP65/NEMA 4 box at the post |
| Antenna cables | LMR-400 with self-amalgamating tape on all outdoor connectors |
| Operating temp | -20°C to +55°C (standard UHF readers) |

---

## Pre-Race Validation Protocol

Run this before every race meeting:

1. **Static read:** Place a programmed chip (same form factor as implant) at lip height in the gate centre. Confirm read at `/race/finish-order`.
2. **Walk pass:** Walk a person through carrying the chip at 0.6m height. Confirm read. Check duplicate count — should be 4–8 reads at walking speed.
3. **Trot pass:** Trot a horse through. Confirm read. Duplicate count should drop to 3–5.
4. **Gallop pass:** Gallop a horse through. Minimum acceptable: 2 reads per pass. If dropping to 1, adjust antenna aim or increase reader transmit power.
5. **Simultaneous pass:** Send 2 horses through the gate together. Confirm both EPCs recorded in correct order.
6. **Noise check:** Confirm no phantom reads appear between passes. If they do, reduce reader power level slightly.

---

## Known Limitations

| Issue | Cause | Mitigation |
| --- | --- | --- |
| Missed read | Chip rotated perpendicular to antenna at transit | Circular polarised antenna handles this — if still missing, add a second antenna at a different angle |
| Swollen lip post-injection | Normal tissue response | Do not race within 72 hours of injection |
| Chip migration | Rare, can move along lip tissue plane | Verify chip position with handheld reader at each race meeting |
| Two horses nose-to-nose | Photo finish margin | System records order accurately if any time gap exists; margins under ~5ms are photo finish territory regardless of timing method |
| Reader power interruption | Cable fault, power loss | UPS on PoE switch; redundant antenna on second reader port |