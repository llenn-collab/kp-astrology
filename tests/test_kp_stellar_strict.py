"""Strict leaf-by-leaf comparison against the committed KP Stellar reference.

Builds the pinned chart in-process (same fixtures as
``test_kp_stellar_reference.py``: 2026-10-30 12:00 IST Pune, ayanamsa kp_new,
mean node, horary number 117, query 2026-10-18 12:00 UTC) and flattens both
documents into ``{json-path: leaf}`` maps -- dicts via ``.key``, list items
via ``[i]``, empty containers treated as leaves (paths mirror
``diagnositics/jdiff.py``; 322 leaves per document).

Every leaf must be **exactly** equal to the reference (same value *and* same
type) unless it is one of the 18 residuals enumerated in ``KNOWN_RESIDUALS``.
Each residual is its own ``xfail(strict=True)`` case carrying its measured
value, so fixing one flips the suite to failure and forces this table to be
updated.  ``test_exactly_eighteen_leaves_differ`` guards the other direction:
a new residual anywhere in the document fails loudly.

The residuals (ours minus reference) are documented in:

* ``diagnositics/findings_planets_dasha.md`` -- nine planetary degrees and
  the five Vimshottari end stamps;
* ``diagnositics/findings_cusp_sunrise.md`` -- sunrise/sunset and cusps 3/9.

The sub-arcsecond comparisons are only meaningful with the full Swiss
Ephemeris files; the module skips when the Moshier fallback would be used.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from kpastro.chart import BirthInfo, chart_to_kp_stellar_json, compute_chart
from kpastro.ephemeris import SwissEphemeris
from kpastro.horary import kp_divisions

REFERENCE_PATH = Path(__file__).resolve().parents[1] / "kp_stellar_output.json"

LAT, LON, TZ = 18.4593067, 73.8654709, 5.5
BIRTH_DATE = (2026, 10, 30)
BIRTH_TIME = (12, 0, 0)
QUERY_UTC = datetime(2026, 10, 18, 12, 0, 0)

#: The horary number in the reference's ``horary_details.horary_no``.
HORARY_NUMBER = 117

#: The canonical reference section name (see ``test_kp_stellar_reference.py``).
DETAILS_SECTION = "horary_details"

#: Every leaf known to differ from the reference, with its measured residual.
#: No others may exist: ``test_exactly_eighteen_leaves_differ`` asserts the
#: actual difference set is exactly this set, so any new or resolved residual
#: fails the suite.
KNOWN_RESIDUALS: dict[str, str] = {
    "$.horary_details.sunrise": (
        "ours\u2212ref = +8 s (06:36:56 vs 06:36:48); no documented "
        "atmosphere/horizon convention reproduces rise and set together; "
        "see diagnositics/findings_cusp_sunrise.md"
    ),
    "$.horary_details.sunset": (
        "ours\u2212ref = \u22127 s (17:59:15 vs 17:59:22); same finding as "
        "sunrise; see diagnositics/findings_cusp_sunrise.md"
    ),
    "$.vimsottari_dasa.dasa.end": (
        "ours\u2212ref = \u22122 h 58 m 58 s (\u221210,738 s; reference later, "
        "constant at all five levels: same durations, dasha-implied Moon "
        "longitude residual \u22120.907\u2033); "
        "see diagnositics/findings_planets_dasha.md"
    ),
    "$.vimsottari_dasa.bhukti.end": (
        "ours\u2212ref = \u22122 h 58 m 58 s (\u221210,738 s; constant at all "
        "five levels); see diagnositics/findings_planets_dasha.md"
    ),
    "$.vimsottari_dasa.antara.end": (
        "ours\u2212ref = \u22122 h 58 m 58 s (\u221210,738 s; constant at all "
        "five levels); see diagnositics/findings_planets_dasha.md"
    ),
    "$.vimsottari_dasa.sookshma.end": (
        "ours\u2212ref = \u22122 h 58 m 58 s (\u221210,738 s; constant at all "
        "five levels); see diagnositics/findings_planets_dasha.md"
    ),
    "$.vimsottari_dasa.prana.end": (
        "ours\u2212ref = \u22122 h 58 m 58 s (\u221210,738 s; constant at all "
        "five levels); see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.SUN.degree": (
        "ours\u2212ref = +9.22\u2033 (printed 12\u00b042'27\" vs 12\u00b042'18\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.MOO.degree": (
        "ours\u2212ref = +1.53\u2033 (printed 08\u00b031'51\" vs 08\u00b031'49\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.MAR.degree": (
        "ours\u2212ref = +9.68\u2033 (printed 23\u00b036'18\" vs 23\u00b036'08\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.RAH.degree": (
        "ours\u2212ref = +9.48\u2033 (printed 02\u00b001'26\" vs 02\u00b001'17\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.JUP.degree": (
        "ours\u2212ref = +9.57\u2033 (printed 29\u00b058'07\" vs 29\u00b057'57\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.SAT.degree": (
        "ours\u2212ref = +9.76\u2033 (printed 15\u00b015'21\" vs 15\u00b015'11\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.MER.degree": (
        "ours\u2212ref = +9.84\u2033 (printed 24\u00b014'50\" vs 24\u00b014'40\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.KET.degree": (
        "ours\u2212ref = +9.48\u2033 (printed 02\u00b001'26\" vs 02\u00b001'17\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.planets.VEN.degree": (
        "ours\u2212ref = +10.13\u2033 (printed 03\u00b000'16\" vs 03\u00b000'06\"); "
        "convention unknown; see diagnositics/findings_planets_dasha.md"
    ),
    "$.cusps.3.degree": (
        "ours\u2212ref = +0.883\u2033 (prints 17\u00b020'11\" vs 17\u00b020'10\"); "
        "no documented Swiss Ephemeris option moves cusp 3 alone; "
        "see diagnositics/findings_cusp_sunrise.md"
    ),
    "$.cusps.9.degree": (
        "ours\u2212ref = +0.883\u2033 (prints 17\u00b020'11\" vs 17\u00b020'10\"); "
        "cusp 9 is cusp 3 + 180 deg, one solve; "
        "see diagnositics/findings_cusp_sunrise.md"
    ),
}

#: Sentinel for "no leaf at this path" in either document.
_MISSING = object()

#: kpastro's *current* value for each residual path, pinned so drift is
#: caught: ``test_exactly_eighteen_leaves_differ`` (not xfail'd) asserts
#: these, because an ``xfail(strict=True)`` alone cannot distinguish "still
#: the recorded residual" from "a different residual at the same path".
KNOWN_OURS: dict[str, object] = {
    "$.horary_details.sunrise": "06:36:56",
    "$.horary_details.sunset": "17:59:15",
    "$.vimsottari_dasa.dasa.end": "24/Apr/2042 20:48:36",
    "$.vimsottari_dasa.bhukti.end": "05/Jan/2027 13:00:36",
    "$.vimsottari_dasa.antara.end": "09/Nov/2026 00:21:54",
    "$.vimsottari_dasa.sookshma.end": "22/Oct/2026 05:01:21",
    "$.vimsottari_dasa.prana.end": "18/Oct/2026 17:36:31",
    "$.planets.SUN.degree": "12\u00b042'27\"",
    "$.planets.MOO.degree": "08\u00b031'51\"",
    "$.planets.MAR.degree": "23\u00b036'18\"",
    "$.planets.RAH.degree": "02\u00b001'26\"",
    "$.planets.JUP.degree": "29\u00b058'07\"",
    "$.planets.SAT.degree": "15\u00b015'21\"",
    "$.planets.MER.degree": "24\u00b014'50\"",
    "$.planets.KET.degree": "02\u00b001'26\"",
    "$.planets.VEN.degree": "03\u00b000'16\"",
    "$.cusps.3.degree": "17\u00b020'11\"",
    "$.cusps.9.degree": "17\u00b020'11\"",
}


# ---------------------------------------------------------------------------
# Fixtures: the pinned chart, built in-process
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def reference() -> dict:
    return json.loads(REFERENCE_PATH.read_text())


@pytest.fixture(scope="module")
def eph() -> SwissEphemeris:
    return SwissEphemeris(ayanamsa="kp_new", node="mean")


@pytest.fixture(scope="module", autouse=True)
def _require_full_ephemeris(eph):
    """Skip under the Moshier fallback: residuals here are sub-arcsecond."""
    if eph.precision != "full":
        pytest.skip(
            f"full Swiss Ephemeris files not present (precision={eph.precision!r})"
        )


@pytest.fixture(scope="module")
def horary_lagna(reference) -> float:
    """The lagna KP Stellar used: the cusp of horary division 117."""
    recorded = int(reference[DETAILS_SECTION]["horary_no"].split()[0])
    assert recorded == HORARY_NUMBER
    return kp_divisions()[HORARY_NUMBER - 1].start_deg


@pytest.fixture(scope="module")
def chart(eph, horary_lagna):
    birth = BirthInfo(
        date=datetime(*BIRTH_DATE).date(),
        time=datetime(2000, 1, 1, *BIRTH_TIME).time(),
        latitude=LAT,
        longitude=LON,
        tz_hours=TZ,
        place="Pune, India",
    )
    return compute_chart(
        birth, ayanamsa="kp_new", node="mean", eph=eph,
        # Pinned so the Sookshma/Prana levels are stable: KP Stellar resolves
        # the stack at the moment of the query, not at birth.
        query_utc=QUERY_UTC,
        horary_lagna=horary_lagna,
    )


@pytest.fixture(scope="module")
def output(chart) -> dict:
    return json.loads(json.dumps(chart_to_kp_stellar_json(
        chart,
        dasha_depth=5,
        query_utc=QUERY_UTC,
        name="KPstellaroutput",
        gender="Male",
        horary_no=HORARY_NUMBER,
        timezone="Asia/Kolkata",
    ), ensure_ascii=False))


# ---------------------------------------------------------------------------
# Leaf flattening and type-aware comparison
# ---------------------------------------------------------------------------

def _leaves(doc, path="$") -> dict:
    """Flatten a JSON document to ``{path: leaf}``.

    Scalars are leaves; so are empty dicts/lists (so a type change on an
    empty container is still caught).  Dict keys append ``.key`` and list
    items append ``[i]`` -- paths match ``diagnositics/jdiff.py``.
    """
    if isinstance(doc, dict):
        if not doc:
            return {path: doc}
        out = {}
        for key, value in doc.items():
            out.update(_leaves(value, f"{path}.{key}"))
        return out
    if isinstance(doc, list):
        if not doc:
            return {path: doc}
        out = {}
        for i, value in enumerate(doc):
            out.update(_leaves(value, f"{path}[{i}]"))
        return out
    return {path: doc}


def _is_exact(ours, reference) -> bool:
    """Exact equality: same value *and* same type (so ``1 == 1.0`` differs)."""
    return type(ours) is type(reference) and ours == reference


@pytest.fixture(scope="module")
def leaf_maps(reference, output) -> tuple[dict, dict]:
    return _leaves(reference), _leaves(output)


def _differing_leaves(ref_leaves: dict, out_leaves: dict) -> list[str]:
    return sorted(
        path
        for path in set(ref_leaves) | set(out_leaves)
        if not _is_exact(out_leaves.get(path, _MISSING),
                         ref_leaves.get(path, _MISSING))
    )


# ---------------------------------------------------------------------------
# The whole document, leaf by leaf
# ---------------------------------------------------------------------------

def test_exactly_eighteen_leaves_differ(leaf_maps):
    """Every leaf is exactly equal except the 18 recorded residuals.

    A new residual anywhere -- value, type, missing or extra key -- fails
    here loudly, as does a residual that has been (partially) fixed.
    """
    ref_leaves, out_leaves = leaf_maps
    diffs = _differing_leaves(ref_leaves, out_leaves)
    assert len(diffs) == 18, (
        f"{len(diffs)} differing leaves, expected 18:\n" + "\n".join(diffs)
    )
    assert set(diffs) == set(KNOWN_RESIDUALS), (
        "unexpected new differences: "
        f"{sorted(set(diffs) - set(KNOWN_RESIDUALS))}; "
        "residuals that disappeared (update KNOWN_RESIDUALS and the "
        f"strict-xfail cases): {sorted(set(KNOWN_RESIDUALS) - set(diffs))}"
    )
    drifted = {
        path: (out_leaves.get(path, _MISSING), want)
        for path, want in KNOWN_OURS.items()
        if out_leaves.get(path, _MISSING) != want
    }
    assert not drifted, (
        "residual values drifted from the recorded measurements (re-measure, "
        f"then update KNOWN_OURS and the reason strings): {drifted}"
    )


#: One xfail(strict=True) parametrised case per known residual: the
#: assertion states the desired end state (exact equality), which currently
#: fails.  If a residual is ever fixed the case XPASSes and strict mode
#: turns that into a failure, forcing this table to be updated.
@pytest.mark.parametrize(
    "path",
    [
        pytest.param(
            path,
            id=path.removeprefix("$.").replace(".", "_").replace("[", "_").replace("]", ""),
            marks=pytest.mark.xfail(strict=True, reason=reason),
        )
        for path, reason in KNOWN_RESIDUALS.items()
    ],
)
def test_known_residual_leaf(path, leaf_maps):
    ref_leaves, out_leaves = leaf_maps
    ours = out_leaves.get(path, _MISSING)
    want = ref_leaves.get(path, _MISSING)
    assert _is_exact(ours, want), f"{path}: ours {ours!r} != reference {want!r}"
