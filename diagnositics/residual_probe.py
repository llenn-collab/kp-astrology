"""Residual probes for the KP Stellar reconciliation (diagnostic only).

Run from the repo root with the full ephemeris installed:
    SE_EPHE_PATH=$HOME/.kpastro/ephe python3 diagnostics/residual_probe.py

Nothing here changes library behaviour. Each probe answers one question that
TASK2.md asks the agent to settle. Output is printed; nothing is written.
"""
import json, re
from datetime import date, time, datetime
import swisseph as swe
from kpastro.chart import BirthInfo, compute_chart, local_datetime
from kpastro.deep_dasha import deep_current_periods
from kpastro.ephemeris import SwissEphemeris
from kpastro.horary import kp_divisions
from kpastro.panchanga import _jd_to_clock
from kpastro.vedic import normalize_longitude

REF = json.load(open("kp_stellar_output.json"))
SIGNS = ["ARI","TAU","GEM","CAN","LEO","VIR","LIB","SCO","SAG","CAP","AQU","PIS"]
LAT, LON = 18.4593067, 73.8654709
QUERY = datetime(2026, 10, 18, 12, 0, 0)

def ref_abs_arcsec(sign, dms):
    d, m, s = map(int, re.match(r"(\d+)°(\d+)'(\d+)", dms).groups())
    return SIGNS.index(sign) * 108000 + d * 3600 + m * 60 + s

def wrap(x):  # signed difference on the 1,296,000" circle
    return x - 1296000 if x > 648000 else (x + 1296000 if x < -648000 else x)

birth = BirthInfo(date=date(2026,10,30), time=time(12,0,0), latitude=LAT,
                  longitude=LON, tz_hours=5.5, place="Pune, India")
chart = compute_chart(birth, ayanamsa="kp_new", node="mean", query_utc=QUERY,
                      horary_lagna=kp_divisions()[116].start_deg)
eph = SwissEphemeris(ayanamsa="kp_new", node="mean")
print("precision:", eph.precision, "| ephe path:", eph.ephe_path)

# 1. Dasha stamps vs a sub-arcsecond Moon shift -------------------------------
print("\n[1] Moon longitude shift needed to reproduce the reference dasha stamps")
KEYS = ["dasa", "bhukti", "antara", "sookshma", "prana"]
ref_stamps = [REF["vimsottari_dasa"][k]["end"] for k in KEYS]
def stamps(moon_lon):
    per = deep_current_periods(moon_lon, birth.utc_datetime(), depth=5, query_utc=QUERY)
    return [local_datetime(p.end, 5.5).strftime("%d/%b/%Y %H:%M:%S") for p in per]
def err_s(a, b):
    pa, pb = (datetime.strptime(x, "%d/%b/%Y %H:%M:%S") for x in (a, b))
    return (pa - pb).total_seconds()
moon0 = chart.planet_lon["Moon"]
print(f"  ours Moon sidereal = {moon0:.6f} deg")
best = None
for k in range(-300, 301):                    # 0.01" steps over +/-3"
    shift = k / 100.0
    st = stamps(moon0 + shift / 3600.0)
    e = max(abs(err_s(a, b)) for a, b in zip(st, ref_stamps))
    if best is None or e < best[1]:
        best = (shift, e)
print(f"  best shift = {best[0]:+.2f} arcsec, max stamp error = {best[1]:.0f} s")
print(f"  unshifted max stamp error = {max(abs(err_s(a,b)) for a,b in zip(stamps(moon0), ref_stamps)):.0f} s")

# 2. Planet longitude vs ephemeris flag variants ------------------------------
print("\n[2] Planet residual (ours - reference, arcsec) under Swiss flag variants")
jd = eph.jd_ut(birth.utc_datetime())
ayan = eph.ayanamsa(jd)
BODIES = {"SUN": swe.SUN, "MOO": swe.MOON, "MAR": swe.MARS, "JUP": swe.JUPITER,
          "SAT": swe.SATURN, "MER": swe.MERCURY, "VEN": swe.VENUS}
refs = {k: ref_abs_arcsec(REF["planets"][k]["sign"], REF["planets"][k]["degree"]) for k in BODIES}
VARIANTS = {
    "apparent (ours)": swe.FLG_SWIEPH | swe.FLG_SPEED,
    "NONUT":           swe.FLG_SWIEPH | swe.FLG_NONUT,
    "MOSEPH apparent": swe.FLG_MOSEPH | swe.FLG_SPEED,
    "TRUEPOS":         swe.FLG_SWIEPH | swe.FLG_TRUEPOS,
}
print("  " + "variant".ljust(18) + "".join(k.rjust(9) for k in BODIES))
for name, fl in VARIANTS.items():
    row = []
    for k, b in BODIES.items():
        arr, _ = swe.calc_ut(jd, b, fl)[:2]
        d = wrap(normalize_longitude(arr[0] - ayan) * 3600 - refs[k])
        row.append(f"{d:+9.2f}")
    print("  " + name.ljust(18) + "".join(row))
print("  note: reference degrees are whole arcseconds, so each entry carries ~+-0.5\" rounding")

# 3. Sunrise / sunset horizon conventions --------------------------------------
print("\n[3] Sunrise/sunset under Swiss rise_trans conventions (reference 06:36:48 / 17:59:22)")
jd_mid = swe.julday(2026, 10, 29, 18.5)   # local midnight 30 Oct IST in UT
geo = (LON, LAT, 0.0)
for name, fl in {"disc+norefr (ours)": swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION,
                 "disc+refr": swe.BIT_DISC_CENTER,
                 "upperlimb+refr": 0,
                 "upperlimb+norefr": swe.BIT_NO_REFRACTION}.items():
    out = []
    for ev, back in ((swe.CALC_RISE, 0.5), (swe.CALC_SET, 0.2)):
        r = swe.rise_trans(jd_mid - back, swe.SUN, ev | fl, geo, 0.0, 0.0)
        out.append(_jd_to_clock(float(r[1][0]), 5.5))
    print(f"  {name:<22} rise {out[0]}  set {out[1]}")

# 4. Placidus cusps 3 and 9 exact values ---------------------------------------
print("\n[4] Exact cusp longitudes (arcsec into sign) vs reference display")
for c in chart.cusps[:12]:
    ref_c = REF["cusps"][str(c.house)]
    print(f"  cusp {c.house:>2}: ours exact {c.longitude % 30 * 3600:12.3f}\"  reference {ref_c['sign']} {ref_c['degree']}")
