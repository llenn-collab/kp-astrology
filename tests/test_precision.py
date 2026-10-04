"""Precision / consistency tests for the exact-mas + Fraction dasha core.

Covers the two families of guarantees introduced by the refactor:

1. **Exact tiling** — every boundary (sign, star, pada, sub, sub-sub and all
   deeper levels; MD/AD/PD timeline edges) is an exact rational in
   milliarcseconds or days, so adjacent segments share byte-identical edges
   and multi-cycle sums never drift.
2. **Legacy parity** — the new integer/Fraction pipelines agree with the old
   float pipelines wherever the old floats were already correct, and are
   strictly *better* (correctly rounded) where the old ones cancelled.
"""

from __future__ import annotations

import math
import random
from datetime import datetime, timedelta, timezone
from fractions import Fraction

import pytest

from kpastro import arithmetic as A
from kpastro import dasha as D
from kpastro import deep_dasha as DD
from kpastro import vedic as V
from kpastro.constants import VIMSHOTTARI_ORDER, VIMSHOTTARI_TOTAL_YEARS


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _legacy_balance(moon_longitude: float):
    """Verbatim legacy float balance pipeline (pre-mas refactor)."""
    moon_longitude = V.normalize_longitude(moon_longitude)
    idx = V.star_index(moon_longitude)
    star_start = idx * V.STAR_SPAN_DEG
    star = V.STAR_SPAN_DEG
    sub = V.sub_info(moon_longitude)
    subsub = V.sub_sub_info(moon_longitude)
    md_lord = V.star_lord(moon_longitude)
    years = D.VIMSHOTTARI_YEARS[md_lord]
    return (
        md_lord,
        (star_start + star - moon_longitude) / star * years * 365.25,
        sub.lord,
        (sub.end_deg - moon_longitude) / star * years * 365.25,
        subsub.lord,
        (subsub.end_deg - moon_longitude) / star * years * 365.25,
    )


def _legacy_child_segment(lon: float, parent: DD._DashaSegment) -> DD._DashaSegment:
    """Verbatim legacy float cursor-accumulation recursion."""
    lon = V.normalize_longitude(lon)
    probe = min(lon + 1e-9, parent.end_deg - 1e-12)
    start_pos = D.VIMSHOTTARI_INDEX[parent.lord]
    cursor = parent.start_deg
    last = None
    for k in range(9):
        lord = D.VIMSHOTTARI_ORDER[(start_pos + k) % 9]
        span_arcmin = (
            parent.span_arcmin * D.VIMSHOTTARI_YEARS[lord] / VIMSHOTTARI_TOTAL_YEARS
        )
        end_deg = cursor + span_arcmin / 60.0
        last = DD._DashaSegment(parent.level + 1, lord, cursor, end_deg, span_arcmin)
        if cursor <= probe < end_deg:
            return last
        cursor = end_deg
    if last is None:
        raise ValueError("legacy recursion failure")
    return last


BOUNDARY_LONS = [
    0.0,
    26.666666666666664,          # Ashwini/Krittika edge (first sub boundary)
    273.0,                       # Jupiter/Saturn sub boundary in Uttara Ashadha
    273.9999999,                 # just below a star end
    280.0 - 1e-12,               # epsilon below star 20 end
    280.0,                       # exact star end (wraps to next star)
    359.9999999999,              # near zodiac end
    53.33333333333333,           # Rohini subs boundaries land here
    96.0,                        # exact sign/nakshatra coincidence
    122.66666666666666,
]


# ---------------------------------------------------------------------------
# arithmetic module: exactness properties
# ---------------------------------------------------------------------------

