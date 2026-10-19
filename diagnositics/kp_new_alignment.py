"""Measure every comparable leaf of the four KP Stellar reference charts.

Builds sets 1, 4, 5 and 6 in-process with the production configuration
(``kp_new`` ayanamsa, mean node, geocentric house latitude) and reports which
printed values differ from the committed references.  Used to calibrate and
re-check the empirical Moon correction in ``kpastro.ephemeris``.

Run from the repository root::

    python diagnositics/kp_new_alignment.py
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import swisseph as swe

from kpastro.chart import BirthInfo, chart_to_kp_stellar_json, compute_chart
from kpastro.ephemeris import SwissEphemeris
from kpastro.horary import kp_divisions

ROOT = Path(__file__).resolve().parents[1]

SIGNS = {
    "ARI": 0, "TAU": 1, "GEM": 2, "CAN": 3, "LEO": 4, "VIR": 5,
    "LIB": 6, "SCO": 7, "SAG": 8, "CAP": 9, "AQU": 10, "PIS": 11,
}
DMS = re.compile(r"^(\d+)°(\d+)'(\d+(?:\.\d+)?)\"?$")
LEGACY = re.compile(r"To (\d{1,2}/[A-Za-z]{3}/\d{4}) \((\d{2}:\d{2}:\d{2})\)")

#: Birth data of the four references (times are local IST).
SETS: dict[str, dict[str, Any]] = {
    "set1": dict(
        date="2026-10-30", time="12:00:00", lat=18.4593067, lon=73.8654709,
        horary_no=117, query="2026-10-18 12:00:00", ref="kp_stellar_output.json",
    ),
    "set4": dict(
        date="2024-06-01", time="09:09:09", lat=17.64558, lon=75.899954,
        horary_no=57, query="2026-10-19 07:26:41", ref="kp_stellar_output4.json",
    ),
    "set5": dict(
        date="2024-06-01", time="09:09:09", lat=28.65195, lon=77.23149,
        horary_no=57, query="2026-10-19 07:26:41", ref="kp_stellar_output5.json",
    ),
    "set6": dict(
        date="2024-06-01", time="10:39:09", lat=17.64558, lon=75.899954,
        horary_no=69, query="2026-10-19 06:25:04", ref="kp_stellar_output6.json",
    ),
}


def _angle(sign: str, text: str) -> float:
    match = DMS.match(text.strip())
    if not match:
        raise ValueError(f"unparsable degree string {text!r}")
    d, m, s = (float(part) for part in match.groups())
    return SIGNS[sign] * 30.0 + d + m / 60.0 + s / 3600.0


def ref_planets(doc: dict[str, Any]) -> dict[str, float]:
    planets = doc["planets"]
    out: dict[str, float] = {}
    if isinstance(planets, dict):
        for key, value in planets.items():
            out[key] = _angle(value.get("sign") or value.get("sgn"),
                              value.get("degree") or value.get("deg"))
    else:
        for value in planets:
            out[value["pla"].rstrip("*")] = _angle(
                value["sign"], value.get("deg") or value.get("degree")
            )
    return out


def ref_cusps(doc: dict[str, Any]) -> dict[str, float]:
    cusps = doc["cusps"]
    out: dict[str, float] = {}
    if isinstance(cusps, dict):
        for key, value in cusps.items():
            name = str(value.get("name") or value.get("cusp") or key)
            out[name] = _angle(value.get("sign") or value.get("sgn"),
                               value.get("degree") or value.get("deg"))
    else:
        for value in cusps:
            out[str(value.get("cusp") or value.get("name"))] = _angle(
                value["sign"], value.get("degree") or value.get("deg")
            )
    return out


def ref_dasha(doc: dict[str, Any]) -> dict[str, str]:
    for key in ("vimsottari_dasa", "vimsottari", "vimsottari_dasha"):
        if key in doc:
            block = doc[key]
            break
    else:
        return {}
    out: dict[str, str] = {}
    for level in ("dasa", "dasha", "bhukti", "antara", "sookshma", "prana"):
        if level not in block:
            continue
        value = block[level]
        if isinstance(value, dict):
            stamp = value["end"]
        else:
            match = LEGACY.search(value)
            stamp = f"{match.group(1)} {match.group(2)}"
        out["dasa" if level == "dasha" else level] = stamp
    return out


def _as_datetime(stamp: str) -> datetime:
    fmt = "%d/%b/%Y %H:%M:%S" if stamp[2] == "/" else "%Y-%m-%d %H:%M:%S"
    return datetime.strptime(stamp, fmt)


def ref_sun(doc: dict[str, Any]) -> dict[str, str]:
    for key in ("horary_details", "meta", "profile"):
        block = doc.get(key)
        if block:
            return {k: block[k] for k in ("sunrise", "sunset") if k in block}
    return {}


def build(cfg: dict[str, Any]) -> dict[str, Any]:
    eph = SwissEphemeris(ayanamsa="kp_new", node="mean")
    birth = BirthInfo(
        date=datetime.strptime(cfg["date"], "%Y-%m-%d").date(),
        time=datetime.strptime(cfg["time"], "%H:%M:%S").time(),
        latitude=cfg["lat"], longitude=cfg["lon"], tz_hours=5.5, place="ref",
    )
    query = datetime.strptime(cfg["query"], "%Y-%m-%d %H:%M:%S")
    chart = compute_chart(
        birth, ayanamsa="kp_new", node="mean", eph=eph, query_utc=query,
        horary_lagna=kp_divisions()[cfg["horary_no"] - 1].start_deg,
    )
    return chart_to_kp_stellar_json(
        chart, dasha_depth=5, query_utc=query, name="ref", gender="Male",
        horary_no=cfg["horary_no"], timezone="Asia/Kolkata",
    )


def compare(label: str, cfg: dict[str, Any]) -> dict[str, list[str]]:
    ref = json.loads((ROOT / cfg["ref"]).read_text(encoding="utf-8"))
    ours = build(cfg)
    problems: dict[str, list[str]] = {}

    rp, op = ref_planets(ref), {}
    for key, value in ours["planets"].items():
        op[key] = _angle(value["sign"], value["degree"])
    bad = [k for k in rp if k in op and abs(op[k] - rp[k]) >= 1e-9]
    if bad:
        problems["planets"] = bad

    rc, oc = ref_cusps(ref), {}
    for key, value in ours["cusps"].items():
        oc[key] = _angle(value["sign"], value["degree"])
    bad = [k for k in rc if k in oc and abs(oc[k] - rc[k]) >= 1e-9]
    if bad:
        problems["cusps"] = bad

    rd, od = ref_dasha(ref), {}
    for key, value in ours["vimsottari_dasa"].items():
        if isinstance(value, dict):
            od[key] = value["end"]
    bad = [
        f"{k}({(_as_datetime(od[k]) - _as_datetime(rd[k])).total_seconds():+.0f}s)"
        for k in rd
        if k in od and _as_datetime(od[k]) != _as_datetime(rd[k])
    ]
    if bad:
        problems["dasha"] = bad

    rs, os_ = ref_sun(ref), ours.get("horary_details", {})
    bad = [
        f"{k}({os_.get(k)} vs {v})" for k, v in rs.items() if os_.get(k) != v
    ]
    if bad:
        problems["sunrise_sunset"] = bad
    return problems


def main() -> None:
    print(f"Swiss Ephemeris {swe.version}")
    eph = SwissEphemeris(ayanamsa="kp_new")
    print(f"data files: {eph.precision} ({eph.ephe_path})")
    total = 0
    for label, cfg in SETS.items():
        problems = compare(label, cfg)
        total += sum(len(v) for v in problems.values())
        print(f"\n{label}: {'OK' if not problems else ''}")
        for section, entries in problems.items():
            print(f"  {section}: {entries}")
    print(f"\ndiffering leaves: {total}")


if __name__ == "__main__":
    main()
