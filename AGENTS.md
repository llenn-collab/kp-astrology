# AGENTS.md

## What this is

`kpastro` — a Krishnamurti Paddhati (KP) Vedic astrology engine. Pure-Python
package, one runtime dependency (`pyswisseph`). Computes sidereal planet
positions, Placidus cusps, KP star/sub/sub-sub-lord chains, Vimshottari dasha,
significators, horary (1-249), and birth-time rectification.

Long-term goal: agree with a designated **KP Stellar** reference (see
"KP Stellar compatibility" below).

## Layout & entry points

`src/` layout, single package `src/kpastro/`. Console script `kpastro` and
`python -m kpastro` both call `kpastro.cli:main`.

- `constants.py` — Vimshottari/nakshatra/sign tables (source of truth for lord order)
- `arithmetic.py` — exact integer/Fraction **milliarcsecond** core; all boundary math
- `vedic.py` — star/sub/sub-sub derivation (no ephemeris; pure longitude math)
- `ephemeris.py` — pyswisseph wrapper: ayanamsa, positions, Placidus cusps, download
- `dasha.py` / `deep_dasha.py` — Vimshottari balances and nested period stacks
- `panchanga.py` — sunrise/sunset, tithi, nitya yoga, karana, nakshatra+pada,
  day lord, and the `dasha_balance` header string
- `chart.py` — `BirthInfo`, `compute_chart`, text renderers,
  `chart_to_kp_json` (kpastro long-form) and `chart_to_kp_stellar_json`
  (KP Stellar printout schema; the default for `natal --json`)
- `significators.py`, `horary.py`, `rectification.py` — higher KP layers
- `cli.py` — argparse subcommands: `natal horary dasha rulings ayanamsa download-ephemeris`

## Commands

```bash
pip install -e .            # runtime only (pyswisseph)
pip install -e .[dev]       # adds pytest + pytest-cov  <-- REQUIRED for tests
python -m kpastro natal --date 1990-01-15 --time 14:30 --tz 5.5 \
    --lat 28.6139 --lon 77.2090 --place "New Delhi"
python -m kpastro download-ephemeris
```

- Run all tests: `python -m pytest`
- Run one test file / test: `python -m pytest tests/test_precision.py::TestClass::test_name`
- Skip the coverage gate while iterating: `python -m pytest --no-cov`
- There is **no** linter, formatter, or typechecker configured. Do not invent
  or add one unless asked.

### `python -m pytest` FAILS on a fresh checkout (verified)

The existing `venv/` now has `kpastro` + `pyswisseph` + pytest 9.1.1 +
pytest-cov (verified 19 Oct 2026); use `venv/bin/python -m pytest --no-cov`.
Even after `pip install -e .[dev]` on a fresh machine the run reports
**5 failures + a coverage-gate failure** (`--cov-fail-under=85`,
actual ~48%). This is pre-existing, not something you broke:

- `test_kahan_sum_beats_naive` — asserts naive `sum([1e16,1,-1e16,1]) != 2.0`;
  on CPython 3.13 it *is* `2.0`, so the "naive fails" premise is platform-dependent.
- `test_quantize_deg_half_up_exact` — `quantize_deg(0.5/3600, 1.0)` returns `0.0`,
  test expects `1/3600`.
- `test_fraction_algebra_values` — asserts `md_years_fraction("Sun") == 17`;
  the code correctly returns `6` (see `VIMSHOTTARI_YEARS`). Test bug.
- `test_balance_requantisation_bound` — zodiac wrap: `mas_to_deg(1296000000)` is
  `360.0`, which folds to `0.0`, so the exact-equality bound fails at the wrap.
- `test_period_helpers` — `format_days(400.0)` returns `1y 1m 4d` (correct with
  month=30.4375d); test expects a `1y 0m` prefix.

Do **not** change calculation code to make these pass. If a task is not about
these tests, use `--no-cov` and treat the *passing* tests as the signal. On
CPython 3.11 `test_kahan_sum_beats_naive` passes, so the baseline there is
4 failures rather than 5. Coverage is thin in `rectification.py`,
`significators.py`, `cli.py`, `chart.py` (all < 50%).

Current green baseline (19 Oct 2026): `venv/bin/python -m pytest --no-cov`
→ **5 failed, 145 passed, 21 xfailed**. The 21 xfails are *intentional*:
18 are the recorded KP Stellar residuals in `tests/test_kp_stellar_strict.py`
(strict, with measured values; `KNOWN_OURS` pins them so drift fails the
suite) and 3 are the converted tolerance tests in
`tests/test_kp_stellar_reference.py`. A residual being fixed flips its xfail
to a failure on purpose — update the table when that happens.

## Ephemeris files

- Names: `sepl_18.se1`, `semo_18.se1`, `seas_18.se1` (`ephemeris.EPHEMERIS_FILES`).
- Location precedence (`SwissEphemeris.__init__`): explicit `ephe_path` arg →
  `$SE_EPHE_PATH` → `~/.kpastro/ephe` (`default_ephe_path()`).
