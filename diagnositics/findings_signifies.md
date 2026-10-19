# §2.E Signifies ordering — candidate rules and measured results

Status: **rules STATED FIRST** (this section), probe run afterwards, measured
tables appended below. Nothing in `src/` is touched unless a rule passes the
full acceptance test (all 9 planet rows + all 48 cusp tiers reproduced, none of
the 51 currently-correct arrays — 6 rows + 45 tiers — changed).

## Chart-derived facts used by the rules

All keys below are computed from the chart alone — no reference value is used:

- `G1(p)` = house occupied by `p`'s star-lord
- `G2(p)` = house occupied by `p` itself
- `G3(p)` = houses whose cusp sign-lord is `p`'s star-lord
- `G4(p)` = houses whose cusp sign-lord is `p`
- `noStar(p)` = True iff **no planet's star-lord is `p`** — this is
  exactly KP Stellar's `*` flag ("no planet occupies a nakshatra this planet
  rules"), already computed by `_planet_flags` (whose check includes the
  planet's own star-lord slot: a planet in its own star is not `*`-flagged).
  In this chart:
  `noStar = {SUN: True, MOO: True, VEN: True, others: False}`.
- `KP order` = `KP_PLANET_ORDER` (Sun, Moon, Mars, Rahu, Jupiter, Saturn,
  Mercury, Ketu, Venus).
- `lon(p)` = absolute sidereal ecliptic longitude of `p`; `house(p)` = house
  `p` occupies.

## Candidate rules

- **R0 (current code, baseline).** Every planet row = groups in order
  `[G1, G2, G3, G4]`, deduplicated first-seen. Every tier = members in
  `KP order`.
- **R1 (unconditional flip).** Every planet row = `[G2, G1, G4, G3]`;
  tiers unchanged (`KP order`).
- **R2 (star-flag rule).** Row: if `noStar(p)` then `[G2, G1, G4, G3]`,
  else `[G1, G2, G3, G4]`. Tier: members sorted by key
  `(0 if noStar(m) else 1, KP index of m)` — `*`-flagged planets first (in
  KP order among themselves), then the rest in KP order.
- **R3 (node-star-lord rule).** Row: if `p`'s star-lord is Rahu or Ketu then
  `[G2, G1, G4, G3]` else `[G1, G2, G3, G4]`; tiers unchanged. (Alternative
  explanation for SUN/MOO, stated to test whether `noStar` is really needed.)
- **T4 (house-ascending tiers).** Tiers sorted by `house(m)` ascending,
  KP index as tie-break; rows = R0.
- **T5 (longitude-ascending tiers).** Tiers sorted by `lon(m)` ascending —
  motivated by KP_STELLAR_RECONCILIATION.md's claim "h11 class A wants
  longitude-ascending"; rows = R0.
- **T6 (Venus-first tiers, H3).** Tiers sorted by key
  `(0 if m == Venus else 1, KP index)`; rows = R0.

Predictions stated before running (R2 is the acceptance candidate):

| candidate | predicted rows | predicted tiers |
|---|---|---|
| R1 | fixes SUN/MOO/VEN, **breaks MAR, RAH, JUP, MER** | n/a (tiers = R0, keeps the 3 tier diffs) |
| R2 | fixes exactly SUN, MOO, VEN; 6 other rows unchanged | fixes 3.C, 8.C, 11.A; all 45 others unchanged |
| R3 | fixes SUN/MOO, **fails VEN** (star-lord = Mars, not a node) | n/a |
| T4 | n/a | **fails 11.A** (house order 1,2,5,11 → [VEN,MER,RAH,KET]) |
| T5 | n/a | **fails 5.A** [SUN,MOO] (lon MOO 68° < SUN 192°) and 1.B |
| T6 | n/a | **fails 1.B** (would put VEN before SUN) |

Acceptance test (TASK2.md §2.E): rule reproduces **all 9 rows and all 48
tiers** vs `kp_stellar_output.json` and changes **none** of the 51 arrays that
already match. Anything else is rejected.

---

## Measured results

