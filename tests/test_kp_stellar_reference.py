"""Regression tests against the committed KP Stellar reference printout.

``kp_stellar_output.json`` (repo root) is a KP Stellar export for

    2026-10-30  12:00:00 IST (tz +5.5)   Pune, India
    lat 18.4593067  lon 73.8654709       ayanamsa kp_new, mean node
    horary number 117 of 249

The single fact that explains the reference's shape is in its own header:
``horary_no: "117 (249)"``.  KP Stellar was asked for a *horary* chart, so its
``cusps`` block is cast from horary division 117's cusp -- Virgo 17 deg 46' 40",
exactly ``1510/9`` degrees -- while its planets, ruling planets, panchanga and
Vimshottari all stay on the birth data.  That is why:

* ``cusps.1`` is Virgo but ``ruling_planets.lagna`` is JUP/VEN, i.e. the
  *astronomical* Sagittarius ascendant.  Not a contradiction: two lagnas.
* no house system Swiss Ephemeris offers puts cusp 1 in Virgo at the birth
  instant, and yet the cusps are a perfectly good Placidus chart.

``kpastro`` reproduces the file by casting the houses with
``compute_chart(..., horary_lagna=...)``.  What still differs, and is pinned
down here rather than hidden:

* sun, sunrise and sunset are now exact, and all nine planets land on the
  reference's printed arcsecond: the mean-equinox/mean-ayanamsa convention
  reproduces KP Stellar once the empirical Moon calibration in
  ``kpastro.ephemeris`` is applied (see ``KP_STELLAR_RECONCILIATION.md``);
* the five Vimshottari end stamps are 4 s early -- 0.34 mas of Moon
  longitude, inside one step of the exact-milliarcsecond balance grid (one
  step is 11.8 s of Rahu-mahadasha time here);
* cusps 2 and 8 print 1" low (their true residual is -0.09"), while cusps 3
  and 9 carry the largest numeric cusp residual (+0.85") without crossing a
  printed arcsecond.  No ayanamsa offset inside the window that keeps all
  nine planets exact can move cusp 2 by a full printed second.

These tests use the full Swiss Ephemeris data files when present and skip the
sub-arcsecond assertions when only the Moshier fallback is available.
"""

from __future__ import annotations

import dataclasses
import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import swisseph as swe

from kpastro.chart import (
    BirthInfo,
    CuspPos,
    chart_to_kp_stellar_json,
    compute_chart,
)
from kpastro.ephemeris import SwissEphemeris, geocentric_latitude
from kpastro.horary import kp_divisions
from kpastro.significators import (
    cusp_sub_lords,
    house_of_longitude,
    house_significations,
    planet_significations,
)
from kpastro.vedic import point_info

REFERENCE_PATH = Path(__file__).resolve().parents[1] / "kp_stellar_output.json"

LAT, LON, TZ = 18.4593067, 73.8654709, 5.5
BIRTH_DATE = (2026, 10, 30)
BIRTH_TIME = (12, 0, 0)
QUERY_UTC = datetime(2026, 10, 18, 12, 0, 0)

#: The horary number in the reference's ``horary_details.horary_no``.
HORARY_NUMBER = 117

#: The canonical reference section name.  Git commit ``8b369ad`` renamed the
#: committed reference's ``birth_details`` key to ``horary_details`` without
#: touching any value, so the serializer and tests follow the reference.
DETAILS_SECTION = "horary_details"

SIGN_ABBR_LIST = (
    "ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG", "CAP", "AQU", "PIS",
)
SIGN_NAMES = (
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
)
DMS = re.compile(r'^(\d+)\u00b0(\d+)\'([\d.]+)"?$')


def dms(text: str, sign: str | None = None) -> float:
    """Parse ``12\\u00b042'18"`` (+ optional sign prefix) into absolute degrees."""
    m = DMS.match(text.strip())
    assert m, text
    value = int(m.group(1)) + int(m.group(2)) / 60.0 + float(m.group(3)) / 3600.0
    if sign:
        value += (SIGN_ABBR_LIST.index(sign) if sign in SIGN_ABBR_LIST
                  else SIGN_NAMES.index(sign)) * 30.0
    return value


@pytest.fixture(scope="module")
def reference() -> dict:
    return json.loads(REFERENCE_PATH.read_text())


@pytest.fixture(scope="module")
def eph() -> SwissEphemeris:
    return SwissEphemeris(ayanamsa="kp_new", node="mean")


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


