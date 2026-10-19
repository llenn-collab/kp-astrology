"""Planet longitude convention probe (diagnostic only, TASK2 §2.B / §8).

Run from the repo root with the full ephemeris installed:
    SE_EPHE_PATH=$HOME/.kpastro/ephe venv/bin/python diagnositics/planet_convention_probe.py

Computes all nine chart bodies under each documented Swiss Ephemeris
convention — ayanamsa flavour (get_ayanamsa_ut / get_ayanamsa_ex_ut default /
get_ayanamsa_ex_ut NONUT) × position flavour (apparent / NONUT / TRUEPOS /
NOABERR / MOSEPH / ICRS / FLG_SIDEREAL) × whole-chart time offset (±20 s) —
and compares exact sidereal longitudes with the committed KP Stellar
reference printout (kp_stellar_output.json).

Nothing here changes library behaviour; every number is measured at run time
and printed only.  Reference values are read from the reference file, never
hard-coded.
"""
import json
import re
from datetime import date, time

import swisseph as swe

from kpastro.chart import BirthInfo
from kpastro.ephemeris import SwissEphemeris, _AYANAMSA_OFFSETS_DEG

REF = json.load(open("kp_stellar_output.json"))
SIGNS = ["ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG", "CAP", "AQU", "PIS"]
BODIES = ["SUN", "MOO", "MAR", "JUP", "SAT", "MER", "VEN", "RAH", "KET"]

#: kp_new zero-point offset as declared in src/kpastro/ephemeris.py (not fitted here).
OFFSET_DEG = _AYANAMSA_OFFSETS_DEG["kp_new"]

POS = {
    "apparent": swe.FLG_SWIEPH | swe.FLG_SPEED,
    "nonut":    swe.FLG_SWIEPH | swe.FLG_NONUT,
    "TRUEPOS":  swe.FLG_SWIEPH | swe.FLG_TRUEPOS,
    "NOABERR":  swe.FLG_SWIEPH | swe.FLG_NOABERR,
    "MOSEPH":   swe.FLG_MOSEPH | swe.FLG_SPEED,
    "ICRS":     swe.FLG_SWIEPH | swe.FLG_ICRS,
}
SWE_ID = {"SUN": swe.SUN, "MOO": swe.MOON, "MAR": swe.MARS, "JUP": swe.JUPITER,
          "SAT": swe.SATURN, "MER": swe.MERCURY, "VEN": swe.VENUS, "RAH": swe.MEAN_NODE}

# 12:00:00 IST on the reference birth date == 06:30:00 UT.  Use the pipeline's
# own UTC->JD conversion: swe.utc_to_jd sits +0.3718 s from swe.julday, which
# moves the Moon by 0.225" -- large enough to matter here.
eph = SwissEphemeris(ayanamsa="kp_new", node="mean")
BIRTH = BirthInfo(date=date(2026, 10, 30), time=time(12, 0, 0),
                  latitude=18.4593067, longitude=73.8654709, tz_hours=5.5,
                  place="Pune, India")
JD0 = eph.jd_ut(BIRTH.utc_datetime())
JD_JUL = swe.julday(2026, 10, 30, 6.5)

swe.set_sid_mode(swe.SIDM_KRISHNAMURTI_VP291)


# --------------------------------------------------------------- helpers
def norm(x):
    return x % 360.0


def wrap_arcsec(x):
    return x - 1296000 if x > 648000 else (x + 1296000 if x < -648000 else x)


def ref_abs_arcsec(name):
    p = REF["planets"][name]
    d, m, s = map(int, re.match(r"(\d+)°(\d+)'(\d+)", p["degree"]).groups())
    return SIGNS.index(p["sign"]) * 108000 + d * 3600 + m * 60 + s


REF_ABS = {n: ref_abs_arcsec(n) for n in BODIES}


def ayan(jd, kind):
    if kind == "mean":
        return swe.get_ayanamsa_ut(jd)                 # doc: "without nutation"
    if kind == "true":
        return swe.get_ayanamsa_ex_ut(jd, 0)[1]        # doc: incl. nutation
    if kind == "exnonut":
        return swe.get_ayanamsa_ex_ut(jd, swe.FLG_NONUT)[1]
    raise ValueError(kind)


def trop(jd, name, flags):
    """Tropical longitude of one body; KET is RAH + 180 by construction."""
    if name == "KET":
        return norm(trop(jd, "RAH", flags) + 180.0)
    xx, _ret = swe.calc_ut(jd, SWE_ID[name], flags)
    return xx[0]


def sid_manual(jd, name, pos_key, ayan_kind):
    return norm(trop(jd, name, POS[pos_key]) - (ayan(jd, ayan_kind) - OFFSET_DEG))


def sid_flag_raw(jd, name, pos_key):
    """FLG_SIDEREAL path as Swiss recommends, before the kp_new offset."""
    return trop(jd, name, POS[pos_key] | swe.FLG_SIDEREAL)


def sid_flag(jd, name, pos_key):
    # kpastro applies ayanamsa = A_swiss - offset, i.e. adds the offset to the
    # sidereal longitude; mirror that here so the FLG_SIDEREAL row is comparable.
    return norm(sid_flag_raw(jd, name, pos_key) + OFFSET_DEG)


