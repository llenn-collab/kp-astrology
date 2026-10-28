# AGENTS.md

## What this is

`kpastro` — a Krishnamurti Paddhati (KP) Vedic astrology engine. Pure-Python
package, one runtime dependency (`pyswisseph`). Computes sidereal planet
positions, Placidus cusps, KP star/sub/sub-sub-lord chains, Vimshottari dasha,
significators, horary (1-249), and birth-time rectification.

## Layout & entry points

`src/` layout, single package `src/kpastro/`. Console script `kpastro` and
`python -m kpastro` both call `kpastro.cli:main`.

- `arithmetic.py` — exact integer/Fraction **milliarcsecond** core; all boundary math
- `vedic.py` — star/sub/sub-sub derivation (no ephemeris; pure longitude math)
- `ephemeris.py` — pyswisseph wrapper: ayanamsa, positions, Placidus cusps, download
- `dasha.py` / `deep_dasha.py` — Vimshottari balances and nested period stacks
- `panchanga.py` — sunrise/sunset, tithi, yoga, karana, nakshatra+pada
- `chart.py` — `BirthInfo`, `compute_chart`, text renderers, both JSON emitters
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
- This machine has a working `.venv/` with kpastro + dev extras installed.
  On a fresh checkout `python -m pytest` fails until `pip install -e .[dev]`.

## Ephemeris files

- Names: `sepl_18.se1`, `semo_18.se1`, `seas_18.se1` (`ephemeris.EPHEMERIS_FILES`).
- Location precedence (`SwissEphemeris.__init__`): explicit `ephe_path` arg →
  `$SE_EPHE_PATH` → `~/.kpastro/ephe` (`default_ephe_path()`).
- They are **not in the repo** and not gitignored (they live under `$HOME`).
- Obtain via `python -m kpastro download-ephemeris`.
- **Missing files are not an error** — the engine silently falls back to the
  built-in Moshier ephemeris (~1" planets, ~0.5" Moon). `SwissEphemeris.precision`
  reports `"full"` vs `"moshier"`. When comparing to a reference, confirm
  `precision == "full"` first; a mismatch is often a missing-file problem.
- Never delete, rename, or regenerate these assets.

## Calculation invariants (do not casually change)

- **Milliarcsecond core**: all sign/star/sub boundaries are exact `Fraction`
  values in mas (`arithmetic.py`). Adjacent segments share byte-identical
  edges. Do not reintroduce float degree arithmetic here.
- **Boundary policy**: `BOUNDARY_TOL_MAS = 1/1000` mas (≡ the historical 1e-9°
  forward-push) — a position just below a boundary belongs to the segment above.
- **Dasha year** = 365.25 days (`dasha.DAYS_PER_YEAR`); sub span = years/120 × 800'.
- **Ayanamsa**: `lahiri` (default), `kp`, `kp_old`, and `kp_new`. `kp_new` is
  `kp` (VP291) plus a fixed `_AYANAMSA_OFFSETS_DEG = 50.7/3600`, and it also
  applies an empirical Moon correction (`_MOON_CORRECTION_*` constants in
  `ephemeris.py`, ~+6.27" drifting +0.0023"/day). Both are deliberate
  calibrations — do not "clean up" the magic numbers; `_MOON_CORRECTION_ENABLED
  = False` restores the raw Moon.
- **House latitude**: `house_latitude_model` defaults to `"geocentric"` — the
  WGS84 geodetic input is converted to geocentric before the Placidus call.
  This is deliberate; `"geodetic"` moves the Ascendant by ~2' at 19°N.
- **Nodes**: `mean` by default (KP convention); `true` optional. Rahu/Ketu are
  always flagged retrograde.
- **Horary lagna — two different points, both needed.**
  `horary.ascendant_from_kp_number(n)` returns the division **midpoint**
  (public API only); `horary.cusps_from_horary_lagna(...)` solves the instant
  whose Placidus ascendant equals the longitude it is given, and both the
  `horary` subcommand and `natal --horary-no N` feed it the division's
  **cusp** (`start_deg`). With a horary lagna set,
  `chart.cusps[0].longitude != chart.ascendant` on purpose: the houses are
  horary, while `ascendant`/`midheaven`/`ruling` stay astronomical.
- **Global engine state**: pyswisseph is process-global. `_set_sid_mode` caches
  the applied sidereal mode behind a module-level lock. Concurrent or
  interleaved charts relying on different ayanamsas must go through this path.
- **Query time vs birth time**: the "current" dasha stack resolves at
  `query_utc`, defaulting to birth (horary) or `datetime.utcnow()` (natal).
  Passing birth for both always yields the birth stack (a past bug).

## JSON emitters, do not conflate them

- `chart_to_kp_stellar_json` — KP Stellar printout schema; the **default** for
  `--json` on `natal` and `horary`.
- `chart_to_kp_json` — kpastro's own long-form payload, via `--json-schema detailed`.

## Working rules

- Verify against source, not memory. The `codebase-memory-mcp` graph tools
  (`search_graph`, `trace_path`, `get_code_snippet`) are available for
  structural questions, but the index can lag; trust the source.
- Preserve existing behavior. No unrelated refactoring, no dependency adds,
  no reformatting. Make the smallest change that satisfies the request.
- Version is declared in two places: `pyproject.toml` (`0.3.0`) and the
  `kpastro/__init__.py` fallback (`0.3.1`). Keep them in sync when bumping.
- `README.md` is the user-facing reference (full CLI flags, JSON examples,
  calculation conventions). Do not duplicate it here; fix it there when
  user-facing behavior changes.