Probe: `venv/bin/python diagnositics/signifies_probe.py` (repo root,
`SE_EPHE_PATH=$HOME/.kpastro/ephe`). All numbers below are probe output, not
hand counts. Tables were measured in two runs: **pre-implementation** (the
official acceptance measurement, where "ours" = the then-current code) and
**post-implementation** (confirming `src/` emits the accepted package).

### Group decomposition (chart-derived, printed by the probe)

```
Sun:  G1=[5] G2=[1]  G3=[]     G4=[12]  noStar=True  sl=Rahu
Moon: G1=[5] G2=[9]  G3=[]     G4=[11]  noStar=True  sl=Rahu
Mars: G1=[2] G2=[11] G3=[1,10] G4=[3,8] noStar=False sl=Mercury
Rahu: G1=[11] G2=[5] G3=[3,8]  G4=[]    noStar=False sl=Mars
Jupiter: G1=[2] G2=[11] G3=[1,10] G4=[4,7] noStar=False sl=Mercury
Saturn: G1=[6] G2=[6] G3=[5,6] G4=[5,6] noStar=False sl=Saturn
Mercury: G1=[11] G2=[2] G3=[4,7] G4=[1,10] noStar=False sl=Jupiter
Ketu:  G1=[11] G2=[11] G3=[]   G4=[]    noStar=False sl=Ketu
Venus: G1=[11] G2=[1] G3=[3,8] G4=[2,9] noStar=True  sl=Mars
```

### Planet rows — candidate results (9 rows)

| candidate | reproduces | fails | predicted (stated first) | prediction correct? |
|---|---|---|---|---|
| R0 old default `[G1,G2,G3,G4]` | 6/9 | SUN, MOO, VEN | (baseline) | — |
| R1 unconditional `[G2,G1,G4,G3]` | 5/9 | **MAR, RAH, JUP, MER** (breaks 4 correct rows) | fixes SUN/MOO/VEN, breaks MAR/RAH/JUP/MER | ✓ |
| **R2 star-flag** | **9/9** | none | fixes exactly SUN/MOO/VEN, 0 breakage | ✓ |
| R3 node-star-lord flip | 8/9 | **VEN** | fails VEN (star-lord = Mars) | ✓ |

### Cusp tiers — candidate results (48 tiers)

| candidate | reproduces | fails | breaks among the 45 previously-correct | predicted | correct? |
|---|---|---|---|---|---|
| T0 old default KP order | 45/48 | 3.C, 8.C, 11.A | 0 (baseline) | — | — |
| T4 house-ascending | 47/48 | **11.A** | 0 | fails 11.A (houses 1,2,5,11) | ✓ |
| T5 longitude-ascending | 45/48 | 1.B, 5.A, 11.A | **1.B, 5.A** | fails 5.A/1.B | ✓ |
| T6 Venus-first (H3) | 47/48 | **1.B** | **1.B** | fails 1.B | ✓ |
| **T1 star-flag** | **48/48** | none | **0** | fixes 3.C, 8.C, 11.A, nothing else moves | ✓ |

Every stated prediction matched the measurement.

### Verdict

**ACCEPTED: R2 (rows) + T1 (tiers) — the star-flag rule.** 9/9 planet rows,
48/48 tiers reproduced; 0 of the 51 previously-correct arrays changed. The
rule keys only on chart-derived facts (`*` flag already emitted and verified
9/9 against the reference; `KP_PLANET_ORDER`), so it is a stated convention,
not a table fitted to the reference — no constant, shift or per-planet entry
enters `src/`.

### Confirmed facts vs hypotheses

- **H1 — CONFIRMED on this chart:** the three reordered rows (SUN, MOO, VEN)
  are exactly the three `*`-flagged planets. *Caveat: n = 1 chart; no second
  KP Stellar reference with ordered rows exists in the repo (the `temp_*`
  files referenced by AGENTS.md are gone; `chart_to_kp_json` has no ordered
  row). The rule is falsifiable — a future reference will confirm or break it.*
