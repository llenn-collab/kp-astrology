"""Regression checks for the set-5/set-6 Moon residual diagnosis.

These tests pin the measured constraints in the committed reference snapshots.
They deliberately do not apply a production longitude correction: the current
fixtures do not uniquely identify whether the remaining effect is an angular
offset, an epoch-dependent lunar-model difference, or a Moon-only time bias.
"""

from __future__ import annotations

from diagnositics.moon_alignment_sets_5_6 import (
    SECONDS_PER_ARCSECOND_SATURN_MD,
    dasha_end,
    moon_longitude,
    read_json,
    report_set,
)


def test_same_instant_reference_moon_is_location_independent(capsys):
    sholapur = read_json("kp_stellar_output4.json")
    delhi = read_json("kp_stellar_output5.json")

    assert moon_longitude(sholapur) == moon_longitude(delhi)
    assert dasha_end(sholapur, reference=True) == dasha_end(delhi, reference=True)


def test_sets_5_and_6_imply_the_same_2024_moon_correction(capsys):
    ref5 = read_json("kp_stellar_output5.json")
    actual5 = read_json("kpastro_actual5.json")
    ref6 = read_json("kp_stellar_output6.json")
    actual6 = read_json("kpastro_actual6.json")

    implied5, delta5 = report_set("set5", ref5, actual5)
    implied6, delta6 = report_set("set6", ref6, actual6)
    # Saturn MD end residuals are KP Astro later than KP Stellar. Moving the
    # Moon forward moves this absolute endpoint earlier.
    assert delta5 == 78_295
    assert delta6 == 78_621
    assert abs(implied5 - 6.267837) < 0.001
    assert abs(implied6 - 6.293935) < 0.001
    assert abs(implied5 - implied6) < 0.03
    assert abs(SECONDS_PER_ARCSECOND_SATURN_MD - 12_491.55) < 1e-8


def test_ninety_minute_pair_has_matching_lunar_motion(capsys):
    ref5 = read_json("kp_stellar_output5.json")
    actual5 = read_json("kpastro_actual5.json")
    ref6 = read_json("kp_stellar_output6.json")
    actual6 = read_json("kpastro_actual6.json")

    reference_speed = (moon_longitude(ref6) - moon_longitude(ref5)) * 3600 / 5400
    kpastro_speed = (
        moon_longitude(actual6) - moon_longitude(actual5)
    ) * 3600 / 5400

    assert abs(reference_speed - 0.5930) < 0.0001
    assert abs(kpastro_speed - 0.5928) < 0.0001
    assert abs(reference_speed - kpastro_speed) < 0.001
