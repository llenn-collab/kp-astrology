"""KP horary (Prashna): the 1-249 number system.

The zodiac contains 27 nakshatras x 9 Vimshottari sub-lords = 243 subs.  Six of
the twelve sign boundaries fall *inside* a sub and split it in two (the sub's
lord stays the same but its zodiac sign changes), which is why a KP horary
chart counts exactly **249** numbered divisions from 0° Aries.

* A querent's number ``n`` (1..249) selects division ``n``.
* The horary ascendant is the **midpoint** of that division.
* Everything else (planets, other cusps, rulers) comes from the moment and
  place of the question, computed with the normal engine.
"""

from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
from functools import lru_cache

from .constants import VIMSHOTTARI_ORDER
from .vedic import (
    normalize_longitude,
    point_info,
    sign_lord_of_longitude,
    sign_name,
    star_lord,
    star_name,
    sub_divisions,
)

MAX_HORARY_NUMBER = 249

#: Tolerance for deciding a sign boundary falls strictly inside a sub.
_BOUNDARY_EPS = 1e-9


@dataclass(frozen=True)
class HoraryDiv:
    """One of the 249 KP horary divisions of the zodiac."""
    number: int
    start_deg: float
    end_deg: float
    sign: str
    sign_lord: str
    star: str
    star_lord: str
    sub_lord: str

    @property
    def mid_deg(self) -> float:
        return (self.start_deg + self.end_deg) / 2.0


def kp_divisions() -> list[HoraryDiv]:
    """Generate all 249 divisions in ascending zodiacal order.

    The table is computed once and cached; each call returns a fresh list
    over the immutable internal table, so callers may not corrupt the cache.
    """
    return list(_divisions_tuple())


@lru_cache(maxsize=None)
def _divisions_tuple() -> tuple[HoraryDiv, ...]:
    subs: list[tuple[float, float, int, str]] = []
    for sidx in range(27):
        for lord, start, end, _span in sub_divisions(sidx):
            subs.append((start, end, sidx, lord))

    divisions: list[HoraryDiv] = []
    num = 0
    for start, end, sidx, sub_owner in subs:
        boundaries = [
            b for b in (30.0 * k for k in range(1, 12))
            if start + _BOUNDARY_EPS < b < end - _BOUNDARY_EPS
        ]
        cursor = start
        for b in boundaries + [end]:
            seg_start, seg_end = cursor, b
            num += 1
            divisions.append(
                HoraryDiv(
                    number=num,
                    start_deg=seg_start,
                    end_deg=seg_end,
                    sign=sign_name(seg_start),
                    sign_lord=sign_lord_of_longitude(seg_start),
                    star=star_name(seg_start),
                    star_lord=star_lord(seg_start),
                    sub_lord=sub_owner,
                )
            )
            cursor = b
    return tuple(divisions)


@lru_cache(maxsize=None)
def _division_starts() -> tuple[float, ...]:
    return tuple(d.start_deg for d in _divisions_tuple())


def ascendant_from_kp_number(n: int) -> dict:
    """The horary ascendant (division midpoint) and its full KP lord chain.

    Returns a dict with ``ascendant`` (sidereal longitude), the division span
    and the sign / star / sub / sub-sub breakdown.
    """
    if not 1 <= n <= MAX_HORARY_NUMBER:
        raise ValueError(f"KP horary number must be within 1-{MAX_HORARY_NUMBER}")
    div = _divisions_tuple()[n - 1]
    mid = div.mid_deg
    info = point_info(mid)
    return {
        "number": n,
        "ascendant": mid,
        "span": (div.start_deg, div.end_deg),
        "sign": info.sign,
        "sign_lord": info.sign_lord,
        "star": info.star,
        "star_lord": info.star_lord,
        "sub_lord": info.sub_lord,
        "sub_sub_lord": info.sub_sub_lord,
        "pada": info.pada,
    }


def kp_number_for_longitude(lon: float) -> int:
    """Inverse lookup: which KP horary division contains this sidereal longitude.

    Uses binary search over the cached division-start table, so a single
    lookup is O(log 249) instead of rescanning the whole zodiac.  Longitudes
    outside [0, 360) are normalised first (the 249 divisions tile the full
    zodiac, so the lookup always succeeds).
    """
    lon = normalize_longitude(lon)
    starts = _division_starts()
    idx = bisect_right(starts, lon) - 1
    return max(idx, 0) + 1