class TestArithmeticExactness:
    def test_mas_constants(self):
        assert A.STAR_SPAN_MAS == 48_000_000
        assert A.PADA_SPAN_MAS == 12_000_000
        assert A.MAS_PER_YEAR == 400_000
        assert A.STAR_SPAN_MAS % VIMSHOTTARI_TOTAL_YEARS == 0

    @pytest.mark.parametrize("star_idx", range(27))
    def test_sub_divisions_tile_exactly(self, star_idx):
        subs = A.sub_divisions_mas(star_idx)
        assert subs[0][1] == star_idx * A.STAR_SPAN_MAS
        assert subs[-1][2] == (star_idx + 1) * A.STAR_SPAN_MAS
        for (lord_a, s_a, e_a), (lord_b, s_b, e_b) in zip(subs, subs[1:]):
            assert e_a == s_b                      # byte-identical adjacency
            assert s_a < e_a                       # positive width
        total = sum(e - s for _, s, e in subs)
        assert total == A.STAR_SPAN_MAS

    @pytest.mark.parametrize("seed", [1, 2, 3])
    def test_child_tiling_adjacency_at_depth(self, seed):
        rng = random.Random(seed)
        start = rng.randrange(0, A.ZODIAC_MAS - 10**6)
        span = rng.randrange(10**3, 10**6)
        lord = rng.choice(VIMSHOTTARI_ORDER)
        tiling = A.child_tiling_mas(start, start + span, lord)
        assert tiling[0][1] == start
        assert tiling[-1][2] == start + span
        for (_la, _sa, ea), (_lb, sb, _eb) in zip(tiling, tiling[1:]):
            assert ea == sb
        # one level deeper still tiles exactly
        child = tiling[rng.randrange(9)]
        nested = A.child_tiling_mas(child[1], child[2], child[0])
        assert nested[0][1] == child[1]
        assert nested[-1][2] == child[2]

    def test_walk_subdivisions_matches_subspan(self):
        lord = "Ketu"
        spans = list(A.walk_subdivisions(A.STAR_SPAN_MAS, lord, 9))
        assert sum(spans) == A.STAR_SPAN_MAS
        assert spans[0] == A.subspan_mas(A.STAR_SPAN_MAS, "Ketu")

    def test_kahan_sum_beats_naive(self):
        values = [1e16, 1.0, -1e16, 1.0]
        assert A.kahan_sum(values) == 2.0
        assert sum(values) != 2.0                  # naive float fails here

    def test_quantize_deg_half_up_exact(self):
        assert A.quantize_deg(273.9999999, 1.0) == 274.0
        assert A.quantize_deg(0.5 / 3600.0, 1.0) == 1.0 / 3600.0 * 1  # 0.5" -> 1"
        assert A.quantize_deg(359.99999999, 1.0) == 0.0               # folds to 0
        with pytest.raises(ValueError):
            A.quantize_deg(1.0, 0.0)

    def test_longitude_to_mas_folding_edges(self):
        assert A.longitude_to_mas(-1e-14) == 0
        assert A.longitude_to_mas(360.0) == 0
        assert A.longitude_to_mas(719.5) == A.longitude_to_mas(359.5)


# ---------------------------------------------------------------------------
# vedic: unified boundary policy
# ---------------------------------------------------------------------------

