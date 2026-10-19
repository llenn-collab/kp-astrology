"""Signifies-ordering candidate probe for TASK2.md §2.E (diagnostic only).

Run from the repo root with the full ephemeris installed:
    export SE_EPHE_PATH="$HOME/.kpastro/ephe"
    venv/bin/python diagnositics/signifies_probe.py

For each of the 9 planet rows and all 48 cusp tiers it prints our current
serializer order, the reference order, and whether each STATED candidate rule
reproduces the reference. The candidate rules are documented (and their
pre-implementation measurements recorded) in findings_signifies.md; none of
them touches src/. Output is printed only; nothing is written.

Two phases are shown:
  * the candidates themselves (R0..R3 / T0..T6) measured against the
    reference -- this is the acceptance test;
  * a cross-check that the code in src/kpastro/chart.py actually emits the
    accepted package (R2 rows + T1 tiers).
"""
import json
from datetime import date, datetime, time

from kpastro.chart import (
    BirthInfo,
    _cusp_sublord_houses,
    _kp_significator_map,
    _signifies_ordered,
    chart_to_kp_stellar_json,
    compute_chart,
)
from kpastro.constants import KP_PLANET_ABBR, KP_PLANET_ORDER, ROMAN
from kpastro.horary import kp_divisions

REF = json.load(open("kp_stellar_output.json"))

birth = BirthInfo(
    date=date(2026, 10, 30), time=time(12, 0, 0),
    latitude=18.4593067, longitude=73.8654709, tz_hours=5.5,
    place="Pune, India",
)
QUERY = datetime(2026, 10, 18, 12, 0, 0)
chart = compute_chart(
    birth, ayanamsa="kp_new", node="mean", query_utc=QUERY,
    horary_lagna=kp_divisions()[116].start_deg,  # division 117's cusp
)

# --- chart-derived facts (no reference values involved) ---------------------
house_of_planet = {p.name: p.house for p in chart.planets}
star_lord = {p.name: p.star_lord for p in chart.planets}
cusp_sign_lord = {c.house: c.sign_lord for c in chart.cusps}
star_lords_all = [p.star_lord for p in chart.planets]
no_star = {p.name: p.name not in star_lords_all for p in chart.planets}


def owns(planet: str) -> list[int]:
    return sorted(h for h, lord in cusp_sign_lord.items() if lord == planet)


def groups(pname: str) -> list[list[int]]:
    sl = star_lord[pname]
    return [
        [house_of_planet[sl]] if sl in house_of_planet else [],
        [house_of_planet[pname]],
        owns(sl),
        owns(pname),
    ]


_EXTRA = _cusp_sublord_houses(chart)


def build_row(pname: str, order: list[int]) -> list[str]:
    """Concatenate the 4 groups in the given group-slot order, dedup, plus
    the (Roman) sub-lord-of-cusps tail that every candidate shares."""
    gs = groups(pname)
    seen: list[int] = []
    for gi in order:
        for h in gs[gi]:
            if h not in seen:
                seen.append(h)
    entry = [str(h) for h in seen]
    if _EXTRA[pname]:
        entry.append("(" + ", ".join(ROMAN[h] for h in _EXTRA[pname]) + ")")
    return entry


# --- planet-row candidates ---------------------------------------------------
# group slot 0=G1(sl's house) 1=G2(own house) 2=G3(sl owns) 3=G4(p owns)
ROW_CANDIDATES = {
    "R0 old default [G1,G2,G3,G4]": lambda p: [0, 1, 2, 3],
    "R1 unconditional [G2,G1,G4,G3]": lambda p: [1, 0, 3, 2],
    "R2 star-flag: * -> [G2,G1,G4,G3] else default":
        lambda p: [1, 0, 3, 2] if no_star[p] else [0, 1, 2, 3],
    "R3 node-star-lord -> [G2,G1,G4,G3] else default":
        lambda p: [1, 0, 3, 2] if star_lord[p] in ("Rahu", "Ketu") else [0, 1, 2, 3],
}

ACCEPTED_ROW_CANDIDATE = "R2 star-flag: * -> [G2,G1,G4,G3] else default"
ACCEPTED_TIER_CANDIDATE = "T1 star-flag: * first, then KP order"


def kp_key(name: str) -> int:
    return KP_PLANET_ORDER.index(name) if name in KP_PLANET_ORDER else 99


TIER_CANDIDATES = {
    "T0 old default KP order": lambda ms: sorted(set(ms), key=kp_key),
    "T4 house-ascending (KP tie)":
        lambda ms: sorted(set(ms), key=lambda m: (house_of_planet[m], kp_key(m))),
    "T5 longitude-ascending":
        lambda ms: sorted(set(ms), key=lambda m: chart.planet_lon[m] % 360),
    "T6 Venus-first (H3)":
        lambda ms: sorted(set(ms), key=lambda m: (0 if m == "Venus" else 1, kp_key(m))),
    "T1 star-flag: * first, then KP order":
        lambda ms: sorted(set(ms), key=lambda m: (0 if no_star[m] else 1, kp_key(m))),
}

TIER_KEYS = [
    "planets_in_star_of_planets_in_house",
    "planets_in_house",
    "planets_in_star_of_house_lord",
    "sign_lord",
]

