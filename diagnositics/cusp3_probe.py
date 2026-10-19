"""Probe A (TASK2 2.C): Placidus cusps 3/9 vs KP Stellar, ~0.88" residual.

Run from the repo root with the full ephemeris installed:
    export SE_EPHE_PATH="$HOME/.kpastro/ephe"
    venv/bin/python diagnositics/cusp3_probe.py

Questions answered:
  1. exact display-rounding arithmetic for every cusp (truncation vs half-up);
  2. does any DOCUMENTED option of swe.houses / swe.houses_ex / swe.houses_armc
     move cusp 3 by the maximum implied residual (-0.883") while keeping the
     other 10 cusps within the currently-matching 0.29" band;
  3. what would a Placidus iteration-tolerance change do (Swiss Ephemeris stops
     at VERY_SMALL_PLAC_ITER = 1/360000 deg = 0.001", swehouse.c:891).

Diagnostic only; nothing in src/ or tests/ is touched.
"""
import json
import math
import re
from datetime import date, datetime, time

import swisseph as swe

from kpastro.chart import BirthInfo, compute_chart
from kpastro.ephemeris import SwissEphemeris, geocentric_latitude
from kpastro.horary import kp_divisions

LAT, LON = 18.4593067, 73.8654709
REF = json.load(open("kp_stellar_output.json"))
MAX_SHIFT = -0.883          # max residual implied by reference display (ours - ref)
OTHER_TOL = 0.29            # arcsec: current matching band for the other 10 cusps

# -- trig helpers (degrees), faithful ports of swehouse.c --------------------
sind = lambda x: math.sin(math.radians(x))
cosd = lambda x: math.cos(math.radians(x))
tand = lambda x: math.tan(math.radians(x))
asind = lambda x: math.degrees(math.asin(x))
atand = lambda x: math.degrees(math.atan(x))
degnorm = lambda x: x % 360.0


def difdeg2n(a, b):         # signed difference in [-180, 180)
    d = (a - b) % 360.0
    return d - 360.0 if d >= 180.0 else d


def asc2(x, f, sine, cose):  # swehouse.c:2100
    ass = -tand(f) * sine + cose * cosd(x)
    sinx = sind(x)
    if abs(ass) < 1e-10:
        ass = 0.0
    if abs(sinx) < 1e-10:
        sinx = 0.0
    if sinx == 0.0:
        ass = -1e-10 if ass < 0 else 1e-10
    elif ass == 0.0:
        return -90.0 if sinx < 0 else 90.0
    else:
        ass = atand(sinx / ass)
    if ass < 0:
        ass += 180.0
    return ass


def asc1(x1, f, sine, cose):  # swehouse.c:2058
    x1 = degnorm(x1)
    n = int(x1 / 90 + 1)
    if n == 1:
        ass = asc2(x1, f, sine, cose)
    elif n == 2:
        ass = 180.0 - asc2(180.0 - x1, -f, sine, cose)
    elif n == 3:
        ass = 180.0 + asc2(x1 - 180.0, -f, sine, cose)
    else:
        ass = 360.0 - asc2(360.0 - x1, f, sine, cose)
    return degnorm(ass)


def placidus_cusps(armc, lat, eps, tol, niter_max=1000):
    """Cusps 11, 12, 2, 3 exactly as swehouse.c CalcH 'P', but with the stop
    tolerance as a parameter (Swiss uses 1/360000 deg)."""
    sine, cose, tane = sind(eps), cosd(eps), tand(eps)
    tanfi = tand(lat)
    a = asind(tanfi * tane)
    fh1 = atand(sind(a / 3.0) / tane)
    fh2 = atand(sind(a * 2.0 / 3.0) / tane)
    out, iters = {}, {}
    for ih, rect, div, fh in ((11, 30, 3.0, fh1), (12, 60, 1.5, fh2),
                              (2, 120, 1.5, fh2), (3, 150, 3.0, fh1)):
        rectasc = degnorm(rect + armc)
        tant = tand(asind(sine * sind(asc1(rectasc, fh, sine, cose))))
        f = atand(sind(asind(tanfi * tant) / div) / tant)
        cusp = asc1(rectasc, f, sine, cose)
        for i in range(1, niter_max + 1):
            tant = tand(asind(sine * sind(cusp)))
            f = atand(sind(asind(tanfi * tant) / div) / tant)
            new = asc1(rectasc, f, sine, cose)
            if i > 1 and abs(difdeg2n(new, cusp)) < tol:
                cusp, _ = new, i
                iters[ih] = i
                break
            cusp = new
        else:
            iters[ih] = niter_max
        out[ih] = cusp
    return out, iters


