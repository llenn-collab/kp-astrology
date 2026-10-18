# TASK2: Close the remaining KP Stellar residuals in the reference-compatible output

Status: **open**. This file supersedes `TASK.md`. Most of `TASK.md` is already implemented in the code (see §1). What remains is numerical: the output is 286 of 322 reference leaves exact (88.8 %). This task is to close as much of the remaining 36 as the evidence supports, and to say plainly what cannot be closed.

Read `AGENTS.md` first. Its invariants still apply: milliarcsecond core, boundary policy, `kp_new` offset, geocentric house latitude, dasha year = 365.25 d, no dependency adds, no reformatting, and `python -m pytest` baseline failures.

## 0. Ground rules for this task

- **Never hard-code the reference.** No constant, shift, or table fitted to one chart may enter `src/`. Any correction must be a stated convention, justified from documentation or from a second independent reference.
- **Never weaken a test to make it pass.** Residuals stay visible as strict `xfail` tests with the measured value in the reason string.
- **Measure before deciding.** Every hypothesis gets a probe script result recorded in the report, including the ones that fail.
- **Time-box the hard parts.** Planetary longitudes are the most expensive residual and the least certain. A stop rule is set in §5.
- **Arrays are ordered data.** Do not sort or set-compare `signifies` or `signifies_A_B_C_D` to hide differences.
- **Sign convention for all deltas:** `ours − reference`, in arcseconds (″) or seconds (s). Positive means ours is ahead.

## 1. What is already done (verified 18 Oct 2026, against the current `HEAD`)

| `TASK.md` item | Current state | Evidence |
|---|---|---|
| 2. `cmd_horary` house frame | **Done.** `horary_lagna = kp_divisions()[n-1].start_deg` is passed to `compute_chart` in both `natal` and `horary`. Cusp 1 = Virgo 17°46′40″ | `cli.py`; `test_horary_division_117_cusp_start_is_1510_over_9` |
| 3. `horary_details` vs `birth_details` | **Done.** Serializer emits `horary_details` first; `birth_details` is absent | `test_horary.py:165-167`; `test_no_birth_details_key_in_strict_payload` |
| 4. Chart instant / coordinates | **Done.** UTC resolves to `2026-10-30 06:30:00`; full-precision lat/lon used | `test_chart_instant_resolves_to_2026_10_30_0630_utc` |
| 5. House-derived fields | **Mostly done.** All `planets[*].house`, cusp signs, cusp `sg/sl/sb/ss`, nodes match | diff run below |
| 6. Deterministic dasha | **Done.** `--query-utc` is honoured by `natal` and `horary` | `test_dasha_stack_is_deterministic_for_pinned_query_utc` |
| 1. `kpastro_actual2.md` as JSON | **Open.** The committed file is still the text report | `kpastro_actual2.md` in repo |

The pasted analysis in the task prompt (“Sookshma ends 13 days later”, “+9 to +10″ planets as the blocker”) was computed from `kpastro_actual3.json`, which is stale. With the pinned command the current code's sub-period error is **2 h 58 m 58 s at every level**, not 13 days. See §2.A.

## 2. Measured state and root-cause findings

### 2.0 Baseline

- Python 3.12.3, `pyswisseph 2.10.03`, `SE_EPHE_PATH=$HOME/.kpastro/ephe`.
- Ephemeris files present and `SwissEphemeris.precision == "full"`: `sepl_18.se1` 484,061 B, `semo_18.se1` 1,304,771 B, `seas_18.se1` 223,004 B (downloaded with `python -m kpastro download-ephemeris` in this session).
- Reference command in `TASK.md` runs with exit 0 and produces the reference schema. Output saved as `kpastro_actual2.json` in the outputs folder for reference (the committed `kpastro_actual2.md` is still the old text report).
- Recursive diff (`diagnostics/jdiff.py`): **322 reference leaves; 286 exact; 36 differ.**

