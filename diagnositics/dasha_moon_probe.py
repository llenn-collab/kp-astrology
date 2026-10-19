"""Dasha-vs-Moon convention probe (diagnostic only, TASK2 §2.A).

Run from the repo root with the full ephemeris installed:
    SE_EPHE_PATH=$HOME/.kpastro/ephe venv/bin/python diagnositics/dasha_moon_probe.py

For every documented Swiss Ephemeris Moon convention the script reports:
  * the sidereal-Moon shift it produces (arcsec, vs the current pipeline),
  * the resulting max error of the five vimsottari_dasa.*.end stamps (s),
  * whether the reference's printed Moon is reproduced under truncation (T)
    and under half-up (H) display rounding,
plus two fine scans: the Moon-longitude shift that best reproduces the
stamps, and the pure Moon-only time-base shift that does so.

Nothing here changes library behaviour; reference values are read from
kp_stellar_output.json, never hard-coded.
"""
import json
import re
from datetime import datetime, date, time

import swisseph as swe

from kpastro.chart import BirthInfo, compute_chart, local_datetime
from kpastro.deep_dasha import deep_current_periods
from kpastro.ephemeris import SwissEphemeris, _AYANAMSA_OFFSETS_DEG
from kpastro.horary import kp_divisions

REF = json.load(open("kp_stellar_output.json"))
KEYS = ["dasa", "bhukti", "antara", "sookshma", "prana"]
REF_STAMPS = [REF["vimsottari_dasa"][k]["end"] for k in KEYS]
SIGNS = ["ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG", "CAP", "AQU", "PIS"]
OFFSET_DEG = _AYANAMSA_OFFSETS_DEG["kp_new"]
LAT, LON = 18.4593067, 73.8654709
QUERY = datetime(2026, 10, 18, 12, 0, 0)
# Use the pipeline's own UTC->JD conversion: swe.utc_to_jd sits +0.3718 s from
# swe.julday, which moves the Moon by 0.225" -- large enough to matter here.
JD0 = None   # set after `birth` is built below
JD_JUL = swe.julday(2026, 10, 30, 6.5)
BASE = swe.FLG_SWIEPH | swe.FLG_SPEED

swe.set_sid_mode(swe.SIDM_KRISHNAMURTI_VP291)

birth = BirthInfo(date=date(2026, 10, 30), time=time(12, 0, 0), latitude=LAT,
                  longitude=LON, tz_hours=5.5, place="Pune, India")
JD0 = SwissEphemeris(ayanamsa="kp_new", node="mean").jd_ut(birth.utc_datetime())
chart = compute_chart(birth, ayanamsa="kp_new", node="mean", query_utc=QUERY,
                      horary_lagna=kp_divisions()[116].start_deg)
MOON0 = chart.planet_lon["Moon"]


# ------------------------------------------------------------- reference
_m = re.match(r"(\d+)°(\d+)'(\d+)", REF["planets"]["MOO"]["degree"])
REF_MOO_SIG = SIGNS.index(REF["planets"]["MOO"]["sign"])
REF_MOO = int(_m[1]) * 3600 + int(_m[2]) * 60 + int(_m[3])      # arcsec into sign


# ------------------------------------------------------------- helpers
def norm(x):
    return x % 360.0


def err_s(a, b):
    pa, pb = (datetime.strptime(x, "%d/%b/%Y %H:%M:%S") for x in (a, b))
    return (pa - pb).total_seconds()


def stamps(moon_lon):
    per = deep_current_periods(moon_lon, birth.utc_datetime(), depth=5, query_utc=QUERY)
    return [local_datetime(p.end, 5.5).strftime("%d/%b/%Y %H:%M:%S") for p in per]


def stamp_errs(moon_lon):
    return [err_s(a, b) for a, b in zip(stamps(moon_lon), REF_STAMPS)]


def dms(lon_deg, rule):
    lon = norm(lon_deg)
    d = int(lon)
    rem = (lon - d) * 60.0
    mnt = int(rem)
    s_f = (rem - mnt) * 60.0
    s = int(s_f) if rule == "trunc" else int(s_f + 0.5)
    if s == 60:
        s, mnt = 0, mnt + 1
    if mnt == 60:
        mnt, d = 0, (d + 1) % 360
    return d, mnt, s


