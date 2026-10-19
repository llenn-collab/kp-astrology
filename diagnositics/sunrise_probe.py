"""Probe B (TASK2 2.D): sunrise/sunset vs KP Stellar (ref 06:36:48 / 17:59:22).

Run from the repo root with the full ephemeris installed:
    export SE_EPHE_PATH="$HOME/.kpastro/ephe"
    venv/bin/python diagnositics/sunrise_probe.py

Questions answered:
  1. reproduce the four TASK2 horizon conventions with deltas (ours - ref);
  2. solve the CONTINUOUS (pressure, temperature) pair of swe.rise_trans's
     documented refraction parameters that reproduces the reference rise and
     set, and check whether that pair is a documented standard atmosphere;
  3. test the other documented inputs (observer elevation, latitude/longitude
     shifts) as hypotheses.

Diagnostic only; nothing in src/ or tests/ is touched.
"""
import math

import swisseph as swe

from kpastro.panchanga import _jd_to_clock

LAT, LON = 18.4593067, 73.8654709
JD_MID = swe.julday(2026, 10, 29, 18.5)      # local midnight 30 Oct 2026 IST in UT
TZ = 5.5


def clock_s(hms):
    h, m, s = map(int, hms.split(":"))
    return h * 3600 + m * 60 + s


REF_R, REF_S = clock_s("06:36:48"), clock_s("17:59:22")


def rise_set_jd(flags, press, temp, lat=LAT, lon=LON, elev=0.0):
    geo = (lon, lat, elev)
    out = []
    for ev, back in ((swe.CALC_RISE, 0.5), (swe.CALC_SET, 0.2)):
        r = swe.rise_trans(JD_MID - back, swe.SUN, ev | flags, geo, press, temp)
        out.append(float(r[1][0]))
    return out


def row(label, jd_pair):
    clocks = [_jd_to_clock(j, TZ) for j in jd_pair]
    dr = clock_s(clocks[0]) - REF_R
    ds = clock_s(clocks[1]) - REF_S
    dl = (clock_s(clocks[1]) - clock_s(clocks[0])) - (REF_S - REF_R)
    print(f"  {label:<34} rise {clocks[0]} ({dr:+5d}s)  set {clocks[1]} ({ds:+5d}s)"
          f"  daylen {dl:+5d}s vs ref")
    return jd_pair


print(f"[1] Horizon conventions (reference 06:36:48 / 17:59:22, daylen 11:22:34)")
CONV = {
    "disc+norefr (ours)": (swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION, 0.0, 10.0),
    "disc+refr (T=0, TASK2 row)": (swe.BIT_DISC_CENTER, 0.0, 0.0),
    "disc+refr (P=1013.25,T=10)": (swe.BIT_DISC_CENTER, 1013.25, 10.0),
    "disc+refr (P=1013.25,T=15)": (swe.BIT_DISC_CENTER, 1013.25, 15.0),
    "upperlimb+refr (T=0)": (0, 0.0, 0.0),
    "upperlimb+norefr": (swe.BIT_NO_REFRACTION, 0.0, 10.0),
}
baseline = None
for name, (fl, p, t) in CONV.items():
    r = rise_set_jd(fl, p, t)     # press=0 means Swiss default 1013.25; temp=0 is literal
    if baseline is None:
        baseline = r
    row(name, r)

# target JDs: centre of the reference's displayed second (IST -> UT -5.5h)
t_rise = swe.julday(2026, 10, 30, (1 + 6 / 60 + 48.5 / 3600))
t_set = swe.julday(2026, 10, 30, (12 + 29 / 60 + 22.5 / 3600))


def bisect_p(temp, which, lo=1.0, hi=1050.0):
    """Pressure matching the reference event. More pressure -> more refraction
    -> earlier rise, later set (opposite monotonicity for the two events)."""
    target = t_rise if which == 0 else t_set
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        v = rise_set_jd(swe.BIT_DISC_CENTER, mid, temp)[which]
        up = v > target if which == 0 else v < target
        if up:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def true_alt(jd_ev):
    lon, lat_, dist = swe.calc_ut(jd_ev, swe.SUN, swe.FLG_SWIEPH)[0][:3]
    geo = (LON, LAT, 0.0)
    return swe.azalt(jd_ev, swe.ECL2HOR, geo, 0.0, 0.0, [lon, lat_, dist])[1]


print("\n[2] Continuous (pressure, temperature) solve, disc centre + refraction")
print(f"  {'T(°C)':>6} {'P_fit(rise) mbar':>17} {'P_fit(set) mbar':>16} "
      f"{'set err at P_rise':>18} {'rise err at P_set':>18} {'geometric dip at rise':>22}")
for temp in (0, 5, 10, 15, 20, 25):
    p_r = bisect_p(temp, 0)
    p_s = bisect_p(temp, 1)
    set_err = (rise_set_jd(swe.BIT_DISC_CENTER, p_r, temp)[1] - t_set) * 86400
    rise_err = (rise_set_jd(swe.BIT_DISC_CENTER, p_s, temp)[0] - t_rise) * 86400
    dip = -true_alt(rise_set_jd(swe.BIT_DISC_CENTER, p_r, temp)[0]) * 3600
    print(f"  {temp:>6} {p_r:17.2f} {p_s:16.2f} {set_err:+18.1f} {rise_err:+18.1f}"
          f" {dip:17.1f}\" ({dip / 60:4.1f}')")

