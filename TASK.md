# TASK: Reconcile `kpastro` horary output with `kp_stellar_output.json`

## Objective

Inspect and fix the repository so the KP horary chart for **30 October 2026 at 12:00:00 IST**, Pune, India, **KP horary number 117 of 249**, reproduces the committed `kp_stellar_output.json` as closely as the underlying computation can legitimately support. The output must be machine-readable JSON and should preserve the reference's schema, field types, ordering conventions, values, and precision. Do not treat a visually similar text table as a successful result.

Work in the existing project and follow `AGENTS.md`. Investigate before changing code. Do not change unrelated behaviour, remove reference assets, hard-code a single chart's answer, or declare exact parity without an automated comparison.

## Canonical input conditions

Use these exact chart inputs throughout the investigation and regression tests:

- Local chart date: `2026-10-30`
- Local chart time: `12:00:00`
- Timezone offset: `+5.5` hours; IANA label: `Asia/Kolkata`
- Equivalent chart instant: `2026-10-30 06:30:00 UTC`
- Latitude: `18.4593067` (north)
- Longitude: `73.8654709` (east-positive)
- Place: `Pune, India`
- KP ayanamsa: `kp_new`
- Node: `mean`
- Horary number: `117` of `249`
- Reference subject metadata: name `KPstellaroutput`, gender `Male`
- Ephemeris directory: `$HOME/.kpastro/ephe`, selected by `SE_EPHE_PATH`; confirm the three required files exist and that `SwissEphemeris.precision == "full"` before evaluating sub-arcsecond residuals.

### Important: chart time and dasha query time are separate

The reference artifact's chart data is for 30 October 2026 at 12:00 IST, but its five `vimsottari_dasa` end stamps correspond to the pinned dasha-evaluation instant `2026-10-18 12:00:00 UTC` used in `KP_STELLAR_RECONCILIATION.md` and `tests/test_kp_stellar_reference.py`. Preserve that distinct `query_utc` when reproducing this **specific reference file**. Do not silently substitute the chart instant for `query_utc`, and do not represent the 18 October dasha evaluation as the chart timestamp. If behaviour for a real-time dasha stack is also tested, make it a separate test case.

## Confirmed problems to investigate and fix

### 1. Current `kpastro_actual2.md` is the wrong output path and format

The committed `kpastro_actual2.md` is a text report headed `KRISHNAMURTI PADDHATI - horary (Prashna)`. It contains a midpoint-based horary summary followed by a normal “Moment chart” text table. It is not the KP Stellar JSON schema and is not suitable for raw-field equality comparison. Produce output with the JSON serializer and validate it with Python's JSON parser. Because the requested target filename is `kpastro_actual2.md`, the requested file should contain **plain JSON text only** (no Markdown heading, prose, or fenced code block); also write an identical `kpastro_actual2.json` copy if useful for tooling. Do not silently keep Markdown output under a JSON requirement.

### 2. `cmd_horary` does not build the KP Stellar house frame

Inspect `src/kpastro/cli.py::cmd_horary`. It calls `ascendant_from_kp_number(args.number)` and prints that result, but calls `compute_chart(...)` without `horary_lagna`. Consequently the planet houses, cusps, and house-derived significators in its “Moment chart” use the astronomical Ascendant at the query instant rather than the horary cusp. The text output in `kpastro_actual2.md` shows an astronomical Ascendant around Sagittarius 26°29′, while the reference's first cusp is Virgo 17°46′40″.

The reference first cusp is the **start/cusp of division 117**, not its midpoint:

- Division 117 span: approximately `167°46′40″` to `169°40′00″`.
- `ascendant_from_kp_number(117)` returns the midpoint, approximately `168°43′20″`.
- Reference `cusps["1"].degree` plus sign is Virgo `17°46′40″`, i.e. the division's `start_deg` (`1510/9` degrees exactly).

For the reference-compatible chart, pass `kp_divisions()[116].start_deg` as `horary_lagna` so `compute_chart` calculates the cusps for the horary house frame. The astronomical Ascendant, MC, ruling planets, panchanga, and planetary coordinates must remain tied to the requested chart instant, as described in `AGENTS.md` and `KP_STELLAR_RECONCILIATION.md`.