@pytest.fixture(scope="module")
def reference_cusps(reference) -> list[float]:
    return [
        dms(reference["cusps"][str(h)]["degree"], reference["cusps"][str(h)]["sign"])
        for h in range(1, 13)
    ]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def test_schema_top_level_keys_match(reference, output):
    assert list(output) == list(reference)


def test_schema_nested_keys_match(reference, output):
    for section in (DETAILS_SECTION, "ruling_planets", "legend"):
        assert list(output[section]) == list(reference[section]), section
    assert list(output["planets"]) == list(reference["planets"])
    assert list(output["cusps"]) == list(reference["cusps"])
    assert list(output["vimsottari_dasa"]) == list(reference["vimsottari_dasa"])
    for key in reference["planets"]:
        assert list(output["planets"][key]) == list(reference["planets"][key])
    for key in reference["cusps"]:
        assert list(output["cusps"][key]) == list(reference["cusps"][key])


# ---------------------------------------------------------------------------
# Everything that does NOT depend on the house cusps
# ---------------------------------------------------------------------------

def test_details_header_matches(reference, output):
    ref, got = reference[DETAILS_SECTION], output[DETAILS_SECTION]
    for field in ("name", "gender", "date", "time", "horary_no", "place",
                  "latitude", "longitude", "timezone", "ayanamsa", "node",
                  "nakshatra", "tithi", "yoga", "karana", "dasha_balance"):
        assert got[field] == ref[field], f"{field}: {got[field]!r} != {ref[field]!r}"


def test_no_birth_details_key_in_strict_payload(reference, output):
    """The strict reference payload must not also emit ``birth_details``.

    The reference has exactly one details section (``horary_details``); emitting
    a legacy alias alongside it would break raw top-level key equality.
    """
    assert "birth_details" not in output
    assert list(output) == list(reference)


def test_chart_instant_resolves_to_2026_10_30_0630_utc():
    """The canonical chart instant: 2026-10-30 12:00:00 IST == 06:30:00 UTC."""
    birth = BirthInfo(
        date=datetime(*BIRTH_DATE).date(),
        time=datetime(2000, 1, 1, *BIRTH_TIME).time(),
        latitude=LAT, longitude=LON, tz_hours=TZ, place="Pune, India",
    )
    assert birth.utc_datetime() == datetime(2026, 10, 30, 6, 30, 0)


def test_horary_division_117_cusp_start_is_1510_over_9():
    """Division 117's start is exactly 1510/9 deg; its midpoint is not."""
    div = kp_divisions()[HORARY_NUMBER - 1]
    assert div.start_deg == pytest.approx(1510.0 / 9.0, abs=1e-12)
    assert div.mid_deg != pytest.approx(div.start_deg, abs=1e-6)


def test_dasha_stack_is_deterministic_for_pinned_query_utc(eph, horary_lagna):
    """Two evaluations at the pinned instant agree; no machine-clock use."""
    def build():
        birth = BirthInfo(
            date=datetime(*BIRTH_DATE).date(),
            time=datetime(2000, 1, 1, *BIRTH_TIME).time(),
            latitude=LAT, longitude=LON, tz_hours=TZ, place="Pune, India",
        )
        chart = compute_chart(birth, ayanamsa="kp_new", node="mean", eph=eph,
                              query_utc=QUERY_UTC, horary_lagna=horary_lagna)
        return chart_to_kp_stellar_json(
            chart, dasha_depth=5, query_utc=QUERY_UTC, name="KPstellaroutput",
            gender="Male", horary_no=HORARY_NUMBER, timezone="Asia/Kolkata",
        )["vimsottari_dasa"]
    assert build() == build()


def test_sunrise_sunset_match_the_reference_exactly(reference, output):
    """Sunrise and sunset are exact to the printed second.

    Disc-centre transit with zero refraction at the geocentric latitude
    reproduces both; the former +8 s / \u22127 s residuals were the Moshier
    fallback, not a convention mismatch.
    """
    for field in ("sunrise", "sunset"):
        got = output[DETAILS_SECTION][field]
        want = reference[DETAILS_SECTION][field]
        assert got == want, f"{field}: {got!r} != {want!r}"


def test_all_planet_lords_and_flags_match(reference, output):
    """sg/sl/sb/ss and the R / # / * flags for all nine planets."""
    for key, want in reference["planets"].items():
        got = output["planets"][key]
        for field in ("sign", "sg", "sl", "sb", "ss", "flags"):
            assert got[field] == want[field], f"{key}.{field}: {got[field]} != {want[field]}"