print("\n  documented atmosphere check (pressure at fit temperature):")
for name, p, t in (("Swiss default", 1013.25, 10), ("IAU standard", 1013.25, 15),
                   ("Meeus", 1010.0, 10), ("std atm at 560 m (Pune)", 954.0, 10)):
    r = rise_set_jd(swe.BIT_DISC_CENTER, p, t)
    row(f"{name} ({p} mbar, {t}°C)", r)

print("\n[3] Other documented inputs")
for elev in (0.0, 560.0, 1000.0):
    r = rise_set_jd(swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION, 0.0, 10.0, elev=elev)
    row(f"disc+norefr, elevation {elev:.0f} m", r)


def rise_set_horhgt(horhgt):
    out = []
    for ev, back in ((swe.CALC_RISE, 0.5), (swe.CALC_SET, 0.2)):
        r = swe.rise_trans_true_hor(JD_MID - back, swe.SUN,
                                    ev | swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION,
                                    (LON, LAT, 0.0), 0.0, 10.0, horhgt)
        out.append(float(r[1][0]))
    return out


def bisect_horhgt(which, lo=-0.1, hi=0.05):
    """Higher horizon -> later rise, earlier set (opposite monotonicity)."""
    target = t_rise if which == 0 else t_set
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        v = rise_set_horhgt(mid)[which]
        up = v > target if which == 0 else v < target
        if up:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


print("\n[3b] swe.rise_trans_true_hor horizon-height (horhgt) solve, disc+norefr")
hr, hs = bisect_horhgt(0), bisect_horhgt(1)
print(f"  horhgt fitting rise : {hr * 3600:+8.1f}\" ({hr * 60:+.2f}')")
print(f"  horhgt fitting set  : {hs * 3600:+8.1f}\" ({hs * 60:+.2f}')")
row("  at horhgt(rise-fit)", rise_set_horhgt(hr))
row("  at horhgt(set-fit) ", rise_set_horhgt(hs))
for h_m in (1.0, 1.03, 2.0, 560.0):
    dip = swe.refrac_extended(0.0, h_m, 1013.25, 10.0, 0.0065, 0)[1][3]
    print(f"  horizon dip (observer {h_m:.2f} m, std atm) = {dip * 3600:+.1f}\""
          f"  (swisseph horhgt = 0.0001 deg + dip = {dip * 3600 + 3.6:+.1f}\")")

print("\n[4] Swiss refraction model at true altitude ~0 (refrac_extended, T=10, lapse 0.0065)")
for p in (1013.25, 954.0, 131.38, 127.22, 124.44):
    ref = swe.refrac_extended(0.0, 0.0, p, 10.0, 0.0065, 0)
    print(f"  P={p:8.2f} mbar -> refraction {ref[1][2] * 3600:8.1f}\"  "
          f"(dip term {ref[1][3] * 3600:+.1f}\")")


def solve_shift(kind, x0, which, h=1e-3):
    """Latitude/longitude shift (deg) making rise (which=0) or set (which=1)
    coincide with the reference time exactly, on raw event times."""
    ref_jd = t_rise if which == 0 else t_set
    def val(xx):
        r = rise_set_jd(swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION, 0.0, 10.0,
                        lat=xx if kind == "lat" else LAT,
                        lon=xx if kind == "lon" else LON)
        return (r[which] - ref_jd) * 86400
    x = x0
    for _ in range(6):
        f0, f1 = val(x), val(x + h)
        slope = (f1 - f0) / h
        if abs(slope) < 1e-6:
            break
        x += (0.0 - f0) / slope
    return x


lat_r = solve_shift("lat", LAT, 0)
lat_s = solve_shift("lat", LAT, 1)
lon_r = solve_shift("lon", LON, 0)
lon_s = solve_shift("lon", LON, 1)
print(f"  latitude  shift to fix rise only : {lat_r - LAT:+.5f} deg")
print(f"  latitude  shift to fix set  only : {lat_s - LAT:+.5f} deg")
print(f"  longitude shift to fix rise only : {lon_r - LON:+.5f} deg")
print(f"  longitude shift to fix set  only : {lon_s - LON:+.5f} deg")
lat_combo = 0.5 * (lat_r + lat_s)
r = rise_set_jd(swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION, 0.0, 10.0, lat=lat_combo)
row(f"  disc+norefr at lat {lat_combo:.5f}", r)
print("  longitude shifts have OPPOSITE signs (a lon change moves both events the")
print("  same way, so it cannot fix one without breaking the other); the latitude")
print("  pair nearly coincides - a ~0.11 deg lower latitude fits BOTH events")
print("  within ~1 s, but contradicts the coordinates both sides agree on.")

print("\nverdict: no documented atmosphere (1010-1013 mbar, 0-15 degC), no documented")
print("horizon convention, and no location change consistent with the reference's own")
print("coordinates reproduce the reference rise AND set. The fits that do exist are")
print("(a) a ~125-131 mbar atmosphere (~1/8 of standard, ~15 km altitude) and")
print("(b) a horizon dip of ~1.6-1.9' below the geoid (observer height ~1 m) -")
print("neither is a documented standard: record the residual, change nothing.")