def ref_arcsec(dms):
    d, m, s = map(int, re.match(r"(\d+)°(\d+)'(\d+)", dms).groups())
    return d * 3600 + m * 60 + s


def dms(arcsec, rule):
    s = int(arcsec) if rule == "trunc" else int(math.floor(arcsec + 0.5))
    d, m = divmod(s, 3600)
    return f"{d:02d}°{m // 60:02d}'{m % 60:02d}\""


# -- setup: same chart as the pinned reconciliation command ------------------
birth = BirthInfo(date=date(2026, 10, 30), time=time(12, 0, 0), latitude=LAT,
                  longitude=LON, tz_hours=5.5, place="Pune, India")
chart = compute_chart(birth, ayanamsa="kp_new", node="mean",
                      query_utc=datetime(2026, 10, 18, 12, 0, 0),
                      horary_lagna=kp_divisions()[116].start_deg)
eph = SwissEphemeris(ayanamsa="kp_new", node="mean")
jd_ref = eph.jd_ut(birth.utc_datetime())
lat_gc = geocentric_latitude(LAT)

# The chart's cusps are the HORARY frame: the instant whose sidereal Ascendant
# equals division 117's cusp (kpastro.horary.cusps_from_horary_lagna solves it
# but does not return the instant).  Re-solve jd* here so every variant below
# runs in the same frame as the reference comparison.
lagna = kp_divisions()[116].start_deg
SID_DAY = 0.9972695663
asc_sid = lambda t: eph.houses(t, LAT, LON)[1]
lo = jd_ref - SID_DAY
jds = [lo + SID_DAY * i / 960 for i in range(961)]
asc = [asc_sid(j) for j in jds]
unwrapped = [asc[0]]
for a_ in asc[1:]:
    d = a_ - unwrapped[-1]
    while d < -180.0:
        d += 360.0
    while d > 180.0:
        d -= 360.0
    unwrapped.append(unwrapped[-1] + d)
target = lagna
while target < unwrapped[0]:
    target += 360.0
while target > unwrapped[-1]:
    target -= 360.0
idx = max(i for i in range(960) if unwrapped[i] <= target <= unwrapped[i + 1])
a, b = jds[idx], jds[idx + 1]
ua = unwrapped[idx]
for _ in range(200):
    m = 0.5 * (a + b)
    d = asc_sid(m) - asc_sid(a)
    while d < -180.0:
        d += 360.0
    while d > 180.0:
        d -= 360.0
    um = ua + d
    if um <= target:
        a, ua = m, um
    else:
        b = m
    if b - a < 1e-11:
        break
jd = 0.5 * (a + b)
ayan = eph.ayanamsa(jd)


def houses_sidereal(jd, lat, lon, flags=0, armc=None, eps=None):
    if armc is not None:
        cusps_t, ascmc = swe.houses_armc(armc, lat, eps, b"P")
    else:
        cusps_t, ascmc = swe.houses_ex(jd, lat, lon, b"P", flags)
    lst = list(cusps_t[1:13] if len(cusps_t) == 13 else cusps_t)
    return [swe.difdeg2n(c, ayan) % 30.0 * 3600.0 for c in lst], list(ascmc)


base, _ = houses_sidereal(jd, lat_gc, LON)
_c, _a = swe.houses_ex(jd, lat_gc, LON, b"P")
base_trop = list(_c[1:13] if len(_c) == 13 else _c)
armc_trop = _a[2]
# True obliquity implied by the MC relation used in swehouse.c (mc = atand(tand(armc)/cose));
# this pyswisseph fork exposes no swe.obliquity/nutation, so derive it from the MC itself.
eps_true = math.degrees(math.acos(
    math.tan(math.radians(armc_trop)) / math.tan(math.radians(_a[1]))))