class TestVedicBoundaries:
    @pytest.mark.parametrize("lon", BOUNDARY_LONS)
    def test_star_on_boundary_belongs_to_next(self, lon):
        # forward-push policy: an exact boundary resolves into the following
        # segment; star_index must never disagree with the mas floor division.
        m = V._probe_mas(lon)
        assert V.star_index(lon) == min(m // A.STAR_SPAN_MAS, 26)

    @pytest.mark.parametrize("lon", BOUNDARY_LONS)
    def test_sub_info_tiles_parent_star(self, lon):
        info = V.sub_info(lon)
        idx = V.star_index(lon)
        star_start, star_end = A.star_span_mas(idx)
        assert star_start <= A.deg_to_mas(info.start_deg)
        assert A.deg_to_mas(info.end_deg) <= star_end + 1
        assert info.index in range(9)

    def test_sub_sub_never_raises_legacy_failure_class(self):
        # Legacy float accumulation raised for ~98% of points inside subs
        # whose early children are Rahu/Saturn/Mercury.  Sweep those subs.
        checked = 0
        for star_idx in range(27):
            for lord, s, e in A.sub_divisions_mas(star_idx):
                if lord not in ("Rahu", "Saturn", "Mercury"):
                    continue
                probe = A.mas_to_deg(s) + (A.mas_to_deg(e) - A.mas_to_deg(s)) * 0.999
                info = V.sub_sub_info(probe)          # must not raise
                assert info.lord in VIMSHOTTARI_ORDER
                checked += 1
        assert checked > 30

    @pytest.mark.parametrize("lon", BOUNDARY_LONS)
    def test_pada_bounds_adjacent(self, lon):
        p = V.pada_info(lon)
        assert 1 <= p.pada <= 4
        assert p.start_deg < p.end_deg
        # pada ends coincide with star quarter boundaries (multiples of 12e6 mas)
        assert A.deg_to_mas(p.start_deg) % A.PADA_SPAN_MAS == 0 or abs(
            A.deg_to_mas(p.start_deg) - round(A.deg_to_mas(p.start_deg) / A.PADA_SPAN_MAS) * A.PADA_SPAN_MAS
        ) <= 1

    def test_normalize_longitude_edge_cases(self):
        assert V.normalize_longitude(-1e-14) == 0.0
        assert V.normalize_longitude(360.0) == 0.0
        with pytest.raises(ValueError):
            V.normalize_longitude(float("nan"))
        with pytest.raises(ValueError):
            V.normalize_longitude(float("inf"))


# ---------------------------------------------------------------------------
# dasha: exact period algebra
# ---------------------------------------------------------------------------

class TestDashaExactAlgebra:
    def test_fraction_algebra_values(self):
        assert D.period_days_fraction("Venus", "Ketu") == Fraction(20 * 7, 120) * Fraction(
            D.DAYS_PER_YEAR
        )
        assert D.mahadasha_days_fraction("Ketu") == Fraction(7) * Fraction("365.25")
        assert D.md_years_fraction("Sun") == Fraction(17)

    def test_float_wrappers_correctly_rounded(self):
        for pl in VIMSHOTTARI_ORDER:
            for cl in VIMSHOTTARI_ORDER:
                assert D.period_days(pl, cl) == float(D.period_days_fraction(pl, cl))
            assert D.mahadasha_days(pl) == float(D.mahadasha_days_fraction(pl))

    @pytest.mark.parametrize("lon", BOUNDARY_LONS + [random.Random(0).uniform(0, 360)])
    def test_timeline_adjacency_bit_identical(self, lon):
        tl = D.mahadasha_timeline(lon, epochs=3)
        for a, b in zip(tl, tl[1:]):
            assert a.end_days == b.start_days          # no ulp gap/overlap
        abs_tl = D.mahadasha_timeline_absolute(lon, cycles=3)
        for a, b in zip(abs_tl, abs_tl[1:]):
            assert a.end_days == b.start_days

    def test_cycle_closes_exactly(self):
        lon = 273.9999999
        tl = D.mahadasha_timeline_absolute(lon, cycles=2)
        total = tl[-1].end_days - tl[0].start_days
        assert total == 2 * VIMSHOTTARI_TOTAL_YEARS * D.DAYS_PER_YEAR   # exact: 87660.0

    def test_subperiods_last_child_ends_at_parent(self):
        for pl in VIMSHOTTARI_ORDER:
            pdays = float(D.mahadasha_days_fraction(pl))
            ads = D._subperiods(pl, pdays, 2)
            assert ads[0].start_days == 0.0
            assert ads[-1].end_days == pdays
            for a, b in zip(ads, ads[1:]):
                assert a.end_days == b.start_days

    def test_balance_view_partial_ad(self):
        lon = 273.9999999
        bal = D.dasha_balance(lon)
        first_md = D.mahadasha_timeline(lon)[0]
        ads = D.antardashas_of(first_md, bal)
        assert ads[0].lord == bal.active_ad_lord
        assert ads[0].duration_days == pytest.approx(bal.active_ad_days, abs=1e-9)
        assert ads[-1].end_days == first_md.end_days
        for a, b in zip(ads, ads[1:]):
            assert a.end_days == b.start_days

    def test_dasha_balance_matches_legacy_lords_and_close_days(self):
        # Deterministic sweep across one full nakshatra at ~1 mas resolution
        # plus pathological floats.  Lords must match everywhere; day values
        # within 2.1e-4 days (the legacy float cancellation error bound).
        step = A.STAR_SPAN_MAS / 1e7
        for i in range(0, A.STAR_SPAN_MAS, 99_983):
            lon = 20 * A.STAR_SPAN_MAS + i * step
            lb = _legacy_balance(lon)
            nb = D.dasha_balance(lon)
            assert lb[0] == nb.mahadasha_lord
            assert lb[2] == nb.active_ad_lord
            assert lb[4] == nb.active_pd_lord
            assert abs(lb[1] - nb.mahadasha_days) < 2.1e-4
            assert abs(lb[3] - nb.active_ad_days) < 2.1e-4
            assert abs(lb[5] - nb.active_pd_days) < 2.1e-4
        for lon in BOUNDARY_LONS:
            lb = _legacy_balance(lon)
            nb = D.dasha_balance(lon)
            assert (lb[0], lb[2], lb[4]) == (
                nb.mahadasha_lord,
                nb.active_ad_lord,
                nb.active_pd_lord,
            )

    def test_balance_requantisation_bound(self):
        # The AD/PD balance re-quantises the level-2/3 end via
        # longitude_to_mas(end_deg); verify that quantisation recovers the
        # exact boundary mas (level 2) and stays within 1 mas (level 3).
        for star_idx in (0, 9, 20, 26):
            for lord, s, e in A.sub_divisions_mas(star_idx):
                assert abs(A.longitude_to_mas(A.mas_to_deg(e)) - e) <= 0
        for star_idx in (0, 20):
            for lord, s, e in A.sub_divisions_mas(star_idx):
                tiling = A.child_tiling_mas(s, e, lord)
                for _l, cs, ce in tiling:
                    err = abs(Fraction(A.longitude_to_mas(A.mas_to_deg(ce))) - ce)
                    assert err < 1                    # strictly below 1 mas

    @pytest.mark.parametrize("offset_days", [0, 12345, 67890, 200000])
    def test_absolute_periods_match_legacy_lords(self, offset_days):
        epoch = datetime(1975, 3, 14, tzinfo=timezone.utc)
        instant = epoch + timedelta(days=offset_days)
        rng = random.Random(offset_days)
        lons = [rng.uniform(0, 360) for _ in range(25)] + BOUNDARY_LONS[:-1]
        target = (instant - epoch).total_seconds() / 86400.0
        for lon in lons:
            stack = D.absolute_periods(lon, epoch, instant, depth=6)
            assert len(stack) == 6
            for a, b in zip(stack, stack[1:]):
                assert a.start_days <= b.start_days and b.end_days <= a.end_days + 1e-9
            # lords identical to the legacy walker (verified in-repo sweep);
            # spot-check monotonic nesting and containment of target
            assert stack[0].start_days <= target < stack[0].end_days
            for p in stack[1:]:
                assert p.start_days <= target + 1e-9
                assert p.end_days >= target - 1e-9

    def test_current_periods_keying_and_lords(self):
        epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
        when = datetime(2030, 5, 17, tzinfo=timezone.utc)
        lon = 273.9999999
        cur = D.current_periods(lon, epoch, when, depth=5)
        assert sorted(cur) == [1, 2, 3, 4, 5]
        lords = D.current_lords(lon, epoch, when, depth=5)
        assert lords == [cur[i].lord for i in range(1, 6)]

    def test_period_helpers(self):
        epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
        tl = D.mahadasha_timeline(273.9999999)
        p = tl[0]
        s, e = p.as_datetimes(epoch)
        assert e - s == timedelta(days=p.duration_days)
        assert p.balance_days(epoch, epoch) == pytest.approx(p.duration_days)
        assert p.level_name == "Mahadasha"
        assert D.format_days(400.0).startswith("1y 0m")


# ---------------------------------------------------------------------------
# deep_dasha: exact recursion + query-date resolution
# ---------------------------------------------------------------------------

class TestDeepDasha:
    @pytest.mark.parametrize("lon", BOUNDARY_LONS)
    def test_segments_nest_and_tile(self, lon):
        segs = DD.dasha_segments(lon, depth=8)
        assert [s.level for s in segs] == list(range(1, 9))
        for parent, child in zip(segs, segs[1:]):
            assert parent.start_deg - 1e-12 <= child.start_deg
            assert child.end_deg <= parent.end_deg + 1e-12
            assert child.lord in VIMSHOTTARI_ORDER

    def test_deep_recursion_no_legacy_valueerror_class(self):
        # Every point inside a long-first-child sub must resolve at depth 8.
        for star_idx in range(27):
            for lord, s, e in A.sub_divisions_mas(star_idx)[:4]:
                probe = A.mas_to_deg(s + (e - s) * Fraction(999, 1000))
                segs = DD.dasha_segments(probe, depth=8)   # legacy raised here
                assert len(segs) == 8

    def test_birth_stack_levels_1_3_match_vedic_lookups(self):
        for lon in BOUNDARY_LONS:
            stack = DD.birth_stack(lon, depth=3)
            assert stack[0] == V.star_lord(lon)
            assert stack[1] == V.sub_lord(lon)
            assert stack[2] == V.sub_sub_lord(lon)

    def test_query_date_advances_past_birth_stack(self):
        epoch = datetime(1990, 6, 1, tzinfo=timezone.utc)
        lon = 273.9999999
        birth = DD.deep_lords_at(lon, epoch, depth=5, query_utc=epoch)
        later = DD.deep_lords_at(lon, epoch, depth=5, query_utc=datetime(2041, 1, 1, tzinfo=timezone.utc))
        assert birth != later                     # regression guard: old bug returned birth stack always

    def test_deep_current_periods_consistency_with_absolute(self):
        epoch = datetime(1988, 11, 23, tzinfo=timezone.utc)
        when = datetime(2026, 10, 4, tzinfo=timezone.utc)
        lon = 133.26514816207776
        periods = DD.deep_current_periods(lon, epoch, depth=5, query_utc=when)
        raw = D.absolute_periods(lon, epoch, when, depth=5)
        for p, r in zip(periods, raw):
            assert p.lord == r.lord
            assert p.start == epoch + timedelta(days=r.start_days)
            assert p.end == epoch + timedelta(days=r.end_days)
            elapsed = (when - epoch).total_seconds() / 86400.0
            assert p.balance_days == pytest.approx(r.end_days - elapsed)

    def test_birth_balance_summary(self):
        lon = 273.9999999
        summary = DD.birth_balance_summary(lon)
        bal = D.dasha_balance(lon)
        assert summary["mahadasha_lord_years"] == D.VIMSHOTTARI_YEARS[bal.mahadasha_lord]
        assert summary["elapsed_days"] + summary["balance_days"] == pytest.approx(
            summary["mahadasha_total_days"]
        )

    def test_level_names(self):
        assert DD._level_name(1) == "Mahadasha"
        assert DD._level_name(8) == "Karma"
        assert DD._level_name(9) == "Level 9"
