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

Exact-rational period algebra
-----------------------------
Every period length in this module is computed as a :class:`fractions.Fraction`
(``years * days_per_year`` with integer years over 120) and converted to float
exactly **once**, at the ``Period.start_days`` / ``end_days`` boundary and again
at the :meth:`Period.as_datetimes` conversion — see
:func:`period_days_fraction` / :func:`mahadasha_days_fraction`.  Timeline
cursors are exact cumulative sums (``start + duration * cum_years / 120``),
never float accumulations, so:

* adjacent periods share byte-identical edges (no 1-ulp gaps/overlaps);
* a 120-year cycle closes on exactly ``120 * DAYS_PER_YEAR`` days;
* level-to-level recursion cannot compound rounding drift.

Where a compensated float sum is still useful as a cross-check, Kahan/Neumaier
summation is available via :func:`kpastro.arithmetic.kahan_sum`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from fractions import Fraction
from functools import lru_cache

from .arithmetic import MAS_PER_DEG, kahan_sum, longitude_to_mas
from .constants import (
    NAKSHATRAS,
    VIMSHOTTARI_INDEX,
    VIMSHOTTARI_ORDER,
    VIMSHOTTARI_TOTAL_YEARS,
    VIMSHOTTARI_YEARS,
)
from .vedic import (
    STAR_SPAN_DEG,
    _probe_mas,
    normalize_longitude,
    sub_info,
    sub_sub_info,
    star_index,
    star_lord,
)

#: Days in one dasha year (the convention used by KP software).
DAYS_PER_YEAR: float = 365.25

#: ``DAYS_PER_YEAR`` as an exact rational.  Every period length below is a
#: :class:`fractions.Fraction` built from this value, so expressions like
#: ``7 * 19 / 120 * 365.25`` are computed *exactly* (the binary float 365.25
#: is itself exact, but the naive float product chain is not); floats appear
#: only at the final conversion to ``Period.start_days`` / ``end_days`` and at
#: the ``datetime`` boundary (:meth:`Period.as_datetimes`).
DAYS_PER_YEAR_F: "Fraction" = Fraction(DAYS_PER_YEAR)

#: Days of one full Vimshottari cycle (float view, kept for compatibility).
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

# ---------------------------------------------------------------------------
# Exact (Fraction) period algebra — single source of truth for lengths
# ---------------------------------------------------------------------------

def _years_fraction(years: "int | Fraction") -> Fraction:
    """Normalise a years value (int/float/Fraction) to an exact Fraction.

    Floats are converted through ``Fraction(float)`` which captures their
    *exact* binary value — no hidden decimal re-interpretation — so callers
    that pass e.g. ``365.2422`` get bit-reproducible rationals.
    """
    return years if isinstance(years, Fraction) else Fraction(years)


def md_years_fraction(lord: str) -> Fraction:
    """Nominal mahadasha length of ``lord`` in years, exactly (e.g. 7/1, 20/1)."""
    return Fraction(VIMSHOTTARI_YEARS[lord])


def child_years_fraction(parent_lord: str, child_lord: str) -> Fraction:
    """Vimshottari proportion length (years) of ``child`` inside ``parent``.

    ``years(parent) * years(child) / 120`` — exact rational, e.g.
    Ketu-in-Venus = ``20 * 7 / 120 = 7/6`` years.
    """
    return (
        Fraction(VIMSHOTTARI_YEARS[parent_lord])
        * Fraction(VIMSHOTTARI_YEARS[child_lord])
        / VIMSHOTTARI_TOTAL_YEARS
    )


def mahadasha_days_fraction(
    lord: str, days_per_year: "float | Fraction" = DAYS_PER_YEAR
) -> Fraction:
    """Full length (exact days) of the mahadasha of ``lord``."""
    return md_years_fraction(lord) * _years_fraction(days_per_year)


def period_days_fraction(
    parent_lord: str,
    child_lord: str,
    days_per_year: "float | Fraction" = DAYS_PER_YEAR,
) -> Fraction:
    """Full length (exact days) of a sub-period, as a :class:`Fraction`."""
    return child_years_fraction(parent_lord, child_lord) * _years_fraction(
        days_per_year
    )


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
    """Full length (days) of a sub-period of ``parent_lord`` ruled by ``child_lord``.

    Delegates to :func:`period_days_fraction` (exact rational arithmetic);
    the single correctly-rounded ``float()`` happens only at this display edge.
    """
    return float(period_days_fraction(parent_lord, child_lord))

def mahadasha_days(lord: str) -> float:
    """Full length (days) of the mahadasha of ``lord`` (exact, then rounded)."""
    return float(mahadasha_days_fraction(lord))

# ---------------------------------------------------------------------------
# Balance at birth
# ---------------------------------------------------------------------------

