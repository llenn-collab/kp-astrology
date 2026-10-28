#!/usr/bin/env python3
"""Diagnostic: raw vs corrected Moon, planet residuals, node conjunctions
for V7/V8/V9 — to determine what production-code change improves all epochs."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from kpastro.chart import BirthInfo, compute_chart
from kpastro.ephemeris import SwissEphemeris
import kpastro.ephemeris as eph_mod
from kpastro.horary import kp_divisions

ROOT = Path(__file__).resolve().parents[1]

ABBR_TO_FULL = {"SUN": "Sun", "MOO": "Moon", "MAR": "Mars", "MER": "Mercury",
                "JUP": "Jupiter", "VEN": "Venus", "SAT": "Saturn",
                "RAH": "Rahu", "KET": "Ketu"}
SIGNS = ("ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG",
         "CAP", "AQU", "PIS")

VERSIONS = [
    ("V7", "2026-10-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 117,
     "2026-10-18 12:00:00", "kp_stellar_output.json"),
    ("V8", "2027-04-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 117,
     "2027-04-18 12:00:00", "kp_stellar_output8.json"),
    ("V9", "2027-10-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 74,
     "2027-10-18 12:00:00", "kp_stellar_output9.json"),
]

DQ = '"'


def dms(deg):
    deg = deg % 360.0
    d = int(deg)
    rem = (deg - d) * 3600.0
    m = int(rem // 60)
    s = rem - m * 60
    return f"{d:02d}\u00b0{m:02d}'{s:06.3f}{DQ}"


def printed(deg):
    deg = deg % 360.0
    d = int(deg)
    rem = (deg - d) * 3600.0
    m = int(rem // 60)
    s = int(rem - m * 60)
    sign_idx = d // 30
    sign_deg = d % 30
    return f"{sign_deg:02d}\u00b0{m:02d}'{s:02d}{DQ}", SIGNS[sign_idx]


def ref_planets(ref_file):
    ref = json.loads((ROOT / ref_file).read_text(encoding="utf-8"))
    out = {}
    planets = ref.get("planets", []) or []
    if isinstance(planets, dict):
        for abbr, p in planets.items():
            ssl = p.get("sgn_stl_sub_ssl") or []
            if isinstance(ssl, str):
                ssl = ssl.split("|")
            out[str(abbr).upper()] = {
                "degree": p.get("degree"),
                "sign": p.get("sign"),
                "sl": ssl[1] if len(ssl) > 1 else None,
            }
    else:
        for p in planets:
            nm = str(p.get("planet") or p.get("name") or "").replace("*", "").strip()
            abbr = {"SUN": "SUN", "MOO": "MOO", "MAR": "MAR", "MER": "MER",
                    "JUP": "JUP", "VEN": "VEN", "SAT": "SAT", "RAH": "RAH",
                    "KET": "KET", "Sun": "SUN", "Moon": "MOO", "Mars": "MAR",
                    "Mercury": "MER", "Jupiter": "JUP", "Venus": "VEN",
                    "Saturn": "SAT", "Rahu": "RAH", "Ketu": "KET"}.get(
                        nm, nm.upper()[:3])
            ssl = p.get("sgn_stl_sub_ssl") or []
            if isinstance(ssl, str):
                ssl = ssl.split("|")
            out[abbr] = {
                "degree": p.get("degree") or p.get("deg"),
                "sign": p.get("sign"),
                "sl": ssl[1] if len(ssl) > 1 else None,
            }
    return out


def ref_nodes(ref_file):
    ref = json.loads((ROOT / ref_file).read_text(encoding="utf-8"))
    out = {}
    nr = ref.get("nodes_representation") or {}
    for node in ("RAH", "KET"):
        v = nr.get(node)
        if v:
            out[node] = {"planets": list(v.get("planets", [])),
                         "houses": list(v.get("houses", []))}
    # fallback: inside planet entries
    if not out:
        planets = ref.get("planets", []) or []
        if isinstance(planets, dict):
            planets = list(planets.values())
        for p in planets:
            nre = p.get("node_represents")
            if nre:
                nm = str(p.get("planet") or p.get("name") or "").replace("*", "").strip()
                abbr = {"SUN": "SUN", "MOO": "MOO", "MAR": "MAR", "MER": "MER",
                        "JUP": "JUP", "VEN": "VEN", "SAT": "SAT", "RAH": "RAH",
                        "KET": "KET", "Sun": "SUN", "Moon": "MOO", "Mars": "MAR",
                        "Mercury": "MER", "Jupiter": "JUP", "Venus": "VEN",
                        "Saturn": "SAT", "Rahu": "RAH", "Ketu": "KET"}.get(
                            nm, nm.upper()[:3])
                out[abbr] = {"planets": list(nre.get("planets", [])),
                             "houses": list(nre.get("houses", []))}
    return out


def circular_dist(a, b):
    d = abs(a - b) % 360.0
    return min(d, 360.0 - d)


def main():
    # Raw readings with correction disabled
    eph_mod._MOON_CORRECTION_ENABLED = False
    eph_raw = SwissEphemeris(ayanamsa="kp_new", node="mean")
    # Corrected readings
    eph_mod._MOON_CORRECTION_ENABLED = True
    eph_corr = SwissEphemeris(ayanamsa="kp_new", node="mean")

    print(f"precision: {eph_corr.precision}\n")

    for (vid, date, tme, tz, lat, lon, hn, query, ref_file) in VERSIONS:
        ref_p = ref_planets(ref_file)
        ref_n = ref_nodes(ref_file)
        birth = BirthInfo(
            date=datetime.strptime(date, "%Y-%m-%d").date(),
            time=datetime.strptime(tme, "%H:%M:%S").time(),
            latitude=lat, longitude=lon, tz_hours=tz, place="Pune, India",
        )
        instant = datetime.strptime(query, "%Y-%m-%d %H:%M:%S")
        horary_lagna = kp_divisions()[hn - 1].start_deg

        chart_raw = compute_chart(birth, ayanamsa="kp_new", node="mean", eph=eph_raw,
                                  query_utc=instant,
                                  horary_lagna=horary_lagna)
        chart_corr = compute_chart(birth, ayanamsa="kp_new", node="mean", eph=eph_corr,
                                   query_utc=instant,
                                   horary_lagna=horary_lagna)

        jd = eph_raw.jd_ut(birth.utc_datetime())
        raw_moon = eph_raw.body(jd, "Moon")[0]
        corr_moon = eph_corr.body(jd, "Moon")[0]
        correction = (corr_moon - raw_moon) * 3600.0

        rm_print, rm_sign = printed(corr_moon)
        ref_moon_deg = ref_p["MOO"]["degree"]
        ref_moon_sign = ref_p["MOO"]["sign"]

        print(f"===== {vid} — {date} {tme} IST, horary {hn}, query {query} =====")
        print(f" Moon RAW : {dms(raw_moon)}  CORR : {dms(corr_moon)}  (corr +{correction:.3f}\")")
        print(f" Moon kp  : {rm_print} ({rm_sign})   KP St : {ref_moon_deg} ({ref_moon_sign})   "
              f"print match: {rm_print == ref_moon_deg and rm_sign == ref_moon_sign}")

        print(" Planet residuals (kpastro-corr − KP Stellar, arcsec):")
        all_within_1 = True
        for abbr in ("SUN", "MOO", "MAR", "MER", "JUP", "VEN", "SAT", "RAH", "KET"):
            full = ABBR_TO_FULL[abbr]
            kp_lon = chart_corr.planet_lon[full]
            r = ref_p[abbr]
            r_abs = dms_to_abs(r["degree"], r["sign"])
            resid = (kp_lon - r_abs) * 3600.0
            kp_print, kp_sign = printed(kp_lon)
            match = "OK" if (kp_print == r["degree"] and kp_sign == r["sign"]) else "DIFF"
            if match == "DIFF":
                all_within_1 = False
            print(f"   {abbr}: kp={dms(kp_lon)} ({kp_sign})  ref={r['degree']} ({r['sign']})  "
                  f"resid={resid:+.2f}\"  [{match}]")
        print(f"   All planets print-match: {all_within_1}")

        # Node conjunction scan (orb 1.0 deg)
        print(" Node conjunction scan (orb 1.0 deg):")
        rahu = chart_corr.planet_lon["Rahu"]
        ketu = chart_corr.planet_lon["Ketu"]
        for abbr in ("SUN", "MOO", "MAR", "MER", "JUP", "VEN", "SAT"):
            pl = chart_corr.planet_lon[ABBR_TO_FULL[abbr]]
            dr = circular_dist(pl, rahu)
            dk = circular_dist(pl, ketu)
            tag = ""
            if dr < 1.0:
                tag += f" conj-RAH({dr*60:.0f}')"
            if dk < 1.0:
                tag += f" conj-KET({dk*60:.0f}')"
            if tag:
                print(f"   {abbr}:{tag}")
        print()

        # Node representation comparison
        print(" Node representation:")
        for node in ("RAH", "KET"):
            kp_n = chart_corr  # computed below
        print()

    eph_mod._MOON_CORRECTION_ENABLED = True


def dms_to_abs(text, sign):
    t = text.replace("\u00b0", " ").replace("'", " ").replace(DQ, " ")
    parts = [p for p in t.split() if p]
    deg = int(parts[0]) + int(parts[1]) / 60.0 + float(parts[2]) / 3600.0
    return deg + SIGNS.index(sign) * 30.0


if __name__ == "__main__":
    main()
