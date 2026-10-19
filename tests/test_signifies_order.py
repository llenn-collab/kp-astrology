"""§2.E signified-list ordering: all 9 planet rows and all 48 cusp tiers.

The accepted rule (stated and measured in ``diagnositics/findings_signifies.md``
before it was implemented) is:

* a planet **no planet sits in the star of** (its own star included) --
  KP Stellar's ``*`` flag -- emits its ``signifies`` groups with each pair flipped (own house
  before the star-lord's house, own signs before the star-lord's signs);
* every ``signifies_A_B_C_D`` tier sorts ``*``-flagged planets first, then
  the rest in KP planet-table order.

The expectations below are the reference values from ``kp_stellar_output.json``
hard-coded in this test (allowed: tests, unlike ``src/``, may name the
reference).  The chart is the pinned one: 2026-10-30 12:00 IST Pune,
ayanamsa kp_new, mean node, horary number 117, query 2026-10-18 12:00 UTC.
"""

from __future__ import annotations

import json
from datetime import datetime, time

import pytest

from kpastro.chart import BirthInfo, chart_to_kp_stellar_json, compute_chart
from kpastro.ephemeris import SwissEphemeris
from kpastro.horary import kp_divisions

#: Reference ``planets.<key>.signifies`` for all nine planets, in order.
EXPECTED_SIGNIFIES = {
    "SUN": ["1", "5", "12"],
    "MOO": ["9", "5", "11", "(VI)"],
    "MAR": ["2", "11", "1", "10", "3", "8", "(IV, VIII)"],
    "RAH": ["11", "5", "3", "8", "(XII)"],
    "JUP": ["2", "11", "1", "10", "4", "7"],
    "SAT": ["6", "5", "(IX)"],
    "MER": ["11", "2", "4", "7", "1", "10", "(I, III, V, VII, XI)"],
    "KET": ["11"],
    "VEN": ["1", "11", "2", "9", "3", "8", "(II, X)"],
}

#: Reference ``cusps.<h>.signifies_A_B_C_D`` for all twelve cusps, tiers
#: ``[A, B, C, D]``.
EXPECTED_TIERS = {
    1: [[], ["SUN", "VEN"], ["MAR", "JUP"], ["MER"]],
    2: [["MAR", "JUP"], ["MER"], [], ["VEN"]],
    3: [[], [], ["VEN", "RAH"], ["MAR"]],
    4: [[], [], ["MER"], ["JUP"]],
    5: [["SUN", "MOO"], ["RAH"], ["SAT"], ["SAT"]],
    6: [["SAT"], ["SAT"], ["SAT"], ["SAT"]],
    7: [[], [], ["MER"], ["JUP"]],
    8: [[], [], ["VEN", "RAH"], ["MAR"]],
    9: [[], ["MOO"], [], ["VEN"]],
    10: [[], [], ["MAR", "JUP"], ["MER"]],
    11: [["VEN", "RAH", "MER", "KET"], ["MAR", "JUP", "KET"], [], ["MOO"]],
    12: [[], [], [], ["SUN"]],
}


@pytest.fixture(scope="module")
def eph() -> SwissEphemeris:
    return SwissEphemeris(ayanamsa="kp_new", node="mean")


@pytest.fixture(scope="module", autouse=True)
def _require_full_ephemeris(eph):
    """Skip under the Moshier fallback: these rows are sub-arcsecond exact."""
    if eph.precision != "full":
        pytest.skip(
            f"full Swiss Ephemeris files not present (precision={eph.precision!r})"
        )


@pytest.fixture(scope="module")
def output(eph) -> dict:
    chart = compute_chart(
        BirthInfo(
            date=datetime(2026, 10, 30).date(),
            time=time(12, 0, 0),
            latitude=18.4593067,
            longitude=73.8654709,
            tz_hours=5.5,
            place="Pune, India",
        ),
        ayanamsa="kp_new",
        node="mean",
        eph=eph,
        query_utc=datetime(2026, 10, 18, 12, 0, 0),
        horary_lagna=kp_divisions()[116].start_deg,
    )
    return chart_to_kp_stellar_json(
        chart,
        dasha_depth=5,
        query_utc=datetime(2026, 10, 18, 12, 0, 0),
        name="KPstellaroutput",
        gender="Male",
        horary_no=117,
        timezone="Asia/Kolkata",
    )


def test_all_nine_signifies_row_orders_match_the_reference(output):
    for key, want in EXPECTED_SIGNIFIES.items():
        got = output["planets"][key]["signifies"]
        assert got == want, f"{key}: {got} != {want}"


def test_all_twelve_cusps_all_four_tiers_match_the_reference(output):
    for house, want_tiers in EXPECTED_TIERS.items():
        got = output["cusps"][str(house)]["signifies_A_B_C_D"]
        for i, want in enumerate(want_tiers):
            assert got[i] == want, f"cusp {house}.{'ABCD'[i]}: {got[i]} != {want}"


def test_star_flagged_planets_are_exactly_the_reordered_rows(output):
    """The rule keys on the ``*`` flag: those three rows are the only ones
    whose group order differs from the old default -- here pinned so a
    future flag change cannot silently re-order rows."""
    starred = {
        key for key, planet in output["planets"].items() if "*" in planet["flags"]
    }
    assert starred == {"SUN", "MOO", "VEN"}