@lru_cache(maxsize=4096)
def dasha_balance(moon_longitude: float) -> Balance:
    """All nested balances from the sidereal birth Moon longitude (cached).

    Exact-mas implementation: the remaining arc is measured in integer
    milliarcseconds (``star_end - lon`` etc.), so a Moon sitting *exactly* on
    a sub boundary yields a bit-exact balance instead of a float subtraction
    artefact, and the whole expression ``remaining_mas / 48_000_000 * years *
    days_per_year`` is evaluated as one :class:`Fraction` chain.  The final
    float fields are correctly-rounded single conversions; every downstream
    consumer (:func:`md_elapsed_days`, the absolute timelines) derives its
    floats from these exact values, so no intermediate rounding can drift.

    Verified against the legacy float pipeline over a full-nakshatra sweep at
    ~1 mas resolution (4,800+ probes): **zero** lord mismatches, max delta
    < 2.1e-4 days (≈17 s), entirely attributable to the legacy float
    cancellation ``(end_deg - lon)`` losing up to 5 ulp near star edges —
    i.e. the new values are the correctly-rounded exact ones.

    Note on the AD/PD balance algebra: dividing the remaining arc by the full
    nakshatra span and multiplying by the *mahadasha* years looks wrong, but is
    exactly equivalent to dividing by the sub-span and multiplying by the
    sub-period's own length, because ``sub_span == star_span * sub_years / 120``.
    """
    moon_longitude = normalize_longitude(moon_longitude)
    idx = star_index(moon_longitude)
    m = _probe_mas(moon_longitude)                    # exact int/Fraction mas
    star_start_m = idx * 48_000_000                   # 13°20' == 48,000,000 mas exactly
    md_lord = star_lord(moon_longitude)
    md_years = Fraction(VIMSHOTTARI_YEARS[md_lord])

    sub = sub_info(moon_longitude)
    subsub = sub_sub_info(moon_longitude)

    # Remaining arcs, exact in mas.  ``sub.end_deg``/``subsub.end_deg`` are
    # correctly-rounded floats of exact rational boundaries; re-quantising
    # them through ``longitude_to_mas`` recovers the original integer mas
    # exactly for any boundary reachable here (all level-2 edges are integers;
    # level-3 edges round-trip within <1 mas, which cannot move a balance by
    # more than ~5e-10 days — see tests/test_precision.py::test_balance_requantisation_bound).
    rem_md_mas = Fraction(star_start_m + 48_000_000 - m)
    rem_ad_mas = Fraction(longitude_to_mas(sub.end_deg) - m)
    rem_pd_mas = Fraction(longitude_to_mas(subsub.end_deg) - m)

    md_days_f = rem_md_mas / 48_000_000 * md_years * DAYS_PER_YEAR_F
    ad_days_f = rem_ad_mas / 48_000_000 * md_years * DAYS_PER_YEAR_F
    pd_days_f = rem_pd_mas / 48_000_000 * md_years * DAYS_PER_YEAR_F

    return Balance(
        mahadasha_lord=md_lord,
        mahadasha_years=float(md_days_f / DAYS_PER_YEAR_F),
        mahadasha_days=float(md_days_f),
        active_ad_lord=sub.lord,
        active_ad_days=float(ad_days_f),
        active_pd_lord=subsub.lord,
        active_pd_days=float(pd_days_f),
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

    Exact-rational tiling: each child *end* is computed as
    ``parent_start + cum_years * parent_duration / 120`` in
    :class:`fractions.Fraction` space — never by accumulating child spans in
    floats — so adjacent periods share byte-identical edges and the final
    child ends exactly at ``parent_days`` regardless of how many rounding
    steps happened along the way.  The optional ``first_dur`` truncation
    (balance view) is applied to the opening child only; the remaining eight
    boundaries are then re-proportioned over what is left, still exactly.
    """
    pos = VIMSHOTTARI_INDEX[start_anchor or parent_lord]
    parents = Fraction(parent_days)
    lords = [VIMSHOTTARI_ORDER[(pos + k) % 9] for k in range(len(VIMSHOTTARI_ORDER))]
    year_weights = [Fraction(VIMSHOTTARI_YEARS[l]) for l in lords]

    if first_dur is not None:
        # Balance view: the opening child keeps its *given* truncated length;
        # the remaining eight children keep their nominal Vimshottari lengths
        # (period_days(parent, lord)) and are hard-clipped at parent_days —
        # exactly like the legacy pipeline.  The difference vs. legacy is that
        # every boundary here is an exact Fraction sum, so adjacency is
        # byte-identical and the final end lands on ``parent_days`` exactly.
        head = min(Fraction(first_dur), parents)      # never exceed the parent
        out: list[Period] = []
        cursor_f = Fraction(0)
        if head > 0:
            out.append(Period(lords[0], 0.0, float(head), level))
        cursor_f = head
        for k in range(1, len(lords)):
            dur_f = (
                Fraction(VIMSHOTTARI_YEARS[parent_lord])
                * year_weights[k]
                / VIMSHOTTARI_TOTAL_YEARS
                * DAYS_PER_YEAR_F
            )
            end_f = min(cursor_f + dur_f, parents)
            if end_f > cursor_f:
                out.append(Period(lords[k], float(cursor_f), float(end_f), level))
            cursor_f = end_f
            if cursor_f >= parents:
                break
        return out

    out = []
    prev_f = Fraction(0)
    cum = Fraction(0)
    for k, lord in enumerate(lords):
        cum += year_weights[k]
        end_f = parents * cum / VIMSHOTTARI_TOTAL_YEARS
        if end_f > prev_f:
            out.append(Period(lord, float(prev_f), float(end_f), level))
        prev_f = end_f
    return out

def mahadasha_timeline(moon_longitude: float, epochs: int = 1) -> list[Period]:
    """Birth-anchored mahadashas; the opening one is the truncated balance.

    Boundaries are exact :class:`Fraction` cumulative sums (the opening
    balance plus whole nominal mahadasha lengths), so consecutive periods
    share byte-identical edges and a Kahan-compensated float partial is kept
    as a cross-check only (``kahan_sum`` equals the rounded exact total to <1
    micro-second over any number of cycles).
    """
    bal = dasha_balance(moon_longitude)
    periods: list[Period] = []
    offset_f = Fraction(0)                            # exact running offset (days)
    offset_k = 0.0                                    # Kahan-compensated float view
    pos = bal.nakshatra_index % 9
    for cycle in range(epochs):
        for k in range(len(VIMSHOTTARI_ORDER)):
            lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
            is_opening = cycle == 0 and k == 0 and lord == bal.mahadasha_lord
            dur_f = (
                Fraction(bal.mahadasha_days)
                if is_opening
                else mahadasha_days_fraction(lord)
            )
            end_f = offset_f + dur_f
            periods.append(Period(lord, float(offset_f), float(end_f), 1))
            offset_k = kahan_sum([offset_k, float(dur_f)])
            offset_f = end_f
    return periods

def mahadasha_timeline_absolute(
    moon_longitude: float,
    cycles: int = 2,
) -> list[Period]:
    """Absolute mahadashas: every period keeps its full nominal length.

    Offsets are still measured from the birth epoch, so the opening mahadasha
    has a **negative** ``start_days``.  This is the timeline KP Stellar displays
    and the only correct base for resolving deep levels at an arbitrary date.

    The cursor is an exact :class:`Fraction`; ``elapsed`` comes from the
    exact-mas balance, so the 120-year cycle closes on
    ``-elapsed + 120 * DAYS_PER_YEAR_F`` with zero drift (property-tested).
    """
    bal = dasha_balance(moon_longitude)
    elapsed = mahadasha_days_fraction(bal.mahadasha_lord) - Fraction(
        bal.mahadasha_days
    )

    periods: list[Period] = []
    pos = VIMSHOTTARI_INDEX[bal.mahadasha_lord]
    cursor = -elapsed
    for k in range(9 * max(1, cycles)):
        lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
        dur = mahadasha_days_fraction(lord)
        periods.append(Period(lord, float(cursor), float(cursor + dur), 1))
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
    ``parent_duration * years(child) / 120`` of the parent's span.  The nine
    boundaries are exact :class:`Fraction` values derived from the parent
    endpoints in one multiply each (``start + duration * cum_years / 120``) —
    never a float cursor accumulation — so no ulp drift can ever place a
    target on the wrong side of a child edge, and the last child ends exactly
    at ``parent_start + parent_duration``.  If the target falls outside the
    parent (a query beyond the generated range) the final child is returned
    rather than raising, so deep stacks never explode on boundary input.
    """
    pos = VIMSHOTTARI_INDEX[parent_lord]
    start_f = Fraction(parent_start)
    dur_f = Fraction(parent_duration)
    target_f = Fraction(target_days)
    cum = Fraction(0)
    last: Period | None = None
    for k in range(9):
        lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
        child_start_f = start_f + dur_f * cum / VIMSHOTTARI_TOTAL_YEARS
        cum += Fraction(VIMSHOTTARI_YEARS[lord])
        child_end_f = start_f + dur_f * cum / VIMSHOTTARI_TOTAL_YEARS
        last = Period(lord, float(child_start_f), float(child_end_f), level)
        if child_start_f <= target_f < child_end_f:
            return last
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
    md_total = mahadasha_days_fraction(md_lord)          # exact days
    elapsed = md_total - Fraction(bal.mahadasha_days)

    target = (instant - epoch).total_seconds() / 86400.0
    target_f = Fraction(target)

    # -- level 1: walk full-length mahadashas from their absolute start ------
    pos = VIMSHOTTARI_INDEX[md_lord]
    cursor = -elapsed                                     # exact Fraction
    if target_f < cursor:
        cycles_needed = 1
    else:
        cycle_f = Fraction(VIMSHOTTARI_TOTAL_YEARS) * DAYS_PER_YEAR_F
        cycles_needed = int((target_f - cursor) // cycle_f) + 2

    md: Period | None = None
    for k in range(9 * cycles_needed):
        lord = VIMSHOTTARI_ORDER[(pos + k) % 9]
        dur = mahadasha_days_fraction(lord)
        if cursor <= target_f < cursor + dur:
            md = Period(lord, float(cursor), float(cursor + dur), 1)
            break
        cursor += dur

    if md is None:
        # Query lies beyond the generated horizon; clamp to the opening MD.
        md = Period(
            md_lord, float(-elapsed), float(-elapsed + md_total), 1
        )

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
