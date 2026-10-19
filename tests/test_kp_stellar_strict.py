"""Strict leaf-by-leaf comparison against the committed KP Stellar reference.

Builds the pinned chart in-process (same fixtures as
``test_kp_stellar_reference.py``: 2026-10-30 12:00 IST Pune, ayanamsa kp_new,
mean node, horary number 117, query 2026-10-18 12:00 UTC) and flattens both
documents into ``{json-path: leaf}`` maps -- dicts via ``.key``, list items
via ``[i]``, empty containers treated as leaves (paths mirror
``diagnositics/jdiff.py``; 322 leaves per document).

Every leaf must be **exactly** equal to the reference (same value *and* same
type) unless it is one of the 7 residuals enumerated in ``KNOWN_RESIDUALS``.
Each residual is its own ``xfail(strict=True)`` case carrying its measured
value, so fixing one flips the suite to failure and forces this table to be
updated.  ``test_exactly_seven_leaves_differ`` guards the other direction:
a new residual anywhere in the document fails loudly.

All nine planet degrees, sunrise and sunset are now exact.  What remains is
sub-arcsecond house geometry and the milliarcsecond quantisation of the dasha
core:

* ``$.cusps.2.degree`` / ``$.cusps.8.degree`` -- kpastro prints 1" lower than
  KP Stellar; every other cusp (including the Ascendant) is exact.
* the five Vimshottari end stamps -- 4 s earlier, i.e. 0.34 mas of Moon
  longitude; the balance is computed on the exact-mas grid, one step of which
  is 11.8 s of Rahu-mahadasha time here.

See ``KP_STELLAR_RECONCILIATION.md`` for the calibration that removed the
former 9-10" planetary residuals and 2 h 59 m dasha residual.

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
#: No others may exist: ``test_exactly_seven_leaves_differ`` asserts the
#: actual difference set is exactly this set, so any new or resolved residual
#: fails the suite.
KNOWN_RESIDUALS: dict[str, str] = {
    "$.vimsottari_dasa.dasa.end": (
        "ours\u2212ref = \u22124 s (23:47:30 vs 23:47:34); the balance is "
        "quantised to exact milliarcseconds, one step of which is 11.8 s of "
        "Rahu-mahadasha time, so \u22124 s is inside a single grid step; "
        "see KP_STELLAR_RECONCILIATION.md"
    ),
    "$.vimsottari_dasa.bhukti.end": (
        "ours\u2212ref = \u22124 s (15:59:30 vs 15:59:34); same "
        "milliarcsecond grid step at every level"
    ),
    "$.vimsottari_dasa.antara.end": (
        "ours\u2212ref = \u22124 s (03:20:48 vs 03:20:52); same "
        "milliarcsecond grid step at every level"
    ),
    "$.vimsottari_dasa.sookshma.end": (
        "ours\u2212ref = \u22124 s (08:00:15 vs 08:00:19); same "
        "milliarcsecond grid step at every level"
    ),
    "$.vimsottari_dasa.prana.end": (
        "ours\u2212ref = \u22124 s (20:35:25 vs 20:35:29); same "
        "milliarcsecond grid step at every level"
    ),
    "$.cusps.2.degree": (
        "ours\u2212ref < 1\u2033 (prints 17\u00b021'11\" vs 17\u00b021'12\"); "
        "cusp 1 is exact, so this is Placidus intermediate-cusp geometry, "
        "not the ayanamsa: the whole ayanamsa window that keeps all nine "
        "planets exact cannot lift cusp 2 by a full arcsecond"
    ),
    "$.cusps.8.degree": (
        "ours\u2212ref < 1\u2033 (prints 17\u00b021'11\" vs 17\u00b021'12\"); "
        "cusp 8 is cusp 2 + 180 deg, so it shares the same single solve"
    ),
}

#: Sentinel for "no leaf at this path" in either document.
_MISSING = object()

#: kpastro's *current* value for each residual path, pinned so drift is
#: caught: ``test_exactly_seven_leaves_differ`` (not xfail'd) asserts
#: these, because an ``xfail(strict=True)`` alone cannot distinguish "still
#: the recorded residual" from "a different residual at the same path".
KNOWN_OURS: dict[str, object] = {
    "$.vimsottari_dasa.dasa.end": "24/Apr/2042 23:47:30",
    "$.vimsottari_dasa.bhukti.end": "05/Jan/2027 15:59:30",
    "$.vimsottari_dasa.antara.end": "09/Nov/2026 03:20:48",
    "$.vimsottari_dasa.sookshma.end": "22/Oct/2026 08:00:15",
    "$.vimsottari_dasa.prana.end": "18/Oct/2026 20:35:25",
    "$.cusps.2.degree": "17\u00b021'11\"",
    "$.cusps.8.degree": "17\u00b021'11\"",
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

def test_exactly_seven_leaves_differ(leaf_maps):
    """Every leaf is exactly equal except the 7 recorded residuals.

    A new residual anywhere -- value, type, missing or extra key -- fails
    here loudly, as does a residual that has been (partially) fixed.
    """
    ref_leaves, out_leaves = leaf_maps
    diffs = _differing_leaves(ref_leaves, out_leaves)
    assert len(diffs) == 7, (
        f"{len(diffs)} differing leaves, expected 7:\n" + "\n".join(diffs)
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