Preferred route: make the JSON-capable chart path correct and deterministic, equivalent to `natal --horary-no 117 --json` with the explicit inputs below. If the `horary` subcommand is intended to be the user's primary horary interface, bring it into line with the same house-frame and JSON semantics rather than maintaining two contradictory implementations. Preserve and document the public midpoint API if the existing contract requires it; do not confuse the midpoint returned by `ascendant_from_kp_number` with KP Stellar's cusp-start convention.

### 3. The reference JSON schema disagrees with the code and tests

Inspect the actual current contents of `kp_stellar_output.json`, not just comments in documentation. The committed reference uses a top-level `horary_details` section. Current `chart_to_kp_stellar_json` in `src/kpastro/chart.py` emits `birth_details`, and `tests/test_kp_stellar_reference.py` also directly indexes `reference["birth_details"]`. `AGENTS.md` / `KP_STELLAR_RECONCILIATION.md` describe the older `birth_details` naming.

Resolve this as a real repository inconsistency:

1. Establish the expected schema from the current committed reference and, if necessary, inspect Git history to determine whether the reference was intentionally updated or accidentally replaced.
2. Do not mutate the reference artifact merely to make the existing tests pass.
3. Align the serializer and regression tests to the verified canonical reference schema. If backward compatibility for `birth_details` is needed, make that explicit and test it; do not emit both keys into the strict-reference payload unless the reference itself does.
4. Match top-level keys, nested keys, insertion order where emitted, nulls, arrays, string formatting, abbreviations, and numeric/string types. Do not silently rename `horary_details` back to `birth_details`.

### 4. Make every calculation use the intended timestamp and location

Verify local-to-UTC conversion, full-precision coordinate propagation, sidereal mode, node mode, and ephemeris selection end to end. Avoid prematurely rounding latitude/longitude to the four decimal places shown in `kpastro_actual2.md`. `BirthInfo.utc_datetime()` for the chart must resolve to `2026-10-30 06:30:00 UTC`. The horary house frame must use the exact supplied coordinates and configured KP New ayanamsa. Record the effective ephemeris precision in test/debug diagnostics without adding non-reference keys to the strict JSON output.

### 5. Reconcile all house-derived fields after fixing the cusp frame

The house-frame difference propagates beyond the `cusps` block. Recompute and check all dependent fields using the selected horary cusps:

- `planets[*].house`
- `cusps[*]` degrees, signs, and lord chains (`sg`, `sl`, `sb`, `ss`)
- `planets[*].signifies`
- `cusps[*].signifies_A_B_C_D`
- `nodes_representation`

Never patch only the printed first cusp or planet-house labels. All dependent data must be computed from the same `Chart` object and the same cusp list. Keep `ruling_planets.lagna` tied to the astronomical Ascendant, as in the reference; it is intentionally not the horary cusp 1.

### 6. Make dasha evaluation deterministic

The reference's dasha stack must be reproducible with the explicit `query_utc` stated above. Current `cmd_horary` forcibly sets `query_time = birth.utc_datetime()`, so it cannot produce the same dasha stack as a reference resolved on 18 October. Use the supported `--query-utc` option on the reference-compatible CLI path, or refactor the shared chart/serialization path so both interfaces can accept that explicit instant. Do not use the machine clock in a reference regression test.

## Starting command for the reference-compatible JSON path

Use this as the starting point once the serializer and horary-cusp path are fixed:

```bash
SE_EPHE_PATH="$HOME/.kpastro/ephe" python -m kpastro.cli natal \
  --date 2026-10-30 \
  --time 12:00:00 \
  --tz 5.5 \
  --lat 18.4593067 \
  --lon 73.8654709 \
  --place "Pune, India" \
  --ayanamsa kp_new \
  --node mean \
  --json \
  --name KPstellaroutput \
  --gender Male \
  --horary-no 117 \
  --timezone Asia/Kolkata \
  --query-utc "2026-10-18 12:00:00" \
  > kpastro_actual2.md
```

The command alone is **not** sufficient until the serializer's section naming and the calculation discrepancies below are resolved. At completion, `kpastro_actual2.md` must parse as JSON despite its `.md` suffix; create `kpastro_actual2.json` as an identical convenience copy if practical. Ensure stdout contains JSON only (diagnostics belong on stderr).