# --- our current serializer output ------------------------------------------
payload = chart_to_kp_stellar_json(
    chart, dasha_depth=5, query_utc=QUERY, name="KPstellaroutput",
    gender="Male", horary_no=117, timezone="Asia/Kolkata",
)
planets = list(KP_PLANET_ORDER)
our_rows = {k: payload["planets"][KP_PLANET_ABBR[k]]["signifies"] for k in planets}
ref_rows = {k: REF["planets"][KP_PLANET_ABBR[k]]["signifies"] for k in planets}

sig_map = _kp_significator_map(chart)
our_tiers: dict[tuple[int, str], list[str]] = {}
ref_tiers: dict[tuple[int, str], list[str]] = {}
for h in range(1, 13):
    for i, key in enumerate(TIER_KEYS):
        k = (h, "ABCD"[i])
        our_tiers[k] = payload["cusps"][str(h)]["signifies_A_B_C_D"][i]
        ref_tiers[k] = REF["cusps"][str(h)]["signifies_A_B_C_D"][i]

# cross-check: the direct helper agrees with the serializer output
assert _signifies_ordered(chart, _EXTRA) == our_rows

print("=== group decomposition (chart-derived) ===")
for k in planets:
    g = groups(k)
    print(
        f"  {k}: G1={g[0]} G2={g[1]} G3={g[2]} G4={g[3]} "
        f"noStar={no_star[k]} sl={star_lord[k]}"
    )

print("\n=== planet rows (9): our code vs reference ===")
for k in planets:
    mark = "ok " if our_rows[k] == ref_rows[k] else "DIFF"
    print(f"  {k:<4} ours={our_rows[k]!s:<38} ref={ref_rows[k]!s:<38}{mark}")

correct_rows = {k for k in planets if our_rows[k] == ref_rows[k]}
row_results: dict[str, set[str]] = {}
for name, fn in ROW_CANDIDATES.items():
    ok, bad, changed = set(), set(), set()
    for k in planets:
        got = build_row(k, fn(k))
        (ok if got == ref_rows[k] else bad).add(k)
        if got != our_rows[k]:
            changed.add(k)
    row_results[name] = ok
    broken = (changed & correct_rows) - ok
    print(f"\n  {name}")
    print(f"    reproduces {len(ok)}/9: {sorted(ok)}")
    print(f"    fails      {len(bad)}/9: {sorted(bad)}")
    print(f"    changes vs code {sorted(changed)}; breaks code-correct: {sorted(broken)}")

print("\n=== cusp tiers (48): our code vs reference ===")
for k in sorted(ref_tiers):
    if len(ref_tiers[k]) > 1 or our_tiers[k] != ref_tiers[k]:
        mark = "ok " if our_tiers[k] == ref_tiers[k] else "DIFF"
        print(f"  cusp{k[0]:>2}.{k[1]}: ours={our_tiers[k]!s:<30} "
              f"ref={ref_tiers[k]!s:<30}{mark}")

correct_tiers = {k for k in ref_tiers if our_tiers[k] == ref_tiers[k]}


def full_names(members_abbrev: list[str]) -> list[str]:
    """A member list (abbreviations) back to full names for the candidate fns."""
    return [n for n in KP_PLANET_ORDER if KP_PLANET_ABBR.get(n, n) in members_abbrev]


tier_results: dict[str, set] = {}
for name, fn in TIER_CANDIDATES.items():
    ok, bad, changed = set(), set(), set()
    for k in ref_tiers:
        got = [KP_PLANET_ABBR.get(n, n) for n in fn(full_names(our_tiers[k]))]
        (ok if got == ref_tiers[k] else bad).add(k)
        if got != our_tiers[k]:
            changed.add(k)
    tier_results[name] = ok
    broken = (changed & correct_tiers) - ok
    print(f"\n  {name}")
    print(f"    reproduces {len(ok)}/48, fails {len(bad)}/48: {sorted(bad)}")
    print(f"    changes vs code {sorted(changed)}; breaks code-correct: {sorted(broken)}")

print("\n=== summary vs acceptance test (9 rows + 48 tiers, 0 breakage) ===")
for name in ROW_CANDIDATES:
    ok = row_results[name]
    print(f"  ROW  {name}: {len(ok)}/9 reproduced, "
          f"{len(correct_rows - ok)} code-correct rows not reproduced")
for name in TIER_CANDIDATES:
    ok = tier_results[name]
    print(f"  TIER {name}: {len(ok)}/48 reproduced, "
          f"{len(correct_tiers - ok)} code-correct tiers not reproduced")

pkg_rows = row_results[ACCEPTED_ROW_CANDIDATE]
pkg_tiers = tier_results[ACCEPTED_TIER_CANDIDATE]
print(f"\nPACKAGE ({ACCEPTED_ROW_CANDIDATE} + {ACCEPTED_TIER_CANDIDATE}): "
      f"rows {len(pkg_rows)}/9, tiers {len(pkg_tiers)}/48, "
      f"not reproduced among code-correct = "
      f"{len(correct_rows - pkg_rows) + len(correct_tiers - pkg_tiers)}")
verdict = (
    len(pkg_rows) == 9 and len(pkg_tiers) == 48
    and not (correct_rows - pkg_rows) and not (correct_tiers - pkg_tiers)
)
print("VERDICT:", "ALL PASS" if verdict else "FAIL")
