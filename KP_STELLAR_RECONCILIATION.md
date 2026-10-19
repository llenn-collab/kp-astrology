# KP Stellar reconciliation — `kp_stellar_output.json`

Both files are at the repo root.

| input | value |
| :-- | :-- |
| date / local time | 2026-10-30, 12:00:00 |
| timezone | +5.5 (Asia/Kolkata) → **06:30:00 UTC** |
| latitude / longitude | 18.4593067 N, 73.8654709 E (Pune, India) |
| ayanamsa | `kp_new` = Swiss `SIDM_KRISHNAMURTI_VP291` − 50.7″ |
| node | mean |
| horary number | **117 (of 249)** |
| ephemeris | `~/.kpastro/ephe` (`sepl_18.se1`, `semo_18.se1`, `seas_18.se1`), `SwissEphemeris.precision == "full"` |

Reproduce with:

```bash
SE_EPHE_PATH="$HOME/.kpastro/ephe" python -m kpastro.cli natal \
  --date 2026-10-30 --time 12:00:00 --tz 5.5 \
  --lat 18.4593067 --lon 73.8654709 --place "Pune, India" \
  --ayanamsa kp_new --node mean --json \
  --name KPstellaroutput --gender Male --horary-no 117 \
  --timezone Asia/Kolkata --query-utc "2026-10-18 12:00:00" \
  > kpastro_actual.json
```

Two of those flags are load-bearing and were not in the original command:

* `--horary-no 117` — see §1. Without it kpastro casts the houses from the
  birth instant and every house-derived field disagrees by a whole sign.
* `--query-utc` — pins the instant the Vimshottari stack resolves at. Without
  it the two deepest levels move with the wall clock (Sookshma ≈ 5 d, Prana
  ≈ 14 h), so no reference comparison is reproducible.

## Result

322 comparable leaves: **304 identical, 18 differing (94.4 %)** (strict
recursive count, `tests/test_kp_stellar_strict.py`).

| category | differing | total | note |
| :-- | --: | --: | :-- |
| header, ruling planets, legend, all lord columns, all flags | 0 | 88 | 100 % |
| `cusps` block | 2 | 96 | cusp 3/9 degrees only, §4 |
| `planets.house` | 0 | 9 | 100 % |
| `nodes_representation` houses **and** planets | 0 | 4 | 100 % |
| `planets.signifies` (order included) | 0 | 10 | 100 % — fixed this pass, §4a |
| `cusps.signifies_A_B_C_D` (order included) | 0 | 48 | 100 % — fixed this pass, §4a |
| `planets.degree` | 9 | 9 | +1.5″ … +10.1″, §3 |
| `vimsottari_dasa` end stamps | 5 | 5 | constant +2 h 58 m 58 s, §3 |
| `sunrise` / `sunset` | 2 | 2 | +8 s / −7 s, §4 |

All twelve house signs, all twelve cusp names and every `sg`/`sl`/`sb`/`ss` on
both planets and cusps match exactly.

## 1. The reference is a horary chart, and says so in its own header

`horary_details.horary_no` is `"117 (249)"`. KP Stellar was asked for a *horary*
chart, so its house cusps are cast from horary division 117's **cusp** while
its planets, ruling planets, panchanga and Vimshottari all stay on the birth
data. That single fact explains everything that looked like a contradiction:

* `cusps.1` is Virgo 17°46′40″ = **1510/9 degrees exactly**, which is division
  117's `start_deg` and *no* division's midpoint
  (`tests/test_kp_stellar_reference.py::test_reference_ascendant_is_the_cusp_of_horary_division_117`).
* All twelve cusps are reproduced by Placidus at Pune's geocentric latitude at
  the instant whose ascendant equals that lagna — ten to better than 0.3″,
  cusps 3/9 to 0.88″ (§4).
* `ruling_planets.lagna` is JUP/VEN, the *astronomical* Sagittarius ascendant,
  not the Virgo one in `cusps.1`. Two lagnas, both correct for their own
  purpose; kpastro keeps the same split.
* At the stated birth instant **none of the 21 house systems Swiss Ephemeris
  implements** puts cusp 1 within a degree of Virgo — which is why no
  ayanamsa, node, latitude-model or `hsys` change could ever have closed the
  gap.

