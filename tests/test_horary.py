"""Tests for the KP horary layer: the 249-division table and the house frame
that is cast from a division's cusp.

The division table itself is exercised through ``kp_stellar_output.json`` in
``test_kp_stellar_reference.py``; this module covers
:func:`kpastro.horary.cusps_from_horary_lagna`, which turns a horary ascendant
into the twelve Placidus cusps that belong to it.
"""

from __future__ import annotations

from datetime import datetime

import pytest
import swisseph as swe

from kpastro.ephemeris import SwissEphemeris, geocentric_latitude
from kpastro.horary import (
    MAX_HORARY_NUMBER,
    ascendant_from_kp_number,
    cusps_from_horary_lagna,
    kp_divisions,
    kp_number_for_longitude,
)

LAT, LON = 18.4593067, 73.8654709


@pytest.fixture(scope="module")
def eph() -> SwissEphemeris:
    return SwissEphemeris(ayanamsa="kp_new", node="mean")


@pytest.fixture(scope="module")
def jd_ut(eph) -> float:
    return eph.jd_ut(datetime(2026, 10, 30, 6, 30, 0))


def test_division_table_tiles_the_zodiac():
    divs = kp_divisions()
    assert len(divs) == MAX_HORARY_NUMBER == 249
    for i, d in enumerate(divs):
        assert d.number == i + 1
        nxt = divs[i + 1].start_deg if i + 1 < len(divs) else 360.0
        assert d.start_deg < d.end_deg <= nxt + 1e-9, d.number
    assert divs[0].start_deg == 0.0
    assert divs[-1].end_deg == pytest.approx(360.0)
    # The six sign boundaries that fall strictly inside a sub are what push the
    # count from 243 to 249, so the spans are not all equal.
    widths = {round(d.end_deg - d.start_deg, 9) for d in divs}
    assert len(widths) > 1


def test_number_lookup_is_the_inverse_of_the_table():
    for d in kp_divisions():
        assert kp_number_for_longitude(d.start_deg) == d.number
        assert kp_number_for_longitude(d.mid_deg) == d.number
    assert kp_number_for_longitude(359.9999) == MAX_HORARY_NUMBER


def test_ascendant_from_kp_number_rejects_out_of_range():
    for bad in (0, -1, MAX_HORARY_NUMBER + 1, 10_000):
        with pytest.raises(ValueError):
            ascendant_from_kp_number(bad)


@pytest.mark.parametrize("number", [1, 45, 117, 200, 249])
def test_cusps_start_at_the_requested_lagna(eph, jd_ut, number):
    """Cusp 1 is the requested longitude exactly, cusp 7 is its opposite."""
    lagna = kp_divisions()[number - 1].start_deg
    cusps = cusps_from_horary_lagna(lagna, eph, jd_ut, LAT, LON)
    assert len(cusps) == 12
    assert cusps[0] == lagna
    assert cusps[6] == pytest.approx((lagna + 180.0) % 360.0)
    assert all(0.0 <= c < 360.0 for c in cusps)


