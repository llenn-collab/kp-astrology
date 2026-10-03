"""Deep recursive Vimshottari dasha periods.

This module computes MD / AD / PD / Sookshma / Prana and can be extended
deeper by increasing the depth argument.

The method used is the KP/Vimshottari arc-to-time mapping:

1. The Moon's position inside the nakshatra determines Mahadasha.
2. The sub, sub-sub, and deeper lords are found by recursively dividing
   the current segment proportionally to Vimshottari years.
3. Arc boundaries are mapped linearly into time using the Mahadasha
   total duration.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .constants import (
    VIMSHOTTARI_INDEX,
    VIMSHOTTARI_ORDER,
    VIMSHOTTARI_TOTAL_YEARS,
    VIMSHOTTARI_YEARS,
)
from .vedic import (
    STAR_SPAN_ARCMIN,
    STAR_SPAN_DEG,
    normalize_longitude,
    star_index,
    star_lord,
    sub_info,
    sub_sub_info,
)

DASHA_LEVEL_NAMES: tuple[str, ...] = (
    "Mahadasha",
    "Antardasha",
    "Pratyantardasha",
    "Sookshma",
    "Prana",
    "Deha",
    "Jeeva",
    "Karma",
)


@dataclass(frozen=True)
class DeepDashaPeriod:
    """One current Vimshottari level: lord, start/end UT, duration, balance."""

    level: int
    name: str
    lord: str
    start: datetime
    end: datetime
    duration_days: float
    balance_days: float


@dataclass(frozen=True)
class _DashaSegment:
    """Arc segment for one dasha level."""

    level: int
    lord: str
    start_deg: float
    end_deg: float
    span_arcmin: float


def _child_segment(lon: float, parent: _DashaSegment) -> _DashaSegment:
    """Find the child segment containing longitude inside parent segment."""
    lon = normalize_longitude(lon)
    probe = min(lon + 1e-9, parent.end_deg - 1e-12)

    start_pos = VIMSHOTTARI_INDEX[parent.lord]
    cursor = parent.start_deg
    last: _DashaSegment | None = None

    for k in range(9):
        lord = VIMSHOTTARI_ORDER[(start_pos + k) % 9]
        span_arcmin = (
            parent.span_arcmin
            * VIMSHOTTARI_YEARS[lord]
            / VIMSHOTTARI_TOTAL_YEARS
        )
        span_deg = span_arcmin / 60.0
        end_deg = cursor + span_deg

        last = _DashaSegment(
            level=parent.level + 1,
            lord=lord,
            start_deg=cursor,
            end_deg=end_deg,
            span_arcmin=span_arcmin,
        )

        if cursor <= probe < end_deg:
            return last

        cursor = end_deg

    if last is None:
        raise ValueError(
            f"could not resolve child dasha segment for longitude {lon}"
        )
    return last


def dasha_segments(moon_lon: float, depth: int = 5) -> list[_DashaSegment]:
    """Return arc segments for dasha levels 1..depth.

    Level 1: Mahadasha / nakshatra segment
    Level 2: Antardasha / sub segment
    Level 3: Pratyantardasha / sub-sub segment
    Level 4+: recursively divided segments
    """
    if depth < 1:
        raise ValueError("depth must be >= 1")

    lon = normalize_longitude(moon_lon)

    # Level 1: Mahadasha / nakshatra
    idx = star_index(lon)
    star_start = idx * STAR_SPAN_DEG
    star_end = (idx + 1) * STAR_SPAN_DEG
    md_lord = star_lord(lon)

    segments: list[_DashaSegment] = [
        _DashaSegment(
            level=1,
            lord=md_lord,
            start_deg=star_start,
            end_deg=star_end,
            span_arcmin=STAR_SPAN_ARCMIN,
        )
    ]

    if depth == 1:
        return segments

    # Level 2: Antardasha / sub
    sub = sub_info(lon)
    segments.append(
        _DashaSegment(
            level=2,
            lord=sub.lord,
            start_deg=sub.start_deg,
            end_deg=sub.end_deg,
            span_arcmin=sub.span_arcmin,
        )
    )

    if depth == 2:
        return segments

    # Level 3: Pratyantardasha / sub-sub
    subsub = sub_sub_info(lon)
    segments.append(
        _DashaSegment(
            level=3,
            lord=subsub.lord,
            start_deg=subsub.start_deg,
            end_deg=subsub.end_deg,
            span_arcmin=subsub.span_arcmin,
        )
    )

    if depth == 3:
        return segments

    # Level 4 and deeper
    parent = segments[-1]
    for _ in range(4, depth + 1):
        child = _child_segment(lon, parent)
        segments.append(child)
        parent = child

    return segments


def deep_current_periods(
    moon_lon: float,
    at_utc: datetime,
    depth: int = 5,
) -> list[DeepDashaPeriod]:
    """Compute current Vimshottari periods up to depth.

    `at_utc` must be UTC, not local time.
    """
    segments = dasha_segments(moon_lon, depth=depth)
    lon = normalize_longitude(moon_lon)

    star_segment = segments[0]
    star_start = star_segment.start_deg
    md_lord = star_segment.lord

    # Mahadasha total duration in days
    md_total_days = VIMSHOTTARI_YEARS[md_lord] * 365.25

    # Elapsed MD days at birth / event time
    elapsed_md_days = (
        (lon - star_start) / STAR_SPAN_DEG * md_total_days
    )

    md_start = at_utc - timedelta(days=elapsed_md_days)

    periods: list[DeepDashaPeriod] = []

    for seg in segments:
        start_offset_days = (
            (seg.start_deg - star_start) / STAR_SPAN_DEG * md_total_days
        )
        end_offset_days = (
            (seg.end_deg - star_start) / STAR_SPAN_DEG * md_total_days
        )

        start = md_start + timedelta(days=start_offset_days)
        end = md_start + timedelta(days=end_offset_days)

        duration_days = (end - start).total_seconds() / 86400.0
        balance_days = (end - at_utc).total_seconds() / 86400.0

        if seg.level <= len(DASHA_LEVEL_NAMES):
            name = DASHA_LEVEL_NAMES[seg.level - 1]
        else:
            name = f"Level {seg.level}"

        periods.append(
            DeepDashaPeriod(
                level=seg.level,
                name=name,
                lord=seg.lord,
                start=start,
                end=end,
                duration_days=duration_days,
                balance_days=balance_days,
            )
        )

    return periods