kpastro was missing the capability, not the arithmetic. Added:

* `horary.cusps_from_horary_lagna(lagna_deg, eph, jd_ref, lat, lon)` — solves
  the instant whose Placidus ascendant equals `lagna_deg` (the ascendant is
  strictly increasing through 360° once per sidereal day, so there is exactly
  one; bracketed by an unwrapping scan, then bisected) and returns that
  instant's twelve sidereal cusps, with cusps 1 and 7 pinned to the exact
  horary longitude rather than to the numerically solved value.
* `compute_chart(..., horary_lagna=...)` — swaps in that house frame while
  leaving `ascendant`, `midheaven`, `ruling` and all planetary data on the
  birth instant. Exposed as `Chart.horary_lagna`.
* `natal --horary-no N` — feeds it division N's cusp.

`horary.ascendant_from_kp_number` still returns the division **midpoint**: it
is public API, documented in the README, and used by the `horary` subcommand.
The two conventions are documented side by side in `AGENTS.md`.

## 2. What matches exactly

* `horary_details`: name, gender, date, time, horary_no, place, latitude,
  longitude, timezone, `ayanamsa` (`24°08'28" (KP New)`), node, `nakshatra`
  (`Ardra (1)`), `tithi` (`Krishna Panchami`), `yoga` (`Siva`), `karana`
  (`Taitula`), `dasha_balance` (`RAH 15y 5m 26d`).
* All nine planets: `sign`, `sg`, `sl`, `sb`, `ss`, `flags`, `house`.
* All five Vimshottari lords.
* `ruling_planets` in full.
* All twelve cusps: `name`, `sign`, `sg`, `sl`, `sb`, `ss`.
* All nine `signifies` rows and all 48 `signifies_A_B_C_D` lists —
  membership **and order** (see §4a); both `nodes_representation` house
  and planet lists.
* The whole `legend`.

Semantics confirmed against the reference, for the record:

* `signifies` = houses the planet occupies ∪ houses its star-lord occupies ∪
  houses whose cusp sign-lord is the planet ∪ houses whose cusp sign-lord is
  its star-lord.
* The trailing parenthesised element, e.g. `"(IV, VIII)"`, is the set of houses
  whose **cusp sub-lord** is that planet, in Roman numerals. Matches 9/9.
* `flags`: `#` = planet in its own star; `*` = no planet occupies a nakshatra
  this planet rules; `R` = retrograde, main planets only — KP Stellar does not
  mark the nodes. Matches 9/9.
* `nodes_representation.planets` = the node's star-lord plus the lord of the
  sign the node occupies.

## 3. Sub-arcsecond input residuals (convention unknown; not fitted)

**Planets.** kpastro runs ahead of the reference by a near-constant amount:

| | SUN | MOO | MAR | MER | JUP | VEN | SAT | RAH | KET |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| kpastro − ref | +9.2″ | +1.5″ | +9.7″ | +9.8″ | +9.6″ | +10.1″ | +9.8″ | +9.5″ | +9.5″ |

**Cause: convention unknown.** kpastro subtracts the *mean* ayanamsa
(`swe.get_ayanamsa_ut`) from *apparent* tropical longitudes. Swiss Ephemeris's
own sidereal path subtracts the nutation-inclusive value (Δψ ≈ 8.042″ at this
epoch, −0.558″ at the 2024-12-18 `kp_new` calibration epoch), and the manual
warns against mixing the two. Removing nutation brings the seven non-Moon
bodies to +1.2″…+2.1″ but moves the Moon to −6.5″, while the dasha (below)
says the reference Moon is ours −0.907″. Measured variants (NONUT, TRUEPOS,
NOABERR, MOSEPH, ICRS, `FLG_SIDEREAL`, mean/true ayanamsa, ±20 s time offsets):
no single documented convention puts all nine bodies within 2″; a fitted
+8…+14 s time offset plus the nutation-free family comes within 1.86″, but
nothing documents such an offset. The residual never crosses a sub-lord
boundary here, which is why all 45 lord columns still match.
Tables: `diagnositics/findings_planets_dasha.md`.