chart_err = max(abs(base[k] - chart.cusps[k].longitude % 30 * 3600) for k in range(12))
print(f"precision={eph.precision}  jd*={jd:.9f} (birth jd {jd_ref:.6f})  "
      f"lat_gc={lat_gc:.7f}  ayan(kp_new)={ayan:.6f}")
print(f"eps_true={eps_true:.9f}  ARMC={armc_trop:.9f}  MC={_a[1]:.9f}")
print(f"baseline vs chart.cusps max diff = {chart_err:.6f} arcsec")

# [1] display-rounding arithmetic --------------------------------------------
print("\n[1] Display rounding: ours exact vs reference (arcsec into the sign)")
print(f"  {'h':>2} {'ours exact':>12} {'trunc':>12} {'half-up':>12} {'reference':>12}"
      f" {'trunc ok':>9} {'halfup ok':>10}")
n_trunc = n_half = 0
for k in range(12):
    ours = base[k]
    ref_s = REF["cusps"][str(k + 1)]["degree"]
    tr, hu = dms(ours, "trunc"), dms(ours, "halfup")
    rok, hok = tr == ref_s, hu == ref_s
    n_trunc += rok
    n_half += hok
    print(f"  {k + 1:>2} {ours:12.3f} {tr:>12} {hu:>12} {ref_s:>12} {str(rok):>9} {str(hok):>10}")
print(f"  matches: truncation {n_trunc}/12, half-up {n_half}/12")
print(f"  tropical cusp9 - cusp3 = {difdeg2n(base_trop[8], base_trop[2]):.9f} deg (identical point)")

# [2] documented API options --------------------------------------------------
print("\n[2] Documented options of swe.houses / houses_ex / houses_armc")
print("  (delta = variant - baseline, arcsec; 'other10' excludes cusps 3 and 9)")


def report(name, vals):
    d = [v - b for v, b in zip(vals, base)]
    d3 = d[2]
    others = [(abs(d[k]), k + 1) for k in range(12) if k not in (2, 8)]
    worst, where = max(others)
    verdict = "OK-candidate" if abs(d3 - MAX_SHIFT) < 0.05 and worst < OTHER_TOL else "moves others"
    print(f"  {name:<34} dcusp3={d3:+9.3f}\"  dcusp9={d[8]:+9.3f}\"  "
          f"max-other={worst:8.3f}\"(cusp{where})  {verdict}")
    return d


cusps_h, _ = swe.houses(jd, lat_gc, LON, b"P")
lst = list(cusps_h[1:13] if len(cusps_h) == 13 else cusps_h)
report("swe.houses (classic entry)", [swe.difdeg2n(c, ayan) % 30 * 3600 for c in lst])
report("houses_ex flags=0 (baseline)", base)

for fname in ("FLG_SPEED", "FLG_SWIEPH", "FLG_MOSEPH", "FLG_NONUT", "FLG_TRUEPOS"):
    fl = getattr(swe, fname, None)
    if fl is None:
        print(f"  {fname:<34} not exported by this pyswisseph")
        continue
    v, _ = houses_sidereal(jd, lat_gc, LON, flags=fl)
    report(f"houses_ex {fname} ({fl})", v)

fl_sid = getattr(swe, "FLG_SIDEREAL", None)
if fl_sid is not None:
    v, _ = houses_sidereal(jd, lat_gc, LON, flags=fl_sid)
    d = report(f"houses_ex FLG_SIDEREAL ({fl_sid})", v)

v, _ = houses_sidereal(jd, LON * 0 + LAT, LON)        # geodetic latitude
report("geodetic lat (repo option)", v)

v, _ = houses_sidereal(jd, lat_gc, LON, armc=armc_trop, eps=eps_true)
report("houses_armc roundtrip (eps_true)", v)


def solve(f, target, x0, h):
    for _ in range(4):
        f0, f1 = f(x0), f(x0 + h)
        slope = (f1 - f0) / h
        if abs(slope) < 1e-12:
            break
        x0 += (target - f0) / slope
    return x0


