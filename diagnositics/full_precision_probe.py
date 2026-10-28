#!/usr/bin/env python3
"""Full-precision residual probe for V7/V8/V9 (sign-relative cusps).

Compares kpastro's full-precision (milliarcsecond) cusp longitudes against the
KP Stellar references' *printed* arcsecond values, both expressed as degrees
within their sign.  Because the references truncate to whole arcseconds, the
true residual lies within +/-1" of the printed delta.

Addresses Phase 3 (Moon full-precision residual) and Phase 5 item 1
(compare full-precision cusp values, not only printed strings).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from kpastro.chart import BirthInfo, chart_to_kp_stellar_json, compute_chart
from kpastro.ephemeris import SwissEphemeris
from kpastro.horary import kp_divisions
from kpastro.vedic import point_info

ROOT = Path(__file__).resolve().parents[1]
DQ = '"'
SIGN_ABBR = ("ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG",
             "CAP", "AQU", "PIS")
ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
                "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}


def cusp_key(raw):
    if raw is None:
        return None
    if raw == "Asc":
        return "1"
    if raw in ROMAN_TO_INT:
        return str(ROMAN_TO_INT[raw])
    return str(raw)

VERSIONS = [
    ("V7", "2026-10-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 117,
     "2026-10-18 12:00:00", "kp_stellar_output.json"),
    ("V8", "2027-04-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 117,
     "2027-04-18 12:00:00", "kp_stellar_output8.json"),
    ("V9", "2027-10-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 74,
     "2027-10-18 12:00:00", "kp_stellar_output9.json"),
]


def deg_to_dms(deg):
    deg = deg % 360.0
    d = int(deg)
    rem = (deg - d) * 3600.0
    m = int(rem // 60)
    s = rem - m * 60
    return d, m, s


def fmt(deg):
    d, m, s = deg_to_dms(deg)
    return "{:02d}\u00b0{:02d}'{:06.3f}{}".format(d, m, s, DQ)


def parse_printed_dms(text):
    if not text:
        return None
    t = text.strip().replace("\u00b0", " ").replace("'", " ").replace(DQ, " ")
    parts = [p for p in t.split() if p]
    if len(parts) < 3:
        return None
    return int(parts[0]) + int(parts[1]) / 60.0 + float(parts[2]) / 3600.0


def ref_cusps_map(ref):
    """Return {house_str: printed_sign_relative_degrees} from a KP Stellar ref."""
    out = {}
    cusps = ref.get("cusps", []) or []
    if isinstance(cusps, dict):
        items = list(cusps.items())
    else:
        items = [(c.get("cusp"), c) for c in cusps]
    for raw_key, c in items:
        if isinstance(c, dict):
            key = c.get("cusp") or raw_key
            deg = c.get("degree")
        else:
            key = raw_key
            deg = c
        key = cusp_key(key)
        out[key] = deg
    return out


def main():
    eph = SwissEphemeris(ayanamsa="kp_new", node="mean")
    assert eph.precision == "full"
    for (vid, date, tme, tz, lat, lon, hn, query, ref_file) in VERSIONS:
        ref = json.loads((ROOT / ref_file).read_text(encoding="utf-8"))
        birth = BirthInfo(
            date=datetime.strptime(date, "%Y-%m-%d").date(),
            time=datetime.strptime(tme, "%H:%M:%S").time(),
            latitude=lat, longitude=lon, tz_hours=tz, place="Pune, India",
        )
        instant = datetime.strptime(query, "%Y-%m-%d %H:%M:%S")
        chart = compute_chart(birth, ayanamsa="kp_new", node="mean", eph=eph,
                              query_utc=instant,
                              horary_lagna=kp_divisions()[hn - 1].start_deg)
        out = chart_to_kp_stellar_json(chart, dasha_depth=5, query_utc=instant,
                                       name="X", gender="Male", horary_no=hn,
                                       timezone="Asia/Kolkata")

        print("\n" + "=" * 66)
        print("### {} full-precision residuals (kpastro vs KP Stellar printed)".format(vid))
        print("=" * 66)

        # Moon
        moon_full = chart.planet_lon["Moon"]
        moon_info = point_info(moon_full)
        print(" Moon full-precision kpastro : {}  ({} {:02d}'{:06.3f}\")".format(
            fmt(moon_full), moon_info.sign,
            *deg_to_dms(moon_info.sign_degree)))
        print(" Moon printed by kpastro    : {}".format(out["planets"]["MOO"]["degree"]))
        ref_moon = None
        planets = ref.get("planets", []) or []
        if isinstance(planets, dict):
            for abbr, p in planets.items():
                if str(abbr).upper() == "MOO":
                    ref_moon = p.get("degree")
                    break
        else:
            for p in planets:
                nm = p.get("planet") or p.get("name") or p.get("pla")
                if nm and str(nm).replace("*", "").strip() == "MOO":
                    ref_moon = p.get("degree") or p.get("deg")
                    break
        print(" Moon printed by KP Stellar : {}".format(ref_moon))
        print("   printed Moon equal: {}".format(
            out["planets"]["MOO"]["degree"] == ref_moon))

        # Cusps: full-precision sign-relative vs printed sign-relative
        print("\n Cusps (full-precision sign-relative kpastro vs printed KP Stellar):")
        ref_cusps = ref_cusps_map(ref)
        for i in range(1, 13):
            key = str(i)
            c = chart.cusps[i - 1]
            info = point_info(c.longitude)
            full_sign_rel = info.sign_degree
            kp_printed = out["cusps"][key]["degree"]
            printed_ref = ref_cusps.get(key)
            resid_str = ""
            if printed_ref:
                ref_deg = parse_printed_dms(printed_ref)
                if ref_deg is not None:
                    resid = (full_sign_rel - ref_deg) * 3600.0
                    resid_str = "{:+.2f}\"".format(resid)
            print("   cusp {:>2}: full={:>13}  kp_printed={}  ref_printed={}  resid_vs_ref={}".format(
                i, fmt(full_sign_rel), kp_printed, printed_ref, resid_str))


if __name__ == "__main__":
    main()
