"""Pin the empirical KP Stellar Moon calibration.

``kpastro.ephemeris`` applies a Moon-only correction for ``kp_new`` charts so
that the dasha end stamps line up with KP Stellar (see
``KP_STELLAR_RECONCILIATION.md`` Addendum B).  The correction is a *measured*
function, so these tests pin both its algebra and the four reference charts
it was derived from; anything that shifts it fails here rather than hiding in
a printed-degree comparison.

The reference values are the Moon corrections implied by the Vimshottari end
stamps, which resolve the Moon to ~0.0001" (one arcsecond of Moon longitude is
11,834.1 s of a Rahu mahadasha and 12,491.55 s of a Saturn mahadasha).  Sets 4
and 5 are the same instant at different latitudes, so they share one value.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from kpastro.chart import BirthInfo, chart_to_kp_stellar_json, compute_chart
from kpastro.ephemeris import SwissEphemeris
from kpastro.horary import kp_divisions

ROOT = Path(__file__).resolve().parents[1]

#: (label, date, IST time, lat, lon, horary no, query UTC, reference file)
SETS = [
    ("set4", "2024-06-01", "09:09:09", 17.64558, 75.899954, 57,
     "2026-10-19 07:26:41", "kp_stellar_output4.json"),
    ("set5", "2024-06-01", "09:09:09", 28.65195, 77.23149, 57,
     "2026-10-19 07:26:41", "kp_stellar_output5.json"),
    ("set6", "2024-06-01", "10:39:09", 17.64558, 75.899954, 69,
     "2026-10-19 06:25:04", "kp_stellar_output6.json"),
    ("set1", "2026-10-30", "12:00:00", 18.4593067, 73.8654709, 117,
     "2026-10-18 12:00:00", "kp_stellar_output.json"),
]

#: Moon correction implied by each chart's dasha end, in arcseconds.
MEASURED_CORRECTION_ARCSEC = {
    "set4": 6.2678,
    "set5": 6.2678,
    "set6": 6.2940,
    "set1": 8.2544,
}

#: Saturn and Rahu mahadasha sensitivity: seconds of dasha per arcsecond.
SECONDS_PER_ARCSEC = {"set4": 12491.55, "set5": 12491.55, "set6": 12491.55,
                      "set1": 11834.1}

#: A linear model cannot fit the 90-minute pair, which is 0.026" apart; the
#: rest must be within one milliarcsecond grid step (0.001").
TOLERANCE_ARCSEC = {"set4": 0.001, "set5": 0.001, "set6": 0.03, "set1": 0.001}


def _model_correction(jd_ut: float) -> float:
    from kpastro.ephemeris import (
        _MOON_CORRECTION_AT_REF_DEG,
        _MOON_CORRECTION_DRIFT_DEG_PER_DAY,
        _MOON_CORRECTION_JD_REF,
    )
    return (
        _MOON_CORRECTION_AT_REF_DEG
        + _MOON_CORRECTION_DRIFT_DEG_PER_DAY * (jd_ut - _MOON_CORRECTION_JD_REF)
    ) * 3600.0


def test_correction_is_zero_for_other_ayanamsas():
    """The calibration is KP Stellar-specific; other modes stay untouched."""
    jd = 2461343.770838
    kp_new = SwissEphemeris(ayanamsa="kp_new")
    kp = SwissEphemeris(ayanamsa="kp")
    assert kp_new._moon_correction(jd) > 0.0
    assert kp._moon_correction(jd) == 0.0


def test_correction_can_be_disabled(monkeypatch):
    """``_MOON_CORRECTION_ENABLED = False`` restores the raw Moon."""
    import kpastro.ephemeris as eph

    monkeypatch.setattr(eph, "_MOON_CORRECTION_ENABLED", False)
    assert SwissEphemeris(ayanamsa="kp_new")._moon_correction(2461343.770838) == 0.0


@pytest.mark.parametrize("label", ["set4", "set5", "set6", "set1"])
def test_model_matches_the_measured_correction(label):
    eph = SwissEphemeris(ayanamsa="kp_new")
    date, time_ = next((s[1], s[2]) for s in SETS if s[0] == label)
    birth = BirthInfo(
        date=datetime.strptime(date, "%Y-%m-%d").date(),
        time=datetime.strptime(time_, "%H:%M:%S").time(),
        latitude=0.0, longitude=0.0, tz_hours=5.5, place="x",
    )
    jd = eph.jd_ut(birth.utc_datetime())
    model = _model_correction(jd)
    assert model == pytest.approx(
        MEASURED_CORRECTION_ARCSEC[label], abs=TOLERANCE_ARCSEC[label]
    )


def _build(cfg):
    label, date, time_, lat, lon, horary_no, query, _ref = cfg
    eph = SwissEphemeris(ayanamsa="kp_new", node="mean")
    if eph.precision != "full":
        pytest.skip("full Swiss Ephemeris files not present")
    birth = BirthInfo(
        date=datetime.strptime(date, "%Y-%m-%d").date(),
        time=datetime.strptime(time_, "%H:%M:%S").time(),
        latitude=lat, longitude=lon, tz_hours=5.5, place="x",
    )
    instant = datetime.strptime(query, "%Y-%m-%d %H:%M:%S")
    chart = compute_chart(
        birth, ayanamsa="kp_new", node="mean", eph=eph, query_utc=instant,
        horary_lagna=kp_divisions()[horary_no - 1].start_deg,
    )
    return chart_to_kp_stellar_json(
        chart, dasha_depth=5, query_utc=instant, name="x", gender="Male",
        horary_no=horary_no, timezone="Asia/Kolkata",
    )


@pytest.mark.parametrize("cfg", SETS, ids=[s[0] for s in SETS])
def test_reference_chart_moon_and_dasha(cfg):
    """Each reference chart's printed Moon matches, and so does its dasha."""
    label = cfg[0]
    output = _build(cfg)
    reference = json.loads((ROOT / cfg[7]).read_text(encoding="utf-8"))

    if label == "set4":
        want_moon = reference["planets"]["MOO"]["deg"]
    elif label == "set6":
        want_moon = next(
            p["deg"] for p in reference["planets"] if p["pla"] == "MOO"
        )
    else:
        want_moon = reference["planets"]["MOO"]["degree"]
    assert output["planets"]["MOO"]["degree"] == want_moon

    # The dasha end is the precise constraint behind the calibration.  It is
    # quantised to milliarcseconds, so a few seconds of residual is expected.
    if label == "set4":
        want = reference["vimsottari"]["dasa"]["end"]
        fmt = "%Y-%m-%d %H:%M:%S"
    elif label == "set5":
        # "SAT: To 12/Aug/2039 (19:27:18)"
        stamp = reference["vimsottari_dasa"]["dasa"]
        want = stamp[stamp.index("To ") + 3:].replace(" (", " ").rstrip(")")
        fmt = "%d/%b/%Y %H:%M:%S"
    elif label == "set6":
        want = reference["vimsottari_dasha"]["dasa"]["end"]
        fmt = "%Y-%m-%d %H:%M:%S"
    else:
        want = reference["vimsottari_dasa"]["dasa"]["end"]
        fmt = "%d/%b/%Y %H:%M:%S"
    got = datetime.strptime(output["vimsottari_dasa"]["dasa"]["end"],
                            "%d/%b/%Y %H:%M:%S")
    delta = abs((got - datetime.strptime(want, fmt)).total_seconds())
    budget = TOLERANCE_ARCSEC[label] * SECONDS_PER_ARCSEC[label]
    assert delta < budget, (
        f"{label}: dasha end off by {delta:.0f} s "
        f"({delta / SECONDS_PER_ARCSEC[label]:.3f}\"), budget {budget:.0f} s"
    )