- They are **not in the repo** and not gitignored (they live under `$HOME`).
  Already present on this machine at `~/.kpastro/ephe`.
- Obtain via `python -m kpastro download-ephemeris` (fetches from the
  `aloistr/swisseph` GitHub mirror; validates size ≥100 KB, writes atomically).
- **Missing files are not an error** — the engine silently falls back to the
  built-in Moshier ephemeris (~1" planets, ~0.5" Moon). `SwissEphemeris.precision`
  reports `"full"` vs `"moshier"`. When comparing to a reference, confirm
  `precision == "full"` first; a mismatch is often a missing-file problem.
- Never delete, rename, or regenerate these assets.

## Calculation invariants (do not casually change)

- **Milliarcsecond core**: all sign/star/sub boundaries are exact
  `Fraction` values in mas (`arithmetic.py`). Adjacent segments share
  byte-identical edges. Do not reintroduce float degree arithmetic here.
- **Boundary policy**: `BOUNDARY_TOL_MAS = 1/1000` mas (≡ the historical 1e-9°
  forward-push) — a position just below a boundary belongs to the segment above.
  `vedic._mas` therefore has to snap *up* when the exact value is within that
  tolerance of the next integer mas; flooring to a whole mas first throws away
  up to 1 mas, which is a thousand times the push, and silently sends exact
  boundaries to the **preceding** segment. That was a real bug: `26.666…`°
  (`= 96 000 000` mas, the Krittika start) resolved to Bharani/Venus, and
  `1510/9`° (`= 604 000 000` mas, the Saturn→Mercury sub edge of Hasta — and
  cusp 1 of `kp_stellar_output.json`) resolved to Saturn.
- **Dasha year** = 365.25 days (`dasha.DAYS_PER_YEAR`); sub span = years/120 × 800'.
- **Ayanamsa**: `lahiri` (default), `kp`, `kp_old`, and `kp_new`. `kp_new` is
  `kp` (VP291) plus a fixed `_AYANAMSA_OFFSETS_DEG = 50.7/3600`, calibrated
  against KP Stellar for one epoch. Treat that offset as provisional until
  verified at a second epoch.
- **House latitude**: `house_latitude_model` defaults to `"geocentric"` — the
  WGS84 geodetic input is converted to geocentric before the Placidus call.
  This is a deliberate KP Stellar alignment; switching to `"geodetic"` moves
  the Ascendant by ~2' at 19°N (MC barely moves).
- **Nodes**: `mean` by default (KP convention); `true` optional. Rahu/Ketu are
  always flagged retrograde.
- **Horary lagna — two different points, both needed.** A KP horary chart takes
  its *lagna* from the querent's number rather than from the clock, so its
  house cusps belong to that ascendant. The two layers disagree on which point
  of the division that is, and the difference is deliberate:
  - `horary.ascendant_from_kp_number(n)` returns the division **midpoint**
    (public API; still used for the `horary` subcommand's text-mode span/lord
    line, but no longer for its house frame).
  - `horary.cusps_from_horary_lagna(...)` solves the instant whose Placidus
    ascendant equals the longitude it is given and returns that instant's
    twelve cusps. `compute_chart(..., horary_lagna=...)` and both
    `natal --horary-no N` and `horary --number N` feed it division N's
    **cusp** (`start_deg`), which is
    what KP Stellar does: `kp_stellar_output.json`'s `cusps.1` is exactly
    `1510/9`° = the cusp of division 117, and no division's midpoint.
  With a horary lagna set, `chart.cusps[0].longitude != chart.ascendant` on
  purpose: the houses are horary, while `ascendant`, `midheaven` and `ruling`
  stay astronomical. KP Stellar reports the same split — its
  `ruling_planets.lagna` is the birth ascendant, not its own `cusps.1`.
- **Global engine state**: pyswisseph is process-global. `_set_sid_mode` caches
  the applied sidereal mode behind a module-level lock. Concurrent or
  interleaved charts relying on different ayanamsas must go through this path.
- **Query time vs birth time**: the "current" dasha stack resolves at
  `query_utc`, defaulting to birth. `cmd_natal` passes `datetime.utcnow()`.
  Passing birth for both always yields the birth stack (a past bug).

## KP Stellar compatibility

The only KP Stellar**-sourced** artifact on `main` is `kp_stellar_output.json`
(a full printout-schema export; see `KP_STELLAR_RECONCILIATION.md`,
`KP_STELLAR_DIFF.md`). The `temp_kp*.json` / `temp_final.md` files this
section used to list are **not on `main`** (branches `qwen` /
`error-free-astrology-repo-upgrades-5d780` only) and are kpastro's own
long-form schema anyway — not independent references. A genuine *second*
KP Stellar printout (any date/place, same schema) is still needed to confirm
the open conventions below.