## Accuracy investigation: do not stop at formatting

`KP_STELLAR_RECONCILIATION.md` records an earlier reconciliation for a correctly constructed horary chart: 199 of 223 comparable leaves matched, while the remaining differences were categorised as follows. Reproduce these results against the **current** reference before assuming they still apply, because the current reference's details-section key conflicts with that document.

- Planet degrees: all nine were reported to differ from the reference by approximately `+1.5″` to `+10.1″` (kpastro minus reference). Investigate whether the difference comes from ephemeris files/precision, Swiss Ephemeris flags and calculation mode, time conversion, ayanamsa handling, or a genuinely different planetary-series implementation in KP Stellar. Do not apply a blanket longitude correction without evidence.
- Dasha end stamps: all five were reported offset by a constant `+2 h 58 m 58 s` with matching period durations. Verify the epoch and Moon longitude inputs before deciding whether the residual is a computational discrepancy or inherited reference-engine behaviour.
- Sunrise/sunset: reported residuals were approximately `+8 s` and `−7 s`. Verify the event flags, date window, location, and time-zone conversion.
- Cusps 3 and 9: reported one-arcsecond display differences; the other ten cusps were reportedly within 0.3″. Inspect Placidus solving precision and rounding. Do not fit a solver to a single sample without showing that the change is principled and does not degrade other cusps or charts.
- Ordering: reconciliation notes list exceptions in `planets[*].signifies` and `cusps[*].signifies_A_B_C_D`. Arrays are ordered data for strict reference comparison; do not sort or compare as sets merely to hide differences. Establish the reference's actual ordering rules and reproduce them consistently.
- Other header values: verify ayanamsa display/rounding, sunrise/sunset, nakshatra/pada, tithi, yoga, karana, dasha balance, flags, nodes, and all schema details against current `kp_stellar_output.json`.

Distinguish confirmed facts from hypotheses in the final report. Do not claim full parity while any output leaf differs. If exact reproduction of a value is blocked by KP Stellar using a different undocumented or proprietary calculation, state that residual clearly with units, measured delta, evidence, and the best technically justified alternative. Do not fake precision or hard-code expected values for this one chart merely to pass the reference test.

## Required implementation workflow

1. Read `AGENTS.md`, `KP_STELLAR_RECONCILIATION.md`, `src/kpastro/cli.py`, `src/kpastro/chart.py`, `src/kpastro/horary.py`, `src/kpastro/ephemeris.py`, `src/kpastro/panchanga.py`, `src/kpastro/significators.py`, and all files under `tests/` before editing.
2. Parse both `kp_stellar_output.json` and the existing `kpastro_actual2.md`. Record exact schemas and relevant output differences. The Markdown file is a rendered text report, so explain its structural differences instead of attempting a naive JSON parser on it.
3. Capture a baseline with full ephemeris data; record Python version, `pyswisseph` version, file presence/sizes, precision mode, and test results.
4. Add/fix regression tests before changing calculation logic. Include at least: schema exactness, chart UTC conversion, horary division 117 cusp-start, cusp 1 equals `1510/9` degrees, astronomical Ascendant remains separate, each dependent house-derived field, and deterministic dasha `query_utc`.
5. Implement the smallest justified changes. Avoid unrelated refactoring and do not alter integer/Fraction boundary invariants in `arithmetic.py` unless an independently reproduced calculation defect proves that change necessary.
6. Generate JSON through the same serializer used by the CLI. Validate with `python -m json.tool kpastro_actual2.md` and compare parsed structures against the reference.
7. Write a field-by-field comparison report to a separate diagnostic file (for example `KP_STELLAR_DIFF.md`); do not add diagnostic keys to the reference-compatible JSON. Report missing/extra paths, type mismatches, exact mismatches, numeric deltas with units, and array-order differences.
8. Run focused tests and then the repository suite. `AGENTS.md` documents known pre-existing test/coverage failures; establish the actual baseline and separate unrelated pre-existing failures from regressions. Do not weaken tests or change unrelated calculation code to bypass the existing baseline.
9. Re-run the reference comparison after all fixes and report the final exact-leaf count, total comparable leaves, remaining differences, and why each remaining difference exists. Be honest about unresolved discrepancies.

## Acceptance criteria

