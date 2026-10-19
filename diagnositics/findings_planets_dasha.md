# Findings: planet-longitude conventions (TASK2 §2.B/§8) & dasha-vs-Moon (§2.A)

Two time-boxed numerical experiments, measured against the committed KP
Stellar reference `kp_stellar_output.json`. Sign convention throughout:
**ours − reference**, arcseconds / seconds (positive = ours ahead).

Run environment: `venv/bin/python`, `SE_EPHE_PATH=$HOME/.kpastro/ephe`,
`SwissEphemeris.precision == "full"`, pyswisseph 2.10.3.2.

Scripts (run from repo root; they read the reference JSON at run time and
hard-code no reference values):

```
venv/bin/python diagnositics/planet_convention_probe.py   # Experiment 1
venv/bin/python diagnositics/dasha_moon_probe.py          # Experiment 2
```

Baseline diff re-verified before starting:
`venv/bin/python -m kpastro.cli natal ... --horary-no 117 ... > /tmp/current.json`
+ `venv/bin/python diagnositics/jdiff.py kp_stellar_output.json /tmp/current.json`
= 36 differing leaves (9 planet `degree`, 5 dasha `end`, 2 sunrise/sunset,
2 cusps `degree`, 18 significator-order VALUEs).

**Repo-state caveat (not caused by these probes):** at the time of the run
`src/kpastro/chart.py` carried an *uncommitted concurrent modification*
(significators ordering, TASK2 §2.E, `_kp_sorted`/`_signifies_ordered`) and
`tests/test_kp_stellar_reference.py` existed, so `pytest --no-cov -q` shows
**7** failures, not the documented 5: the 5 pre-existing `test_precision.py`
failures plus 2 significators-layer tests from that in-flight work. The diff
does not touch `compute_chart`, ephemeris, ayanamsa, houses or dasha, and
every baseline number in TASK2 (36 leaf diffs, +10,738 s stamps, NONUT row
etc.) was reproduced before/after it. These probes changed nothing outside
`diagnositics/`.

---

## Experiment 1 — planetary longitudes: which convention?

### Confirmed facts (measured this run)

1. **Ayanamsa functions at the reference instant** (sid mode set to VP291
   first — calling them before `swe.set_sid_mode` silently measures the
   Fagan/Bradley default):

   | function | value (deg) | note |
   |---|---|---|
   | `get_ayanamsa_ut` | 24.1551364385 | doc: "without nutation" |
   | `get_ayanamsa_ex_ut(jd, 0)` | 24.1573702431 | includes nutation |
   | `get_ayanamsa_ex_ut(jd, SEFLG_NONUT)` | 24.1551364385 | **bit-identical** to `get_ayanamsa_ut` |
   | Δψ = ex(0) − ex(NONUT) | 8.0417″ | equals `SE_ECL_NUT` x[2] |

   Cited documentation (Swiss Ephemeris Programmer's Manual,
   `https://www.astro.com/swisseph/swephprg.htm`, ch. "swe_get_ayanamsa_ex_ut(),
   swe_get_ayanamsa_ex(), swe_get_ayanamsa() and swe_get_ayanamsa_ut()"):
   - "The functions `swe_get_ayanamsa()` and `swe_get_ayanamsa_ut()` provide
     the ayanamsha **without nutation**."
   - "`swe_get_ayanamsa_ex()`/`_ex_ut()` … if `iflag` contains `SEFLG_NONUT`
     the ayanamsha is calculated without nutation, otherwise … including
     nutation."
   - "**It is not recommended to use the ayanamsha functions for calculating
     sidereal planetary positions** from tropical positions … For sidereal
     planets, please use `swe_calc_ut()`/`swe_calc()` with the flag
     `SEFLG_SIDEREAL`."
   - "Use the ayanamsha function only for 'academical' purposes … it is
     recommended to indicate the ayanamsha **including nutation**."
   General doc Appendix E quotes IAE: "True Ayanamsa = Mean Ayanamsa +
   Nutation in Longitude". §5.6: "swe_calc() usually computes the positions
   as referred to the **true** equinox of the date (i.e. with nutation). If
   you want the mean equinox, … `SEFLG_NONUT`."

2. **`FLG_SIDEREAL` subtracts the *true* (nutation-including) ayanamsa**
   exactly: internal ayanamsa vs `get_ayanamsa_ex_ut(0)` differs by 0.0000″
   over all bodies (vs 8.0417″ from the mean one). Measured, matches the
   manual's recommendation. This confirms — against source, not memory — the
   AGENTS.md claim about the sidereal path.

3. **The printed ayanamsa is mean-flavoured.** Our `mean − 50.7″` zero point
   is 24°08′27.79″ → prints `24°08'28"` under **both** truncation and
   half-up = the reference string. A true-ayanamsa zero point (`+ Δψ`) would
   be 24°08′35.8″ → would print `24°08'36"`, 8″ off the reference. So if KP
   Stellar prints its own internal sidereal zero point, that print is
   nutation-free at this epoch.

4. **JD quirk:** the pipeline's `swe.utc_to_jd` sits **+0.3719 s** from
   `swe.julday(2026,10,30,6.5)` (systematic, ~same at all times of day).
   The Moon moves 0.225″ in that interval — this probe therefore uses the
   pipeline's own `jd_ut` everywhere. (Not the explanation of any residual:
   the direction/sign is wrong and 0.225″ ≪ 1.53″.)

