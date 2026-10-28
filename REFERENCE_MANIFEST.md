# V7 / V8 / V9 reference-integrity manifest

**Purpose.** Freeze the intended inputs for the three KP Stellar accuracy
reference charts (V7, V8, V9) before any production calculation change, per
the implementation plan's mandatory pre-implementation gate (context1 §2 Phase 1
+ context2 "Mandatory pre-implementation gate").

**Status.** Gate Task 1 (freeze intended inputs) and Task 3 (prove query-time
consistency) are complete for kpastro. Gate Task 2 (regenerate matching KP
Stellar references) is **blocked**: the KP Stellar outputs are printouts from
the external commercial KP Stellar app, which is not available in this
checkout, so they cannot be regenerated here. The committed KP Stellar V8/V9
references still carry STALE dasha end stamps (Oct–Nov 2026) and must not be
treated as valid timing evidence. See §"KP Stellar reference limitation".

---

## 1. Common inputs (all three versions)

| item | value |
| :-- | :-- |
| Place | Pune, India |
| Latitude | 18.4593067 N |
| Longitude | 73.8654709 E |
| Timezone | +5.50 (Asia/Kolkata) |
| Ayanamsa mode | `kp_new` (KP New) |
| Node mode | `mean` |
| Ephemeris | Swiss Ephemeris JPL/VSOP compressed files (`sepl_18.se1`, `semo_18.se1`, `seas_18.se1`) |
| Ephemeris source | `github.com/mivion/swisseph` (`ephe/`), installed to `~/.kpastro/ephe` |
| `SwissEphemeris.precision` | `"full"` (verified; not the Moshier fallback) |
| Ephemeris note | The code's `EPHEMERIS_BASE_URL` points at `aloistr/swisseph`, but that repo carries no `.se1` files; the canonical available mirror is `mivion/swisseph`. File sizes differ by a few bytes from the `aloistr` sizes quoted in `KP_STELLAR_DIFF.md`, which produces sub-arcsecond / tens-of-seconds dasha-stamp drift vs. the committed snapshots. This is an environment condition, not a code change. |
| House latitude model | `geocentric` (default) |
| Dasha depth | 5 (MD/AD/PD/Sookshma/Prana) |
| Dasha year | 365.25 days; sub span = years/120 × 800′ |
| Moon correction | Enabled (`_MOON_CORRECTION_ENABLED = True`), `kp_new` only: `6.26784″ + 0.0022545″/day × (JD − JD(2024-06-01 09:09:09 IST))` |

**Local → UTC conversion.** All charts use local time 12:00:00 IST = 06:30:00 UTC
(on 2026-10-30 / 2027-04-30 / 2027-10-30; India does not observe DST, so the
offset is a fixed +5:30).

---

## 2. Version-specific inputs

### V7 — chart 2026-10-30 (Pune), horary 117

| item | value |
| :-- | :-- |
| Chart date / local time | 2026-10-30 12:00:00 IST |
| Chart UTC | 2026-10-30 06:30:00 UTC |
| Horary number | 117 (of 249) |
| Intended `--query-utc` | `2026-10-18 12:00:00` (12-day interval; per `KP_STELLAR_RECONCILIATION.md` pinned command) |
| kpastro source file | `kpastro_actual.json` — generated with the pinned query (reproduction of the reconciliation-report command). `kpastro_actual7.json` is the same chart but its dasha stack was produced with the CLI default `datetime.utcnow()` (≈ late-Oct-2026), so only the sookshma/prana stamps differ; planets, cusps and MD/AD/PD match the pinned query. |
| KP Stellar reference | `kp_stellar_output.json` |
| Query-time consistency | Verified: independent regen with `--query-utc "2026-10-18 12:00:00"` reproduces `kpastro_actual.json` exactly except dasha end stamps ~24 s later (ephemeris-mirror drift; see common ephemeris note). MD/AD/PD and all planetary/cusp fields identical. |

### V8 — chart 2027-04-30 (Pune), horary 117