def c3_of(knob_kind, x):
    if knob_kind == "eps":
        v, _ = houses_sidereal(jd, lat_gc, LON, armc=armc_trop, eps=x)
    elif knob_kind == "tjd":
        v, _ = houses_sidereal(x, lat_gc, LON)
    elif knob_kind == "lat":
        v, _ = houses_sidereal(jd, x, LON)
    else:
        v, _ = houses_sidereal(jd, lat_gc, x)
    return v[2]


print(f"\n  input/parameter perturbations solving for dcusp3 = {MAX_SHIFT}\" (max implied):")
for kind, x0, h, unit in (("eps", eps_true, 1e-5, "deg obliquity"),
                          ("tjd", jd, 1e-4, "d (=%.1f s)" % (1e-4 * 86400)),
                          ("lat", lat_gc, 1e-4, "deg latitude"),
                          ("lon", LON, 1e-4, "deg longitude")):
    x = solve(lambda k: c3_of(kind, k) - base[2], MAX_SHIFT, x0, h)
    if kind == "eps":
        v, _ = houses_sidereal(jd, lat_gc, LON, armc=armc_trop, eps=x)
    elif kind == "tjd":
        v, _ = houses_sidereal(x, lat_gc, LON)
    elif kind == "lat":
        v, _ = houses_sidereal(jd, x, LON)
    else:
        v, _ = houses_sidereal(jd, lat_gc, x)
    report(f"solve: shift {unit}", v)

# [3] iteration tolerance -----------------------------------------------------
print("\n[3] Placidus iteration tolerance (Swiss stops at 1/360000 deg = 0.001\")")
conv, _ = placidus_cusps(armc_trop, lat_gc, eps_true, 1e-14)
valid = max(abs(conv[h] - base_trop[h - 1]) * 3600 for h in (2, 3, 11, 12))
print(f"  reimplementation vs swe.houses_ex: max diff (cusps 2,3,11,12) = {valid:.4f}\"")
print(f"  {'tolerance':>14} {'cusp3 arcsec-in-sign':>21} {'error vs converged':>19} {'iters(c3)':>10}")
for tol_deg, label in ((1e-14, "1e-14 deg"), (1.0 / 360000, "1/360000 deg (Swiss)"),
                       (1e-4, "1e-4 deg (0.36\")"), (1e-3, "1e-3 deg (3.6\")"),
                       (1e-2, "1e-2 deg (36\")")):
    cs, it = placidus_cusps(armc_trop, lat_gc, eps_true, tol_deg)
    c3 = cs[3] - ayan
    c3 = c3 % 30.0 * 3600.0
    err = c3 - (conv[3] - ayan) % 30.0 * 3600.0
    print(f"  {label:>14} {c3:21.6f} {err:+19.6f} {it[3]:>10}")

# fixed-point contraction factor of the cusp-3 map (error amplification per step)
cs, _ = placidus_cusps(armc_trop, lat_gc, eps_true, 1e-14)
sine, cose, tane = sind(eps_true), cosd(eps_true), tand(eps_true)
tanfi, a = tand(lat_gc), asind(tand(lat_gc) * tand(eps_true))
fh1 = atand(sind(a / 3.0) / tane)
step = 1e-4
def c3_map(c):
    tant = tand(asind(sine * sind(c)))
    f = atand(sind(asind(tanfi * tant) / 3.0) / tant)
    return asc1(degnorm(150 + armc_trop), f, sine, cose)
k = abs((c3_map(cs[3] + step) - c3_map(cs[3] - step)) / (2 * step))
print(f"  measured contraction factor of the cusp-3 fixed-point map: {k:.4f}")
print(f"  => iteration stop-tolerance T bounds the cusp-3 error by ~T*k/(1-k) = "
      f"{(1/360000)*3600*k/(1-k):.6f}\" at Swiss tolerance")
print("\nverdict: a documented option or tolerance change that moves cusp 3 by -0.883\"")
print("while keeping the other 10 cusps within 0.29\": see 'OK-candidate' rows above (if any).")