5. **The three nutation-consistent conventions agree exactly with each
   other** (first-order identity verified numerically to <0.01″):
   `apparent − true ayanamsa` ≡ `NONUT − mean ayanamsa` ≡ `FLG_SIDEREAL`
   (with kpastro's +50.7″ applied). They put the eight non-Moon bodies at
   **+1.17…+2.09″** and the Moon at **−6.51″** vs the reference prints.
   The current kpastro convention (`apparent − mean ayanamsa`) puts them at
   **+9.22…+10.13″** and the Moon at **+1.53″**.

### Table [2]: position flavour × ayanamsa flavour (manual subtraction, kp_new offset fixed at 50.7″)

| convention | SUN | MOO | MAR | JUP | SAT | MER | VEN | RAH | KET | max | ≤2″ | disp T/H/B |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| apparent − mean(ut)  **(current)** | +9.22 | +1.53 | +9.68 | +9.57 | +9.76 | +9.84 | +10.13 | +9.48 | +9.48 | 10.13 | 1/9 | 0/0/0 |
| apparent − true(ex0) | +1.18 | −6.51 | +1.64 | +1.53 | +1.72 | +1.80 | +2.09 | +1.44 | +1.44 | 6.51 | 7/9 | 0/0/0 |
| apparent − ex(NONUT) | +9.22 | +1.53 | +9.68 | +9.57 | +9.76 | +9.84 | +10.13 | +9.48 | +9.48 | 10.13 | 1/9 | 0/0/0 |
| nonut − mean(ut) | +1.18 | −6.51 | +1.64 | +1.53 | +1.72 | +1.80 | +2.09 | +1.44 | +1.44 | 6.51 | 7/9 | 0/0/0 |
| nonut − true(ex0) | −6.86 | −14.55 | −6.40 | −6.52 | −6.32 | −6.24 | −5.96 | −6.61 | −6.61 | 14.55 | 0/9 | 0/0/0 |
| nonut − ex(NONUT) | +1.18 | −6.51 | +1.64 | +1.53 | +1.72 | +1.80 | +2.09 | +1.44 | +1.44 | 6.51 | 7/9 | 0/0/0 |
| TRUEPOS − mean | +29.85 | +2.27 | +24.99 | +23.98 | −1.73 | −2.95 | +7.01 | +9.48 | +9.48 | 29.85 | 1/9 | 0/0/0 |
| TRUEPOS − true | +21.81 | −5.77 | +16.95 | +15.93 | −9.78 | −10.99 | −1.03 | +1.44 | +1.44 | 21.81 | 3/9 | 0/0/0 |
| TRUEPOS − ex(NONUT) | +29.85 | +2.27 | +24.99 | +23.98 | −1.73 | −2.95 | +7.01 | +9.48 | +9.48 | 29.85 | 1/9 | 0/0/0 |
| NOABERR − mean | +29.85 | −10.34 | +13.29 | +15.40 | −8.42 | +30.12 | +30.49 | +9.48 | +9.48 | 30.49 | 0/9 | 0/0/0 |
| NOABERR − true | +21.81 | −18.38 | +5.25 | +7.36 | −16.46 | +22.08 | +22.45 | +1.44 | +1.44 | 22.45 | 2/9 | 0/0/0 |
| NOABERR − ex(NONUT) | +29.85 | −10.34 | +13.29 | +15.40 | −8.42 | +30.12 | +30.49 | +9.48 | +9.48 | 30.49 | 0/9 | 0/0/0 |
| MOSEPH − mean | +9.24 | +1.59 | +9.70 | +9.74 | +9.70 | +9.87 | +10.17 | +9.48 | +9.48 | 10.17 | 1/9 | 0/0/0 |
| MOSEPH − true | +1.20 | −6.45 | +1.65 | +1.70 | +1.66 | +1.83 | +2.13 | +1.44 | +1.44 | 6.45 | 7/9 | 0/0/0 |
| MOSEPH − ex(NONUT) | +9.24 | +1.59 | +9.70 | +9.74 | +9.70 | +9.87 | +10.17 | +9.48 | +9.48 | 10.17 | 1/9 | 0/0/0 |
| ICRS − mean | +9.22 | +1.53 | +9.68 | +9.56 | +9.75 | +9.83 | +10.12 | +9.48 | +9.48 | 10.12 | 1/9 | 0/0/0 |
| ICRS − true | +1.17 | −6.52 | +1.64 | +1.52 | +1.71 | +1.79 | +2.08 | +1.44 | +1.44 | 6.52 | 7/9 | 0/0/0 |
| ICRS − ex(NONUT) | +9.22 | +1.53 | +9.68 | +9.56 | +9.75 | +9.83 | +10.12 | +9.48 | +9.48 | 10.12 | 1/9 | 0/0/0 |

(disp T/H/B = # of bodies whose *displayed string* would match the reference
under truncation / half-up / both; reference whole-arcsecond prints, so each
delta carries ±0.5″ display uncertainty. ICRS ≈ SWIEPH to <0.02″; MOSEPH
≈ SWIEPH to <0.2″; nothing in this family helps.)

### Table [3]: `FLG_SIDEREAL` (the manual's recommended path) & hypothesis B

| convention | SUN | MOO | … max | ≤2″ |
|---|---|---|---|---|
| FLG_SIDEREAL\|apparent (+50.7″) | +1.18 | −6.51 | 6.51 | 7/9 |
| FLG_SIDEREAL\|nonut (+50.7″) | +1.18 | −6.51 | 6.51 | 7/9 |
| FLG_SIDEREAL\|TRUEPOS (+50.7″) | +21.81 | −5.77 | 21.81 | 3/9 |
| **mixed-B: NONUT planets + apparent Moon** | +1.18 | **+1.53** | 2.09 (VEN) | 8/9 |

Hypothesis B (nutation-free planets, apparent Moon) matches the *pattern*
of the reference (planets ~+1.5″, Moon ~+1.5″) but is not a single
convention, and even as a mixed construction its worst body (VEN +2.09″)
fails the 2″ test at the pinned offset.

### Table [4]: whole-chart time offset (±20 s, ayanamsa recomputed) × convention

Fine scan at 0.1 s steps; "all-9 ≤2″" = every body within 2″ of its print:

| convention | all-9 ≤2″ window | best max\|Δ\| | all-9 trunc-match | all-9 halfup-match |
|---|---|---|---|---|
| C1 app−mean (current) | none (best 9.90″ @ +10.2 s) | 9.90 | none | none |
| C2 app−true ayan | **+7.5…+14.0 s** (6.6 s wide) | 1.86 @ +10.2 s | none | none |
| C3 nonut−mean | **+7.5…+14.0 s** | 1.86 @ +10.2 s | none | none |
| C4 FLG_SIDEREAL | **+7.5…+14.0 s** | 1.86 @ +10.2 s | none | none |
| C5 mixed-B | none (best 2.07″ @ +0.8 s) | 2.07 | none | none |

C2 ≡ C3 ≡ C4 row-for-row (identity from fact 5). So a single convention
(nutation-consistent) + a single **fitted** clock offset of ≈ +8…+14 s does
bring all nine bodies within 2″. Selected rows (C3; per-body):

| dt (s) | SUN | MOO | MAR | JUP | SAT | MER | VEN | RAH | KET | n≤2″ |
|---|---|---|---|---|---|---|---|---|---|---|
| 0.0 | +1.18 | −6.51 | +1.64 | +1.53 | +1.72 | +1.80 | +2.09 | +1.44 | +1.44 | 7/9 |
| +5.0 | +1.39 | −3.48 | +1.75 | +1.55 | +1.71 | +1.61 | +1.97 | +1.42 | +1.42 | 8/9 |
| +10.0 | +1.60 | −0.46 | +1.85 | +1.58 | +1.69 | +1.43 | +1.86 | +1.41 | +1.41 | 9/9 |
| +13.5 | +1.74 | +1.66 | +1.93 | +1.60 | +1.68 | +1.30 | +1.78 | +1.41 | +1.41 | 9/9 |

**But no +N s offset is documented anywhere** (the only measured
"time-base" effect is the `utc_to_jd` quirk of +0.372 s; ΔT is 68.8 s and
would move the Moon by 41.7″). +13.5 s was itself *fitted* in TASK2 §8.3
from this same chart, so the "explanation" is not independent.

### Table [5]: implied kp_new offset K for all-nine ≤2″ at dt=0 (analysis only; `src/` untouched)

K window = (50.7 + maxΔ − 2, 50.7 + minΔ + 2]:

| convention | K window (″) | intersects printout window (49.665, 50.491]? |
|---|---|---|
| C1 app−mean | empty | — |
| C2/C3/C4 | empty (Moon −6.51 vs planets +1.2…+2.1) | — |
| C5 mixed-B | (50.786, 53.881] | **no** |

The prior calibration-epoch fact (printed `24°08'28"` holds at both epochs
under truncation for K ∈ (49.665, 50.491]) rules out the only non-empty
K window. No second in-repo reference exists to re-derive it
(`temp_kp*.json` are absent from this checkout — verified).

### Cross-consistency check (hypothesis A quantified, recorded as hypothesis)

C3 (nonut − mean ayan, K = 50.7″) + whole-chart dt = **+11.78 s** (fitted
from the dasha stamps — see Experiment 2, whose optimal Moon offset is
−0.9066″, reached by C3's −8.042″ plus 11.78 s × 0.6055″/s):

- planets: +0.62…+1.89″ → **9/9 within 2″**
- five dasha stamps: +20 s each (same irreducible residual as §2.A's best fit)
- printed Moon: reproduced under truncation, NOT under half-up
- horary cusps: insensitive to the clock (they are *solved* from the
  horary lagna), consistent with cusps matching at ±1″

So hypothesis A is *numerically viable as a single-convention,
single-offset fit*, but every part of it is fitted (dt) or in tension with
the reference's own mean-flavoured ayanamsa print (fact 3). It is **not**
a documented convention.

### Experiment 1 verdict (stop rule applied)

**STOP.** No single *documented* convention (with at most a documented time
offset) puts all nine bodies within 2″ of the reference at the pinned
kp_new offset. The current pipeline remains:

> **planets ≈ +10″, Moon ≈ +1.5″, convention unknown.**

Recorded alongside: the nutation-consistent family (NONUT/true-ayan/
FLG_SIDEREAL) moves the planets to ≈ +1.5″ but the Moon to −6.5″; only a
fitted +8…14 s clock offset makes them coexist, and nothing documents such
an offset. Displayed strings are not reproducible under either rounding
rule for any candidate (all-9 trunc/halfup match: none, all conventions).

---

## Experiment 2 — dasha end stamps vs Moon longitude

### Confirmed facts (measured this run)

1. Baseline reproduced exactly: unshifted max stamp error **+10,738 s**
   (= +2 h 58 m 58 s, reference later, identical on all five levels);
   shift −0.91″ → 31 s; −1.0″ → 1,097 s; −1.5″ → 7,014 s.
2. **All five levels always share the same error** (per-level vectors at the
   best fits: `[31,31,31,31,31]` and `[8,8,8,8,8]`). The stamps behave as an
   absolute grid: boundary time = birth + (B − p), so every level moves
   together. Sensitivity measured ≈ (10,738−31)/0.91 ≈ **11,800 s per
   arcsecond** of birth-Moon longitude. A constant stamp offset ⟺ a constant
   Moon-longitude offset (−10,738/11,8xx ≈ **−0.907″**) — it cannot be produced
   by a birth-time shift (that moves the Moon by ~6,000″ and jumps
   mahadashas).
3. Moon speed at t0 = **+0.6055″/s** → 1″ = 1.651 s of Moon motion. The
   dasha-implied Moon *time* shift is therefore **−1.503 s** (the earlier
   −1.66 s figure assumed the mean lunar speed 0.546″/s).
4. Node mode (mean vs true) changes the Moon by 0.000000″ — it only selects
   the Rahu/Ketu body id, as expected.
5. `swe.calc(jd_et)` (correct ET entry) ≡ `swe.calc_ut` (0.000″); feeding UT
   as ET shifts the Moon by −41.7″; topocentric shifts it by −2,998.8″
   (lunar parallax). Both far too large, both recorded.

### Table [2]: documented Moon candidates

shift = vs the current pipeline Moon; stamp errs = dasa/bhukti/antara/
sookshma/prana (s); T/H = printed Moon `08°31'49"` reproduced under
truncation / half-up:

| candidate | shift (″) | vs ref (″) | stamp errs (s) | max \|s\| | T | H |
|---|---|---|---|---|---|---|
| baseline: apparent − mean ayan (pipeline) | +0.000 | +1.531 | −10738 ×5 | 10738 | n | n |
| SEFLG_NONUT | −8.042 | −6.511 | +84420 ×4, −5322 | 84420 | n | n |
| SEFLG_TRUEPOS (no light-time/aberration) | +0.739 | +2.270 | −19495 ×4, +15021 | 19495 | n | n |
| SEFLG_NOABERR (aberration off, light-time kept) | −11.866 | −10.335 | +129686 ×3, −284508, +15782 | 284508 | n | n |
| SEFLG_MOSEPH | +0.060 | +1.591 | −11459 ×4, +23056 | 23056 | n | n |
| SEFLG_ICRS | −0.005 | +1.526 | −10678…−10679 | 10679 | n | n |
| SEFLG_SPEED3 (position must be identical) | +0.000 | +1.531 | −10738 ×5 | 10738 | n | n |
| SEFLG_JPLHOR (JPL-Horizons nutation model) | +0.000 | +1.531 | −10738 ×5 | 10738 | n | n |
| FLG_SIDEREAL (documented sidereal path) | −8.042 | −6.511 | +84420 ×4, −5322 | 84420 | n | n |
| FLG_SIDEREAL \| NONUT | −8.042 | −6.511 | +84420 ×4, −5322 | 84420 | n | n |
| topocentric (set_topo + TOPOCTR) | −2998.845 | −2997.314 | huge | 3.5e7 | n | n |
| swe.calc(jd_et) correct ET entry | +0.000 | +1.531 | −10738 ×5 | 10738 | n | n |
| swe.calc(jd_ut) UT fed as ET (mixup) | −41.667 | −40.136 | +482354 ×3, +68160, +75063 | 482354 | n | n |
| Moon-only time shift dt=−4.00 s | −2.422 | −0.891 | +17925 ×4, −2785 | 17925 | n | n |
| Moon-only time shift dt=−3.00 s | −1.817 | −0.286 | +10753 ×4, −9957 | 10753 | n | Y |
| Moon-only time shift dt=−2.00 s | −1.211 | +0.320 | +3594 ×5 | 3594 | Y | Y |
| Moon-only time shift dt=−1.66 s | −1.005 | +0.526 | +1156 ×5 | 1156 | Y | n |
| Moon-only time shift dt=−1.00 s | −0.606 | +0.925 | −3578 ×5 | 3578 | Y | n |
| Moon-only time shift dt=−0.50 s | −0.303 | +1.228 | −7164 ×5 | 7164 | n | n |
| Moon-only time shift dt=+0.50 s | +0.303 | +1.834 | −14323 ×4, +20193 | 20193 | n | n |

No documented flag comes within ~700 s of the reference stamps, let alone a
few seconds. TRUEPOS (the light-time convention) moves the Moon the *wrong
way* (+0.74″, not −0.91″); NONUT and FLG_SIDEREAL move it 9× too far
(−8.04″); MOSEPH/ICRS/SPEED3/JPLHOR barely move it at all (≤0.06″);
topocentric and time-scale mixups are off by orders of magnitude.

### Fine scans (fitted, not documented)

| scan | best | max stamp err | Moon print trunc / half-up |
|---|---|---|---|
| pure Moon-longitude shift, 0.01″ steps, ±3″ | **−0.91″** | **31 s** | Y / n |
| Moon-only time shift, 0.01 s steps, −4…+1 s | **−1.50 s** (≡ −0.908″) | **8 s** | Y / n |

- No δ anywhere in ±3″ reaches <5 s stamp error; the <60 s windows collapse
  to the single grid points δ = −0.91″ (0.01″ grid) and dt = −1.50 s
  (0.01 s grid). The residual 8–31 s is
  irreducible by any Moon-longitude shift or Moon-only time shift.
- Reference-print windows (arcsec into sign): truncation [30709, 30710),
  half-up [30708.5, 30709.5). The stamp-optimal shift (−0.9066″, leaving
  the Moon at +0.62″ vs the print) sits inside the **truncation** window
  only; under half-up the stamp-optimal Moon would print `08°31'50"`.
  Within the ±3″ scan, **no shift matches the printed Moon under half-up
  *and* keeps any stamp error < 1,000 s** (half-up needs δ ∈ (−2.03″,
  −1.03″], where stamp errors are ≥ ~1,100 s).

### Experiment 2 verdict (stop rule applied)

**STOP.** No documented Moon convention reproduces the printed Moon and all
five dasha stamps together under any rounding rule. §2.A is recorded as-is:

> five `vimsottari_dasa.*.end` stamps off by a constant **+2 h 58 m 58 s**;
> best Moon-only fits are **fitted** (δ = −0.91″ → 31 s residual;
> Moon-only dt = −1.50 s → 8 s residual) and match the printed Moon **only
> under truncation**.

**Rounding rule: remains unresolved** overall (the cusp evidence still
conflicts: truncation explains cusps 3/9 but not 2/8, 6/12; half-up the
reverse). Within §2.A's own data the printed Moon + stamps are consistent
**only with truncation**; under half-up the two reference facts (Moon print
`08°31'49"` and stamps 10,738 s later than ours) cannot both hold for any
Moon longitude. This is recorded, not resolved.

No src/ change was made, no constant was fitted into the library, and the
house-cusp path was untouched.

---

## Commands run (abridged, all from repo root)

```bash
export SE_EPHE_PATH="$HOME/.kpastro/ephe"
# baseline reproduction
venv/bin/python -m kpastro.cli natal --date 2026-10-30 --time 12:00:00 --tz 5.5 \
  --lat 18.4593067 --lon 73.8654709 --place "Pune, India" --ayanamsa kp_new \
  --node mean --json --name KPstellaroutput --gender Male --horary-no 117 \
  --timezone Asia/Kolkata --query-utc "2026-10-18 12:00:00" > /tmp/current.json
venv/bin/python diagnositics/jdiff.py kp_stellar_output.json /tmp/current.json
# experiments
venv/bin/python diagnositics/planet_convention_probe.py   # tables [0]-[5]
venv/bin/python diagnositics/dasha_moon_probe.py          # tables [0]-[4]
# regression guard (see repo-state caveat above)
venv/bin/python -m pytest --no-cov -q
```

Documentation fetched for citation:
`https://www.astro.com/swisseph/swephprg.htm` (programmer's manual) and
`https://www.astro.com/swisseph/swisseph.htm` (general manual, Appendix E).
`https://www.astro.com/astrology/in_ayanamsha_e.htm` is JS-gated and could
not be fetched; web search returned no results. **No public documentation
of the commercial KP Stellar app's internal convention was found** — its
"KP New" print remains undocumented.
