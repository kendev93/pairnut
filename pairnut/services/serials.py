"""Serial number generation."""

from __future__ import annotations

from ..database import repositories


def next_serial_no(variety_id: int) -> str:
    variety = repositories.get_variety(variety_id)
    if variety is None:
        raise ValueError("Variety not found.")
    prefix = variety["code_prefix"].strip().upper()
    walnuts = repositories.list_walnuts(variety_id=variety_id, include_locked=True)
    max_value = 0
    for walnut in walnuts:
        serial_no = walnut["serial_no"]
        if not serial_no.startswith(f"{prefix}-"):
            continue
        suffix = serial_no.split("-")[-1]
        if suffix.isdigit():
            max_value = max(max_value, int(suffix))
    return f"{prefix}-{max_value + 1:04d}"