**Dasha end stamps.** All five differ by *exactly* +2 h 58 m 58 s, so the
durations agree and only the epoch does. The dasha stack is driven by the
sidereal Moon longitude with sensitivity ≈ **3.29 h per arcsecond** in a Rahu
mahadasha; the constant offset corresponds to a Moon residual of **−0.907″**.
No documented Moon convention (NONUT, TRUEPOS, NOABERR, MOSEPH, topocentric,
ET/UT, node mode) produces it; the closest fits are fitted constants, which
the ground rules forbid. Fixing it would mean changing the Moon.
The truncation-vs-half-up display rule stays unresolved: under truncation the
printed Moon and the dasha agree; under half-up they do not.

## 4. The remaining 18 differences, in full

```
/horary_details/sunrise                  06:36:48  vs  06:36:56   (+8 s)
/horary_details/sunset                   17:59:22  vs  17:59:15   (-7 s)
/vimsottari_dasa/{5 levels}/end           constant +2 h 58 m 58 s          §3
/planets/{9 planets}/degree               +1.5" .. +10.1"                  §3
/cusps/{3,9}/degree                       17°20'10" vs 17°20'11"           (0.88")
```

Each is pinned as `xfail(strict=True)` with its measured value in
`tests/test_kp_stellar_strict.py` (`KNOWN_RESIDUALS`), and the current values
are pinned in `KNOWN_OURS` so drift fails the suite rather than hiding in an
xfail.

**Cusps 3 and 9.** The same point, 180° apart. kpastro's value is 227.3363565°
against the reference's 227.3361111° — **+0.88″**, which crosses the arcsecond
rounding boundary; the other ten cusps agree to better than 0.3″. The earlier
"Placidus iteration converges a hair short" hypothesis is **disproved**: the
Swiss stop-tolerance is compile-time (0.001″) with a fixed-point contraction
factor ≈1e-4 (a 36″ tolerance moves cusp 3 by <1e-6″), and no documented
`swe.houses`/`houses_ex` option (NONUT, SIDEREAL, TRUEPOS, MOSEPH, geodetic
latitude) moves cusp 3 without moving others. Display rounding is also
unresolved: cusp 3/9's 10.883″ only prints `10"` under truncation, but cusps
2/8 (11.916″ → `12"`) and 6/12 (33.995″ → `34"`) require half-up.
Table: `diagnositics/findings_cusp_sunrise.md`.

**Sunrise / sunset.** kpastro uses the Sun's **disc centre with no refraction**
(the panchanga convention) via `swe.rise_trans`. The reference's day is 15 s
longer. Every documented atmosphere (Swiss 1013.25/10, IAU 1013.25/15, Meeus
1010/10) misses by 2.2–2.5 min; the only fits are non-standard (an effective
horizon ≈1.6–1.75′ below geometric — reproducible by a ~125 mbar atmosphere or
a ~1.0 m observer height), so the current convention is kept.
Table: `diagnositics/findings_cusp_sunrise.md`.

## 4a. Fixed this pass: signifies row order (18 leaves → 0)

