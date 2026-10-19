# Findings: cusp 3/9 rounding probe (A) and sunrise/sunset probe (B)

> **Superseded (2026-10-19).** The +8 s / −7 s sunrise/sunset residuals were
> the Moshier fallback; with the ephemeris files installed both are exact.
> The cusp story moved: cusps 3/9 now print the reference arcsecond and it is
> cusps 2/8 that print 1″ low, on a true residual of only −0.09″.  See
> Addendum B of `KP_STELLAR_RECONCILIATION.md`.

TASK2 §2.C / §2.D. Both probes are **diagnostic only** — no `src/` or `tests/`
file was created, modified, or deleted; nothing was committed. Sign convention
throughout: **ours − reference**, seconds / arcseconds.

Environment: `venv/bin/python` (Python 3.13.7, pyswisseph 2.10.3.2 fork,
kpastro editable), `SE_EPHE_PATH=$HOME/.kpastro/ephe`, precision `"full"`.

Exact commands (from the repo root):

```bash
export SE_EPHE_PATH="$HOME/.kpastro/ephe"
venv/bin/python diagnositics/cusp3_probe.py
venv/bin/python diagnositics/sunrise_probe.py
venv/bin/python -m pytest --no-cov -q     # baseline unchanged by these probes
```

Test baseline note: `pytest --no-cov -q` shows the 5 documented pre-existing
failures in `tests/test_precision.py` **plus** 2 failures in
`tests/test_kp_stellar_reference.py`
(`test_house_derived_fields_match_the_reference`,
`test_injecting_the_reference_cusps_leaves_only_the_1_arcsec_residual`).
Those 2 come from the parent session's in-flight, uncommitted `chart.py`
significators work + the unresolved cusp-3 residual itself — not from anything
these probes did (probes are new untracked files under `diagnositics/` only).

---

## Probe A — Placidus cusps 3 and 9 (`diagnositics/cusp3_probe.py`)

### Frame