- [ ] Inputs are passed exactly as specified; chart instant resolves to `2026-10-30 06:30:00 UTC`.
- [ ] KP horary number 117 uses division 117's **start/cusp** for house 1 (`1510/9°` = Virgo `17°46′40″`), not its midpoint.
- [ ] Planets/ruling planets remain on the specified chart instant; horary house cusps and all dependent fields use the horary house frame.
- [ ] Dasha levels use the pinned `2026-10-18 12:00:00 UTC` instant when matching this exact reference file.
- [ ] The reference schema and serializer agree. Resolve the `horary_details` versus `birth_details` mismatch using the current reference as evidence; tests must not assume an obsolete schema.
- [ ] `kpastro_actual2.md` contains valid plain JSON only, with no Markdown or text-table wrapper. An identical `kpastro_actual2.json` may also be emitted.
- [ ] JSON keys/sections, values, types, lord symbols, flags, and ordered arrays match the current `kp_stellar_output.json` wherever the underlying engine can reproduce them. Every residual is quantified and explained; none is silently ignored.
- [ ] Automated, repeatable tests compare parsed JSON recursively to the reference and provide useful per-path diffs. No machine-clock dependency, rounded-input substitution, or hard-coded chart result.
- [ ] Full-precision ephemeris availability is verified; test results and residuals state whether full ephemeris or Moshier fallback was used.
- [ ] The final report lists files changed, commands run, tests and their results, exact-match rate, all remaining diffs, and any genuinely irreducible limitations.

## Primary repository files

- `kp_stellar_output.json` — canonical reference artifact
- `kpastro_actual2.md` — current incorrect text-rendered output; requested JSON destination
- `KP_STELLAR_RECONCILIATION.md` — previous reconciliation; revalidate against the current reference
- `AGENTS.md` — project invariants and testing notes
- `src/kpastro/cli.py` — CLI paths and timestamp handling
- `src/kpastro/chart.py` — chart calculation, JSON schema and serialization
- `src/kpastro/horary.py` — 249 divisions and horary cusp solving
- `src/kpastro/ephemeris.py` — Swiss Ephemeris precision, ayanamsa, coordinates and Placidus houses
- `src/kpastro/panchanga.py` — sunrise/sunset and panchanga values
- `src/kpastro/significators.py` — house and planet significators
- `tests/test_kp_stellar_reference.py`, `tests/test_horary.py`, `tests/test_precision.py` — regression coverage

## OpenCode execution setup: exact ECC skills, agents, and MCPs

This task is a **Python numerical-reconciliation/debugging task**, not a browser UI or end-to-end web-app task. Prefer a small, targeted set of workflows and tools. Treat this section as setup guidance; the implementation must remain runnable with ordinary OpenCode file, shell, and test tools if any optional integration is unavailable.

### ECC / agent skills to enable or invoke

Use the currently installed ECC version's OpenCode-compatible files. Do not assume a skill or slash command exists just because it appears in another agent's configuration. OpenCode supports skills in `.agents/skills/<skill-name>/SKILL.md` and also has its own skill/agent configuration conventions; check the actual installed paths first.

**Keep these active for this task:**

1. **`tdd-workflow` skill** — ECC path: `.agents/skills/tdd-workflow/SKILL.md`. Use test-first to create minimal failing tests for the cusp-start convention, strict schema, and deterministic dasha evaluation before editing implementation code.
2. **`verification-loop` skill** — ECC path: `.agents/skills/verification-loop/SKILL.md`. Use after each meaningful change and before finishing. Run focused tests, JSON parsing, recursive reference diff, and the final suite; report exact commands and outcomes.
3. **`change-impact` skill** — ECC path: `.agents/skills/change-impact/SKILL.md`. Use to map the effects of changing `cmd_horary`, chart construction, serializers, cusp-derived house assignments, and significators. Keep the change narrow.
4. **`python-reviewer` agent** — ECC agent name/path: `agents/python-reviewer.md` (or the equivalent OpenCode adapter such as `.opencode/prompts/agents/python-reviewer.txt`, depending on the installed ECC release). Ask it to review numerical correctness, datetime/timezone handling, serializer types/order, regression tests, and unintended API changes.
5. **`code-reviewer` agent** — ECC agent name/path: `agents/code-reviewer.md` (or the installed OpenCode adapter). Run once after implementation, focusing on correctness and unintended changes, not generic style-only suggestions.