The 10 `planets.signifies` rows and 8 `cusps.signifies_A_B_C_D` elements that
differed **in order only** are fixed by a chart-derived rule, stated before it
was tested (`diagnositics/findings_signifies.md`): a planet no planet sits in
the star of (KP Stellar's `*` flag) emits its signify groups with each pair
flipped (own house before star-lord's house, own signs before the star-lord's
signs), and `*`-flagged planets sort first inside `signifies_A_B_C_D` tiers,
the rest in KP planet-table order. The rule reproduces all 9 rows and all 48
tiers and broke none of the 51 previously-correct arrays; no fitted constant
entered `src/`. Candidate rules R1/R3/T4/T5/T6 and their measured failures are
tabulated in the findings file. Caveat: confirmed on n=1 chart — a second KP
Stellar printout could falsify it, which is why
`tests/test_signifies_order.py` pins all 57 arrays exactly.

## 5. Bugs found and fixed in kpastro

1. **No horary house frame existed.** `horary.ascendant_from_kp_number` printed
   a lagna but nothing cast houses from one. See §1.
2. **`--json` did not emit the KP Stellar schema at all.** `chart_to_kp_json`
   emitted a kpastro-specific long-form payload (full lord names, an
   `Ascendant` cusp key, UTC dasha stamps, no details/panchanga section at
   all), despite
   `AGENTS.md` describing it as "the Stellar-aligned schema". Added
   `chart_to_kp_stellar_json` plus `--json-schema {stellar,detailed}`;
   `stellar` is the default and the old payload is still reachable.
   The printout's details section is named **`horary_details`**, matching the
   committed reference (git commit `8b369ad` renamed it from `birth_details`
   with all values unchanged); the serializer and tests follow the reference.
3. **No panchanga layer existed.** New `kpastro/panchanga.py`: sunrise/sunset,
   tithi, nitya yoga, karana, nakshatra + pada, day-lord, and the
   `dasha_balance` header string. All five match the reference.
4. **`dasha_balance` needs a flat 30-day month.** `dasha.format_days` uses
   30.4375 d and prints `15y 5m 24d`; KP Stellar floors with a 30-day month and
   prints `15y 5m 26d`. Implemented as `panchanga.dasha_balance_str`, leaving
   `format_days` alone.
5. **Sub-lord boundary policy contradicted its own documentation.**
   `vedic._mas` floored a longitude to a whole mas *before* applying
   `BOUNDARY_TOL_MAS` (1/1000 mas), so a double sitting exactly on a segment
   edge landed a full mas short of it and resolved to the **preceding**
   segment — the opposite of the policy in `AGENTS.md` and of KP Stellar. Two
   concrete cases, both now correct:
   * `26.666666666666664` (= 95 999 999.9999999851 mas, the exact Krittika
     start, and the worked example in `_mas`'s own docstring) resolved to
     Bharani/Venus instead of Krittika/Sun;
   * `1510/9` (= 604 000 000 mas exactly, the Saturn → Mercury sub edge of
     Hasta, **and cusp 1 of the reference**) resolved to SAT where KP Stellar
     prints MER.

   `_mas` now snaps up when the exact rational value is within
   `BOUNDARY_TOL_MAS` of the next integer mas; points further below an edge
   still resolve down (`sub_info(1510/9 − 1e-6).lord == "Saturn"`).
6. **Sunset returned the previous day's.** `sunrise_sunset` searched both
   events from one window, so the previous afternoon's sunset was reported for
   today. Each event now has its own back-off.

## 6. Verification

```
venv/bin/python -m pytest --no-cov      ->  5 failed, 145 passed, 21 xfailed
```

The 5 failures are the ones `AGENTS.md` documents as pre-existing and
test-side (`test_kahan_sum_beats_naive`, `test_quantize_deg_half_up_exact`,
`test_fraction_algebra_values`, `test_balance_requantisation_bound`,
`test_period_helpers`). The 21 xfails are the 18 strict residual leaves plus
the 3 converted reference tests (sunrise/sunset, planet degrees, dasha
stamps), each carrying its measured residual in the reason string.
`python -m pytest` also fails the `--cov-fail-under=85` gate, as documented.

Tests:

* `tests/test_kp_stellar_reference.py` — field-by-field against the
  committed reference, including the horary-lagna proof; the formerly
  tolerance-based assertions are now exact + `xfail(strict=True)`.
* `tests/test_kp_stellar_strict.py` — recursive type-aware leaf comparison;
  asserts exactly 18 differing leaves, pins their set (`KNOWN_RESIDUALS`) and
  their current values (`KNOWN_OURS`), one strict xfail per residual.
* `tests/test_signifies_order.py` — all 9 `signifies` rows and all 48 tiers
  hard-coded exact.
* `tests/test_horary.py` — the 249-division table, and
  `cusps_from_horary_lagna` checked against an independent ascendant solve that
  shares no code with the function under test.

## 7. What would close the remaining residuals

One further KP Stellar printout (any date/place, same schema, same "KP New"
setting) would let us test: (i) truncation vs half-up on ≥20 printed angles,
(ii) whether the nutation-consistent ayanamsa family recurs, (iii) whether a
small time offset recurs, (iv) whether the `*`-flag ordering rule survives a
second chart. The `temp_kp*.json` files `AGENTS.md` used to mention are **not**
on `main` (branches `qwen` / `error-free-astrology-repo-upgrades-5d780` only)
and are kpastro's own long-form schema anyway — not independent references.