| Group | Leaves | Residual | Status |
|---|---|---|---|
| `horary_details.sunrise` / `sunset` | 2 | +8 s / −7 s | Unexplained (§2.D) |
| `vimsottari_dasa.*.end` (5 levels) | 5 | constant +2 h 58 m 58 s (ref later) | Cause found (§2.A); reference-side conflict open |
| `planets.*.degree` (9 bodies) | 9 | Sun +9.2″, Mars +9.7″, Jup +9.6″, Sat +9.8″, Mer +9.8″, Ven +10.1″, Rahu/Ketu +9.5″, Moon +1.5″ | Not solved (§2.B) |
| `planets.*.signifies` order | 10 | rows SUN, MOO, VEN | Unexplained order (§2.E) |
| `cusps.3/9.degree` | 2 | +0.88″ | Unexplained (§2.C) |
| `cusps.3/8/11.signifies_A_B_C_D` order | 8 | ref `[VEN,RAH]`, ours `[RAH,VEN]`, etc. | Unexplained order (§2.E) |

Everything else matches exactly: all planet `sign`, `house`, `sg/sl/sb/ss`, `flags`; all 12 cusp `sign`, `name`, and 10 of 12 cusp degrees; `ruling_planets`; `nodes_representation`; `legend`; `horary_details` text fields (name, gender, date, time, horary_no, place, latitude, longitude, timezone, ayanamsa, node, nakshatra, tithi, yoga, karana, dasha_balance); every `sg/sl/sb/ss` in cusps.

### 2.A Dasha end stamps: cause found, one reference-side inconsistency left