def cusps_from_horary_lagna(
    lagna_deg: float,
    eph,
    jd_ref: float,
    latitude: float,
    longitude: float,
    *,
    tol_deg: float = 1e-12,
    scan_steps: int = 960,
) -> list[float]:
    """The sidereal Placidus cusps whose ascendant equals ``lagna_deg``.

    A KP horary chart takes its *lagna* from the querent's number, not from the
    clock, so its house cusps are the Placidus cusps at whatever local sidereal
    time yields that ascendant for the observer's latitude.  The ascendant
    sweeps 360 degrees once per sidereal day and increases strictly through it,
    so exactly one such instant falls in the sidereal day ending at ``jd_ref``;
    it is bracketed by a coarse scan (which unwraps the 360 -> 0 discontinuity)
    and then bisected.

    The returned list is twelve ascending sidereal longitudes in KP house order.
    ``lagna_deg`` is a sidereal longitude; ``latitude`` / ``longitude`` are the
    geographic ones the caller uses for houses.

    Args:
        lagna_deg: target sidereal ascendant, degrees in [0, 360).
        eph: :class:`~kpastro.ephemeris.Ephemeris` already configured with the
            chart's ayanamsa and node mode.
        jd_ref: Julian day UT near the moment the horary chart is being cast
            for; the instant solved for is the latest one at or before it.
        latitude: geographic latitude in degrees.
        longitude: geographic longitude in degrees, east positive.
        tol_deg: bisection tolerance on the ascendant.
        scan_steps: coarse samples across the sidereal day.

    Returns:
        Twelve sidereal house cusp longitudes.

    Raises:
        ValueError: if no instant in the searched day produces the ascendant
            (which can happen beyond the polar circles, where the ascendant is
            not monotonic in sidereal time).
    """
    day = 0.9972695663  # mean sidereal day in solar days
    lo_jd = jd_ref - day

    def asc_at(jd: float) -> float:
        return eph.houses(jd, latitude, longitude)[1]

    # Coarse scan, unwrapping so the target can be bracketed even across 0 deg.
    jds = [lo_jd + day * i / scan_steps for i in range(scan_steps + 1)]
    asc = [asc_at(j) for j in jds]
    unwrapped = [asc[0]]
    for a in asc[1:]:
        prev = unwrapped[-1]
        delta = a - prev
        while delta < -180.0:
            delta += 360.0
        while delta > 180.0:
            delta -= 360.0
        unwrapped.append(prev + delta)
    span = unwrapped[-1] - unwrapped[0]
    if span <= 0.0:
        raise ValueError(
            f"cannot solve the horary ascendant at latitude {latitude:g}"
        )

    # Express the target on the unwrapped scale, then take the last crossing.
    target = lagna_deg
    while target < unwrapped[0]:
        target += 360.0
    while target > unwrapped[-1]:
        target -= 360.0
    idx = None
    for i in range(scan_steps):
        if unwrapped[i] <= target <= unwrapped[i + 1]:
            idx = i
    if idx is None:
        raise ValueError(
            f"no instant within a sidereal day of jd {jd_ref:.6f} puts the "
            f"ascendant at {lagna_deg:.9f} deg"
        )

    a, b = jds[idx], jds[idx + 1]
    asc_a = asc_at(a)
    ua = unwrapped[idx]  # ascendant at ``a``, on the unwrapped scale
    for _ in range(200):
        m = 0.5 * (a + b)
        asc_m = asc_at(m)
        # Re-unwrap the midpoint against the current lower bracket endpoint.
        d = asc_m - asc_a
        while d < -180.0:
            d += 360.0
        while d > 180.0:
            d -= 360.0
        um = ua + d
        if um <= target:
            a, asc_a, ua = m, asc_m, um
        else:
            b = m
        if b - a < 1e-11 or abs(um - target) < tol_deg:
            break
    out = list(eph.houses(0.5 * (a + b), latitude, longitude)[0])
    # The horary lagna is exact by construction (a division cusp is an exact
    # rational longitude), so report it verbatim instead of the numerically
    # solved ascendant.  Left a hair below the target, a cusp sitting exactly
    # on a sub-lord boundary resolves to the wrong side of it.
    out[0] = normalize_longitude(lagna_deg)
    out[6] = normalize_longitude(lagna_deg + 180.0)
    return out
