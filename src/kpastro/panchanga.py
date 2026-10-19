"""Panchanga layer: sunrise/sunset, tithi, nitya yoga, karana, nakshatra.

These are the five "limbs" that KP Stellar prints in the birth-details header
next to the KP data.  They are *derived* quantities, not new astronomy:

* **tithi** and **karana** are pure functions of the Sun-Moon elongation, so
  they are invariant to the ayanamsa (both longitudes shift together).
* **yoga** is the nakshatra-sized division of ``Sun + Moon``, which *does*
  depend on the ayanamsa (it moves by twice the ayanamsa), so it must be fed
  sidereal longitudes.
* **nakshatra/pada** of the Moon is the same star the KP dasha balance is
  anchored to.
* **sunrise/sunset** come from Swiss Ephemeris' ``rise_trans`` on the
  Sun's **disc centre with no refraction** -- the convention used by Hindu
  panchangas (and by KP Stellar), which puts the event ~2 min earlier than the
  meteorological "upper limb + standard refraction" definition.

All longitudes passed in here are **sidereal degrees** in ``[0, 360)``.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

import swisseph as swe

from .constants import (
    KARANA_FIXED_TAIL,
    KARANA_NAMES,
    NAKSHATRAS,
    TITHI_NAMES,
    WEEKDAY_LORDS,
    YOGA_NAMES,
)
from .dasha import DAYS_PER_YEAR
from .vedic import normalize_longitude, pada_info, star_index

__all__ = [
    "sunrise_sunset",
    "tithi",
    "nitya_yoga",
    "karana",
    "nakshatra_pada",
    "day_lord",
    "dasha_balance_str",
]

#: Seconds of arc in one nakshatra (13 deg 20') and one yoga step.
NAKSHATRA_SPAN_DEG: float = 360.0 / 27.0

#: KP Stellar renders the dasha balance with a 365.25-day year and a flat
#: 30-day month (``dasha.format_days`` uses the 30.4375-day month instead --
#: a different, equally defensible convention that is kept as-is).
BALANCE_DAYS_PER_MONTH: float = 30.0


# ---------------------------------------------------------------------------
# Sunrise / sunset
# ---------------------------------------------------------------------------

def sunrise_sunset(
    jd_ut: float,
    latitude: float,
    longitude: float,
    tz_hours: float = 0.0,
    elevation: float = 0.0,
) -> tuple[Optional[float], Optional[float]]:
    """Julian dates (UT) of the sunrise and sunset of the local day of ``jd_ut``.

    ``jd_ut`` must be **local midnight of that day expressed in UT** (that is
    what :func:`kpastro.chart._horary_details` passes).  Returns
    ``(None, None)`` in the polar day/night cases where no event exists.

    ``swe.rise_trans`` returns the *first* event at or after the search
    instant, so each event needs its own window or the sunset of the previous
    afternoon is reported for today:

    * sunrise sits ~0.25 d after local midnight -> search from 0.5 d earlier;
    * sunset sits ~0.75 d after local midnight -> search from 0.2 d earlier
      (yesterday's ~18:00 sunset is then already behind the start instant).

    ``geopos`` is handed to Swiss Ephemeris in its native
    ``(longitude, latitude, elevation)`` order -- the reverse of the
    ``(lat, lon)`` order used everywhere else in this library.
    """
    from .ephemeris import geocentric_latitude
    geo = (longitude, geocentric_latitude(latitude), elevation)
    flags = swe.BIT_DISC_CENTER | swe.BIT_NO_REFRACTION
    out = []
    for event, backoff in ((swe.CALC_RISE, 0.5), (swe.CALC_SET, 0.2)):
        result = swe.rise_trans(jd_ut - backoff, swe.SUN, event | flags, geo, 0.0, 10.0)
        jd_event = float(result[1][0]) if result[1] else 0.0
        out.append(jd_event if jd_event > 0 else None)
    return out[0], out[1]


def _jd_to_clock(jd_ut: Optional[float], tz_hours: float) -> Optional[str]:
    """Render a Julian date (UT) as ``HH:MM:SS`` local wall time."""
    if jd_ut is None:
        return None
    year, month, day, hour = swe.revjul(jd_ut + tz_hours / 24.0)
    hh = int(hour)
    mm = int((hour - hh) * 60.0)
    ss = int((((hour - hh) * 60.0) - mm) * 60.0 + 1e-6)   # KP Stellar truncates seconds
    if ss == 60:                      # 23:59:59.6 must not render as ...:60
        ss = 0
        mm += 1
    if mm == 60:
        mm = 0
        hh = (hh + 1) % 24
    return f"{hh:02d}:{mm:02d}:{ss:02d}"


def sunrise_sunset_clock(
    jd_ut: float,
    latitude: float,
    longitude: float,
    tz_hours: float = 0.0,
    elevation: float = 0.0,
) -> tuple[Optional[str], Optional[str]]:
    """``(sunrise, sunset)`` as local ``HH:MM:SS`` strings."""
    rise, sett = sunrise_sunset(jd_ut, latitude, longitude, tz_hours, elevation)
    return _jd_to_clock(rise, tz_hours), _jd_to_clock(sett, tz_hours)


# ---------------------------------------------------------------------------
# Tithi / yoga / karana
# ---------------------------------------------------------------------------

def tithi(sun_lon: float, moon_lon: float) -> tuple[str, int]:
    """``("Krishna Panchami", index)`` -- index is 0..29 over the lunar month.

    A tithi is a 12 deg step of the Sun-Moon elongation.  Indices 0..14 are the
    waxing (Shukla) fortnight, 15..29 the waning (Krishna) one.  Amavasya is
    the 15th Krishna tithi (index 29 -> name ``Purnima``'s counterpart), which
    KP Stellar prints as ``Amavasya``.
    """
    elong = normalize_longitude(moon_lon - sun_lon)
    idx = int(elong // 12.0) % 30
    if idx == 29:
        return "Amavasya", idx
    paksha = "Krishna" if idx >= 15 else "Shukla"
    return f"{paksha} {TITHI_NAMES[idx % 15]}", idx


def nitya_yoga(sun_lon: float, moon_lon: float) -> tuple[str, int]:
    """``("Siva", index)`` -- the nitya yoga, a 13 deg 20' step of Sun + Moon."""
    total = normalize_longitude(sun_lon + moon_lon)
    idx = int(total // NAKSHATRA_SPAN_DEG) % 27
    return YOGA_NAMES[idx], idx


def karana(sun_lon: float, moon_lon: float) -> tuple[str, int]:
    """``("Taitula", index)`` -- the karana, a 6 deg step of the elongation.

    The 60 karanas are: one fixed (``Kinstughna``), eight repeats of the seven
    moving karanas, then four more fixed ones closing the cycle.
    """
    elong = normalize_longitude(moon_lon - sun_lon)
    idx = int(elong // 6.0) % 60
    if idx == 0:
        return "Kinstughna", idx
    if idx <= 56:
        return KARANA_NAMES[(idx - 1) % 7], idx
    return KARANA_FIXED_TAIL[idx - 57], idx


def nakshatra_pada(moon_lon: float) -> tuple[str, int, int]:
    """``("Ardra", nakshatra_index, pada)`` for the Moon's sidereal longitude."""
    return NAKSHATRAS[star_index(moon_lon)], star_index(moon_lon), pada_info(moon_lon).pada


def day_lord(when: datetime) -> str:
    """KP day-lord (weekday lord) of a *local* date/datetime."""
    return WEEKDAY_LORDS[when.weekday() % 7]


# ---------------------------------------------------------------------------
# Dasha balance string
# ---------------------------------------------------------------------------

def dasha_balance_str(lord_abbr: str, balance_days: float) -> str:
    """``"RAH 15y 5m 26d"`` -- the KP Stellar balance-of-dasha header line.

    Year = 365.25 days, month = a flat 30 days, both truncated (KP Stellar
    floors rather than rounds).  This is deliberately *not*
    :func:`kpastro.dasha.format_days`, which uses a 30.4375-day month.
    """
    years, rem = divmod(max(balance_days, 0.0), DAYS_PER_YEAR)
    months, rem = divmod(rem, BALANCE_DAYS_PER_MONTH)
    return f"{lord_abbr} {int(years)}y {int(months)}m {int(rem)}d"


def balance_days_from_moon(moon_lon: float, mahadasha_total_days: float) -> float:
    """Days of the opening mahadasha still to run at the birth instant.

    Pure longitude math: the fraction of the Moon's nakshatra still ahead of
    it, scaled by the full length of that nakshatra lord's mahadasha.
    """
    idx = star_index(moon_lon)
    star_start = idx * NAKSHATRA_SPAN_DEG
    elapsed_deg = normalize_longitude(moon_lon - star_start)
    remaining = 1.0 - elapsed_deg / NAKSHATRA_SPAN_DEG
    return remaining * mahadasha_total_days


def local_datetime(dt_utc: datetime, tz_hours: float) -> datetime:
    """Shift a naive-UTC datetime to naive local wall time."""
    return dt_utc + timedelta(hours=tz_hours)