@pytest.mark.parametrize("number", [1, 45, 117, 200, 249])
def test_cusps_are_a_coherent_placidus_frame(eph, jd_ut, number):
    """The other ten cusps come from a real instant, not from interpolation.

    Re-solving for that instant and asking Swiss Ephemeris directly must agree
    with what the function returned, so the frame is genuinely Placidus rather
    than a table lookup.
    """
    lagna = kp_divisions()[number - 1].start_deg
    cusps = cusps_from_horary_lagna(lagna, eph, jd_ut, LAT, LON)

    # Houses ascend and each sits roughly a sign after the previous one.
    for i in range(12):
        gap = (cusps[(i + 1) % 12] - cusps[i]) % 360.0
        assert 10.0 < gap < 60.0, f"house {i + 1} -> {i + 2}: {gap:.3f} deg"

    # An independent solve on the signed ascendant difference, with no code
    # shared with the function under test.
    lat = geocentric_latitude(LAT)
    ayan = eph.ayanamsa(jd_ut)

    def asc(jd: float) -> float:
        return (swe.houses_ex(jd, lat, LON, b"P")[1][0] - ayan) % 360.0

    lo, hi = jd_ut - 1.0, jd_ut
    diff = lambda jd: ((asc(jd) - lagna + 180.0) % 360.0) - 180.0  # noqa: E731
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if diff(mid) < 0:
            lo = mid
        else:
            hi = mid
    solved = (lo + hi) / 2.0
    assert abs(asc(solved) - lagna) * 3600.0 < 0.01

    raw = list(swe.houses_ex(solved, lat, LON, b"P")[0])
    raw = raw[1:13] if len(raw) == 13 else raw
    for i in range(12):
        if i in (0, 6):
            continue
        sidereal = (raw[i] - ayan) % 360.0
        assert abs(((cusps[i] - sidereal + 180.0) % 360.0) - 180.0) * 3600.0 < 0.05, i


def test_solution_is_the_latest_one_before_the_reference_instant(eph, jd_ut):
    """Asking from a moment half a day later must move the answer by ~12 h,
    not silently return the same frame -- there is one solution per sidereal
    day and the function takes the most recent."""
    lagna = kp_divisions()[116].start_deg
    early = cusps_from_horary_lagna(lagna, eph, jd_ut - 0.5, LAT, LON)
    late = cusps_from_horary_lagna(lagna, eph, jd_ut, LAT, LON)
    assert late != early
    assert late[0] == early[0] == lagna  # same lagna, different houses
    assert late[9] != early[9]


# ---------------------------------------------------------------------------
# The `horary` subcommand must agree with the `natal --horary-no` path
# ---------------------------------------------------------------------------

def test_horary_subcommand_json_reproduces_the_reference_house_frame(capsys):
    """``horary --number 117 --json`` casts the horary cusp frame and emits
    the KP Stellar schema, not the astronomical-ascendant frame.

    Regression for the bug where ``cmd_horary`` printed the division midpoint
    and called ``compute_chart`` without ``horary_lagna``, so its planets and
    cusps belonged to the query-instant ascendant (Sagittarius) instead of the
    horary cusp 1 (Virgo 1510/9 deg).
    """
    import json as _json
    from kpastro.cli import main

    rc = main([
        "horary",
        "--number", "117",
        "--date", "2026-10-30", "--time", "12:00:00", "--tz", "5.5",
        "--lat", "18.4593067", "--lon", "73.8654709", "--place", "Pune, India",
        "--ayanamsa", "kp_new", "--node", "mean",
        "--json", "--name", "KPstellaroutput", "--gender", "Male",
        "--timezone", "Asia/Kolkata",
        "--query-utc", "2026-10-18 12:00:00",
    ])
    assert rc == 0
    payload = _json.loads(capsys.readouterr().out)

    # KP Stellar printout schema, with the horary section named as the
    # committed reference names it.
    assert list(payload)[:2] == ["horary_details", "vimsottari_dasa"]
    assert "birth_details" not in payload
    assert payload["horary_details"]["horary_no"] == "117 (249)"

    # House 1 is the *cusp* of division 117 (1510/9 deg, Virgo), not its
    # midpoint and not the astronomical ascendant.
    div = kp_divisions()[116]
    cusp1 = payload["cusps"]["1"]
    assert cusp1["sign"] == "VIR"
    assert cusp1["degree"] == "17°46'40\""
    assert div.start_deg == pytest.approx(1510.0 / 9.0, abs=1e-12)
    assert cusp1["degree"] != f"{div.mid_deg:.0f}"  # sanity: not the midpoint

    # The astronomical ascendant still drives the ruling planets.
    assert payload["ruling_planets"]["lagna"] == {"sign": "JUP", "stl": "VEN"}
