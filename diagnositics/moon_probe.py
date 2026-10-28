#!/usr/bin/env python3
"""Clean raw vs corrected Moon probe — toggles the global flag between calls."""
from __future__ import annotations

from datetime import datetime

from kpastro.chart import BirthInfo, compute_chart
from kpastro.ephemeris import SwissEphemeris
import kpastro.ephemeris as eph_mod
from kpastro.horary import kp_divisions

VERSIONS = [
    ("V7", "2026-10-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 117,
     "2026-10-18 12:00:00"),
    ("V8", "2027-04-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 117,
     "2027-04-18 12:00:00"),
    ("V9", "2027-10-30", "12:00:00", 5.5, 18.4593067, 73.8654709, 74,
     "2027-10-18 12:00:00"),
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
    sign = ("ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG",
            "CAP", "AQU", "PIS")[d // 30]
    return f"{d % 30:02d}\u00b0{m:02d}'{s:02d}{DQ}", sign


def main():
    eph = SwissEphemeris(ayanamsa="kp_new", node="mean")
    print(f"precision: {eph.precision}\n")

    for (vid, date, tme, tz, lat, lon, hn, query) in VERSIONS:
        birth = BirthInfo(
            date=datetime.strptime(date, "%Y-%m-%d").date(),
            time=datetime.strptime(tme, "%H:%M:%S").time(),
            latitude=lat, longitude=lon, tz_hours=tz, place="Pune, India",
        )
        instant = datetime.strptime(query, "%Y-%m-%d %H:%M:%S")
        jd = eph.jd_ut(birth.utc_datetime())

        # Raw (correction OFF)
        eph_mod._MOON_CORRECTION_ENABLED = False
        raw_moon = eph.body(jd, "Moon")[0]

        # Corrected (correction ON)
        eph_mod._MOON_CORRECTION_ENABLED = True
        corr_moon = eph.body(jd, "Moon")[0]

        correction = (corr_moon - raw_moon) * 3600.0
        rp, rs = printed(corr_moon)

        # What correction would make kpastro match KP Stellar's printed value?
        kp_stellar_moon = {"V7": "08\u00b031'49\"", "V8": "01\u00b008'31\"",
                           "V9": "21\u00b022'53\""}[vid]
        kp_stellar_abs = None

        print(f"===== {vid} — {date} {tme} IST =====")
        print(f" Moon RAW  : {dms(raw_moon)}")
        print(f" Moon CORR : {dms(corr_moon)}  (applied correction +{correction:.3f}\")")
        print(f" Moon print: {rp} ({rs})")
        print(f" Model correction at this epoch: +{correction:.3f}\"")

        # Compute what correction is NEEDED
        t = kp_stellar_moon.replace("\u00b0", " ").replace("'", " ").replace(DQ, " ")
        parts = [p for p in t.split() if p]
        ks_abs = int(parts[0]) + int(parts[1]) / 60.0 + float(parts[2]) / 3600.0
        ks_abs += ("ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG",
                   "CAP", "AQU", "PIS").index(rs) * 30.0
        raw_abs = raw_moon % 360.0
        needed = (ks_abs - raw_abs) * 3600.0
        print(f" KP Stellar Moon: {kp_stellar_moon} (= {ks_abs:.6f}\" abs in sign)")
        print(f" Correction NEEDED to match: +{needed:.3f}\"")
        print(f" Correction EXCESS (model − needed): +{correction - needed:+.3f}\"")
        print()

    eph_mod._MOON_CORRECTION_ENABLED = True


if __name__ == "__main__":
    main()