| item | value |
| :-- | :-- |
| Chart date / local time | 2027-04-30 12:00:00 IST |
| Chart UTC | 2027-04-30 06:30:00 UTC |
| Horary number | 117 (of 249) |
| Intended `--query-utc` | `2027-04-18 12:00:00` (18 Apr, 17:30 IST) |
| kpastro source file | `kpastro_actual8-2.json` — regenerated with the intended query. Independently regenerated as `kpastro_actual8_query.json`; matches `-2` exactly on every field except the 5 dasha end stamps, which are 4–5 s later (ephemeris-mirror drift). Dasha window is now April 2027 (prana ends 18/Apr/2027), bracketing the query instant. |
| Stale file (do not use for timing) | `kpastro_actual8.json` — same chart, but its dasha end stamps remain in Oct–Nov 2026. |
| KP Stellar reference | `kp_stellar_output8.json` — **STALE dasha**: its Prana endpoint is 29/Oct/2026, not comparable to the April-2027 query. Cannot be regenerated (external app). |
| Local query time | 18 Apr 2027, 17:30 IST |
| Query-time consistency | Verified: new kpastro prana ends 18/Apr/2027 20:12:42 IST, after the 12:00 UTC query; sookshma/antara endpoints fall in plausible future positions relative to the query. (context2 query-time check) |

### V9 — chart 2027-10-30 (Pune), horary 74

| item | value |
| :-- | :-- |
| Chart date / local time | 2027-10-30 12:00:00 IST |
| Chart UTC | 2027-10-30 06:30:00 UTC |
| Horary number | **74 (of 249)** — treated as INTENTIONAL. All three V9 artifacts agree: `kpastro_actual9.json`, `kpastro_actual9-2.json`, and the KP Stellar reference `kp_stellar_output9.json` all report `74 (249)`. This is not a kpastro-only anomaly, so it is not silently changed to 117. (See §"V9 horary number" below.) |
| Intended `--query-utc` | `2027-10-18 12:00:00` (18 Oct, 17:30 IST) |
| kpastro source file | `kpastro_actual9-2.json` — regenerated with the intended query. Independently regenerated as `kpastro_actual9_query.json`; matches `-2` exactly on every field except the 5 dasha end stamps, which are a constant +21 s later (ephemeris-mirror drift). Dasha window is now Oct 2027 (prana ends 19/Oct/2027), bracketing the query instant. |
| Stale file (do not use for timing) | `kpastro_actual9.json` — same chart, but its dasha end stamps remain in Oct–Nov 2026. |
| KP Stellar reference | `kp_stellar_output9.json` — **STALE dasha**: its Prana endpoint is 30/Oct/2026, not comparable to the Oct-2027 query. Cannot be regenerated (external app). |
| Local query time | 18 Oct 2027, 17:30 IST |
| Query-time consistency | Verified: new kpastro prana ends 19/Oct/2027 05:31:11 IST, after the 12:00 UTC query; sookshma/antara endpoints fall in plausible future positions relative to the query. (context2 query-time check) |

---

## 3. V9 horary number (74 vs 117)

The implementation plan (context1 §1) flags that V9 reports horary `74` while V7/V8 report `117`, and asks whether 74 was intentional. Evidence:

- `kpastro_actual9.json` → `horary_no: "74 (249)"`
- `kpastro_actual9-2.json` → `horary_no: "74 (249)"`
- `kp_stellar_output9.json` → `horary_no: "74 (249)"` (KP Stellar's own V9 reference)

Because KP Stellar's own V9 printout was cast with horary 74, 74 is the **intended input for V9**. It is not silently replaced with 117. V9 therefore tests a different horary configuration than V7/V8 (117), which is itself a legitimate comparison axis.

If the owner intended V9 to use 117 (same configuration as V7/V8), regenerate `kpastro_actual9-2.json` / `kpastro_actual9_query.json` with `--horary-no 117` and update this manifest.

---

## 4. Generation commands (kpastro)

Run from the repo root with the full ephemeris installed:

```bash
export SE_EPHE_PATH="$HOME/.kpastro/ephe"

# V7 (pinned query, reproduces reconciliation-report command)
python -m kpastro.cli natal \
  --date 2026-10-30 --time 12:00:00 --tz 5.5 \
  --lat 18.4593067 --lon 73.8654709 --place "Pune, India" \
  --ayanamsa kp_new --node mean --json \
  --name KPstellaroutput --gender Male --horary-no 117 \
  --timezone Asia/Kolkata --query-utc "2026-10-18 12:00:00" \
  > kpastro_actual.json

# V8
python -m kpastro.cli natal \
  --date 2027-04-30 --time 12:00:00 --tz 5.5 \
  --lat 18.4593067 --lon 73.8654709 --place "Pune, India" \
  --ayanamsa kp_new --node mean --json \
  --name KPstellaroutput8 --gender Male --horary-no 117 \
  --timezone Asia/Kolkata --query-utc "2027-04-18 12:00:00" \
  > kpastro_actual8_query.json

# V9 (horary 74, intentional)
python -m kpastro.cli natal \
  --date 2027-10-30 --time 12:00:00 --tz 5.5 \
  --lat 18.4593067 --lon 73.8654709 --place "Pune, India" \
  --ayanamsa kp_new --node mean --json \
  --name KPstellaroutput9 --gender Male --horary-no 74 \
  --timezone Asia/Kolkata --query-utc "2027-10-18 12:00:00" \
  > kpastro_actual9_query.json
```

The committed regenerated references are `kpastro_actual8-2.json` (V8) and
`kpastro_actual9-2.json` (V9); `*_query.json` files above are independent
regens produced for this manifest. V8/V9 `-2` and `_query` copies match on all
non-dasha-stamp fields.

---

## 5. KP Stellar reference limitation (Gate Task 2 — blocked)

The KP Stellar V8/V9 reference files (`kp_stellar_output8.json`,
`kp_stellar_output9.json`) are printouts from the external commercial KP Stellar
app. This checkout contains only kpastro, so they **cannot** be regenerated with
matching query instants here. Both still contain stale dasha end stamps
(Oct–Nov 2026):

- V8 KP Stellar prana ends 29/Oct/2026 vs. kpastro prana ends 18/Apr/2027
- V9 KP Stellar prana ends 30/Oct/2026 vs. kpastro prana ends 19/Oct/2027

Consequence: dasha end-stamp and active-stack comparisons between kpastro and
KP Stellar are **invalid for V8 and V9** until a genuine KP Stellar printout at
the matching query instant is obtained. Non-dasha fields (planets, cusps,
ayanamsa, sunrise/sunset, nodes, significators) remain comparable because they
depend on the chart instant (30 Apr / 30 Oct 2027), not the dasha query.

A genuine second KP Stellar printout (any date/place, same schema) is still
needed to confirm the open conventions (per `KP_STELLAR_RECONCILIATION.md`
§7).

---

## 6. Files referenced

| file | role |
| :-- | :-- |
| `kpastro_actual.json` | V7 kpastro, pinned query 2026-10-18 12:00 UTC |
| `kpastro_actual7.json` | V7 kpastro, runtime-query dasha (historical snapshot) |
| `kpastro_actual7_query.json` | V7 independent regen, pinned query |
| `kpastro_actual8.json` | V8 kpastro, STALE dasha (do not use for timing) |
| `kpastro_actual8-2.json` | V8 kpastro, regenerated query 2027-04-18 12:00 UTC |
| `kpastro_actual8_query.json` | V8 independent regen, query 2027-04-18 12:00 UTC |
| `kpastro_actual9.json` | V9 kpastro, STALE dasha + horary 74 (do not use for timing) |
| `kpastro_actual9-2.json` | V9 kpastro, regenerated query 2027-10-18 12:00 UTC, horary 74 |
| `kpastro_actual9_query.json` | V9 independent regen, query 2027-10-18 12:00 UTC, horary 74 |
| `kp_stellar_output.json` | V7 KP Stellar reference |
| `kp_stellar_output8.json` | V8 KP Stellar reference (STALE dasha) |
| `kp_stellar_output9.json` | V9 KP Stellar reference (STALE dasha, horary 74) |

---

## Next steps (gate Task 4 → Phase 2)

Build the normalized three-version comparison report across full-precision
planetary longitudes, lord chains, cusps, dasha balance, nodes/representation,
significators (membership separate from order), sunrise/sunset, and schema/null
differences; report signed residuals in arcseconds/seconds. Dasha timing
comparisons against KP Stellar remain blocked for V8/V9 per §5.
