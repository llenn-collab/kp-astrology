"""Pure-Python KP sub-division mathematics.

This module needs **no ephemeris**: everything here is derived from a single
sidereal longitude using the classic KP tables.

Conventions
-----------
* Zodiac is **sidereal** 0°-360°, measured from 0° Aries.
* Every nakshatra spans :math:`13°20'` (800 arc-minutes).
* A nakshatra is divided into **9 unequal sub-lords** whose widths are
  proportional to the Vimshottari mahadasha years:

  .. math::

      \\text{sub span} = \\frac{\\text{lord's years}}{120} \\times 800'

  and the sub-lord sequence starts from the star-lord and runs through the
  Vimshottari order (wrapping).
* The **sub-sub-lord** divides the sub again with the same proportions,
  starting from the sub-lord.

Integer milliarcsecond core
---------------------------
All boundary decisions are made in **exact integer/Fraction milliarcseconds**
via :mod:`kpastro.arithmetic`:

* every zodiacal position is quantised once at the I/O edge
  (:func:`kpastro.arithmetic.longitude_to_mas`, nearest-mas rounding of the
  exact binary value of the incoming float), so no float ``//`` division or
  accumulated degree arithmetic can flip a segment assignment;
* every sub / sub-sub boundary is an exact rational of its parent arc
  (``start + span * cum_years / 120``) — never a sum of child spans — so
  adjacent segments share byte-identical edges at any depth;
* one unified boundary policy applies everywhere:
  :data:`kpastro.arithmetic.BOUNDARY_TOL_MAS` (1/1000 mas ≡ the historical
  1e-9° forward-push tolerance), clamped to just below the parent end
  (≡ the historical ``end - 1e-12`` guard).

Display-facing APIs keep returning floats rounded from the exact values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

from .arithmetic import (
    BOUNDARY_TOL_MAS,
    MAS_PER_DEG,
    PADA_SPAN_MAS,
    STAR_SPAN_MAS,
    ZODIAC_MAS,
    child_tiling_mas,
    deg_to_mas,
    locate_in_tiling,
    longitude_to_mas,
    mas_pada,
    mas_star_index,
    mas_to_deg,
    pada_bounds_mas,
    sub_divisions_mas,
)
from .constants import (
    NAKSHATRAS,
    SIGN_LORDS,
    SIGNS,
    VIMSHOTTARI_INDEX,
    VIMSHOTTARI_ORDER,
    VIMSHOTTARI_TOTAL_YEARS,
    VIMSHOTTARI_YEARS,
)

#: Nakshatra span in arc-minutes (13°20').
STAR_SPAN_ARCMIN: float = 800.0
#: Nakshatra span in decimal degrees.
STAR_SPAN_DEG: float = STAR_SPAN_ARCMIN / 60.0
#: Pada (quarter) span inside a star: 3°20'.
PADA_SPAN_DEG: float = STAR_SPAN_DEG / 4.0

#: Tolerance (degrees) used when a longitude lands exactly on a sub boundary:
#: values within 1e-9° below a boundary are assigned to the following sub, so
#: exact boundaries (e.g. 273.0 = Jupiter/Saturn edge) resolve deterministically.
#: 1e-9° ~ 3.6e-6 arcseconds, far below any ephemeris precision.
#:
#: This public constant is kept for backward compatibility only; it is an
#: *alias by value* of the single source of truth
#: :data:`kpastro.arithmetic.BOUNDARY_TOL_MAS` (1/1000 mas == 3.6e-4 mas-scale
#: tolerance == 1e-9 degrees exactly).  New code must use the mas constant.
_BOUNDARY_TOL: float = float(BOUNDARY_TOL_MAS) / MAS_PER_DEG   # == 1e-9


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def normalize_longitude(lon: float) -> float:
    """Fold a longitude into [0, 360).

    Edge cases (property-tested in ``tests/test_precision.py``):

    * ``lon % 360`` can return ``360.0`` for tiny negative inputs (e.g.
      ``-1e-14``); that maps to ``0.0``.
    * Python's modulo keeps the sign of the divisor, but ``-0.0 % 360.0``
      yields ``0.0`` already; the explicit guard makes the intent visible.
    * NaN / ±inf raise :exc:`ValueError` instead of silently propagating
      (a NaN longitude would poison every downstream lookup).
    """
    if not math.isfinite(lon):
        raise ValueError(f"longitude must be finite, got {lon!r}")
    lon = lon % 360.0
    # Gather FP rounding that lands exactly on 360.0 (e.g. -1e-14).
    return 0.0 if lon == 360.0 else lon


def _mas(lon_deg: float) -> "int | Fraction":
    """Quantise an input longitude to the exact-mas space (single edge point).

    Floor (truncate) rather than round: the legacy pipeline compared raw
    floats against float boundaries, resolving points at sub-mas precision.
    Flooring keeps every interior point and every exact boundary float in the
    same segment the legacy forward-push policy chose (boundary floats such as
    ``26.666666666666664``, whose exact value is a hair below 96,000,000 mas,
    floor *below* the integer edge and therefore stay with the following
    segment via the tolerance push — rounding would snap them onto the edge
    and assign them a segment early).

    Input must already be folded into [0, 360); use :func:`_probe_mas` for
    arbitrary inputs.
    """
    return Fraction(math.floor(Fraction(lon_deg) * MAS_PER_DEG))


def _probe_mas(lon_deg: float) -> "int | Fraction":
    """Fold + floor-quantise any longitude into exact mas in [0, ZODIAC_MAS)."""
    lon = normalize_longitude(lon_deg)
    return _mas(lon) % ZODIAC_MAS


def sub_span_arcmin(lord: str) -> float:
    """Width of a sub ruled by ``lord`` in arc-minutes.

    ``years / 120 * 800`` e.g. Ketu -> 7/120*800 = 46.67'; Venus -> 133.33'.
    """
    return VIMSHOTTARI_YEARS[lord] * STAR_SPAN_ARCMIN / VIMSHOTTARI_TOTAL_YEARS


def format_longitude(lon: float, arcsec: bool = True) -> str:
    """Render a longitude as ``D°MM'SS`` (seconds with one decimal, e.g. ``23°56'04.1"``).

    The sign name is not included here so callers can append it.

    Presentation-only half-up rounding *of the displayed seconds field*: the
    tenth-of-second value is rounded away from zero on the exact scaled
    remainder, and 60″/60′ carries are applied — so a longitude like
    ``9.9999999999`` renders ``10°00'00.0"`` and never ``9°59'60.0"``.
    """
    lon = normalize_longitude(lon)
    deg = int(lon)
    rem = (lon - deg) * 60.0
    minute = int(rem)
    sec = (rem - minute) * 60.0
    if arcsec:
        # Half-up rounding of the displayed tenth, carried through 60s/60'.
        tenths = int(Fraction(sec) * 10 + Fraction(1, 2))
        if tenths >= 600:
            tenths -= 600
            minute += 1
            if minute == 60:
                minute = 0
                deg = (deg + 1) % 360
        return f"{deg}\u00b0{minute:02d}'{tenths // 10:02d}.{tenths % 10}\""
    if sec >= 59.95:  # carry rounding overflow (e.g. ... 59' 60.0")
        minute += 1
        if minute == 60:
            deg += 1
            minute = 0
    deg %= 360
    return f"{deg}\u00b0{minute:02d}'"


# ---------------------------------------------------------------------------
# Sign (rashi)
# ---------------------------------------------------------------------------

def sign_index(lon: float) -> int:
    """Which of the 12 rashis the longitude falls in (0..11).

    Exact mas comparison — ``29.999999999999996`` cannot tip over into the
    next sign through float ``//`` drift because the quantisation happens
    before the division.
    """
    m = _probe_mas(lon)
    return min(int(m // (30 * MAS_PER_DEG)), 11)


def sign_name(lon: float) -> str:
    return SIGNS[sign_index(lon)]


def sign_lord_of_longitude(lon: float) -> str:
    return SIGN_LORDS[sign_name(lon)]


# ---------------------------------------------------------------------------
# Nakshatra (star)
# ---------------------------------------------------------------------------

def star_index(lon: float) -> int:
    """Nakshatra ordinal (0..26) containing the longitude.

    Star boundaries are exact multiples of 48,000,000 mas, so the lookup is
    an integer floor division in the mas space of :mod:`kpastro.arithmetic`;
    the legacy ``idx * 800/60`` degree round-off at the edges (e.g.
    ``21*800/60`` vs ``21 * 13.333333333333334``) cannot occur.
    """
    return mas_star_index(_probe_mas(lon))


def star_name(lon: float) -> str:
    return NAKSHATRAS[star_index(lon)]


def star_lord(lon: float) -> str:
    """Vimshottari star-lord of the nakshatra containing ``lon``."""
    from .constants import star_lord_of_index
    return star_lord_of_index(star_index(lon))


def star_span(lon: float) -> tuple[float, float]:
    """Start and end longitude of the nakshatra containing ``lon`` (degrees)."""
    idx = star_index(lon)
    return idx * STAR_SPAN_DEG, (idx + 1) * STAR_SPAN_DEG


# ---------------------------------------------------------------------------
# Pada (quarter of a star)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PadaInfo:
    """Quarter of a nakshatra (used for navamsa-style reference)."""
    pada: int                 # 1..4
    start_deg: float
    end_deg: float


def pada_info(lon: float) -> PadaInfo:
    """Pada containing ``lon``, resolved with the unified boundary policy.

    Forward-push at exact pada edges (same 1/1000 mas tolerance as every
    other boundary in the library), clamped so the last pada of the last
    star can never overflow to a fifth pada.
    """
    m = _probe_mas(lon)
    idx = mas_star_index(m)
    star_start = idx * STAR_SPAN_MAS
    probe = min(m + BOUNDARY_TOL_MAS, star_start + STAR_SPAN_MAS - BOUNDARY_TOL_MAS)
    pada = min(int((probe - star_start) // PADA_SPAN_MAS) + 1, 4)
    start, end = pada_bounds_mas(probe)
    return PadaInfo(pada, mas_to_deg(start), mas_to_deg(end))


# ---------------------------------------------------------------------------
# Sub-lord (the heart of KP)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubInfo:
    """Sub-lord of a longitude inside its nakshatra."""
    lord: str                # sub-lord planet
    index: int               # 0..8 position among the nine subs of the star
    start_deg: float         # absolute start longitude of the sub
    end_deg: float           # absolute end longitude of the sub
    span_arcmin: float


@lru_cache(maxsize=4096)
def sub_divisions(star_idx: int) -> tuple[tuple[str, float, float, float], ...]:
    """The 9 sub-divisions of nakshatra ``star_idx`` (lord, start, end, span').

    Single source of truth for sub tiling: the boundaries are computed once
    per star in **exact integer mas** by
    :func:`kpastro.arithmetic.sub_divisions_mas` (``star_start +
    cum_years * 400_000`` — every edge an integer, adjacency provable) and
    only converted to floats at the display edge via correctly-rounded
    ``float(Fraction)``.  No two code paths can drift, and the result is
    bit-identical to the previous arc-minute formula (which was already
    ulp-exact for these small numerators) while being structurally safe.
    """
    out: list[tuple[str, float, float, float]] = []
    for lord, start_m, end_m in sub_divisions_mas(star_idx):
        out.append(
            (
                lord,
                mas_to_deg(start_m),
                mas_to_deg(end_m),
                float(Fraction(VIMSHOTTARI_YEARS[lord]) * 800 / VIMSHOTTARI_TOTAL_YEARS),
            )
        )
    return tuple(out)


@lru_cache(maxsize=4096)
def sub_info(lon: float) -> SubInfo:
    """Locate the Vimshottari sub-lord of the given sidereal longitude.

    Deterministic and immutable, so results are cached; repeated lookups for
    the same longitude (e.g. one used as both a planet position and a cusp)
    resolve instantly.

    Boundary policy (unified): the longitude is quantised to exact mas, then
    forward-pushed by :data:`~kpastro.arithmetic.BOUNDARY_TOL_MAS` so exact
    boundaries belong to the following sub, clamped to just below the star
    end so the final sub can never overflow.
    """
    m = _probe_mas(lon)
    idx = mas_star_index(m)
    star_end = (idx + 1) * STAR_SPAN_MAS
    probe = min(m + BOUNDARY_TOL_MAS, star_end - BOUNDARY_TOL_MAS)
    lord, k, start_m, end_m = locate_in_tiling(
        [(l, Fraction(s), Fraction(e)) for l, s, e in sub_divisions_mas(idx)],
        probe,
    )
    return SubInfo(
        lord=lord,
        index=k,
        start_deg=mas_to_deg(start_m),
        end_deg=mas_to_deg(end_m),
        span_arcmin=sub_span_arcmin(lord),
    )


def sub_lord(lon: float) -> str:
    return sub_info(lon).lord


# ---------------------------------------------------------------------------
# Sub-sub-lord
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubSubInfo:
    """Sub-sub-lord: the sub divided again with the same proportions."""
    lord: str
    index: int
    start_deg: float
    end_deg: float
    span_arcmin: float


@lru_cache(maxsize=4096)
def sub_sub_info(lon: float) -> SubSubInfo:
    """Locate the sub-sub-lord of the given sidereal longitude (cached).

    Level-3 boundaries are exact rationals of the level-2 (sub) arc —
    ``sub_start + sub_span * cum_years / 120`` in mas — computed by
    :func:`kpastro.arithmetic.child_tiling_mas`.  The previous implementation
    accumulated ``running += span`` in float arcminutes and re-derived each
    endpoint in degrees; that lost adjacency at roughly every third boundary
    and raised ``ValueError`` for ~98% of longitudes inside a sub whose first
    child is Rahu/Saturn/Mercury (accumulated drift pushed the probe past the
    last computed end).  Both failure modes are structurally impossible now.
    """
    m = _probe_mas(lon)
    sub = sub_info(lon)
    idx = mas_star_index(m)
    _, sub_start_m, sub_end_m = sub_divisions_mas(idx)[sub.index]
    probe = min(m + BOUNDARY_TOL_MAS, sub_end_m - BOUNDARY_TOL_MAS)
    tiling = child_tiling_mas(sub_start_m, sub_end_m, sub.lord)
    lord, k, start_m, end_m = locate_in_tiling(tiling, probe)
    return SubSubInfo(
        lord=lord,
        index=k,
        start_deg=mas_to_deg(start_m),
        end_deg=mas_to_deg(end_m),
        span_arcmin=float((end_m - start_m) * 60 / MAS_PER_DEG),
    )


def sub_sub_lord(lon: float) -> str:
    return sub_sub_info(lon).lord


# ---------------------------------------------------------------------------
# Convenience aggregate
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PointInfo:
    """Full KP breakdown of a sidereal longitude."""
    longitude: float
    sign: str
    sign_lord: str
    sign_degree: float
    star: str
    star_lord: str
    star_index: int
    sub_lord: str
    sub_sub_lord: str
    pada: int


def point_info(lon: float) -> PointInfo:
    lon = normalize_longitude(lon)
    sub = sub_info(lon)
    return PointInfo(
        longitude=lon,
        sign=sign_name(lon),
        sign_lord=sign_lord_of_longitude(lon),
        sign_degree=mas_to_deg(_mas(lon) - sign_index(lon) * 30 * MAS_PER_DEG),
        star=star_name(lon),
        star_lord=star_lord(lon),
        star_index=star_index(lon),
        sub_lord=sub.lord,
        sub_sub_lord=sub_sub_lord(lon),
        pada=pada_info(lon).pada,
    )
