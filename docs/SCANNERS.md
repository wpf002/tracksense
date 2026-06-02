# LF Microchip Scanners

TrackSense identifies every horse by its **Jockey Club LF microchip** — the
ISO 11784/11785 FDX-B chip already implanted for breed registration. It is read
with a **commodity handheld scanner** at arm's length while the horse stands
still. This is a deliberate point-of-care scan, not an automatic gate read.

## Chip ID format

- **15-digit numeric** string (ISO 11784/11785 FDX-B), e.g. `985112000000001`.
- TrackSense validates `^\d{15}$` (`app/identity.py`). Non-15-digit values are
  rejected at horse creation and at scanner lookup.

## Supported readers (v1)

All of these present as a **USB HID keyboard wedge** by default — they "type" the
scanned chip number followed by Enter into whatever field is focused. That's the
v1 integration path: no driver, no SDK.

| Reader | Notes |
|--------|-------|
| **Halo Scanner** | USB HID keyboard wedge; also BLE on some models. |
| **Datamars iMax+ / GPR+** | HID keyboard wedge over USB; serial mode available. |
| **Microsensys** readers | HID keyboard wedge or USB-serial (CDC). |

Most also offer a **USB-serial (CDC)** mode. A serial driver is **out of scope for
v1** (deferred); the HID-wedge path covers the demo and pilot.

## How a scan reaches TrackSense

The **Quick Check-In** screen (`/mobile/checkin`) auto-focuses the Chip ID input.
With a reader in HID-wedge mode:

1. Scan the chip → the 15 digits + Enter land in the focused field.
2. TrackSense looks the horse up (`GET /horses/{chip_id}/summary`) and shows
   identity + welfare/compliance flags (temperature alert, recent works, open
   test-barn, vet records).
3. The official optionally enters a temperature and taps **Check In**, which
   records the visit (`POST /horses/{chip_id}/checkins`).

Because it's a keyboard wedge, the same flow works by **typing** the chip number on
any device — useful when no reader is attached.

## macOS / browser notes

- HID-wedge readers need no permission — they emulate a keyboard. Just keep the
  Chip ID field focused (the screen auto-focuses it on load and after each check-in).
- For USB-serial mode (not used in v1), the OS assigns a `/dev/tty.usb*` device and
  a serial driver would be required — deferred.

## Out of scope (later)

USB-serial / CDC drivers, BLE pairing, multi-reader desk setups, and chip
enrollment/registration against the Jockey Club registry. v1 is read-and-resolve
via the HID wedge.
