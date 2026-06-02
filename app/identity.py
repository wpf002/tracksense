"""
identity.py

Horse identity is the Jockey Club LF microchip ID — a 15-digit numeric value
(ISO 11784/11785 FDX-B) read by a commodity handheld scanner. This replaces the
prior UHF EPC. One helper here is the single source of truth for what a valid
chip ID looks like; reused by horse creation and the scanner lookup path.
"""

import re

CHIP_ID_RE = re.compile(r"^\d{15}$")


def normalize_chip_id(raw: str) -> str:
    """Strip surrounding/inner whitespace from a scanned or typed chip ID."""
    if raw is None:
        return ""
    return "".join(str(raw).split())


def is_valid_chip_id(raw: str) -> bool:
    """A valid Jockey Club LF chip ID is exactly 15 digits (ISO 11784/11785 FDX-B)."""
    return bool(CHIP_ID_RE.match(normalize_chip_id(raw)))
