## Strict KP Stellar reference tests, corrected TASK2 plan, residual diagnostics

No calculation code is changed. Reference parity is **286 / 322 leaves (88.8%)**, unchanged.

### What this adds
- `tests/test_kp_stellar_strict.py`: exact, recursive, type-aware comparison with the committed `kp_stellar_output.json`. The 36 differing leaves are pinned by path in both directions, so a new difference fails and a fixed residual also fails (forcing the list to be updated). Seven strict `xfail` group tests record each residual.
- `TASK2.md`: measured root causes, stop rules, and second-pass findings.
- `tools/diagnostics/`: `jdiff.py`, `residual_probe.py`, `nutation_convention_probe.py` (read-only probes that reproduce every number).

### Findings (all ours − reference)
- **Dasha stamps (+2h58m58s at every level)** are a Moon-longitude effect, not a dasha-algorithm bug: about 3.29 h per arcsecond of Moon longitude; a −0.91″ Moon shift reproduces all five stamps within 31 s.
- **Planets (+9–10″)**: Swiss's own sidereal path subtracts an ayanamsa that includes nutation (+8.042″ here), so it sits 8.042″ below kpastro for every body. That removes most of the planet residual but moves the Moon the wrong way, and two hypotheses fit the single chart equally. Not applied as a default.
- Sunrise/sunset (+8 s/−7 s), cusps 3/9 (+0.88″), and `signifies` ordering (18 leaves) remain, with measured values in the tests.

### Verification
`SE_EPHE_PATH=$HOME/.kpastro/ephe python -m pytest --no-cov`: only the 5 documented pre-existing `test_precision.py` failures; strict tests: 4 pass, 7 xfail as designed.

### Needs from the owner
A second genuine KP Stellar printout. The `temp_kp*.json` files on `qwen` are kpastro output in its own schema, so they are not independent.