**Confirmed.** The dasha stack is driven by the sidereal Moon longitude. A constant time shift on every level means the epoch (the Moon's position) differs; the durations are identical. Probing the Moon longitude (`diagnostics/residual_probe.py`, section 1):

- Unshifted: max stamp error **10,738 s**.
- Moon shifted by **−0.91″** (dasha-implied): max stamp error **31 s** (0.01″ grid).
- Moon shifted by −1.0″: 1,097 s. By −1.5″: 7,014 s.
- Sensitivity: **≈ 3.29 h per arcsecond of Moon longitude** for a Rahu mahadasha (18 y × 365.25 d / 48,000″).

So the “dasha drift” is not a dasha-algorithm bug. The proportional sub-period arithmetic already reproduces the reference when the Moon is right. The whole error is the Moon's sub-arcsecond difference.

**Reference-side consistency depends on the display rounding rule (corrected in the second pass).**
The earlier draft of this file called the reference internally inconsistent. That was an artefact of assuming half-up rounding of the printed arcseconds.

- Under **half-up** rounding the printed Moon `08°31'49″` requires a shift of (−2.03″, −1.03″] from ours (ours = 30710.531″). The dasha needs −0.91″. The windows do not overlap.
- Under **truncation** the printed Moon requires (−1.53″, −0.53″], which **contains** −0.91″. No conflict.
- Evidence on the rule is mixed: truncation explains cusps 3/9 (exact 10.883″, printed 10″) but not cusps 2/8 or 6/12 (exact 71.916″, 53.995″, printed 72″, 54″); half-up explains those but not 3/9. A scan of the ayanamsa offset (K = 49.0 … 50.7″) under both rules never gets past 10 of 12 cusps, so the cusps cannot settle it. The printed ayanamsa 24°08'28″ (ours 27.79″) favours half-up unless the reference value is ≥ 28.0″.
- Moon time-base probe (`dt` seconds applied to the Moon only): the dasha needs **−1.66 s**; the printed Moon is satisfied by −2 s and −3 s under half-up, and by −1 s … −2 s under truncation. So under truncation a single Moon time/position shift reproduces both. Treat the rounding rule as **unresolved**.

Stop rule for §2.A: if the rounding rule cannot be settled from a second KP Stellar printout, leave the dasha test as `xfail(strict=True)` with the 10,738 s / 31 s numbers in the reason, and do **not** add a Moon offset to `src/`.

### 2.B Planet longitudes: not solved; say so and move on

Seven planets carry an offset of ≈ +9.2″ to +10.1″ and Moon +1.5″ (ours − reference, `residual_probe.py` section 2):

| Variant | SUN | MOO | MAR | JUP | SAT | MER | VEN |
|---|---|---|---|---|---|---|---|
| apparent (ours) | +9.22 | +1.53 | +9.68 | +9.57 | +9.76 | +9.84 | +10.13 |
| NONUT (no nutation in longitude) | +1.18 | −6.51 | +1.64 | +1.53 | +1.72 | +1.80 | +2.09 |
| MOSEPH apparent | +9.24 | +1.59 | +9.70 | +9.74 | +9.70 | +9.87 | +10.17 |
| TRUEPOS | +29.85 | +2.27 | +24.99 | +23.98 | −1.73 | −2.95 | +7.01 |

Findings:

- **Ephemeris precision is not the cause.** Moshier and full Swiss files agree to ≈0.1″ for every body. The `download-ephemeris` step was worth doing, but it does not close the residual.
- **Nutation in longitude is the leading hypothesis for the seven non-Moon planets.** Δψ at this epoch is ≈ 8.04″. Removing it brings those planets to +1.2″ to +2.1″. It does **not** fit the Moon (−6.5″), and the house cusps, which use the same ayanamsa path, already match exactly. So “drop nutation for planets” is not a consistent model.
- **Light-time and aberration variants are worse.** TRUEPOS moves Sun and Mars by ≈ +25–30″.
- **The `kp_new` zero-point offset (50.7″) was calibrated at one epoch** (2024-12-18, per `ephemeris.py`). Any convention difference of the nutation kind can be partly absorbed into that calibration, so one more epoch is needed to separate them.
- **Only one reference epoch exists in this repo.** `AGENTS.md` mentions `temp_kp.json`, `temp_kp_test2.json`, `temp_kp_test3.json` and `temp_final.md`, but **none of them are in the checked-out repository**. They would give a second epoch.

**Decision requested:** planetary-longitude work is **not guaranteed** to succeed with the data available. Time-box it to one experiment (§3 Phase 6). If no single documented convention brings all nine bodies within 2″ of the reference, and no second-epoch reference is supplied, document the residual as: planets ≈ +10″, Moon ≈ +1.5″, convention unknown, and move on. Do not apply a blanket longitude correction.

### 2.C Cusps 3 and 9

Exact values (`residual_probe.py` section 4): cusp 3 = 62410.883″ into the sign; reference displays `17°20'10″`, so the reference is ≈0.88″ lower. Cusp 9 is identical by construction. Every other cusp is within 0.29″ and displays correctly under half-up rounding.

Cusps 3 and 9 are the only cusps off, and they are an opposite pair from the same Placidus solve. Candidate causes: the reference's Placidus iteration tolerance, or its handling of the intermediate-house trisection near the Asc–MC geometry. Probe `swe.houses_ex` with its own tolerance settings if available, but **do not fit a solver to this one sample**. Accept the residual unless a principled change degrades no other cusp in a second chart.

### 2.D Sunrise and sunset

Reference day length 11:22:34; ours 11:22:19 (**+15 s**). `residual_probe.py` section 3 tests the standard Swiss conventions:

| Convention | Rise | Set |
|---|---|---|
| disc + no refraction (ours) | 06:36:56 | 17:59:15 |
| disc + refraction | 06:34:16 | 18:01:55 |
| upper limb + refraction | 06:33:06 | 18:03:05 |
| upper limb + no refraction | 06:35:46 | 18:00:25 |
| **reference** | **06:36:48** | **17:59:22** |

None of the standard conventions reproduces the reference. The residual corresponds to a horizon about 0.03° below the disc-centre horizon, which is not a standard constant. Low severity. Keep the current convention. Tighten the existing “within a minute” test to an explicit `xfail` that records +8 s / −7 s.

### 2.E Signifies ordering

Confirmed: `cusps` and `planets` arrays contain the same members as the reference but in a different order. Ordering is the only difference in these 18 leaves.

- Planets: `chart.py::_signifies_ordered` emits groups in the order *star-lord's house, own house, houses owned by star-lord, houses owned by planet* (deduplicated). This reproduces **6 of 9** reference rows (MAR, RAH, JUP, SAT, MER, KET). SUN, MOO and VEN do not. Example, MOO: reference `["9","5","11"]` (own house first), ours `["5","9","11"]`. VEN: reference `["1","11","2","9","3","8"]`, ours `["11","1","3","8","2","9"]`.
- Cusp tiers: cusp 3 and cusp 8 tier C: reference `["VEN","RAH"]`, ours `["RAH","VEN"]`. Cusp 11 tier A: reference `["VEN","RAH","MER","KET"]`, ours `["RAH","MER","KET","VEN"]`.
- **No single group order explains all 9 planet rows.** The existing comment in `chart.py` says the remaining rows are “not a function of anything in the chart”. That is a hypothesis, not a proof.

Rule for this sub-task: a candidate ordering rule is accepted only if it (a) is stated before it is tested, (b) reproduces all 9 planet rows and all 3 cusp tiers, and (c) does not change any currently-correct row. Anything that only fits the reference by construction is rejected. If no rule passes, keep the current order and report the 10 + 8 leaves as known ordering residuals.

## 3. Work plan

Each phase has an owner (skill or sub-agent) and an exit condition. Phases 3–6 have strict time-boxes.

**Phase 0 — Baseline (≈15 min).** Re-run §2.0 commands. Record versions, file sizes, precision, `pytest --no-cov` results (expect the 5 pre-existing failures in `test_precision.py`, none in `test_kp_stellar_reference.py` or `test_horary.py`). Copy `diagnostics/` into the repo under `tools/diagnostics/`, or keep them outside `src/`. Owner: `engineering:debug` (structured reproduce → isolate).

**Phase 1 — Strict tests first (test-first; ≈1 h).** Owner: `tdd-workflow` skill.
- Add `tests/test_kp_stellar_strict.py`: recursive, type-aware comparison of the pinned command's JSON against `kp_stellar_output.json`. Each differing path is a separate parametrised case with the measured residual in its message.
- Convert each currently tolerance-based assertion in `test_kp_stellar_reference.py` (planet ≤15″, dasha ≤ a few hours, sunrise ≤ a minute) to an exact assertion marked `xfail(strict=True, reason="<measured residual>")`. A strict xfail flips to a failure the moment the residual is fixed, which forces the test to be updated.
- Keep all currently passing exact checks (schema, instant, division 117, cusp 1, ruling planets, flags, nodes) as-is.

**Phase 2 — Deliverable file (≈15 min).** Generate `kpastro_actual2.md` as **plain JSON** from the CLI serializer (not by hand). Validate with `python -m json.tool kpastro_actual2.md`. Create `kpastro_actual2.json` as an identical copy. Confirm stdout contains only JSON; diagnostics go to stderr. Do not touch the old text report except by replacing it. Owner: `verification-loop`.

**Phase 3 — Dasha / Moon (time-boxed 2 h).** Owner: `engineering:debug` with `documentation-lookup` for Swiss Ephemeris time-base and light-time flags.
- Run candidates 1–3 from §2.A. Record a table: candidate, Moon shift needed, dasha max error, printed-Moon consistency.
- Exit: either a principled convention reproduces the printed Moon **and** all five stamps within a few seconds, or the stop rule in §2.A applies.
- Do not add a Moon offset to `src/`.

**Phase 4 — Cusps 3 and 9 (time-boxed 1 h).** Owner: `engineering:debug`. Probe solver tolerance and Placidus variants. Exit: accept the 0.88″ residual with a `xfail` record, or a principled change that also keeps the other 10 cusps exact on a second chart.

**Phase 5 — Sunrise / sunset (time-boxed 30 min).** Owner: `engineering:debug`. Re-run `residual_probe.py` section 3. Exit: record the residual. No further work unless a standard convention matches.

**Phase 6 — Planetary longitudes (time-boxed 2 h, then stop).** Owner: `engineering:debug` + `documentation-lookup`.
- One bounded experiment: the nutation-in-ayanamsa convention (`get_ayanamsa_ex_ut` with the true-of-date flag, applied to planets only; house path unchanged). Measure all nine bodies.
- Exit (required): if no single documented convention puts all nine bodies within 2″ **and** no second-epoch reference exists, write “planets ≈+10″ / Moon ≈+1.5″, convention unknown” and proceed to Phase 7.
- Do not change the house path, the `kp_new` offset, or the ephemeris file set in this phase.

**Phase 7 — Signifies ordering (time-boxed 2 h).** Owner: `change-impact` (map `chart.py::_signifies_ordered` and `significators.py` callers first) and `tdd-workflow` for the candidate rules.
- Write the candidate rules down before testing (§2.E rule).
- Exit: one rule that passes all 9 planet rows + 3 cusp tiers without breaking the 6 current matches, or a documented failure with the candidates tried.

**Phase 8 — Verification (≈30 min).** Owner: `verification-loop`.
- `python -m pytest --no-cov` (baseline = 5 pre-existing `test_precision.py` failures; anything else is a regression).
- Regenerate `kpastro_actual2.md` and run the recursive diff. Save the raw diff output to `KP_STELLAR_DIFF.md`, replacing the old file's content with the new numbers.
- Record exact-leaf count / total.

**Phase 9 — Review (≈30 min).** Owner: `python-reviewer` (numerics, datetime/timezone, serializer types and order, unintended API change) then `code-reviewer` once. Inspect every reported difference against raw artifacts, not against any compressed summary.

**Phase 10 — Documentation (≈30 min).** Owner: `engineering:documentation`.
- Update `KP_STELLAR_RECONCILIATION.md` with the §2 findings (it currently describes 199/223 and the pre-fix state).
- Update `AGENTS.md`: the dasha–Moon sensitivity (3.29 h/″), the nutation hypothesis, and the missing `temp_*.json` references.
- Archive `TASK.md` as `TASK-archive.md`; it is obsolete.

## 4. Skills and sub-agents

Names follow `TASK.md`'s ECC section. This session did not verify that those skill paths are installed; confirm with the installed ECC release before relying on them. Equivalent skills available in this environment are noted.

| Role | Tool | Used in |
|---|---|---|
| Structured debugging (reproduce, isolate, diagnose) | `engineering:debug` (or ECC `debug` workflow) | Phases 0, 3–5, 6 |
| Test-first for strict xfail tests and candidate rules | `tdd-workflow` | Phases 1, 7 |
| Verification after each change, final suite and diff | `verification-loop` | Phases 2, 8 |
| Impact map for serializer, cusp-derived houses, significators | `change-impact` | Phase 7 (and before any change to `cmd_horary`/`chart.py`) |
| Swiss Ephemeris / pyswisseph API confirmation | `documentation-lookup` (+ `context7` only if needed) | Phases 3, 6 |
| Numerics and API review | `python-reviewer` agent | Phase 9 |
| Final correctness review | `code-reviewer` agent | Phase 9 |
| Build/import failures only | `build-error-resolver` (conditional) | Only if a new import or packaging error appears |
| Documentation updates | `engineering:documentation` | Phase 10 |

MCPs: `codebase-memory-mcp` for call-graph navigation only (the graph can be stale); `context-mode` for large diffs, with all comparison values written to files rather than summarised. Keep `headroom` **off** when `context-mode` is on. `playwright` and `skillspector` are off; no browser and no new third-party skill are needed.

## 5. Stop rules (summary)

| Item | Stop when |
|---|---|
| Dasha / Moon (§2.A) | Phase 3 time-box ends, or no candidate reproduces printed Moon and stamps together |
| Planets (§2.B) | Phase 6 time-box ends with no convention bringing all nine within 2″, and no second-epoch reference |
| Cusps 3/9 (§2.C) | Phase 4 time-box ends without a principled change that keeps the other ten cusps exact |
| Sunrise (§2.D) | Phase 5 time-box ends (no standard convention matches) |
| Signifies order (§2.E) | Phase 7 time-box ends with no rule passing the stated acceptance test |

Hitting a stop rule is a successful outcome if the residual is recorded with units, measured delta, evidence and the best justified alternative.

## 6. Acceptance criteria

- [ ] `kpastro_actual2.md` is valid plain JSON (`python -m json.tool` passes); `kpastro_actual2.json` is identical.
- [ ] Strict recursive test exists; every one of the 36 current differing leaves has an explicit `xfail(strict=True)` with its measured value, or is fixed.
- [ ] No fitted or hard-coded value for this chart entered `src/`.
- [ ] Dasha: either reproduced by a documented convention, or recorded as reference-internal inconsistency with the §2.A numbers.
- [ ] Planets: either reproduced by a documented convention for all nine bodies, or recorded as “convention unknown” with the §2.B table.
- [ ] Cusps 3/9, sunrise/sunset: residuals recorded with measured values; no unprincipled fit.
- [ ] Signifies order: either a pre-stated rule passes all acceptance cases, or ordering residuals are recorded with the candidates tried.
- [ ] `python -m pytest --no-cov` has no new failures beyond the 5 documented pre-existing ones in `test_precision.py`.
- [ ] Final report lists: files changed, commands run, test results, exact-leaf count (current: 286/322), each remaining residual with units and evidence, and which facts are confirmed versus hypotheses.

## 7. What is needed from the owner

1. **A second KP Stellar reference** (any date/place, with the same printout schema). Without it, no planetary or ayanamsa convention can be confirmed. Upload the `temp_kp*.json` files that `AGENTS.md` mentions, or a new export.
2. Confirmation that `kp_stellar_output.json` was generated with the same KP Stellar version and the same “KP New” ayanamsa setting as the second reference.
3. Decision on whether `TASK.md` should be archived (recommended).

## Appendix: reproduce the numbers in this document

```bash
export SE_EPHE_PATH="$HOME/.kpastro/ephe"
python3 -m kpastro.cli natal --date 2026-10-30 --time 12:00:00 --tz 5.5 \
  --lat 18.4593067 --lon 73.8654709 --place "Pune, India" --ayanamsa kp_new \
  --node mean --json --name KPstellaroutput --gender Male --horary-no 117 \
  --timezone Asia/Kolkata --query-utc "2026-10-18 12:00:00" > /tmp/current.json
python3 diagnostics/jdiff.py kp_stellar_output.json /tmp/current.json
python3 diagnostics/residual_probe.py
```

Expected: 36 differences, 286/322 exact leaves; probe section 1 reports best Moon shift −0.91″ with max error 31 s; section 2 reproduces the planet table above; section 3 reproduces the sunrise table above.


## 8. Second-pass findings (added after TASK.md was confirmed executed)

Measured with the full ephemeris. All deltas are ours − reference.

**8.1 The engine mixes apparent longitudes with a mean ayanamsa.** `swe.get_ayanamsa_ut` returns the mean ayanamsa; `swe.get_ayanamsa_ex_ut` (default flags) includes nutation in longitude, **+8.042″ at 2026-10-30 06:30 UT** (−0.558″ at the 2024-12-18 calibration epoch). Swiss Ephemeris's own sidereal path (`FLG_SIDEREAL`) subtracts the nutation-including value, so every body comes out exactly **8.042″ lower** than kpastro's. `ephemeris.py` uses the mean one.

**8.2 Effect on the reference.** With nutation removed, the seven non-Moon planets drop from +9.2…+10.1″ to +1.2…+2.1″ (Sun +1.18, Mars +1.64, Jupiter +1.53, Saturn +1.72, Mercury +1.80, Venus +2.09, Rahu +1.44). A common remainder of ≈ +1.1″ would then explain all seven under truncation windows. This is a real convention difference, but it is **not sufficient** to match any printed digit, and it moves the **Moon the wrong way** (+1.5″ → −6.5″, while the dasha says the reference Moon is ours −0.91″).

**8.3 Two hypotheses fit the one chart equally; they cannot be separated yet.**
- (A) Nutation-free sidereal positions for every body, `kp_new` offset ≈ 49.66″ (instead of 50.7″), chart evaluated ≈ 13.5 s later than 12:00:00 IST. All eight bodies fall inside truncation windows. The 13.5 s is, in effect, a free parameter fixed by the Moon, so the fit is not independent evidence.
- (B) Nutation-free planets but an apparent (nutated) Moon, as if planets and Moon came from different engines.
They predict different outputs on any other chart. Do **not** implement either as a default.

**8.4 Calibration-epoch cross-check.** Requiring the displayed ayanamsa to hold at both epochs under whole-second truncation gives an offset window K ∈ (49.665, 50.491]″. Hypothesis (A)'s K ≈ 49.66″ sits on its lower edge. Consistent, not confirmatory.

**8.5 The "second epoch" files are not independent.** `temp_kp.json`, `temp_kp_test2.json`, `temp_final.md` exist on branches `qwen` and `error-free-astrology-repo-upgrades-5d780` (not on `main`). They use kpastro's own long-form schema (`ayanamsa_mode`, `vimsottari_dasha.levels`), so their planet degrees are kpastro output. The only KP Stellar-sourced datum in them is the calibration ayanamsa `24°06'54.0"`. A real second KP Stellar printout is still required.

**8.6 What would close this.** One further KP Stellar printout (any date, same schema) lets us test: (i) truncation vs half-up on ≥ 20 printed angles, (ii) planets vs Moon nutation treatment, (iii) whether a ≈ 13 s time offset recurs. If (A) holds, three changes follow: true-ayanamsa positions, a recalibrated `kp_new` offset, and the time offset's origin identified. If (B), only the planet path changes.

**8.7 Cusps 3/9 are unaffected.** No tested combination of ayanamsa mode (mean/true), offset (49.0–50.7″) or display rule reaches more than 10 of 12 cusps. The residual stays at ≈ 0.88″.
