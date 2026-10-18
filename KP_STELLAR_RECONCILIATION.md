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

223 comparable leaves: **199 identical, 24 differing (89.2 %)**.

| category | differing | total | note |
| :-- | --: | --: | :-- |
| header, ruling planets, legend, all lord columns, all flags | 0 | 88 | 100 % |
| `cusps` block | 5 | 96 | §4 |
| `planets.house` | 0 | 9 | 100 % |
| `nodes_representation` houses **and** planets | 0 | 4 | 100 % |
| `planets.signifies` | 3 | 10 | row order only, §4 |
| `planets.degree` | 9 | 9 | +1.5″ … +10.1″, §3 |
| `vimsottari_dasa` end stamps | 5 | 5 | constant +2 h 58 m 58 s, §3 |
| `sunrise` / `sunset` | 2 | 2 | +8 s / −7 s, §4 |

All twelve house signs, all twelve cusp names and every `sg`/`sl`/`sb`/`ss` on
both planets and cusps match exactly.

## 1. The reference is a horary chart, and says so in its own header

`birth_details.horary_no` is `"117 (249)"`. KP Stellar was asked for a *horary*
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

* `birth_details`: name, gender, date, time, horary_no, place, latitude,
  longitude, timezone, `ayanamsa` (`24°08'28" (KP New)`), node, `nakshatra`
  (`Ardra (1)`), `tithi` (`Krishna Panchami`), `yoga` (`Siva`), `karana`
  (`Taitula`), `dasha_balance` (`RAH 15y 5m 26d`).
* All nine planets: `sign`, `sg`, `sl`, `sb`, `ss`, `flags`, `house`.
* All five Vimshottari lords.
* `ruling_planets` in full.
* All twelve cusps: `name`, `sign`, `sg`, `sl`, `sb`, `ss`.
* All 48 `signifies_A_B_C_D` memberships; both `nodes_representation` house
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

## 3. Sub-arcsecond input residuals (not kpastro bugs)

**Planets.** kpastro runs ahead of the reference by a near-constant amount:

| | SUN | MOO | MAR | MER | JUP | VEN | SAT | RAH | KET |
| :-- | --: | --: | --: | --: | --: | --: | --: | --: | --: |
| kpastro − ref | +9.2″ | +1.5″ | +9.7″ | +9.8″ | +9.6″ | +10.1″ | +9.8″ | +9.5″ | +9.5″ |

Not an ayanamsa difference: the reference *prints* 24°08′28″ and kpastro
computes 24°08′27.791″, 0.21″ apart, and a uniform ayanamsa shift would move
the Moon by the same 9.5″ as the rest. Not a time difference either — that
would move the Moon ~47 000× faster than the Sun. Consistent with KP Stellar
using its own truncated planetary series. The residual never crosses a
sub-lord boundary here, which is why all 45 lord columns still match.

**Dasha end stamps.** All five differ by *exactly* +2 h 58 m 58 s, so the
durations agree and only the epoch does. That offset is the ~0.9–1.5″ Moon
difference seen through an 18-year Rahu mahadasha
(0.124 d / 6574.5 d × 13.333° = 0.91″). Fixing it would mean changing the Moon.

## 4. The remaining 24 differences, in full

```
/birth_details/sunrise                    06:36:48  vs  06:36:56   (+8 s)
/birth_details/sunset                     17:59:22  vs  17:59:15   (-7 s)
/vimsottari_dasa/{5 levels}/end           constant +2 h 58 m 58 s          §3
/planets/{9 planets}/degree               +1.5" .. +10.1"                  §3
/planets/{SUN,MOO,VEN}/signifies          row order only
/cusps/{3,9}/degree                       17°20'10" vs 17°20'11"           (1")
/cusps/3/signifies_A_B_C_D                ['VEN','RAH'] vs ['RAH','VEN']   (order)
/cusps/8/signifies_A_B_C_D                ['VEN','RAH'] vs ['RAH','VEN']   (order)
/cusps/11/signifies_A_B_C_D               ['VEN','RAH','MER','KET'] vs
                                          ['RAH','MER','KET','VEN']        (order)
```

**Cusps 3 and 9.** The same point, 180° apart. kpastro's value is 227.3363565°
against the reference's 227.3361111° — **+0.88″**, which crosses the arcsecond
rounding boundary; the other ten cusps agree to better than 0.3″. Sweeping the
solved instant shows cusps 2, 3 and 4 all move ~14″ per second of time, so no
single time offset fixes cusp 3 without breaking cusp 2 (11.92″ → correctly
rounds to 12″). Neither a geodetic/geocentric swap nor any house system
reproduces it: the four latitude combinations give −57″, +36″ and −22″. It is
KP Stellar's Placidus cusp-3 iteration converging slightly short, and it is
left alone rather than fitted to one sample.

**Sunrise / sunset.** kpastro uses the Sun's **disc centre with no refraction**
(the panchanga convention) via `swe.rise_trans`. The reference's day is 15 s
longer — the same order as the §3 planetary residual. Tested within 60 s.

**Row order.** kpastro emits `signifies` as [star-lord's occupied house, own
house, houses the star-lord owns, houses the planet owns] and every
`signifies_A_B_C_D` list in KP planet-table order. That reproduces 6 of 9 rows
and 45 of 48 lists verbatim. KP Stellar's order for the six exceptions is not a
function of anything in the chart — h5 class A wants planet-table order while
h11 class A wants longitude-ascending — so with n=9 it cannot be fitted
without over-fitting. They are named explicitly in the tests rather than hidden
behind a set comparison.

## 5. Bugs found and fixed in kpastro

1. **No horary house frame existed.** `horary.ascendant_from_kp_number` printed
   a lagna but nothing cast houses from one. See §1.
2. **`--json` did not emit the KP Stellar schema at all.** `chart_to_kp_json`
   emitted a kpastro-specific long-form payload (full lord names, an
   `Ascendant` cusp key, UTC dasha stamps, no `birth_details`), despite
   `AGENTS.md` describing it as "the Stellar-aligned schema". Added
   `chart_to_kp_stellar_json` plus `--json-schema {stellar,detailed}`;
   `stellar` is the default and the old payload is still reachable.
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
python -m pytest --no-cov      ->  139 passed, 4 failed
```

The 4 failures are the ones `AGENTS.md` documents as pre-existing and test-side
(`test_quantize_deg_half_up_exact`, `test_fraction_algebra_values`,
`test_balance_requantisation_bound`, `test_period_helpers`); their messages are
byte-identical to before this work. `python -m pytest` also fails the
`--cov-fail-under=85` gate, as documented.

New tests:

* `tests/test_kp_stellar_reference.py` (18) — field-by-field against the
  committed reference, including the horary-lagna proof and an explicit list of
  every ordering-only residual.
* `tests/test_horary.py` (14) — the 249-division table, and
  `cusps_from_horary_lagna` checked against an independent ascendant solve that
  shares no code with the function under test.