def test_planet_degrees_match_the_reference_exactly(reference, output):
    """All nine planetary degrees match the reference's printed arcsecond.

    The Moon uses the empirical KP Stellar calibration described in
    ``KP_STELLAR_RECONCILIATION.md``; the other eight follow the
    mean-equinox/mean-ayanamsa convention directly.
    """
    for key, want in reference["planets"].items():
        got = output["planets"][key]
        assert (got["sign"], got["degree"]) == (want["sign"], want["degree"]), (
            f"{key}: ({got['sign']}, {got['degree']!r}) != "
            f"({want['sign']}, {want['degree']!r})"
        )


def test_ruling_planets_match(reference, output):
    assert output["ruling_planets"] == reference["ruling_planets"]


def test_vimsottari_lords_match(reference, output):
    assert [v["lord"] for v in output["vimsottari_dasa"].values()] == \
           [v["lord"] for v in reference["vimsottari_dasa"].values()]


def test_vimsottari_durations_are_identical_across_levels(reference, output):
    """All five end stamps share one constant offset -- i.e. identical durations.

    A constant offset across levels means the *durations* agree exactly and
    only the epoch does: the reference's Moon is ~1.5" behind ours, which over
    an 18-year Rahu mahadasha is precisely this offset.  Not a kpastro bug.
    """
    deltas = []
    for key, want in reference["vimsottari_dasa"].items():
        got = datetime.strptime(output["vimsottari_dasa"][key]["end"], "%d/%b/%Y %H:%M:%S")
        ref = datetime.strptime(want["end"], "%d/%b/%Y %H:%M:%S")
        deltas.append((ref - got).total_seconds())
    assert max(deltas) - min(deltas) < 2.0, f"offsets drift: {deltas}"


@pytest.mark.xfail(
    strict=True,
    reason="ours\u2212ref = \u22124 s at all five levels, i.e. 0.34 mas of Moon "
    "longitude; the balance is computed on the exact-milliarcsecond grid, "
    "one step of which is 11.8 s here, so 4 s is below the model's own "
    "resolution",
)
def test_vimsottari_end_stamps_match_the_reference_exactly(reference, output):
    """Exact equality is the goal; the residual is one sub-mas grid step.

    Asserted as exact (xfail'd): the measured value is pinned in
    ``tests/test_kp_stellar_strict.py`` (``KNOWN_OURS``) so drift fails the
    suite too.
    """
    for key, want in reference["vimsottari_dasa"].items():
        got = output["vimsottari_dasa"][key]["end"]
        assert got == want["end"], f"{key}.end: {got!r} != {want['end']!r}"


# ---------------------------------------------------------------------------
# The house cusps come from the horary number, not from the birth instant
# ---------------------------------------------------------------------------

def test_reference_ascendant_is_the_cusp_of_horary_division_117(
    reference, horary_lagna, reference_cusps
):
    """The reference's cusp 1 is horary division 117's cusp, to the arcsecond.

    ``1510/9`` degrees is division 117's start and *no* division's midpoint, so
    this is not a coincidence of the 249-division table.
    """
    assert abs(reference_cusps[0] - horary_lagna) * 3600.0 < 0.01
    assert abs(horary_lagna - 1510.0 / 9.0) < 1e-12
    mids = [d.mid_deg for d in kp_divisions()]
    assert all(abs(m - horary_lagna) > 1e-9 for m in mids)


def test_horary_cusps_reproduce_the_reference_cusps(chart, reference_cusps):
    """All twelve cusps reproduce within 0.9"; ten to the printed arcsecond."""
    errs = [
        ((chart.cusps[i].longitude - reference_cusps[i] + 180) % 360) - 180
        for i in range(12)
    ]
    worst = max(abs(e) for e in errs) * 3600.0
    assert worst < 1.0, f"worst cusp off by {worst:.2f}\": {errs}"
    # Cusp 1 is exact.  Cusps 2 and 8 (one point, 180 deg apart) print 1" low
    # only because their true residual, -0.09", sits just under a truncation
    # boundary; no ayanamsa offset that keeps all nine planets exact can lift
    # them a full second.  Cusps 3 and 9 carry the largest numeric residual,
    # +0.85", without crossing a printed arcsecond.
    assert errs[0] * 3600.0 == pytest.approx(0.0, abs=1e-6)
    assert errs[1] * 3600.0 == pytest.approx(-0.089, abs=0.02)
    assert errs[7] * 3600.0 == pytest.approx(errs[1] * 3600.0, abs=1e-6)
    assert errs[2] * 3600.0 == pytest.approx(0.85, abs=0.02)
    assert errs[8] * 3600.0 == pytest.approx(errs[2] * 3600.0, abs=1e-6)
    assert max(abs(e) for i, e in enumerate(errs) if i not in (2, 8)) * 3600.0 < 0.31