def delta(lon_sid, name):
    """ours - reference, arcseconds (reference is a whole-arcsecond print)."""
    return wrap_arcsec(norm(lon_sid) * 3600.0 - REF_ABS[name])


def dms(lon_deg, rule):
    lon = norm(lon_deg)
    d = int(lon)
    rem = (lon - d) * 60.0
    m = int(rem)
    s_f = (rem - m) * 60.0
    s = int(s_f) if rule == "trunc" else int(s_f + 0.5)
    if s == 60:
        s, m = 0, m + 1
    if m == 60:
        m, d = 0, (d + 1) % 360
    return d, m, s


def ref_triple(name):
    p = REF["planets"][name]
    d, m, s = map(int, re.match(r"(\d+)°(\d+)'(\d+)", p["degree"]).groups())
    return SIGNS.index(p["sign"]), d, m, s


REF_T = {n: ref_triple(n) for n in BODIES}


def display_matches(lon_sid, name, rule):
    d, m, s = dms(lon_sid, rule)
    return (d // 30, d % 30, m, s) == REF_T[name]


def row(label, get_lon, jd=JD0, show=()):
    ds = {n: delta(get_lon(jd, n), n) for n in BODIES}
    cells = []
    for n in BODIES:
        d = ds[n]
        cells.append(f"{d:+8.2f}" if (not show or n in show) else "       .")
    worst = max(abs(ds[n]) for n in BODIES)
    n2 = sum(abs(ds[n]) <= 2.0 for n in BODIES)
    trunc = sum(display_matches(get_lon(jd, n), n, "trunc") for n in BODIES)
    half = sum(display_matches(get_lon(jd, n), n, "half") for n in BODIES)
    both = sum(display_matches(get_lon(jd, n), n, "trunc")
               and display_matches(get_lon(jd, n), n, "half") for n in BODIES)
    print(f"  {label:<34}" + "".join(cells)
          + f"  | max {worst:6.2f} | <=2\" {n2}/9 | disp T{trunc} H{half} B{both}")
    return ds, worst, n2


# ---------------------------------------------------------------- table 1
print("=" * 100)
print(f"[0] setup: precision={eph.precision}  sid mode=VP291  jd_ut={JD0:.9f}  "
      f"kp_new offset={OFFSET_DEG * 3600:.1f}\"")
print(f"    jd note: swe.utc_to_jd (pipeline path) - swe.julday = {(JD0 - JD_JUL) * 86400:+.4f} s "
      f"(Moon {abs(sid_manual(JD0, 'MOO', 'apparent', 'mean') - sid_manual(JD_JUL, 'MOO', 'apparent', 'mean')) * 3600:.3f}\")")
a_mean, a_true, a_nonut = ayan(JD0, "mean"), ayan(JD0, "true"), ayan(JD0, "exnonut")
xx, _ = swe.calc_ut(JD0, swe.ECL_NUT, 0)
dpsi = xx[2] * 3600.0
print("\n[1] ayanamsa functions at the reference instant (sid mode set first)")
print(f"    get_ayanamsa_ut  (doc: 'without nutation') = {a_mean:.10f} deg = {a_mean * 3600:14.3f}\"")
print(f"    get_ayanamsa_ex_ut(0)   (incl. nutation)   = {a_true:.10f} deg = {a_true * 3600:14.3f}\"")
print(f"    get_ayanamsa_ex_ut(NONUT)                  = {a_nonut:.10f} deg = {a_nonut * 3600:14.3f}\"")
print(f"    ex(0) - ex(NONUT) = {(a_true - a_nonut) * 3600:.4f}\"   dpsi from SE_ECL_NUT = {dpsi:.4f}\"")
print(f"    ut == ex(NONUT) exactly: {a_mean == a_nonut}")
kp_aya = a_mean - OFFSET_DEG
print(f"    kpastro sidereal zero (mean - {OFFSET_DEG * 3600:.1f}\") = {kp_aya:.8f} deg")
ref_aya = REF["horary_details"]["ayanamsa"]
m = re.match(r"(\d+)°(\d+)'(\d+)", ref_aya)
ref_aya_arcsec = int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])
our_arcsec = kp_aya * 3600.0 % 108000.0
t_s = int(our_arcsec) // 3600
t_m = (int(our_arcsec) % 3600) // 60
print(f"    printed ayanamsa: ref '{ref_aya.split(' (')[0]}'  ours trunc "
      f"{t_s}deg {t_m}min / exact {our_arcsec:.3f}\"-into-sign "
      f"(halfup would print {int(our_arcsec + 0.5)}\")")

# ---------------------------------------------------------------- table 2
print("\n[2] sidereal deltas vs reference, manual subtraction of each ayanamsa flavour "
      "(rows: position flavour x ayanamsa flavour)")
