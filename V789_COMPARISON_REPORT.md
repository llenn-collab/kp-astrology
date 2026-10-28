# V7 / V8 / V9 normalized comparison report

**Generated:** 2026-10-28 (agent session on branch `arena/219ace0b-kp-astrology`)
**Tool:** `diagnositics/v789_comparison.py` (schema-aware comparator; normalizes the three
differently-shaped KP Stellar reference schemas into one internal representation)
**Full-precision probe:** `diagnositics/full_precision_probe.py`
**Ephemeris:** `mivion/swisseph` JPL/VSOP files in `~/.kpastro/ephe`, `SwissEphemeris.precision == "full"`

## 1. Inputs verified (gate — see REFERENCE_MANIFEST.md)

| version | chart (IST) | UTC | horary | `--query-utc` | kpastro file | KP Stellar ref |
|:--|:--|:--|:--|:--|:--|:--|
| V7 | 2026-10-30 12:00 | 06:30 | 117 | 2026-10-18 12:00 UTC | `kpastro_actual.json` (pinned-query regen) | `kp_stellar_output.json` |
| V8 | 2027-04-30 12:00 | 06:30 | 117 | 2027-04-18 12:00 UTC | `kpastro_actual8_query.json` / `-2` | `kp_stellar_output8.json` |
| V9 | 2027-10-30 12:00 | 06:30 | **74** | 2027-10-18 12:00 UTC | `kpastro_actual9_query.json` / `-2` | `kp_stellar_output9.json` |

- V8/V9 `-2` files were independently regenerated with the documented `--query-utc`
  and match on every field except sub-second dasha end stamps (ephemeris-mirror drift;
  see §7). This proves the query-time windows (April 2027 / October 2027).