**Use conditionally, only when needed:**

- **`documentation-lookup` skill** (`.agents/skills/documentation-lookup/SKILL.md`) when confirming the installed `pyswisseph` / Swiss Ephemeris API, house calculation behaviour, ephemeris flags, or sunrise/sunset conventions against primary documentation.
- **`build-error-resolver` agent** (`agents/build-error-resolver.md` or OpenCode adapter) only if the test/runtime environment produces new import, packaging, or test failures. Do not ask it to “fix” the pre-existing test failures documented in `AGENTS.md` by changing unrelated math.
- **`tdd-guide` agent** (`agents/tdd-guide.md` or OpenCode adapter) is an alternative orchestration agent for `tdd-workflow`; do not run two overlapping TDD agents on the same change.

Do **not** enable a broad collection of unrelated ECC skills for this task. In particular, frontend, React, design, E2E/browser, database, deployment, marketing, and multi-agent orchestration workflows do not apply. The task does not need Playwright or a browser.

### MCPs to keep enabled during implementation

| MCP | Decision | Exact reason / constraint |
| --- | --- | --- |
| `codebase-memory-mcp` | **ON, if its index is available** | Useful for call-graph, symbol, impact, and dependency discovery across `cli.py`, `chart.py`, `horary.py`, `ephemeris.py`, and significator logic. Treat results as navigation hints only: the checked-out source and tests are authoritative because a generated graph can be stale. |
| `context-mode` | **ON, preferred context helper** | Helpful when inspecting large files, test output, or recursive diffs. Use its search/retrieval to locate evidence, but ensure all comparison-critical values are retained exactly in files/reports or retrieved raw; never accept a compressed summary as evidence of JSON equality. |
| `context7` | **ON only when API documentation is needed; otherwise OFF** | Fetch current primary documentation for Swiss Ephemeris / `pyswisseph` behavior if code inspection and local tests do not explain a residual. Do not spend calls on library docs unrelated to this Python package. |

### MCPs to leave off for the main implementation loop

| MCP | Decision | When to turn it on |
| --- | --- | --- |
| `headroom` | **OFF when `context-mode` is ON** | It also compresses tool outputs/context. Avoid stacking two compression/routing layers during a task where arcseconds, timestamps, ordered JSON arrays, and exact diff evidence must not be lost. If `context-mode` is unavailable or incompatible with this OpenCode setup, use Headroom as the alternative, not both. In either case, preserve raw comparison artifacts and verify them directly. |
| `playwright` | **OFF** | There is no browser-driven UI or web app under test. The acceptance checks are local Python calculations, CLI invocation, JSON parsing, and automated tests. Only enable it if a concrete, necessary browser workflow is discovered. |
| `skillspector` | **OFF during ordinary coding; use as an install/audit gate** | Run SkillSpector against a third-party skill or MCP package before adding/enabling it. No new third-party skill is required to execute this task, so the scanner does not need to consume a slot throughout implementation. A scan is a security aid, not proof that the skill's output is correct. |

Do not enable duplicate MCP implementations of the same capability. In particular, do not run both `context-mode` and `headroom` as output compressors simultaneously. Keep the active MCP set minimal; every active tool must serve a concrete step in this task.

### Exact execution order

1. Start with repository-native tools: inspect `AGENTS.md`, the reconciliation document, reference JSON, serializers, CLI, and tests. Establish a baseline before editing.
2. Invoke `change-impact` and `tdd-workflow`; write failing tests for the actual reference schema and horary-cusp start convention.
3. Implement only the supported fix; run the relevant tests and a recursive, type-aware JSON diff. Keep diff output both machine-readable and human-readable so exact values can be rechecked even if MCP output is compressed.
4. Invoke `verification-loop` and `python-reviewer`; inspect any reported difference against raw source/artifacts, not their compressed summaries.
5. Use `documentation-lookup` + `context7` only for residuals requiring confirmation from Swiss Ephemeris/pyswisseph documentation.
6. Finish with `code-reviewer`, full test results, exact-match counts, quantified residuals, and a record of the MCP/ephemeris context actually used.