- **H2 — CONFIRMED:** for SUN/MOO the reference is `[G2, G1, G4]` (G3 empty
  because a node owns no cusp signs), for VEN `[G2, G1, G4, G3]` — one rule
  `[G2, G1, G4, G3]` covers all three.
- **H3 — FALSIFIED (as already suspected):** Venus-first breaks cusp 1.B
  (ref `[SUN, VEN]`). Tier `*`-flag-first with KP-order ties fits all 48.
- **New: R3 (node star-lord) FALSIFIED** by VEN (star-lord Mars).
- **New: T5 (longitude-ascending, the prior doc's guess) FALSIFIED** by 1.B
  and 5.A — KP_STELLAR_RECONCILIATION.md §4's "h11 class A wants
  longitude-ascending" is wrong; both "contradictory" tiers (5.A planet-table,
  11.A not) fall out of T1.
- The within-`*` tie-break (KP order vs house-ascending) cannot be
  distinguished by this chart's data (only tiers 1.B and 5.A contain two
  `*` planets; both orders agree there); KP order chosen as the existing
  codebase convention.

### Acceptance-test deviation: two stale assertions in `tests/test_kp_stellar_reference.py` (RESOLVED by parent — stronger than the remedy below)

**Parent applied a stronger fix**: both constants were deleted outright and
`_check_house_derived` now demands exact equality for every row and tier (no
set-comparison escape hatch remains). Kept for history, the deviation was:

Running the full suite after the fix:

```
venv/bin/python -m pytest --no-cov -q
```

gives **7 failures = the 5 pre-existing `test_precision.py` failures + 2
collateral**, both the *same single line*:

```
tests/test_kp_stellar_reference.py:454: AssertionError: set()
assert set() == {('11', 0), ('3', 2), ('8', 2)}
```

`_check_house_derived` asserts `order_only_seen == ABCD_ORDER_ONLY` — i.e.
that these 3 tier order mismatches **still exist**. Implementing any accepted
rule necessarily makes `order_only_seen` empty, so no fix can avoid this; every
other assertion in both tests passes (`SIGNIFIES_ORDER_ONLY` set-comparisons
pass trivially once rows match exactly). Per my task's file-scope rule I did
not modify that file. The remedy is a pure strengthening (2 constants →
empty, demands exact equality everywhere):

```python
#: §2.E star-flag order rule: all nine rows now match the reference exactly.
SIGNIFIES_ORDER_ONLY = set()
#: §2.E: all 48 A_B_C_D tiers now match the reference exactly.
ABCD_ORDER_ONLY = set()
```

(plus deleting the two stale comments and the module docstring bullet
naming the six ordering residuals).

### Commands run

```bash
export SE_EPHE_PATH="$HOME/.kpastro/ephe"
venv/bin/python diagnositics/signifies_probe.py                    # candidate tables
venv/bin/python -m pytest --no-cov -q                              # 5 baseline (+2 collateral after fix)
venv/bin/python -m pytest --no-cov -q tests/test_signifies_order.py # 3 passed
# pinned natal command (see TASK2 §2.E) -> /tmp/current.json
venv/bin/python diagnositics/jdiff.py kp_stellar_output.json /tmp/current.json
```

### Final counts

- jdiff: **36 → 18 differing leaves** (322 total; 286 → **304 exact**). All 18
  ordering leaves are gone; the remaining 18 are sunrise/sunset (2), dasha
  stamps (5), planet degrees (9), cusp 3/9 degrees (2) — other phases.
- `tests/test_signifies_order.py`: 3 passed (all 9 rows + all 48 tiers
  hard-coded exact).

### Files created / changed

- created `diagnositics/signifies_probe.py`
- created `diagnositics/findings_signifies.md`
- created `tests/test_signifies_order.py`
- modified `src/kpastro/chart.py` (`_signifies_ordered`, `_kp_sorted`,
  serializer `star_flag`, comment block updated)
- **not** modified by this phase: `tests/test_kp_stellar_reference.py` —
  since resolved by the parent (both constants deleted, exact equality
  everywhere)