Current state against `kp_stellar_output.json` (pinned command in
`KP_STELLAR_DIFF.md`): **315 of 322 leaves exact**; the 7 residuals are
recorded as strict xfails in `tests/test_kp_stellar_strict.py`. Four
independent references now exist — set 1 (2026-10-30, Pune, horary 117),
set 4 (2024-06-01, Sholapur, horary 57), set 5 (same instant, Delhi) and
set 6 (+90 min, horary 69) — re-measured by
`python diagnositics/kp_new_alignment.py`.

- **Install the full ephemeris files** (`python -m kpastro
  download-ephemeris`). Without them Swiss falls back to Moshier and every
  planet is ~9–10″ out, sunrise/sunset drift by 8 s, and the tests skip. With
  them, all nine planetary degrees and sunrise/sunset are exact.
- **The Moon carries an empirical calibration**: `+6.26784″ +
  0.0022545″/day` after 2024-06-01 (≈ +0.82″/year), applied for `kp_new`
  only. It is measured from the Vimshottari end stamps (one arcsecond of
  Moon = 11,834 s in a Rahu mahadasha, 12,491.55 s in a Saturn mahadasha),
  not fitted to the printed degrees. No documented Swiss Ephemeris flag
  reproduces it; `_MOON_CORRECTION_ENABLED = False` restores the raw Moon.
  See the Addendum B of `KP_STELLAR_RECONCILIATION.md`.
- Remaining 7 leaves: cusps 2/8 print 1″ low (true residual 0.09″), and the
  five dasha end stamps are 4 s early — 0.34 mas, below one step of the
  exact-mas balance grid.
- **The ayanamsa zero point drifts by epoch**: the planet-print windows are
  49.52–49.61″ in Oct 2026 but 49.97–50.25″ in Jun 2024, i.e. ≈ −0.20″/year
  against `SIDM_KRISHNAMURTI_VP291`. `kp_new` deliberately keeps the single
  value **49.58″** (the 2026 optimum, consistent with the reference's own
  printed ayanamsa at both epochs); the cost is that three or four planets in
  the 2024 sets print 1″ low.
- Signifies **row order is fixed** by the `*`-flag rule (a planet no planet
  sits in the star of flips its group pairs and sorts first in cusp tiers) —
  stated and measured in `diagnositics/findings_signifies.md`, pinned in
  `tests/test_signifies_order.py`; confirmed on n=1 chart, falsifiable by
  the next reference.

Probe scripts and full findings live under `diagnositics/` (note the typo'd
directory name — it is pre-existing; do not rename).

Two emitters, do not conflate them: `chart_to_kp_stellar_json` emits the KP
Stellar printout schema (`horary_details` / `vimsottari_dasa` / `ruling_planets`
/ `planets` / `cusps` / `nodes_representation` / `legend`) and is what
`natal --json` uses; `chart_to_kp_json` emits kpastro's own long-form payload
and is reachable as `--json-schema detailed`.

**Read the reference's `horary_no` before anything else.** If it is non-empty
the reference's `cusps` block is a *horary* frame — cast from that division's
cusp — while its planets and ruling planets are on the birth data. Casting
houses from the birth instant instead will disagree by a whole sign and no
ayanamsa, node, latitude or house-system change will close it.

When reconciling with a supplied KP Stellar reference:

1. Treat the reference output as the **expected** behavior for its inputs.
2. Record input conditions, expected value, actual value, units, precision,
   and tolerance for every comparison.
3. Separate **confirmed discrepancies** from **hypotheses**.
4. Add a **regression test reproducing a discrepancy before fixing it**.
5. Investigate stage/config differences (ayanamsa mode, node mode, house
   latitude model, ephemeris precision, query time) before touching algorithms.
6. Never claim full compatibility from a handful of matching examples.
7. Do not invent missing reference values or assume undocumented defaults.

## Working rules

- Verify against source, not memory. `codebase-memory-mcp` graph tools
  (`search_graph`, `trace_path`, `get_code_snippet`, `get_architecture`) are
  available for structural questions — but the index can lag; trust the source.
- Preserve existing behavior. No unrelated refactoring, no dependency adds,
  no reformatting. Make the smallest change that satisfies the request.
- Several files are committed that look like junk or scratch output —
  `.DS_Store`, `src/kpastro/__pycache__/*.pyc`, `src/kpastro.egg-info/`.
  Leave them alone unless explicitly asked.
- `kpastro_actual2.md` is plain JSON (a CLI serialization, despite the `.md`
  extension); `kpastro_actual2.json` is its identical copy. Regenerate both
  from the pinned command in `KP_STELLAR_DIFF.md` — never edit by hand.
- Version is declared in two places and currently disagrees: `pyproject.toml`
  says `0.3.0`, `kpastro/__init__.py` fallback says `0.3.1`. Keep them in sync
  when bumping.
- `mkdocs.yml` and the README reference files that do not exist in the repo
  (`docs/*.md`, `CONTRIBUTING.md`). Do not assume docs build cleanly.