print("  " + "convention".ljust(34) + "".join(n.rjust(9) for n in BODIES))
KEY = {"mean": "mean(ut)", "true": "true(ex0)", "exnonut": "ex(NONUT)"}
for pos_key in POS:
    for aya_kind in ("mean", "true", "exnonut"):
        row(f"{pos_key} - {KEY[aya_kind]}", lambda jd, n, p=pos_key, a=aya_kind: sid_manual(jd, n, p, a))

# ---------------------------------------------------------------- table 3
print("\n[3] FLG_SIDEREAL (the convention the Swiss manual recommends for sidereal positions)")
for pos_key in ("apparent", "nonut", "TRUEPOS"):
    row(f"FLG_SIDEREAL|{pos_key} + 50.7\"", lambda jd, n, p=pos_key: sid_flag(jd, n, p))

print("\n[3b] which ayanamsa does FLG_SIDEREAL subtract internally?")
for aya_kind in ("mean", "true", "exnonut"):
    worst = 0.0
    for n in BODIES:
        if n == "KET":
            continue
        internal = norm(trop(JD0, n, POS["apparent"]) - sid_flag_raw(JD0, n, "apparent"))
        worst = max(worst, abs(internal - ayan(JD0, aya_kind)) * 3600.0)
    print(f"    internal ayan vs {KEY[aya_kind]:<12}: max |diff| over bodies = {worst:.4f}\"")

# ---------------------------------------------------------------- table 4
print("\n[4] whole-chart time offset (seconds applied to jd_ut, ayanamsa recomputed) x convention")
CONV = [
    ("C1 app-mean (current kpastro)",   lambda jd, n: sid_manual(jd, n, "apparent", "mean")),
    ("C2 app-true ayan (ex_ut 0)",      lambda jd, n: sid_manual(jd, n, "apparent", "true")),
    ("C3 nonut-mean",                   lambda jd, n: sid_manual(jd, n, "nonut", "mean")),
    ("C4 FLG_SIDEREAL",                 lambda jd, n: sid_flag(jd, n, "apparent")),
    ("C5 mixed-B nonut pl / app Moon",  lambda jd, n: sid_manual(jd, n, "apparent" if n == "MOO" else "nonut", "mean")),
]
SELECTED = [-20, -13.5, -10, -5, -3, -2, -1, 0, 1, 2, 3, 5, 10, 13.5, 20]
for label, fn in CONV:
    print(f"\n  {label}")
    print("    " + "dt(s)".rjust(6) + "max|d|".rjust(9) + "n<=2\"".rjust(7)
          + "  trunc/9 halfup/9 both/9   (both = exact in [ref, ref+0.5\"))")
    for dt in SELECTED:
        jd = JD0 + dt / 86400.0
        ds, worst, n2 = row(f"dt={dt:+.1f}", fn, jd)
        # row() prints the full body line; for this table only the summary is wanted
    # fine scan: does ANY offset in +/-20 s bring all nine within 2" (and/or all displays)?
    best = None
    ok2, okt, okh, okb = [], [], [], []
    dtv = -200
    while dtv <= 200:
        jd = JD0 + dtv / 10.0 / 86400.0
        ds = {n: delta(fn(jd, n), n) for n in BODIES}
        worst = max(abs(ds[n]) for n in BODIES)
        if best is None or worst < best[1]:
            best = (dtv / 10.0, worst)
        if all(abs(ds[n]) <= 2.0 for n in BODIES):
            ok2.append(dtv / 10.0)
        if all(display_matches(fn(jd, n), n, "trunc") for n in BODIES):
            okt.append(dtv / 10.0)
        if all(display_matches(fn(jd, n), n, "half") for n in BODIES):
            okh.append(dtv / 10.0)
        if all(display_matches(fn(jd, n), n, "trunc") and display_matches(fn(jd, n), n, "half")
                for n in BODIES):
            okb.append(dtv / 10.0)
        dtv += 1

    def span(v):
        if not v:
            return "none"
        return f"{min(v):+.1f}..{max(v):+.1f}s ({len(v) / 10.0:.1f} s wide)"

    print(f"    fine scan: best dt={best[0]:+.1f}s (max|d|={best[1]:.2f}\") | "
          f"all-9 <=2\": {span(ok2)} | all-9 trunc: {span(okt)} | "
          f"all-9 halfup: {span(okh)} | all-9 both: {span(okb)}")

# ------------------------------------------------------- table 5: K window
print("\n[5] implied kp_new offset K for all-nine <=2\" at dt=0 (ANALYSIS ONLY, src not touched)")
print("    delta_new = delta - (K - 50.7); all-nine <=2\" iff K in (50.7 + max_d - 2, 50.7 + min_d + 2]")
for label, fn in CONV:
    # delta_new = delta - (K - 50.7); all-nine <=2" iff K-50.7 in [max d - 2, min d + 2]
    ds = {n: delta(fn(JD0, n), n) for n in BODIES}
    lo = 50.7 + max(ds[n] for n in BODIES) - 2.0
    hi = 50.7 + min(ds[n] for n in BODIES) + 2.0
    flag = "  <-- non-empty" if lo < hi else "  (empty: no single K works)"
    print(f"    {label:<34} K in ({lo:.3f}, {hi:.3f}]{flag}")

print("\ndone.")
