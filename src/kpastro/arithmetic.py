"""Integer milliarcsecond core for all zodiacal / sub-division boundaries.

Every KP boundary (sign, nakshatra, pada, sub, sub-sub and deeper) is an exact
rational multiple of a Vimshottari year count:

* one sign  = 30 deg            = 108,000,000 mas
* one star  = 13 deg 20'        =  48,000,000 mas
* one pada  =  3 deg 20'        =  12,000,000 mas
* sub boundary inside a star = ``years * 400,000`` mas   (800'/120 = 20/3')
* deeper levels divide the parent span by the same 120-year proportion, so
  level ``L`` boundaries are exact multiples of ``years * 400_000 / 120**(L-2)``.

Representing them as :class:`fractions.Fraction` values in **milliarcseconds**
(mas) makes every boundary an exact rational number: no two code paths can
drift by an ulp, adjacency is provable (sub ``k`` end == sub ``k+1`` start),
and the whole class of float round-off boundary bugs disappears.

Display-facing APIs keep returning floats; only the internal tiling math uses
this module.
"""

from __future__ import annotations

import math
from fractions import Fraction
from functools import lru_cache
from typing import Iterator

from .constants import VIMSHOTTARI_ORDER, VIMSHOTTARI_TOTAL_YEARS, VIMSHOTTARI_YEARS

__all__ = [
    "MAS_PER_DEG",
    "ZODIAC_MAS",
    "SIGN_SPAN_MAS",
    "STAR_SPAN_MAS",
    "PADA_SPAN_MAS",
    "MAS_PER_YEAR",
    "BOUNDARY_TOL_MAS",
    "deg_to_mas",
    "mas_to_deg",
    "longitude_to_mas",
    "mas_sign_index",
    "mas_star_index",
    "mas_pada",
    "pada_bounds_mas",
    "star_span_mas",
    "sub_divisions_mas",
    "child_tiling_mas",
    "locate_in_tiling",
    "subspan_mas",
    "walk_subdivisions",
    "kahan_sum",
    "quantize_deg",
]

#: Milliarcseconds per degree (1000 mas = 1 arcsec, 3600 arcsec = 1 deg).
MAS_PER_DEG: int = 3600 * 1000

#: Full zodiacal circle in mas.
ZODIAC_MAS: int = 360 * MAS_PER_DEG            # 1,296,000,000

#: Exact spans, in mas.
SIGN_SPAN_MAS: int = 30 * MAS_PER_DEG          # 108,000,000
STAR_SPAN_MAS: int = 48_000_000                # 13 deg 20' (= 800')
PADA_SPAN_MAS: int = STAR_SPAN_MAS // 4        # 12,000,000 (= 3 deg 20')

#: Mas that one Vimshottari mahadasha-year occupies inside a nakshatra arc:
#: ``STAR_SPAN_MAS / VIMSHOTTARI_TOTAL_YEARS`` == exactly 400,000 mas/year.
#: This integrality is what makes every sub boundary an *integer* mas value.
MAS_PER_YEAR: int = STAR_SPAN_MAS // VIMSHOTTARI_TOTAL_YEARS
assert STAR_SPAN_MAS % VIMSHOTTARI_TOTAL_YEARS == 0

#: Unified boundary policy, expressed in mas: a longitude within this distance
#: *below* a boundary resolves to the segment *above* it (forward-push), so
#: exact boundaries always belong to the following segment.  1e-9 deg (the
#: tolerance vedic.py used historically) is exactly 3.6e-4 mas, so
#: ``1/1000`` mas reproduces that policy bit-for-bit while being far below any
#: ephemeris precision (~0.05" Moon error with Moshier).
BOUNDARY_TOL_MAS: "Fraction" = Fraction(1, 1000)


# ---------------------------------------------------------------------------
# Conversions
# ---------------------------------------------------------------------------

def deg_to_mas(lon_deg: float) -> int:
    """Convert a decimal-degree longitude to integer mas (nearest).

    ``lon_deg`` is expected in [0, 360); anything else is folded first.
    The scaling is done on the *exact* binary value of the float via
    :class:`fractions.Fraction`, so no extra float round-off is introduced;
    ties (which cannot occur for finite binary fractions scaled by an integer,
    but are handled anyway) round half away from zero, which is deterministic
    across platforms (no banker's-rounding surprises).
    """
    exact = Fraction(lon_deg) * MAS_PER_DEG
    n, d = exact.numerator, exact.denominator          # d > 0
    q, r = divmod(n, d)
    if 2 * r >= d:                                     # half-up on the exact value
        q += 1
    return q


def mas_to_deg(mas: "int | Fraction") -> float:
    """Convert an integer/Fraction mas value back to decimal degrees."""
    return float(Fraction(mas)) / MAS_PER_DEG