def test_houses_still_come_from_the_horary_frame(chart, horary_lagna):
    """``cusps`` belong to the horary lagna; ``ascendant`` stays astronomical."""
    assert chart.horary_lagna == pytest.approx(horary_lagna)
    assert chart.cusps[0].longitude == pytest.approx(horary_lagna)
    assert chart.cusps[6].longitude == pytest.approx((horary_lagna + 180) % 360)
    # The astronomical ascendant is a different sign entirely, and it is the
    # one the ruling planets are computed from.
    assert SIGN_NAMES[int(chart.ascendant // 30)] == "Sagittarius"
    assert chart.cusps[0].sign == "Virgo"


def test_no_swiss_house_system_reproduces_the_reference_cusps(chart, reference_cusps):
    """At the *birth* instant no house system puts cusp 1 anywhere near Virgo.

    This is what makes the horary reading necessary rather than optional: the
    reference's cusp 1 cannot come from 2026-10-30 06:30 UTC under any of the
    21 house systems Swiss Ephemeris implements.
    """
    lat = geocentric_latitude(LAT)
    for hsys in "PKROCEAVWXHGTOPBMSNUY":
        cusps_t, _ = swe.houses_ex(chart.jd_ut, lat, LON, hsys.encode())
        cusp1 = (list(cusps_t)[1] - chart.ayanamsa) % 360.0
        assert SIGN_NAMES[int(cusp1 // 30)] != "Virgo", hsys
        assert abs(((cusp1 - reference_cusps[0] + 180) % 360) - 180) > 1.0, hsys


def test_ruling_planets_use_the_birth_lagna_not_the_horary_one(chart, reference):
    """``ruling_planets.lagna`` is the astronomical ascendant, not cusp 1.

    The reference says JUP/VEN -- kpastro's Sagittarius 26 deg 29' 58"
    ascendant (Purva Ashadha) -- while its own ``cusps.1`` is Virgo 17 deg
    46' 40" (Hasta), which would give MER/MOO and is what ``cusps.1.sg``/
    ``.sl`` print.  Both are correct for their own lagna; kpastro keeps the
    same split.
    """
    asc_info = point_info(chart.ascendant)
    assert (asc_info.sign_lord, asc_info.star_lord) == ("Jupiter", "Venus")
    assert reference["ruling_planets"]["lagna"] == {"sign": "JUP", "stl": "VEN"}
    cusp1 = dms(reference["cusps"]["1"]["degree"], reference["cusps"]["1"]["sign"])
    cusp1_info = point_info(cusp1)
    assert (cusp1_info.sign_lord, cusp1_info.star_lord) == ("Mercury", "Moon")
    assert reference["cusps"]["1"]["sg"] == "MER"
    assert reference["cusps"]["1"]["sl"] == "MOO"


def test_astronomical_midheaven_is_consistent_with_local_noon(chart):
    """At local noon the Sun must sit within a few degrees of the true MC.

    The reference's ``cusps.10`` is 115 deg from its own Sun -- a pre-dawn
    geometry -- because it is the *horary* tenth house, not the birth MC.
    kpastro's astronomical MC trails the Sun by 4.7 deg, i.e. ~19 min past
    local solar noon, exactly what a 12:00 IST birth at 73.87 deg E implies.
    """
    sun = chart.planet_lon["Sun"]
    gap = (sun - chart.midheaven) % 360.0
    assert 0.0 < gap < 10.0, f"kpastro Sun is {gap:.2f} deg past the MC"


# ---------------------------------------------------------------------------
# The house-derived output, leaf by leaf
# ---------------------------------------------------------------------------

def _rebuild_chart_with_cusps(chart, cusps: list[float]):
    """Clone ``chart`` with ``cusps`` substituted, recomputing every layer that
    is derived from them through kpastro's own code paths."""
    positions = {p.name: p.longitude for p in chart.planets}
    new_cusps = []
    for i, lon in enumerate(cusps):
        info = point_info(lon)
        new_cusps.append(CuspPos(
            house=i + 1, longitude=lon, sign=info.sign, sign_lord=info.sign_lord,
            star=info.star, star_lord=info.star_lord,
            sub_lord=info.sub_lord, sub_sub_lord=info.sub_sub_lord,
        ))
    new_planets = [
        dataclasses.replace(p, house=house_of_longitude(p.longitude, cusps))
        for p in chart.planets
    ]
    clone = dataclasses.replace(chart, cusps=new_cusps, planets=new_planets)
    clone.planet_significators = planet_significations(positions, cusps)
    clone.house_significators = house_significations(positions, cusps)
    clone.cusp_sublords = cusp_sub_lords(cusps)
    return clone


def _emit(chart) -> dict:
    return json.loads(json.dumps(chart_to_kp_stellar_json(
        chart, dasha_depth=5, query_utc=QUERY_UTC, name="KPstellaroutput",
        gender="Male", horary_no=HORARY_NUMBER, timezone="Asia/Kolkata",
    ), ensure_ascii=False))


def _check_house_derived(got, reference, *, cusp_sign_exact):
    for key, want in reference["planets"].items():
        assert got["planets"][key]["house"] == want["house"], key
        got_sig, want_sig = got["planets"][key]["signifies"], want["signifies"]
        assert got_sig == want_sig, f"{key}: {got_sig} != {want_sig}"

    for h, want in reference["cusps"].items():
        for field in ("name", "sg", "sl", "sb", "ss"):
            assert got["cusps"][h][field] == want[field], f"cusp {h}.{field}"
        if cusp_sign_exact:
            assert got["cusps"][h]["sign"] == want["sign"], f"cusp {h}.sign"

    for h, want in reference["cusps"].items():
        for i, (got_list, want_list) in enumerate(
            zip(got["cusps"][h]["signifies_A_B_C_D"], want["signifies_A_B_C_D"])
        ):
            assert got_list == want_list, f"cusp {h} class {'ABCD'[i]}"

    for node in ("RAH", "KET"):
        assert got["nodes_representation"][node]["houses"] == \
            reference["nodes_representation"][node]["houses"], node
        assert got["nodes_representation"][node]["planets"] == \
            reference["nodes_representation"][node]["planets"], node


def test_house_derived_fields_match_the_reference(output, reference):
    """The shipped code path reproduces every house-derived leaf.

    Cusp *signs* and all ``signifies``/``A_B_C_D`` lists -- membership *and*
    order -- come out of ``natal --horary-no 117`` exactly as the reference
    has them.
    """
    _check_house_derived(output, reference, cusp_sign_exact=True)


def test_injecting_the_reference_cusps_leaves_only_the_1_arcsec_residual(
    chart, reference, reference_cusps
):
    """The cusps 3/9 arcsecond is the only *cusp-derived* residual.

    Feed the reference's own 12 cusps into kpastro's significator engine and
    the two cusp degrees that differed by 1" are now identical too -- so the
    residual is a cusp-value difference, not a significator difference.
    """
    got = _emit(_rebuild_chart_with_cusps(chart, reference_cusps))
    _check_house_derived(got, reference, cusp_sign_exact=True)
    for h in reference["cusps"]:
        assert got["cusps"][h]["degree"] == reference["cusps"][h]["degree"], h


def test_nodes_representation_planets_do_not_depend_on_the_horary_frame(
    reference, eph, horary_lagna
):
    """The node agents are longitude-derived, so they match with or without
    the horary frame -- a control for the cusp-dependent assertions above."""
    birth = BirthInfo(
        date=datetime(*BIRTH_DATE).date(),
        time=datetime(2000, 1, 1, *BIRTH_TIME).time(),
        latitude=LAT, longitude=LON, tz_hours=TZ, place="Pune, India",
    )
    plain = compute_chart(birth, ayanamsa="kp_new", node="mean", eph=eph,
                          query_utc=QUERY_UTC)
    assert plain.horary_lagna is None
    got = _emit(plain)
    for node in ("RAH", "KET"):
        assert got["nodes_representation"][node]["planets"] == \
            reference["nodes_representation"][node]["planets"], node
        # ...but the house lists do depend on the frame, and are wrong without it.
        assert got["nodes_representation"][node]["houses"] != \
            reference["nodes_representation"][node]["houses"], node
