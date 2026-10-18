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
- `chart.py` — `BirthInfo`, `compute_chart`, text renderers, `chart_to_kp_json`
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

The existing `venv/` has `kpastro` + `pyswisseph` but **not** pytest — activate
it and you get `No module named pytest`. After `pip install -e .[dev]`, the run
still reports **5 failures + a coverage-gate failure** (`--cov-fail-under=85`,
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
these tests, use `--no-cov` and treat the 102 passing tests as the signal.
Coverage is thin in `rectification.py`, `significators.py`, `cli.py`,
`chart.py` (all < 50%).

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
- **Global engine state**: pyswisseph is process-global. `_set_sid_mode` caches
  the applied sidereal mode behind a module-level lock. Concurrent or
  interleaved charts relying on different ayanamsas must go through this path.
- **Query time vs birth time**: the "current" dasha stack resolves at
  `query_utc`, defaulting to birth. `cmd_natal` passes `datetime.utcnow()`.
  Passing birth for both always yields the birth stack (a past bug).

## KP Stellar compatibility (future work)

KP Stellar reference outputs exist in the repo as committed artifacts:
`temp_kp.json` (mode `kp`), `temp_kp_test2.json` and `temp_kp_test3.json`
(mode `kp_new`), `temp_final.md` (text render). `chart_to_kp_json` /
`render_chart_json` emit the Stellar-aligned schema.

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
  `.DS_Store`, `src/kpastro/__pycache__/*.pyc`, `src/kpastro.egg-info/`,
  `temp_*.json`, `temp_final.md`. Leave them alone unless explicitly asked;
  the `temp_*` files are KP Stellar references (see above).
- Version is declared in two places and currently disagrees: `pyproject.toml`
  says `0.3.0`, `kpastro/__init__.py` fallback says `0.3.1`. Keep them in sync
  when bumping.
- `mkdocs.yml` and the README reference files that do not exist in the repo
  (`docs/*.md`, `CONTRIBUTING.md`). Do not assume docs build cleanly.