- **V9 horary 74 is intentional** — it is consistent across `kpastro_actual9.json`,
  `kpastro_actual9-2.json`, AND `kp_stellar_output9.json` (KP Stellar's own V9 reference).
  Not silently changed to 117.
- **KP Stellar V8/V9 references carry STALE dasha** (Oct–Nov 2026 end stamps) and cannot
  be regenerated here (external app). Dasha timing comparisons against KP Stellar are
  therefore invalid for V8/V9. Non-dasha fields (planets, cusps, ayanamsa, sunrise/sunset,
  nodes) depend on the chart instant and remain comparable.

## 2. Comparison results — planets (printed arcsecond, kpastro − KP Stellar)

All nine planets, their signs, houses and lord chains (sg/sl/sb/ss) were compared.

### V7 (horary 117) — the baseline
Every planet degree matches KP Stellar exactly (+0.00"). All lord chains match.
This reproduces `KP_STELLAR_RECONCILIATION.md` Addendum B (315/322 leaves exact).

### V8 (horary 117) — matches context1 §"V8 specific differences" exactly
| planet | kpastro | KP Stellar | resid (kp − ref) |
|:--|:--|:--|:--|
| SUN | 15°33'18" | 15°33'18" | 0.00" |
| MOO | 01°08'33" | 01°08'31" | **+2.00"** |
| MAR | 01°09'07" | 01°09'08" | **−1.00"** |
| MER | 17°10'40" | 17°10'41" | **−1.00"** |
| JUP | 23°17'47" | 23°17'47" | 0.00" |
| VEN | 18°06'21" | 18°06'22" | **−1.00"** |
| SAT | 26°19'41" | 26°19'41" | 0.00" |
| RAH | 22°22'36" | 22°22'37" | **−1.00"** |
| KET | 22°22'36" | 22°22'37" | **−1.00"** |

All sign/lord/star/sub/sub-sub columns match; only the four 1" residuals and the
2" Moon residual above differ at the printed level.

### V9 (horary 74) — matches context1 §"V9 specific differences" exactly
| planet | kpastro | KP Stellar | resid (kp − ref) |
|:--|:--|:--|:--|
| SUN | 12°26'53" | 12°26'54" | **−1.00"** |
| MOO | 21°22'54" | 21°22'53" | **+1.00"** |
| MAR | 16°08'48" | 16°08'49" | **−1.00"** |
| MER | 25°24'43" | 25°24'43" | 0.00" |
| JUP | 25°49'04" | 25°49'04" | 0.00" |
| VEN | 03°18'05" | 03°18'06" | **−1.00"** |
| SAT | 29°17'25" | 29°17'25" | 0.00" |
| RAH | 12°40'45" | 12°40'45" | 0.00" |
| KET | 12°40'45" | 12°40'45" | 0.00"** |

## 3. Comparison results — cusps (full-precision vs printed)

Printed residuals (kpastro − KP Stellar) and the underlying full-precision truth:

| version | printed cusp residuals | full-precision truth (kpastro − ref printed) |
|:--|:--|:--|
| V7 | cusps 2/8 −1" (print) | 2/8 −0.09"; 3/9 +0.85" (hidden by truncation) |
| V8 | cusps 3/9 +1" (print) | 3/9 +1.08"; 2/8 +0.73" (hidden by truncation) |
| V9 | 2/8 −2", 3/9 −2", 4/10 −3", 5/11 −2" | 2/8 −1.12"; 3/9 −1.65"; 4/10 −2.15"; 5/11 −1.09"; 6/12 +0.18" |

**Phase 5 finding:** the cusp discrepancy is **not a uniform global offset**. It varies
by epoch (V7 hits 2/8, V8 hits 3/9, V9 spreads across 2/8, 3/9, 4/10, 5/11) and the
true residuals range from +1.08" to −2.15". Per the plan's stop rule, the global
ayanamsa must NOT be changed to fix cusps unless it is shown to preserve the planetary
matches (which it would not — V8/V9 planets are already within 2" while cusps are off
by up to 3"). The residual is attributable to input/solver/display-quantization
differences, not a single ayanamsa shift.

Sunrise and sunset match KP Stellar in all three versions (to the printed second).
Ayanamsa matches in V7/V8; V9 prints 19" vs ref 18" (1" printed difference — recorded
in KP_STELLAR_RECONCILIATION.md Addendum B.5 as the epoch-drifting ayanamsa window).

## 4. Nodes / Rahu-Ketu representation

| version | kpastro RAH | KP Stellar RAH | kpastro KET | KP Stellar KET |
|:--|:--|:--|:--|:--|
| V7 | MAR, SAT | MAR, SAT | KET, SUN | KET, SUN |
| V8 | MOO, SAT | MOO, SAT, **JUP** | MER, MOO | MER, MOO, **JUP** |
| V9 | MOO, SAT | MOO, SAT | SAT, MOO | SAT, MOO |

**Phase 6 finding:** only V8 differs — KP Stellar includes **Jupiter** in both the
Rahu and Ketu represented-planet lists (and adds houses 4 to RAH, house 4/9 area to
KET), kpastro does not. V7 and V9 match exactly. This is the conjunction /
node-agency rule difference to investigate (trace star-lord + sign-lord of the node,
and how KP Stellar adds an extra agent near a node).

## 5. Dasha

| version | kpastro balance | KP Stellar balance | note |
|:--|:--|:--|:--|
| V7 | RAH 15y 5m 26d | RAH 15y 5m 26d | exact match |
| V8 | MAR 2y 10m 28d | MAR 2y 10m 25d | **+3 days** (context2) |
| V9 | JUP 14y 4m 4d | JUP 14y 4m 5d | **−1 day** (context2) |

The header balance is a distinct comparison from the active dasha stack at the query
instant (context2 §2). The V8/V9 KP Stellar active-stack end stamps are stale
(Oct–Nov 2026) and cannot be compared to the kpastro April/October 2027 windows.
V7's five end stamps differ by ~24 s (kpastro later) — this is the pre-existing
ephemeris-mirror condition (see §7), not a new code change.

## 6. Schema differences (no false accuracy failures)

The three KP Stellar references use different schemas, all normalized by the comparator:
- V7 (`kp_stellar_output.json`): `horary_details`, `vimsottari_dasa`, planets as a
  dict keyed by abbr with separate `sg`/`sl`/`sb`/`ss` fields, cusps as a dict keyed
  by "1".."12".
- V8 (`kp_stellar_output8.json`): `birth_details`, `vimsottari_dasha`, `node_type`
  (not `node`), planets/cusps as lists with `|`-joined `sgn_stl_sub_ssl`.
- V9 (`kp_stellar_output9.json`): `metadata` + nested `panchanga`, `vimsottari_dasha`,
  planets/cusps as lists.

The comparator treats missing/empty/null/empty-array distinctly, compares significator
membership separately from order, and treats display labels/names as metadata.

## 7. Environment conditions (pre-existing, not caused by this session)

- The code's `EPHEMERIS_BASE_URL` points at `aloistr/swisseph`, which carries no
  `.se1` files. Files were obtained from `mivion/swisseph` (Git contents API +
  git clone, since `raw.githubusercontent.com` is not reachable in this sandbox).
- `mivion` file sizes differ by a few bytes from the `aloistr` sizes quoted in
  `KP_STELLAR_DIFF.md` (sepl: 484,055 vs 484,061; seas: 223,002 vs 223,004). This
  produces sub-arcsecond / tens-of-seconds dasha-stamp drift vs the committed
  snapshots (e.g. V7 dasha stamps ~24 s later than `KNOWN_OURS`; V8/V9 regen stamps
  4–21 s later than the `-2` files). Planets/cusps are unaffected (match to the
  printed arcsecond).
- Test baseline on this machine: 8 failed / 157 passed / 8 xfailed. The failures are
  pre-existing: 4 `test_precision` cases (documented in AGENTS.md), plus
  `test_exactly_seven_leaves_differ` and `test_moon_calibration` (set4/set5/set1)
  which fail only because the recorded dasha values drift with this ephemeris mirror.
  No source code was changed in this session, so no new failures were introduced.

## 8. Conclusions / next steps (implementation order)

1. ✅ V8/V9 references verified and regenerated with documented query times (gate Task 1–3).
2. ✅ Normalized comparison report built (Phase 2); all context1 specific differences
   reproduced exactly.
3. Moon calibration (Phase 3): printed Moon residuals vs KP Stellar are V7 equal,
   V8 +2", V9 +1". Dasha-timing validation for 2027 is blocked because KP Stellar's
   V8/V9 references are stale. Per the stop rule, no fitted Moon constant is added
   until it improves all valid epochs AND passes the regression suite.
4. Cusp precision (Phase 5): residuals vary by epoch and are not a global offset;
   do not change the global ayanamsa for cusps.
5. Rahu/Ketu representation (Phase 6): V8 KP Stellar adds Jupiter to both node
   representations; add regression tests and a documented node-agency rule.
6. Comparator ordering/schema rules (Phase 7): the comparator built here already
   normalizes schemas and separates membership from order; convert into reusable
   regression assertions.
7. Regression (Phase 8): add V7/V8/V9 references to the suite once a genuine KP
   Stellar printout at the matching query instant is obtained for V8/V9 dasha timing.

**Immediate blocker:** a genuine second KP Stellar printout (any date/place, same
schema, "KP New" setting) is required to validate dasha timing and the Moon
calibration at 2027 epochs (KP_STELLAR_RECONCILIATION.md §7).