def longitude_to_mas(lon_deg: float) -> int:
    """Fold a (possibly negative/>=360) longitude into [0, 360) and give mas.

    Folding happens on the *degree* value first (matching
    ``vedic.normalize_longitude``), then the folded float is quantised, so the
    result is identical to what the legacy float pipeline would have seen at
    the same precision.  A float that folds to exactly 360.0 (e.g. inputs just
    below 0 whose modulo rounds up) is mapped to 0 mas.
    """
    lon = lon_deg % 360.0
    if lon == 360.0 or math.copysign(1.0, lon) < 0:    # -0.0 style edge
        lon = 0.0
    m = deg_to_mas(lon)
    return m % ZODIAC_MAS


# ---------------------------------------------------------------------------
# Exact index lookups (no float division anywhere)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def mas_sign_index(mas: int) -> int:
    """Sign ordinal (0..11) for an integer-mas longitude."""
    return min(mas // SIGN_SPAN_MAS, 11)


@lru_cache(maxsize=None)
def mas_star_index(mas: int) -> int:
    """Nakshatra ordinal (0..26) for an integer-mas longitude.

    Star boundaries are exact multiples of 48,000,000 mas, so integer floor
    division cannot drift the way ``idx * 800/60`` degree arithmetic does.
    """
    return min(mas // STAR_SPAN_MAS, 26)


def mas_pada(mas: "int | Fraction") -> int:
    """Pada (1..4) inside the containing nakshatra, forward-push at edges."""
    idx = mas_star_index(mas)
    offset = Fraction(mas) - idx * STAR_SPAN_MAS
    probe = offset + BOUNDARY_TOL_MAS
    pada = int(probe // PADA_SPAN_MAS) + 1
    return min(pada, 4)


def pada_bounds_mas(mas: "int | Fraction") -> "tuple[Fraction, Fraction]":
    """Exact [start, end) mas bounds of the pada containing ``mas``."""
    idx = mas_star_index(mas)
    star_start = idx * STAR_SPAN_MAS
    pada = mas_pada(mas)
    return (
        star_start + (pada - 1) * PADA_SPAN_MAS,
        star_start + pada * PADA_SPAN_MAS,
    )


def star_span_mas(star_idx: int) -> tuple[int, int]:
    """Exact [start, end) mas span of nakshatra ``star_idx``."""
    return star_idx * STAR_SPAN_MAS, (star_idx + 1) * STAR_SPAN_MAS


# ---------------------------------------------------------------------------
# Sub / sub-sub / deeper tilings, exact in mas
# ---------------------------------------------------------------------------

def subspan_mas(parent_span_mas: "int | Fraction", lord: str) -> "Fraction":
    """Child span (mas) of a parent arc, proportional to the Vimshottari years.

    Pass the parent span in mas (int or Fraction) and receive the child span
    in mas as an exact Fraction: ``parent * years(lord) / 120``.
    """
    return (
        Fraction(parent_span_mas)
        * VIMSHOTTARI_YEARS[lord]
        / VIMSHOTTARI_TOTAL_YEARS
    )


@lru_cache(maxsize=None)
def sub_divisions_mas(star_idx: int) -> tuple[tuple[str, int, int], ...]:
    """The nine sub-divisions of nakshatra ``star_idx`` as exact integer mas.

    Every boundary is ``star_start + cum_years * 400_000`` mas, an exact
    integer, because ``800'/120 * 1e6 mas/' = 400_000`` mas per dasha-year.
    Adjacent subs therefore share byte-identical edges.
    """
    star_start = star_idx * STAR_SPAN_MAS
    start_pos = star_idx % 9
    cum_years = 0
    out: list[tuple[str, int, int]] = []
    for k in range(9):
        lord = VIMSHOTTARI_ORDER[(start_pos + k) % 9]
        cum_years += VIMSHOTTARI_YEARS[lord]
        end = star_start + cum_years * MAS_PER_YEAR
        out.append((lord, end - VIMSHOTTARI_YEARS[lord] * MAS_PER_YEAR, end))
    return tuple(out)


def child_tiling_mas(
    parent_start_mas: "int | Fraction",
    parent_end_mas: "int | Fraction",
    start_lord: str,
) -> tuple[tuple[str, "Fraction", "Fraction"], ...]:
    """Exact ``[start, end)`` mas tiling of *any* parent arc by the nine lords.

    This is the generalisation of :func:`sub_divisions_mas` used by every
    deeper level (sub-sub and below).  Each boundary is derived from the
    parent endpoints with one exact rational multiply —
    ``start + (end - start) * cum_years / 120`` — never by accumulating span
    floats, so adjacency is exact at every depth and the nine children tile
    the parent perfectly (child 8 end == parent end, byte-identical).
    """
    start = Fraction(parent_start_mas)
    span = Fraction(parent_end_mas) - start
    if span <= 0:
        raise ValueError("parent arc must have positive span")
    pos = _vimsottari_index(start_lord)
    cum_years = 0
    out: list[tuple[str, Fraction, Fraction]] = []
    for k in range(9):
        lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
        child_start = start + span * cum_years / VIMSHOTTARI_TOTAL_YEARS
        cum_years += VIMSHOTTARI_YEARS[lord]
        child_end = start + span * cum_years / VIMSHOTTARI_TOTAL_YEARS
        out.append((lord, child_start, child_end))
    return tuple(out)


def locate_in_tiling(
    tiling: tuple[tuple[str, "Fraction", "Fraction"], ...],
    probe_mas: "int | Fraction",
) -> "tuple[str, int, Fraction, Fraction]":
    """Return ``(lord, index, start, end)`` of the segment holding the probe.

    The probe is expected to have been forward-pushed already (see
    :data:`BOUNDARY_TOL_MAS`).  A probe that still misses every segment
    (e.g. it sits at or beyond the final end after clamping) resolves to the
    last segment instead of raising, matching the historical tolerance-first
    behaviour of the dasha walkers.
    """
    p = Fraction(probe_mas)
    for k, (lord, start, end) in enumerate(tiling):
        if start <= p < end:
            return lord, k, start, end
    lord, start, end = tiling[-1]
    return lord, len(tiling) - 1, start, end


def walk_subdivisions(
    span_mas: "int | Fraction",
    start_lord: str,
    depth: int,
) -> Iterator["Fraction"]:
    """Yield the nine exact child spans (mas) of a parent arc of ``span_mas``.

    Used by the fraction-space recursion in :mod:`kpastro.deep_dasha`: the
    recursion never accumulates absolute longitudes, only exact fractional
    offsets inside the current parent arc, so drift cannot compound with depth.
    """
    for lord in _vimsottari_from(start_lord, depth):
        yield subspan_mas(span_mas, lord)


def _vimsottari_index(lord: str) -> int:
    """Position of ``lord`` in the Vimshottari order (0..8)."""
    from .constants import VIMSHOTTARI_INDEX

    return VIMSHOTTARI_INDEX[lord]


def _vimsottari_from(lord: str, n: int) -> list[str]:
    """``n`` consecutive lords starting at ``lord`` (wrapping the order)."""
    pos = _vimsottari_index(lord)
    return [VIMSHOTTARI_ORDER[(pos + k) % 9] for k in range(n)]


# ---------------------------------------------------------------------------
# Float-era helpers (Kahan summation & presentation quantization)
# ---------------------------------------------------------------------------

def kahan_sum(values) -> float:
    """Neumaier-compensated sum of an iterable of floats.

    Used wherever a float timeline must still be accumulated (e.g. the
    120-year dasha tables in :mod:`kpastro.dasha`): plain left-to-right
    addition drifts by ~1 ulp per term; compensated summation is exact to
    within one final rounding, so period edges stay adjacent and the total
    equals the true rounded sum.
    """
    s = 0.0
    c = 0.0                                   # running compensation
    for v in values:
        t = s + v
        if abs(s) >= abs(v):
            c += (s - t) + v                  # large + small
        else:
            c += (v - t) + s                  # small + large (Neumaier)
        s = t
    return s + c


def quantize_deg(
    lon_deg: float,
    step_arcsec: "float | Fraction" = 1.0,
    *,
    fold: bool = True,
) -> float:
    """Round a longitude to a multiple of ``step_arcsec`` arcseconds, half-up.

    KP Stellar truncates/rounds cusps to whole seconds before deriving
    sub-lords; matching that display quantization is often the last arcsecond
    of parity.  The arithmetic runs through :class:`fractions.Fraction`, so
    the result is the *exact* nearest multiple rendered as the closest float —
    no binary round-off surprises (``quantize_deg(273.9999999, 1.0)`` returns
    exactly ``274.0``).

    ``fold=True`` maps a result of exactly 360 back to 0.0 (longitude space);
    pass ``fold=False`` when quantizing a *span* rather than a position.
    Negative inputs are treated like longitudes (folded) when ``fold`` is set;
    otherwise they round away-from-zero symmetrically.
    """
    step_mas = Fraction(step_arcsec) * 1000
    if step_mas <= 0:
        raise ValueError("quantization step must be positive")
    step_deg = step_mas / MAS_PER_DEG                     # exact degrees per step
    value = Fraction(lon_deg)
    if fold:
        value %= 360
    q = value / step_deg
    n, d = q.numerator, q.denominator
    k, r = divmod(abs(n), d)
    if 2 * r >= d:                                          # half away from zero
        k += 1
    if n < 0:
        k = -k
    out = float(k * step_deg)
    if fold:
        out %= 360.0
        if out == 360.0:
            out = 0.0
    return out