def display_match(lon_sid, rule):
    d, mnt, s = dms(lon_sid, rule)
    return (d // 30, d % 30, mnt, s) == (REF_MOO_SIG,) + tuple(
        map(int, (REF_MOO // 3600, (REF_MOO % 3600) // 60, REF_MOO % 60)))


def ayan_mean(jd):
    return swe.get_ayanamsa_ut(jd) - OFFSET_DEG


def sid_manual(jd, flags):
    xx, _ = swe.calc_ut(jd, swe.MOON, flags)
    return norm(xx[0] - ayan_mean(jd))


def sid_flag(jd, flags):
    xx, _ = swe.calc_ut(jd, swe.MOON, flags | swe.FLG_SIDEREAL)
    return norm(xx[0] + OFFSET_DEG)   # kpastro applies A - offset, i.e. adds it


def moon_speed_arcsec_s(jd):
    xx, _ = swe.calc_ut(jd, swe.MOON, BASE)
    return xx[3] * 3600.0 / 86400.0


# ------------------------------------------------------------- candidates
def build_candidates():
    cands = [("baseline: apparent - mean ayan (current pipeline)",
              lambda: sid_manual(JD0, BASE))]
    cands += [
        ("SEFLG_NONUT (mean equinox of date)",
         lambda: sid_manual(JD0, BASE | swe.FLG_NONUT)),
        ("SEFLG_TRUEPOS (no light-time, no aberration)",
         lambda: sid_manual(JD0, BASE | swe.FLG_TRUEPOS)),
        ("SEFLG_NOABERR (aberration off, light-time kept)",
         lambda: sid_manual(JD0, BASE | swe.FLG_NOABERR)),
        ("SEFLG_MOSEPH (Moshier ephemeris)",
         lambda: sid_manual(JD0, swe.FLG_MOSEPH | swe.FLG_SPEED)),
        ("SEFLG_ICRS (ICRS frame, no FK5 transform)",
         lambda: sid_manual(JD0, BASE | swe.FLG_ICRS)),
        ("SEFLG_SPEED3 (3-position speed; pos must be identical)",
         lambda: sid_manual(JD0, swe.FLG_SWIEPH | swe.FLG_SPEED3)),
        ("SEFLG_JPLHOR (JPL-Horizons nutation model)",
         lambda: sid_manual(JD0, BASE | swe.FLG_DPSIDEPS_1980)),
        ("FLG_SIDEREAL (documented sidereal path)",
         lambda: sid_flag(JD0, BASE)),
        ("FLG_SIDEREAL | NONUT",
         lambda: sid_flag(JD0, BASE | swe.FLG_NONUT)),
    ]
    # topocentric
    swe.set_topo(LON, LAT, 0.0)
    cands.append(("topocentric (swe_set_topo + FLG_TOPOCTR)",
                  lambda: sid_manual(JD0, BASE | swe.FLG_TOPOCTR)))
    # time-scale entries
    jd_et = JD0 + swe.deltat(JD0)
    xx, _ = swe.calc(jd_et, swe.MOON, BASE)
    cands.append(("swe.calc(jd_et) correct ET entry",
                  lambda: norm(xx[0] - ayan_mean(JD0))))
    xx2, _ = swe.calc(JD0, swe.MOON, BASE)          # UT number used as ET: wrong
    cands.append(("swe.calc(jd_ut) UT fed as ET (time-scale mixup)",
                  lambda: norm(xx2[0] - ayan_mean(JD0))))
    # Moon-only time-base shifts (dt seconds)
    for dt in (-4.0, -3.0, -2.0, -1.66, -1.0, -0.5, 0.5):
        cands.append((f"Moon-only time shift dt={dt:+.2f}s",
                      lambda dt=dt: sid_manual(JD0 + dt / 86400.0, BASE)))
    return cands


# ------------------------------------------------------------- table
def report(lon, base_lon):
    shift = wrap((lon - base_lon) * 3600.0)
    dref = wrap(lon * 3600.0 % 108000.0 - REF_MOO)
    errs = stamp_errs(lon)
    mx = max(abs(e) for e in errs)
    t = display_match(lon, "trunc")
    h = display_match(lon, "half")
    return shift, dref, errs, mx, t, h


def wrap(x):
    return x - 1296000 if x > 648000 else (x + 1296000 if x < -648000 else x)


print("=" * 118)
print(f"[0] baseline Moon (exact, sidereal) = {MOON0:.9f} deg;  reference print "
      f"{REF['planets']['MOO']['sign']} {REF['planets']['MOO']['degree']}")
manual0 = sid_manual(JD0, BASE)
print(f"    manual re-derivation matches pipeline: {abs((manual0 - MOON0) * 3600) < 1e-6} "
      f"(diff {abs((manual0 - MOON0) * 3600):.9f}\")")
print(f"    jd note: swe.utc_to_jd (pipeline path) - swe.julday = {(JD0 - JD_JUL) * 86400:+.4f} s "
      f"(Moon {abs(manual0 - sid_manual(JD_JUL, BASE)) * 3600:.3f}\")")
print(f"    Moon speed at t0 = {moon_speed_arcsec_s(JD0):.4f}\"/s "
      f"-> 1\" = {1.0 / moon_speed_arcsec_s(JD0):.3f} s of Moon motion")
r_t, r_h = REF_MOO, REF_MOO
print(f"    ref Moon print window: truncation exact in [{r_t}, {r_t + 1})\", "
      f"half-up exact in [{r_h - 0.5}, {r_h + 0.5})\" (arcsec into sign)")

# established-fact reproduction
print("\n[1] reproduction of the established residual_probe numbers (stamps, arcsec grid)")
for k in (-150, -100, -91, -50, 0):
    e = max(abs(x) for x in stamp_errs(MOON0 + k / 100.0 / 3600.0))
    print(f"    moon shift {k / 100.0:+.2f}\" -> max stamp error {e:9.1f} s")

print("\n[2] candidate conventions")
print("  " + "candidate".ljust(54) + "shift\"".rjust(8) + "vsref\"".rjust(9)
      + "  stamp errs s (dasa/bhukti/antara/sookshma/prana)".ljust(56)
      + "max|s|".rjust(9) + "  T H")
best = None
for name, fn in build_candidates():
    try:
        lon = fn()
        shift, dref, errs, mx, t, h = report(lon, MOON0)
    except Exception as exc:  # documented flag combos that pyswisseph rejects
        print(f"  {name:<54} ERROR: {exc}")
        continue
    print(f"  {name:<54}{shift:+8.3f}{dref:+9.3f}  "
          + "/".join(f"{e:+.0f}" for e in errs).ljust(54)
          + f"{mx:9.1f}  {'Y' if t else 'n'} {'Y' if h else 'n'}")
    if best is None or mx < best[1]:
        best = (name, mx)

# node-mode independence (mean vs true node must not touch the Moon)
m_mean = SwissEphemeris(ayanamsa="kp_new", node="mean").body(JD0, "Moon")[0]
m_true = SwissEphemeris(ayanamsa="kp_new", node="true").body(JD0, "Moon")[0]
print(f"\n  node mode mean vs true: Moon shift = {wrap((m_true - m_mean) * 3600):+.6f}\" "
      f"(expected 0; node choice only selects the Rahu/Ketu body id)")
print(f"  best candidate by stamp error alone: {best[0]} ({best[1]:.1f} s)")

# ------------------------------------------------------------- fine scans
print("\n[3] fine scan: pure Moon-longitude shift delta (0.01\" steps)")
best_d = None
win5, win60 = [], []
k = -300
while k <= 300:
    lon = MOON0 + k / 100.0 / 3600.0
    e = max(abs(x) for x in stamp_errs(lon))
    if best_d is None or e < best_d[1]:
        best_d = (k / 100.0, e)
    if e < 5:
        win5.append(k / 100.0)
    if e < 60:
        win60.append(k / 100.0)
    k += 1
print(f"    best delta = {best_d[0]:+.2f}\" -> max stamp error {best_d[1]:.1f} s")
print(f"    delta window with max error < 5 s : "
      f"{(str(min(win5)) + '..' + str(max(win5)) + '\"') if win5 else 'none'}"
      f"  ({(max(win5) - min(win5)) / 100 if win5 else 0:.2f}\" wide)")
print(f"    delta window with max error < 60 s: "
      f"{(str(min(win60)) + '..' + str(max(win60)) + '\"') if win60 else 'none'}"
      f"  ({(max(win60) - min(win60)) / 100 if win60 else 0:.2f}\" wide)")
mb = MOON0 + best_d[0] / 3600.0
print(f"    at best delta: printed Moon trunc={'Y' if display_match(mb, 'trunc') else 'n'} "
      f"halfup={'Y' if display_match(mb, 'half') else 'n'}; "
      f"moon time equivalent = {best_d[0] / moon_speed_arcsec_s(JD0):+.3f} s")

print("\n[4] fine scan: Moon-only time-base shift dt (0.01 s steps)")
best_t = None
win5, win60 = [], []
i = -400
while i <= 100:
    dt = i / 100.0
    lon = sid_manual(JD0 + dt / 86400.0, BASE)
    e = max(abs(x) for x in stamp_errs(lon))
    if best_t is None or e < best_t[1]:
        best_t = (dt, e, lon)
    if e < 5:
        win5.append(dt)
    if e < 60:
        win60.append(dt)
    i += 1
print(f"    best dt = {best_t[0]:+.2f} s -> max stamp error {best_t[1]:.1f} s; "
      f"printed Moon trunc={'Y' if display_match(best_t[2], 'trunc') else 'n'} "
      f"halfup={'Y' if display_match(best_t[2], 'half') else 'n'}")
print(f"    dt window with max error < 5 s : {min(win5):+.2f}..{max(win5):+.2f} s"
      if win5 else "    dt window <5 s: none")
print(f"    dt window with max error < 60 s: {min(win60):+.2f}..{max(win60):+.2f} s"
      if win60 else "    dt window <60 s: none")

print("\ndone.")
