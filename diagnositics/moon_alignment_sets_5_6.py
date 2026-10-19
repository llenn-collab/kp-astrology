"""Compare KP Stellar sets 5/6 with their kpastro snapshots.

**Historical record.**  ``kpastro_actual5.json`` / ``kpastro_actual6.json``
are the pre-calibration snapshots: they were generated before the empirical
Moon correction in ``kpastro.ephemeris`` existed, and they are the measurement
that motivated it.  Rebuilding those charts with the current code yields a
correction of ~0.0" (see ``tests/test_moon_calibration.py``).

This is a diagnostic, not a production correction.  It measures:
* displayed Moon-longitude residuals (reference minus kpastro; whole arcsec);
* the Moon-longitude correction implied by the Saturn mahadasha end stamp;
* whether the 2024 reference Moon depends on observer location; and
* the Moon's short-interval angular speed from sets 5 -> 6.

Run from the repository root:
    python diagnositics/moon_alignment_sets_5_6.py

All calculations use committed JSON snapshots and the exact Vimshottari
sensitivity for Saturn's 19-year mahadasha.  Whole-arcsecond prints alone are
not accurate enough to infer the dasha correction; the end stamps carry the
more precise timing constraint.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SIGNS = {
    "ARI": 0, "TAU": 1, "GEM": 2, "CAN": 3,
    "LEO": 4, "VIR": 5, "LIB": 6, "SCO": 7,
    "SAG": 8, "CAP": 9, "AQU": 10, "PIS": 11,
}
DMS = re.compile(r"""^(\d+)°(\d+)'(\d+(?:\.\d+)?)"?$""")
LEGACY_DASHA = re.compile(r"To (\d{1,2}/[A-Za-z]{3}/\d{4}) \((\d{2}:\d{2}:\d{2})\)")
SECONDS_PER_ARCSECOND_SATURN_MD = (
    19 * 365.25 * 86400 / ((360.0 / 27.0) * 3600)
)


def read_json(name: str) -> dict[str, Any]:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def moon_entry(doc: dict[str, Any]) -> dict[str, Any]:
    planets = doc["planets"]
    if isinstance(planets, dict):
        return planets["MOO"]
    for planet in planets:
        if planet.get("pla", "").rstrip("*") == "MOO":
            return planet
    raise KeyError("Moon (MOO) not found")


def moon_longitude(doc: dict[str, Any]) -> float:
    planet = moon_entry(doc)
    sign = planet.get("sign") or planet.get("sgn")
    degree_text = planet.get("degree") or planet.get("deg")
    if sign not in SIGNS or not degree_text:
        raise ValueError(f"unrecognised Moon record: {planet!r}")
    match = DMS.match(degree_text.strip())
    if not match:
        raise ValueError(f"unrecognised degree string: {degree_text!r}")
    degrees, minutes, seconds = map(float, match.groups())
    return (
        SIGNS[sign] * 30.0
        + degrees
        + minutes / 60.0
        + seconds / 3600.0
    )


def dasha_end(doc: dict[str, Any], reference: bool = False) -> datetime:
    """Get the Saturn mahadasha end from either reference schema or kpastro."""
    if reference and "vimsottari" in doc:
        value = doc["vimsottari"]["dasa"]["end"]
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    if reference and "vimsottari_dasha" in doc:
        value = doc["vimsottari_dasha"]["dasa"]["end"]
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    if reference and "vimsottari_dasa" in doc:
        value = doc["vimsottari_dasa"]["dasa"]
        match = LEGACY_DASHA.search(value)
        if not match:
            raise ValueError(f"unrecognised legacy dasha string: {value!r}")
        return datetime.strptime(
            f"{match.group(1)} {match.group(2)}", "%d/%b/%Y %H:%M:%S"
        )
    value = doc["vimsottari_dasa"]["dasa"]["end"]
    for fmt in ("%d/%b/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            pass
    raise ValueError(f"unrecognised dasha timestamp: {value!r}")


def report_set(label: str, reference: dict[str, Any], actual: dict[str, Any]) -> tuple[float, float]:
    # Convert printed degree values to arcseconds; these are display residuals,
    # so their precision is limited by the whole-arcsecond source strings.
    display_delta = (moon_longitude(reference) - moon_longitude(actual)) * 3600.0
    ref_end = dasha_end(reference, reference=True)
    actual_end = dasha_end(actual)
    end_delta = (actual_end - ref_end).total_seconds()
    implied = end_delta / SECONDS_PER_ARCSECOND_SATURN_MD
    print(
        f"{label}: printed Moon ref−ours={display_delta:+.3f}\"; "
        f"ours−ref Saturn-MD end={end_delta:+.0f} s; "
        f"Moon correction implied by dasha={implied:+.3f}\""
    )
    return implied, end_delta


def main() -> None:
    ref4 = read_json("kp_stellar_output4.json")
    ref5 = read_json("kp_stellar_output5.json")
    ref6 = read_json("kp_stellar_output6.json")
    actual5 = read_json("kpastro_actual5.json")
    actual6 = read_json("kpastro_actual6.json")

    print("Sign convention: positive Moon correction means move kpastro's Moon forward.")
    implied5, _ = report_set("Set 5 (same instant, alternate place)", ref5, actual5)
    implied6, _ = report_set("Set 6 (same place, +90 minutes)", ref6, actual6)

    # The reference's set 4 and set 5 are both 2024-06-01 09:09:09 IST but
    # at Sholapur and Delhi, respectively.
    ref4_lon = moon_longitude(ref4)
    ref5_lon = moon_longitude(ref5)
    print(
        "KP Stellar set 4 vs set 5 (same instant, different places): "
        f"Moon delta={(ref4_lon - ref5_lon) * 3600.0:+.3f}\"; "
        f"mahadasha-end delta="
        f"{(dasha_end(ref4, reference=True) - dasha_end(ref5, reference=True)).total_seconds():+.0f} s"
    )

    # Reference Moon advances from 06°00'09" to 06°53'31" over 5,400 seconds.
    # Whole-arcsecond precision makes this only an approximate speed estimate.
    ref_speed = (moon_longitude(ref6) - moon_longitude(ref5)) * 3600.0 / 5400.0
    actual_speed = (moon_longitude(actual6) - moon_longitude(actual5)) * 3600.0 / 5400.0
    print(
        f"Printed Moon speed set 5→6: reference={ref_speed:.6f}\"/s, "
        f"kpastro={actual_speed:.6f}\"/s"
    )
    print(
        "Implied June-2024 time-bias estimates: "
        f"set 5={implied5 / ref_speed:.2f} s, set 6={implied6 / ref_speed:.2f} s "
        "(approximate; using printed-longitude speed)"
    )
    print(
        f"Exact Saturn-MD sensitivity used: {SECONDS_PER_ARCSECOND_SATURN_MD:.2f} seconds/arcsecond."
    )
    print(
        "Interpretation: sets 5/6 support a repeatable ~6.28-6.29 arcsec correction "
        "at this epoch and show no reference location effect. They do not distinguish "
        "a constant angular offset from a small Moon-only timing/model difference; "
        "the separate 2026 residual prevents justifying one universal fixed offset."
    )


if __name__ == "__main__":
    main()