The reference `cusps` block is the **horary frame**: the instant whose
sidereal Placidus Ascendant equals horary division 117's cusp
(VIR 17°46'40" = `1510/9`°). `kpastro.horary.cusps_from_horary_lagna` solves
that instant but does not return it; the probe re-solves it
(jd\* = 2461343.473219101, i.e. ~7.2 h before the birth instant) and verifies
its baseline cusps against `chart.cusps` — **max diff 0.000076″**, so all
measurements below are in the same frame as the reference.

Ground truth from the Swiss C source (fetched from `aloistr/swisseph`):

- `swehouse.c:891` — `VERY_SMALL_PLAC_ITER = 1.0/360000.0` **degrees = 0.001″**:
  the fixed compile-time stop tolerance of the Placidus iteration
  (houses 11/12/2/3, `swehouse.c:1830-1985`). It is not a runtime option of
  `swe.houses` / `swe.houses_ex` / `swe.houses_armc`.
- `swe_houses_ex2` (`swehouse.c:207`): the only documented `iflag` effects are
  `SEFLG_NONUT` (zero nutation → mean obliquity and mean sidereal time in
  ARMC) and `SEFLG_SIDEREAL` (subtract ayanamsa inside the call);
  `SEFLG_RADIANS` is a unit change. Obliquity always comes from the analytic
  series (`swi_epsiln`), so ephemeris flags (SWIEPH/MOSEPH/JPLEPH) cannot
  change it. This pyswisseph build exports **no** `SEFLG_J2H`/`J2G` house
  flags; `houses_armc`'s `ascmc9` parameter is only used by Sunshine ('I')
  houses. There is no documented iteration-tolerance parameter.

### [1] Display-rounding arithmetic (arcsec into the sign)

| h | ours exact | trunc | half-up | reference | trunc ok | half-up ok |
|---|-----------:|-------|---------|-----------|----------|------------|
| 1  | 64000.000¹ | 17°46'39"¹ | 17°46'40" | 17°46'40" | (artifact) | yes |
| 2  | 62471.916 | 17°21'11" | 17°21'12" | 17°21'12" | no | yes |
| 3  | **62410.883** | **17°20'10"** | **17°20'11"** | **17°20'10"** | **yes** | **no** |
| 4  | 62570.122 | 17°22'50" | 17°22'50" | 17°22'50" | yes | yes |
| 5  | 64388.286 | 17°53'08" | 17°53'08" | 17°53'08" | yes | yes |
| 6  | 66753.995 | 18°32'33" | 18°32'34" | 18°32'34" | no | yes |
| 7  | 64000.000¹ | — | 17°46'40" | 17°46'40" | (artifact) | yes |
| 8  | 62471.916 | 17°21'11" | 17°21'12" | 17°21'12" | no | yes |
| 9  | **62410.883** | **17°20'10"** | **17°20'11"** | **17°20'10"** | **yes** | **no** |
| 10 | 62570.122 | 17°22'50" | 17°22'50" | 17°22'50" | yes | yes |
| 11 | 64388.286 | 17°53'08" | 17°53'08" | 17°53'08" | yes | yes |
| 12 | 66753.995 | 18°32'33" | 18°32'34" | 18°32'34" | no | yes |

¹ Cusps 1/7 are the exact rational lagna (`1510/9`° → exactly 64000.000″); the
"39″" under truncation is a binary-float artifact of `int()` in the probe
(`63999.99999…`), not a rule difference. In exact arithmetic both rules print
40″.

**Rounding-rule analysis.** The reference's own display is **half-up for 10 of
12 cusps**: cusps 2/8 (11.916″ → `12"`), 6/12 (33.995″ → `34"`) and 1/7 all
require half-up — pure truncation would print them one arcsecond lower than
the reference does. The only cusps whose reference display agrees with
truncation of *our* value are 3/9 (10.883″ → `10"`). Two readings remain:

- **(a) display-only:** the reference truncates — but then it truncates
  inconsistently with its own 2/8/6/12/1/7 values, which is hard to square
  with a single formatter;
- **(b) genuine differential:** the reference rounds half-up like the rest of
  its output and its internal cusp 3/9 is **0.383″–0.883″ lower** than ours
  (internal value in [62410.0, 62410.5] vs our 62410.883).

Under truncation the reference's internal cusp 3 could be anywhere in
[62410.0, 62411.0), so ours−reference ∈ (−0.117″, +0.883″]. **The rounding
rule for this cusp is UNRESOLVED; both readings are recorded.**

Structural fact (measured): tropical cusp 9 − cusp 3 = exactly 180.000000000°
— the pair is one point from one solve; no parameter can move one without the
other.

### [2] Documented options of `swe.houses` / `houses_ex` / `houses_armc`

Δ = variant − baseline (arcsec); "max-other" = largest |Δ| over the 10 cusps
that currently match (all except 3 and 9). Acceptance bar: Δcusp3 = −0.883″
(max implied) **and** max-other < 0.29″.

| variant | Δcusp3 | Δcusp9 | max-other | verdict |
|---|---:|---:|---:|---|
| `swe.houses` (classic entry) | +0.000″ | +0.000″ | 0.000″ (cusp12) | identical to baseline |
| `houses_ex` flags=0 (baseline) | +0.000″ | +0.000″ | 0.000″ | — |
| `houses_ex FLG_SPEED (256)` | +0.000″ | +0.000″ | 0.000″ | no effect |
| `houses_ex FLG_SWIEPH (2)` | +0.000″ | +0.000″ | 0.000″ | no effect |
| `houses_ex FLG_MOSEPH (4)` | +0.000″ | +0.000″ | 0.000″ | no effect |
| `houses_ex FLG_TRUEPOS (16)` | +0.000″ | +0.000″ | 0.000″ | no effect |
| `houses_ex FLG_NONUT (64)` | −6.869″ | −6.869″ | 7.369″ (cusp8) | moves everything ~7–9″ |
| `houses_ex FLG_SIDEREAL (65536)` | +21033.556″ | +21033.556″ | 21033.556″ | uniform shift (no `kp_new` offset); breaks all 10 |
| geodetic latitude (repo's documented `house_latitude_model="geodetic"`) | −58.068″ | −58.068″ | 79.515″ (cusp2) | moves Asc/angles massively |
| `houses_armc` roundtrip (derived true ε = 23.437916358°) | −0.000″ | +0.000″ | 0.000″ | validates ε and the solver path |

Continuous input perturbations, each solved so that Δcusp3 = exactly −0.883″
(max implied shift):

| knob solved | collateral on the other 10 | verdict |
|---|---|---|
| obliquity ε (via `houses_armc`) | cusp11 moves 6.859″ | rejected |
| time tjd (Δ ≈ −0.058 s) | all cusps move ~0.95″ (max cusp12 0.945″) | rejected (>0.29″) |
| latitude | cusp8 moves 1.210″ | rejected |
| longitude | all cusps move ~0.95″ (max cusp12 0.945″) | rejected |

Every documented knob either moves nothing (all ephemeris/speed flags) or
moves **all** cusps (NONUT, sidereal mode, tjd/lon: uniform shift;
lat/ε: strongly non-uniform). **No documented option isolates cusps 3/9.**

### [3] Iteration / tolerance probe

The probe reimplements the Swiss Placidus fixed-point iteration for cusps
11/12/2/3 (`swehouse.c` `CalcH` case 'P', incl. `Asc1`/`Asc2`) with the stop
tolerance as a parameter. Validation: the reimplementation reproduces
`swe.houses_ex` cusps 2, 3, 11, 12 to **< 0.0001″**.

| stop tolerance | cusp3 (arcsec in sign) | error vs fully converged | iterations |
|---|---:|---:|---:|
| 1e-14 deg (converged) | 62410.883375 | 0.000000″ | 3 |
| 1/360000 deg (Swiss, `VERY_SMALL_PLAC_ITER`) | 62410.883375 | 0.000000″ | 2 |
| 1e-4 deg (0.36″) | 62410.883375 | 0.000000″ | 2 |
| 1e-3 deg (3.6″) | 62410.883375 | 0.000000″ | 2 |
| 1e-2 deg (36″) | 62410.883375 | 0.000000″ | 2 |

Measured contraction factor of the cusp-3 fixed-point map: **k ≈ 0.0001** —
the error after the stop is ≤ T·k/(1−k) ≈ **1e-7″** at Swiss tolerance. The
iteration converges from a good initial guess in 2 steps regardless of any
sane tolerance. **This disproves the hypothesis written in
`tests/test_kp_stellar_reference.py` (line 29) that "the Placidus cusp-3
iteration converges a hair short"** — convergence is exact to well under
0.001″; the 0.4–0.9″ gap is not iteration error.

### Verdict A

**Change proposed: NO.** No documented `swe.houses`/`houses_ex`/`houses_armc`
option, no documented obliquity/nutation variant, and no iteration-tolerance
change moves cusp 3 (and its identical opposite cusp 9) down by the implied
0.383″–0.883″ while keeping the other 10 cusps within their current 0.29″
agreement. Every knob that moves 3/9 at all moves 1/4/7/10 and/or 2/8/6/11/12
by at least ~0.95″. Residual recorded; the most economical explanation is the
reference's internal cusp-3/9 value sitting ~0.4–0.9″ below the (otherwise
half-up-displayed) value its own engine produces differently, or an
undocumented internal detail of KP Stellar — neither is reproducible from
documented Swiss options, so nothing in `src/` changes.

---

## Probe B — sunrise / sunset (`diagnositics/sunrise_probe.py`)

Reference: rise 06:36:48, set 17:59:22 (day length 11:22:34).
Ours (disc centre, no refraction): 06:36:56 / 17:59:15 → **+8 s / −7 s**,
day length −15 s. The reference's day is ~15 s longer, i.e. its effective
horizon is *below* the disc-centre geometric horizon (rise earlier, set
later); latitude/longitude alone cannot do that (see below).

### [1] Horizon conventions (all reproduced exactly; TASK2 table confirmed)

| convention | rise (Δ vs ref) | set (Δ vs ref) | daylen Δ |
|---|---|---|---:|
| disc + no refraction (ours) | 06:36:56 (+8 s) | 17:59:15 (−7 s) | −15 s |
| disc + refraction, P=def, **T=0°C** (TASK2 row) | 06:34:16 (−152 s) | 18:01:55 (+153 s) | +305 s |
| disc + refraction, P=1013.25, T=10°C | 06:34:26 (−142 s) | 18:01:46 (+144 s) | +286 s |
| disc + refraction, P=1013.25, T=15°C | 06:34:30 (−138 s) | 18:01:41 (+139 s) | +277 s |
| upper limb + refraction, T=0°C | 06:33:06 (−222 s) | 18:03:05 (+223 s) | +445 s |
| upper limb + no refraction | 06:35:46 (−62 s) | 18:00:25 (+63 s) | +125 s |

pyswisseph quirk worth recording: in `swe.rise_trans`, `atpress=0.0` means
"default 1013.25 mbar" but `attemp=0.0` is taken **literally as 0°C** —
that is why TASK2's "disc+refr" row (measured with `(0.0, 0.0)`) is 06:34:16,
10 s earlier than the (1013.25 mbar, 10°C) default row.

### [2] Continuous (pressure, temperature) solve — disc centre + refraction

For each temperature, pressure bisected to match the reference rise, then the
set evaluated at that same pressure (and vice versa):

| T °C | P fit (rise) mbar | P fit (set) mbar | set err at P_rise | rise err at P_set | geometric dip at rise |
|---:|---:|---:|---:|---:|---:|
| 0 | 124.44 | 122.83 | +0.3 s | +0.3 s | 96.1″ (1.60′) |
| 5 | 125.83 | 124.17 | +0.3 s | +0.3 s | 96.1″ |
| 10 | 127.22 | 125.50 | +0.3 s | +0.3 s | 96.1″ |
| 15 | 128.60 | 126.84 | +0.3 s | +0.3 s | 96.1″ |
| 20 | 129.99 | 128.18 | +0.3 s | +0.3 s | 96.1″ |
| 25 | 131.38 | 129.51 | +0.3 s | +0.3 s | 96.1″ |

A single (P, T) on this curve does reproduce **both** events to ≤0.3 s — but
the required pressure is **~123–131 mbar**, roughly 1/8 of standard
atmosphere (~15 km altitude). Not a documented standard:

| documented atmosphere | rise (Δ) | set (Δ) |
|---|---|---|
| Swiss default (1013.25, 10) | 06:34:26 (−142 s) | 18:01:46 (+144 s) |
| IAU standard (1013.25, 15) | 06:34:30 (−138 s) | 18:01:41 (+139 s) |
| Meeus (1010, 10) | 06:34:26 (−142 s) | 18:01:45 (+143 s) |
| std atmosphere at Pune 560 m (954, 10) | 06:34:35 (−133 s) | 18:01:36 (+134 s) |

Model check (`swe.refrac_extended`, true alt 0°, T=10, lapse 0.0065): the
Swiss refraction is linear in pressure — 1739.3″ @ 1013.25 mbar, 1644.0″ @
954, but only 97.8–112.9″ @ 124–131 mbar — consistent with the measured
96.1″ geometric dip at the fitted event (dip measured directly as the Sun's
true altitude at the fitted instant via `swe.azalt`).

### [3] Other documented inputs

- **Observer elevation** (`geopos[2]` in `swe.rise_trans`): 0 / 560 / 1000 m
  give byte-identical results — the plain `rise_trans` **ignores elevation**
  (documented; only `rise_trans_true_hor(horhgt=-100)` derives a dip from it).
- **`swe.rise_trans_true_hor` horizon height (`horhgt`)** — the one genuinely
  documented horizon parameter:

  | horhgt fit | value | at that horhgt: rise / set |
  |---|---:|---|
  | fitting rise | −105.0″ (−1.75′) | 06:36:49 (+1 s) / 17:59:23 (+1 s) |
  | fitting set | −101.3″ (−1.69′) | 06:36:49 (+1 s) / 17:59:22 (+0 s) |

  A single horhgt ≈ **−103″** fits both events within 1 s. Compare Swiss's own
  `calc_dip` (horizon dip of an elevated observer, standard atmosphere):
  1.00 m → −99.4″, 1.03 m → −100.9″, 2.00 m → −140.6″, **Pune 560 m →
  −2352″**. So the fit is equivalent to "observer eye height ≈ 1.0 m" —
  not a documented panchanga/KP convention, not Pune's elevation, and not
  something kpastro's `elevation=0` input would produce.
- **Location shifts** (disc+norefr): matching rise needs lat −0.11663°,
  matching set needs lat −0.11117° — a combined lat ≈ −0.1139° fits both
  within ~1 s, but **contradicts the coordinates both kpastro and the
  reference itself state** (18.4593067 N). Longitude shifts come out with
  **opposite signs** (+0.0318° vs −0.0306°), so longitude cannot work at all
  (it moves both events the same way).

### Verdict B

**Change proposed: NO.** No documented atmosphere (1010–1013 mbar at any
standard temperature), no documented horizon convention
(disc/limb × refraction, horhgt = 0), and no location change consistent with
the agreed coordinates reproduces the reference rise **and** set. The fits
that exist are all the same underlying effective horizon ≈ **1.6–1.75′ below
the disc-centre geometric horizon**: (a) a 123–131 mbar atmosphere, (b) a
`horhgt` ≈ −103″ ≈ the dip of a 1.0 m-high observer, or (c) latitude ~0.11°
south — each non-documented for this use. The residual (+8 s / −7 s) is
recorded and unchanged.

---

## Summary of answers

- **(a)** Does any documented Placidus option move cusp 3 by −0.88″ while
  keeping the other 10 exact? **No.** All `houses`/`houses_ex` flags either
  do nothing (SPEED/SWIEPH/MOSEPH/TRUEPOS — measured 0.000″) or move every
  cusp (NONUT ~7–9″; SIDEREAL uniform; geodetic latitude 58–80″ on the
  angles); every input perturbation that shifts cusp 3 by −0.88″ shifts at
  least one currently-matching cusp by ≥0.87″; the iteration tolerance is a
  compile-time constant (0.001″) whose effect is provably <1e-6″ here.
  Cusp 9 is the identical opposite point (exactly 180°) and moves with 3.
- **(b)** Does any documented atmosphere/refraction setting reproduce the
  reference rise AND set? **No.** Standard atmospheres miss by >2 minutes.
  A (P, T) fit exists at P ≈ 123–131 mbar (≤0.3 s on both events) and a
  horizon-dip fit at horhgt ≈ −103″ (≤1 s on both) — both non-standard
  constants; per the task constraint, nothing changes.
