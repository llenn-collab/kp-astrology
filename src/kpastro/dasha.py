"""Vimshottari dasha: balances, timelines and active-period resolution.

Two anchoring conventions exist and must not be confused:

* **Birth-anchored** (:func:`mahadasha_timeline`) - offsets are measured from
  the birth moment; the opening mahadasha is the truncated *balance*.
* **Absolute** (:func:`absolute_periods`, :func:`mahadasha_timeline_absolute`) -
  the opening mahadasha keeps its full nominal length and simply starts
  *before* birth (negative offset).  This is the convention KP Stellar uses
  and the only one that resolves deep levels correctly for an arbitrary
  query date.

All offsets are in days of 365.25 (the KP software convention).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from functools import lru_cache

from .constants import (
    NAKSHATRAS,
    VIMSHOTTARI_INDEX,
    VIMSHOTTARI_ORDER,
    VIMSHOTTARI_TOTAL_YEARS,
    VIMSHOTTARI_YEARS,
)
from .vedic import (
    STAR_SPAN_DEG,
    normalize_longitude,
    sub_info,
    sub_sub_info,
    star_index,
    star_lord,
)

#: Days in one dasha year (the convention used by KP software).
DAYS_PER_YEAR: float = 365.25

#: Days of one full Vimshottari cycle.
CYCLE_DAYS: float = VIMSHOTTARI_TOTAL_YEARS * DAYS_PER_YEAR

#: Canonical level names, index 0 == level 1.
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

# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Balance:
    """Nested dasha balances at a birth moment, anchored to the birth Moon."""
    mahadasha_lord: str
    mahadasha_years: float
    mahadasha_days: float
    active_ad_lord: str
    active_ad_days: float
    active_pd_lord: str
    active_pd_days: float
    nakshatra: str
    nakshatra_index: int

@dataclass(frozen=True)
class Period:
    """A dasha period with offsets measured in days from the epoch."""
    lord: str
    start_days: float
    end_days: float
    level: int                      # 1 mahadasha, 2 antardasha, 3 pratyantar...

    @property
    def duration_days(self) -> float:
        return self.end_days - self.start_days

    @property
    def duration_years(self) -> float:
        return self.duration_days / DAYS_PER_YEAR

    @property
    def level_name(self) -> str:
        if 1 <= self.level <= len(DASHA_LEVEL_NAMES):
            return DASHA_LEVEL_NAMES[self.level - 1]
        return f"Level {self.level}"

    def as_datetimes(self, epoch: datetime) -> tuple[datetime, datetime]:
        return (
            epoch + timedelta(days=self.start_days),
            epoch + timedelta(days=self.end_days),
        )

    def balance_days(self, instant: datetime, epoch: datetime) -> float:
        """Days remaining in this period at ``instant`` (may be negative)."""
        elapsed = (instant - epoch).total_seconds() / 86400.0
        return self.end_days - elapsed

def period_days(parent_lord: str, child_lord: str) -> float:
    """Full length (days) of a sub-period of ``parent_lord`` ruled by ``child_lord``."""
    return (
        VIMSHOTTARI_YEARS[parent_lord]
        * VIMSHOTTARI_YEARS[child_lord]
        / VIMSHOTTARI_TOTAL_YEARS
        * DAYS_PER_YEAR
    )

def mahadasha_days(lord: str) -> float:
    return VIMSHOTTARI_YEARS[lord] * DAYS_PER_YEAR

# ---------------------------------------------------------------------------
# Balance at birth
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def dasha_balance(moon_longitude: float) -> Balance:
    """All nested balances from the sidereal birth Moon longitude (cached).

    Note on the AD/PD balance algebra: dividing the remaining arc by the full
    nakshatra span and multiplying by the *mahadasha* years looks wrong, but is
    exactly equivalent to dividing by the sub-span and multiplying by the
    sub-period's own length, because ``sub_span == star_span * sub_years / 120``.
    """
    moon_longitude = normalize_longitude(moon_longitude)
    idx = star_index(moon_longitude)
    star_start = idx * STAR_SPAN_DEG
    star = STAR_SPAN_DEG

    sub = sub_info(moon_longitude)
    subsub = sub_sub_info(moon_longitude)

    md_lord = star_lord(moon_longitude)
    md_days = (star_start + star - moon_longitude) / star * VIMSHOTTARI_YEARS[md_lord] * DAYS_PER_YEAR
    ad_days = (sub.end_deg - moon_longitude) / star * VIMSHOTTARI_YEARS[md_lord] * DAYS_PER_YEAR
    pd_days = (subsub.end_deg - moon_longitude) / star * VIMSHOTTARI_YEARS[md_lord] * DAYS_PER_YEAR

    return Balance(
        mahadasha_lord=md_lord,
        mahadasha_years=md_days / DAYS_PER_YEAR,
        mahadasha_days=md_days,
        active_ad_lord=sub.lord,
        active_ad_days=ad_days,
        active_pd_lord=subsub.lord,
        active_pd_days=pd_days,
        nakshatra=NAKSHATRAS[idx],
        nakshatra_index=idx,
    )

def md_elapsed_days(moon_longitude: float) -> float:
    """Days already elapsed in the birth mahadasha at the birth moment."""
    bal = dasha_balance(moon_longitude)
    return mahadasha_days(bal.mahadasha_lord) - bal.mahadasha_days

# ---------------------------------------------------------------------------
# Sub-period generation (birth-anchored view)
# ---------------------------------------------------------------------------

def _subperiods(
    parent_lord: str,
    parent_days: float,
    level: int,
    start_anchor: str | None = None,
    first_dur: float | None = None,
) -> list[Period]:
    """Generate the nine sub-periods of a parent dasha.

    ``start_anchor`` overrides the usual "start from the parent lord" rule and
    ``first_dur`` truncates the opening period (both used for a partial
    balance-anchored parent).  Runs out at ``parent_days``.
    """
    pos = VIMSHOTTARI_INDEX[start_anchor or parent_lord]
    out: list[Period] = []
    offset = 0.0
    for k in range(len(VIMSHOTTARI_ORDER)):
        lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
        if k == 0 and first_dur is not None:
            dur = first_dur
        else:
            dur = period_days(parent_lord, lord)
        if offset + dur > parent_days:
            dur = max(parent_days - offset, 0.0)
        if dur > 0:
            out.append(Period(lord, offset, offset + dur, level))
        offset += dur
    return out

def mahadasha_timeline(moon_longitude: float, epochs: int = 1) -> list[Period]:
    """Birth-anchored mahadashas; the opening one is the truncated balance."""
    bal = dasha_balance(moon_longitude)
    periods: list[Period] = []
    offset = 0.0
    pos = bal.nakshatra_index % 9
    for cycle in range(epochs):
        for k in range(len(VIMSHOTTARI_ORDER)):
            lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
            is_opening = cycle == 0 and k == 0 and lord == bal.mahadasha_lord
            dur = bal.mahadasha_days if is_opening else mahadasha_days(lord)
            periods.append(Period(lord, offset, offset + dur, 1))
            offset += dur
    return periods

def mahadasha_timeline_absolute(
    moon_longitude: float,
    cycles: int = 2,
) -> list[Period]:
    """Absolute mahadashas: every period keeps its full nominal length.

    Offsets are still measured from the birth epoch, so the opening mahadasha
    has a **negative** ``start_days``.  This is the timeline KP Stellar displays
    and the only correct base for resolving deep levels at an arbitrary date.
    """
    bal = dasha_balance(moon_longitude)
    elapsed = mahadasha_days(bal.mahadasha_lord) - bal.mahadasha_days

    periods: list[Period] = []
    pos = VIMSHOTTARI_INDEX[bal.mahadasha_lord]
    cursor = -elapsed
    for k in range(9 * max(1, cycles)):
        lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
        dur = mahadasha_days(lord)
        periods.append(Period(lord, cursor, cursor + dur, 1))
        cursor += dur
    return periods

def antardashas_of(period: Period, balance: Balance | None = None) -> list[Period]:
    """Antardashas inside a mahadasha.

    For the opening (balance) mahadasha the sequence begins at the birth Moon's
    sub-lord and is truncated to the AD balance; otherwise it begins at the
    mahadasha lord with full AD periods.
    """
    partial = balance is not None and period.lord == balance.mahadasha_lord
    return _subperiods(
        period.lord,
        period.duration_days,
        2,
        start_anchor=balance.active_ad_lord if partial else None,
        first_dur=balance.active_ad_days if partial else None,
    )

def pratyantardashas_of(
    ad: Period,
    balance: Balance | None = None,
    md_is_partial: bool = False,
) -> list[Period]:
    """Pratyantardashas inside an antardasha (refined only for the birth AD)."""
    most_refined = balance is not None and md_is_partial and ad.start_days == 0
    return _subperiods(
        ad.lord,
        ad.duration_days,
        3,
        start_anchor=balance.active_pd_lord if most_refined else None,
        first_dur=balance.active_pd_days if most_refined else None,
    )

def sookshmas_of(pd_period: Period, level: int = 4) -> list[Period]:
    """Sookshma (4th level) periods inside a pratyantardasha."""
    return _subperiods(pd_period.lord, pd_period.duration_days, level)

def pranas_of(sookshma: Period, level: int = 5) -> list[Period]:
    """Prana (5th level) periods inside a sookshma."""
    return _subperiods(sookshma.lord, sookshma.duration_days, level)

def sub_periods_of(parent: Period, level: int | None = None) -> list[Period]:
    """Generic child periods of ``parent`` (unrefined / absolute convention)."""
    lvl = level if level is not None else parent.level + 1
    return _subperiods(parent.lord, parent.duration_days, lvl)

# ---------------------------------------------------------------------------
# Active-period resolution
# ---------------------------------------------------------------------------

def _locate(periods: list[Period], offset_days: float) -> Period | None:
    for p in periods:
        if p.start_days <= offset_days < p.end_days:
            return p
    return None

def _find_child(
    parent_lord: str,
    parent_start: float,
    parent_duration: float,
    target_days: float,
    level: int,
) -> Period:
    """Walk the nine children of a parent and return the one holding ``target_days``.

    Children always begin with the parent's own lord and each takes
    ``parent_duration * years(child) / 120`` of the parent's span.  If the
    target falls outside the parent (floating-point edge, or a query beyond the
    generated range) the final child is returned rather than raising, so deep
    stacks never explode on boundary input.
    """
    pos = VIMSHOTTARI_INDEX[parent_lord]
    cursor = parent_start
    last: Period | None = None
    for k in range(9):
        lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
        dur = parent_duration * VIMSHOTTARI_YEARS[lord] / VIMSHOTTARI_TOTAL_YEARS
        last = Period(lord, cursor, cursor + dur, level)
        if cursor <= target_days < cursor + dur:
            return last
        cursor += dur
    assert last is not None
    return last

def absolute_periods(
    moon_longitude: float,
    epoch: datetime,
    instant: datetime,
    depth: int = 5,
) -> list[Period]:
    """Active MD/AD/PD/Sookshma/Prana... stack at ``instant``, levels 1..depth.

    ``epoch`` is the birth moment (it fixes the mahadasha anchor via the birth
    Moon); ``instant`` is the date the stack is resolved for.  Offsets in the
    returned periods are days relative to ``epoch`` and may be negative.
    """
    if depth < 1:
        raise ValueError("depth must be >= 1")

    bal = dasha_balance(moon_longitude)
    md_lord = bal.mahadasha_lord
    md_total = mahadasha_days(md_lord)
    elapsed = md_total - bal.mahadasha_days

    target = (instant - epoch).total_seconds() / 86400.0

    # -- level 1: walk full-length mahadashas from their absolute start ------
    pos = VIMSHOTTARI_INDEX[md_lord]
    cursor = -elapsed
    if target < cursor:
        cycles_needed = 1
    else:
        cycles_needed = int((target - cursor) // CYCLE_DAYS) + 2

    md: Period | None = None
    for k in range(9 * cycles_needed):
        lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
        dur = mahadasha_days(lord)
        if cursor <= target < cursor + dur:
            md = Period(lord, cursor, cursor + dur, 1)
            break
        cursor += dur

    if md is None:
        # Query lies beyond the generated horizon; clamp to the opening MD.
        md = Period(md_lord, -elapsed, -elapsed + md_total, 1)

    periods: list[Period] = [md]

    # -- levels 2..depth: recurse into the located parent --------------------
    for level in range(2, depth + 1):
        parent = periods[-1]
        periods.append(
            _find_child(
                parent.lord,
                parent.start_days,
                parent.duration_days,
                target,
                level,
            )
        )

    return periods

def current_periods(
    moon_longitude: float,
    epoch: datetime,
    instant: datetime,
    depth: int = 3,
) -> dict[int, Period]:
    """Active periods keyed by level (1=MD, 2=AD, 3=PD, 4=Sookshma, 5=Prana).

    ``epoch`` is the birth moment, ``instant`` the evaluation date.  Passing
    ``epoch`` for both yields the birth stack, which is almost never what a
    "current dasha" panel should show.
    """
    return {p.level: p for p in absolute_periods(moon_longitude, epoch, instant, depth)}

def current_lords(
    moon_longitude: float,
    epoch: datetime,
    instant: datetime,
    depth: int = 5,
) -> list[str]:
    """Convenience: just the lord names of the active stack, MD first."""
    return [p.lord for p in absolute_periods(moon_longitude, epoch, instant, depth)]

def format_days(days: float) -> str:
    """Render days as ``Yy Mm Dd`` (year = 365.25 days, month = 30.4375 days)."""
    negative = days < 0
    days = abs(days)
    years, rem = divmod(days, 365.25)
    months, rem = divmod(rem, 365.25 / 12.0)
    days_f, _ = divmod(rem, 1.0)
    text = f"{int(years)}y {int(months)}m {days_f:.0f}d"
    return f"-{text}" if negative else text
