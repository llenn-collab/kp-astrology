"""A complete KP chart: compute, then render as professional text tables."""

from __future__ import annotations

import json

from dataclasses import dataclass, field
from datetime import date as DateType, datetime, timedelta, time as TimeType
from typing import Any, Iterable, Optional

from .constants import (
    AYANAMSA_LABELS,
    CUSP_NAMES,
    KP_PLANET_ABBR,
    KP_PLANET_ORDER,
    PLANET_ABBR,
    ROMAN,
    SIGN_ABBR,
    TZ_ZONE_NAMES,
)
from .dasha import (
    Balance,
    Period,
    antardashas_of,
    current_periods,
    dasha_balance,
    format_days,
    mahadasha_days,
    mahadasha_timeline,
    mahadasha_timeline_absolute,
)
from .ephemeris import SwissEphemeris
from .horary import MAX_HORARY_NUMBER
from .panchanga import (
    day_lord,
    dasha_balance_str,
    balance_days_from_moon,
    karana,
    local_datetime,
    nakshatra_pada,
    nitya_yoga,
    sunrise_sunset_clock,
    tithi,
)
from .horary import cusps_from_horary_lagna
from .significators import (
    Signification,
    cusp_sub_lords,
    house_significations,
    house_of_longitude,
    planet_significations,
    ruling_planets,
)
from .vedic import format_longitude, normalize_longitude, point_info
from .deep_dasha import deep_current_periods


@dataclass(frozen=True)
class BirthInfo:
    """Birth / event details. ``time`` is local; ``tz_hours`` is the UTC offset."""
    date: DateType
    time: TimeType
    latitude: float
    longitude: float
    tz_hours: float = 0.0
    place: str = ""

    def __post_init__(self) -> None:
        try:
            datetime.combine(self.date, self.time)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"invalid date/time combination: {self.date} {self.time}"
            ) from exc
        if not -90.0 <= self.latitude <= 90.0:
            raise ValueError(
                f"latitude must be within [-90, 90], got {self.latitude}"
            )
        if not -180.0 <= self.longitude <= 180.0:
            raise ValueError(
                f"longitude must be within [-180, 180], got {self.longitude}"
            )
        if not -24.0 <= self.tz_hours <= 24.0:
            raise ValueError(
                f"tz_hours must be within [-24, 24], got {self.tz_hours}"
            )
        if 66.5 < abs(self.latitude) <= 90.0:
            raise ValueError(
                f"latitude {self.latitude} is beyond the Placidus house-cutoff "
                f"(|lat| <= 66.5 deg); Placidus cusps are undefined there"
            )

    def utc_datetime(self) -> datetime:
        local = datetime.combine(self.date, self.time)
        return local - timedelta(hours=self.tz_hours)


@dataclass(frozen=True)
class PlanetPos:
    name: str
    longitude: float
    house: int
    sign: str
    sign_degree: float
    sign_lord: str
    star: str
    star_lord: str
    sub_lord: str
    sub_sub_lord: str
    pada: int
    speed_deg_day: float
    retrograde: bool


@dataclass(frozen=True)
class CuspPos:
    house: int
    longitude: float
    sign: str
    sign_lord: str
    star: str
    star_lord: str
    sub_lord: str
    sub_sub_lord: str


@dataclass
class Chart:
    birth: BirthInfo
    jd_ut: float
    ayanamsa: float
    ayanamsa_mode: str
    node: str
    planets: list[PlanetPos]
    cusps: list[CuspPos]
    ascendant: float
    midheaven: float
    armc: float
    planet_lon: dict[str, float]
    balance: Balance
    mahadashas: list[Period]
    current: dict[int, Period]
    planet_significators: dict[str, list[Signification]]
    house_significators: list[list[tuple[str, int]]]
    cusp_sublords: dict[int, str]
    ruling: list = field(default_factory=list)
    #: UTC instant the dasha stack in ``current`` was resolved for.
    query_utc: datetime | None = None
    #: Sidereal ascendant imposed by a KP horary number, when one was supplied.
    #:
    #: When set, ``cusps`` are the Placidus cusps belonging to *that* lagna,
    #: while ``ascendant`` and ``ruling`` stay the astronomical ones for the
    #: birth instant -- so ``cusps[0].longitude`` need not equal ``ascendant``.
    #: That is what KP Stellar prints: a horary house frame over birth-time
    #: planets and ruling planets.
    horary_lagna: float | None = None

    @property
    def birth_utc(self) -> datetime:
        return self.birth.utc_datetime()

    @property
    def effective_query_utc(self) -> datetime:
        """``query_utc`` when set, otherwise the birth moment."""
        return self.query_utc or self.birth.utc_datetime()


def compute_chart(
    birth: BirthInfo,
    ayanamsa: str = "lahiri",
    node: str = "mean",
    eph: SwissEphemeris | None = None,
    query_utc: datetime | None = None,
    house_latitude_model: str = "geocentric",
    horary_lagna: float | None = None,
) -> Chart:
    """Compute every KP layer for a birth chart.

    ``query_utc`` is the instant the Vimshottari stack is resolved for.  It
    defaults to the birth moment; pass ``datetime.utcnow()`` (or an explicit
    date) to reproduce a commercial app's "current dasha" panel.
    """
    eph = eph or SwissEphemeris(
        ayanamsa=ayanamsa,
        node=node,
        house_latitude_model=house_latitude_model,
    )
    if eph.ayanamsa_mode != ayanamsa or eph.node != node:
        raise ValueError(
            f"ayanamsa/node do not match the injected eph instance: "
            f"eph uses ayanamsa={eph.ayanamsa_mode!r}, node={eph.node!r}; "
            f"requested ayanamsa={ayanamsa!r}, node={node!r}"
        )
    dt_utc = birth.utc_datetime()
    instant_utc = query_utc or dt_utc

    jd = eph.jd_ut(dt_utc)
    ayan = eph.ayanamsa(jd)
    sider = eph.sidereal_positions(jd)
    cusps, asc, mc, armc = eph.houses(jd, birth.latitude, birth.longitude)
    if horary_lagna is not None:
        # A KP horary chart takes its lagna from the querent's number rather
        # than from the clock, so its houses belong to that ascendant.  The
        # planets, the astronomical ascendant and the ruling planets all stay
        # on the birth data, exactly as KP Stellar reports them.
        cusps = cusps_from_horary_lagna(
            horary_lagna, eph, jd, birth.latitude, birth.longitude
        )

    planets: list[PlanetPos] = []
    for name in ("Sun", "Moon", "Mars", "Mercury", "Jupiter", "Venus", "Saturn",
                 "Rahu", "Ketu"):
        lon, speed = sider[name]
        info = point_info(lon)
        planets.append(
            PlanetPos(
                name=name,
                longitude=lon,
                house=house_of_longitude(lon, cusps),
                sign=info.sign,
                sign_degree=info.sign_degree,
                sign_lord=info.sign_lord,
                star=info.star,
                star_lord=info.star_lord,
                sub_lord=info.sub_lord,
                sub_sub_lord=info.sub_sub_lord,
                pada=info.pada,
                speed_deg_day=speed,
                retrograde=(speed < 0) or (name in ("Rahu", "Ketu")),
            )
        )

    cusp_pos: list[CuspPos] = []
    for i, c in enumerate(cusps):
        info = point_info(c)
        cusp_pos.append(
            CuspPos(
                house=i + 1,
                longitude=c,
                sign=info.sign,
                sign_lord=info.sign_lord,
                star=info.star,
                star_lord=info.star_lord,
                sub_lord=info.sub_lord,
                sub_sub_lord=info.sub_sub_lord,
            )
        )

    moon_lon = sider["Moon"][0]
    balance = dasha_balance(moon_lon)
    mds = mahadasha_timeline(moon_lon)
    # NOTE: epoch == birth, instant == query. Passing the birth moment for both
    # (the previous behaviour) always yields the birth stack, never the current
    # one -- that was the Saturn/Saturn bug.
    current = current_periods(moon_lon, dt_utc, instant_utc, depth=5)

    positions = {name: lon for name, (lon, _) in sider.items()}
    chart = Chart(
        birth=birth,
        jd_ut=jd,
        ayanamsa=ayan,
        ayanamsa_mode=ayanamsa,
        node=node,
        planets=planets,
        cusps=cusp_pos,
        ascendant=asc,
        midheaven=mc,
        armc=armc,
        planet_lon=positions,
        balance=balance,
        mahadashas=mds,
        current=current,
        planet_significators=planet_significations(positions, cusps),
        house_significators=house_significations(positions, cusps),
        cusp_sublords=cusp_sub_lords(cusps),
        ruling=[
            rp
            for rp in ruling_planets(asc, moon_lon, birth.date.weekday())
        ],
        query_utc=instant_utc,
        horary_lagna=None if horary_lagna is None else normalize_longitude(horary_lagna),
    )
    return chart


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _dms(lon: float) -> str:
    return format_longitude(lon, arcsec=False)


def render_planets(chart: Chart) -> str:
    lines = [
        f" {'Planet':<9} {'Longitude':>10} {'Sign':<12} {'Star':<18} "
        f"{'Star-Lord':<10} {'Sub':<9} {'Sub-Sub':<9} {'House':>5} {'R':>2}"
    ]
    lines.append("-" * len(lines[0]))
    for p in sorted(chart.planets, key=lambda x: x.longitude):
        lines.append(
            f" {p.name:<9} {_dms(p.sign_degree):<10} {p.sign:<12} "
            f"{p.star:<18} {p.star_lord:<10} {p.sub_lord:<9} "
            f"{p.sub_sub_lord:<9} {p.house:>5} "
            f"{'R' if p.retrograde else '.':>2}"
        )
    return "\n".join(lines)


def render_cusps(chart: Chart) -> str:
    lines = [
        f" {'House':>5} {'Cusp':>10} {'Sign':<12} {'Star':<18} "
        f"{'Star-Lord':<10} {'Sub':<9} {'Sub-Sub':<9}"
    ]
    lines.append("-" * len(lines[0]))
    for c in chart.cusps:
        lines.append(
            f" {c.house:>5} {_dms(c.longitude % 30.0):>10} {c.sign:<12} "
            f"{c.star:<18} {c.star_lord:<10} {c.sub_lord:<9} {c.sub_sub_lord:<9}"
        )
    return "\n".join(lines)


def render_significators(chart: Chart) -> str:
    lines = [
        " House  Significators (tier: 1 occupant, 2 occupant-star, 3 cuspal lord,"
        " 4 cuspal-star)  [sub-lord = final arbiter]"
    ]
    lines.append("-" * len(lines[0]))
    for i, tiers in enumerate(chart.house_significators, start=1):
        sig = ", ".join(f"{p}({t})" for p, t in tiers) or "—"
        judge = chart.cusp_sublords.get(i, "?")
        lines.append(f"  {i:>4}   {sig:<52} arbiter: {judge}")
    return "\n".join(lines)


def render_ruling(chart: Chart) -> str:
    return "\n".join(f"  {rp.planet:<10} {rp.source}" for rp in chart.ruling)


def render_deep_dasha(
    chart: Chart,
    depth: int = 5,
    query_utc: datetime | None = None,
) -> str:
    """Self-contained deep dasha renderer. Does NOT depend on render_dasha."""
    moon_lon = chart.planet_lon["Moon"]
    birth_utc = chart.birth.utc_datetime()
    instant = query_utc or chart.effective_query_utc
    periods = deep_current_periods(moon_lon, birth_utc, depth=depth, query_utc=instant)

    lines = [f" VIMSHOTTARI DASHA - DEEP ({depth} LEVELS)"]
    lines.append(f" Resolved for: {instant:%Y-%m-%d %H:%M:%S} UT"
                 f"   (birth: {birth_utc:%Y-%m-%d %H:%M:%S} UT)")
    lines.append("-" * 108)
    lines.append(
        f" {'Level':<18} {'Lord':<8} {'Start UT':>19} {'End UT':>19} "
        f"{'Duration':>12} {'Balance':>12}"
    )
    lines.append("-" * 108)

    for p in periods:
        lines.append(
            f" {p.name:<18} {p.lord:<8} "
            f"{p.start:%Y-%m-%d %H:%M:%S} {p.end:%Y-%m-%d %H:%M:%S} "
            f"{format_days(p.duration_days):>12} "
            f"{format_days(p.balance_days):>12}"
        )

    stack = " / ".join(p.lord for p in periods)
    lines.append("")
    lines.append(f" Current stack: {stack}")

    # Absolute mahadasha timeline: every MD at full nominal length, the opening
    # one starting before birth.  This is the KP Stellar convention and the only
    # one that lines up with the deep levels above.
    moon_lon = chart.planet_lon["Moon"]
    absolute_mds = mahadasha_timeline_absolute(moon_lon, cycles=2)
    lines.append("")
    lines.append(" Mahadasha timeline, absolute (1 yr = 365.25 d):")
    lines.append("-" * 46)
    lines.append(f" {'Lord':<10} {'Start':>10} {'End':>10} {'Days':>9}")
    for md in absolute_mds:
        start, end = md.as_datetimes(birth_utc)
        lines.append(
            f" {md.lord:<10} {start:%Y-%m-%d} {end:%Y-%m-%d} "
            f"{md.duration_days:>8.1f}"
        )
    return "\n".join(lines)


def render_chart(chart: Chart, dasha_depth: int = 5) -> str:
    """Human-readable representation of the full KP chart."""
    birth = chart.birth
    out = []
    out.append("=" * 72)
    out.append(" KRISHNAMURTI PADDHATI  -  birth chart")
    out.append("=" * 72)
    out.append(
        f" {birth.date} {birth.time:%H:%M}  "
        f"({birth.latitude:.4f}, {birth.longitude:.4f})"
        f"  tz={birth.tz_hours:+.1f}  {birth.place}".rstrip()
    )
    out.append(
        f" Ayanamsa: {chart.ayanamsa_mode} = "
        f"{format_longitude(chart.ayanamsa)}  "
        f"node: {chart.node}  |  Asc {format_longitude(chart.ascendant)}  "
        f"MC {format_longitude(chart.midheaven)}"
    )
    out.append("")
    out.append("PLANETS (sidereal, KP subdivision)")
    out.append(render_planets(chart))
    out.append("")
    out.append("HOUSE CUSPS (Placidus, sidereal)")
    out.append(render_cusps(chart))
    out.append("")
    out.append("SIGNIFICATORS (Bhaav Nirdeshan)")
    out.append(render_significators(chart))
    out.append("")
    out.append("RULING PLANETS")
    out.append(render_ruling(chart))
    out.append("")
    out.append(render_deep_dasha(chart, depth=dasha_depth))
    out.append("")
    out.append("=" * 72)
    return "\n".join(out)


# ---------------------------------------------------------------------------
# JSON export — schema aligned with KP Stellar (temp_v2.json)
# ---------------------------------------------------------------------------

def _deg_str(lon: float) -> str:
    """Format longitude as DD°MM'SS" with zero padding."""
    lon = lon % 360.0
    d = int(lon)
    rem = (lon - d) * 60.0
    m = int(rem)
    s = round((rem - m) * 60.0)
    if s == 60:
        s = 0
        m += 1
    if m == 60:
        m = 0
        d = (d + 1) % 360
    return f"{d:02d}\u00b0{m:02d}'{s:02d}\""


def _strip_strings(obj: Any) -> Any:
    """Recursively strip whitespace from every dict key and string value.

    Downstream formatters (``format_longitude``, ``point_info``) emit padded
    strings such as ``'24°07'44.7 "'`` and ``'Saturn '``.  Left in place they
    break exact-match diffing against reference JSON, corrupt key lookups, and
    waste LLM tokens.  Normalising once at the serialisation boundary keeps the
    internal model untouched while guaranteeing clean output.
    """
    if isinstance(obj, dict):
        return {
            (k.strip() if isinstance(k, str) else k): _strip_strings(v)
            for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [_strip_strings(v) for v in obj]
    if isinstance(obj, str):
        return obj.strip()
    return obj


def _kp_significator_map(chart: Chart) -> dict[int, dict[str, list[str]]]:
    """Compute A/B/C/D significators per house from first principles."""
    occupants: dict[int, list[str]] = {h: [] for h in range(1, 13)}
    for p in chart.planets:
        occupants[p.house].append(p.name)

    house_of_planet: dict[str, int] = {p.name: p.house for p in chart.planets}

    result: dict[int, dict[str, list[str]]] = {}
    for h in range(1, 13):
        cusp = chart.cusps[h - 1]
        sign_lord = cusp.sign_lord

        b = list(occupants[h])
        a = [
            p.name for p in chart.planets
            if house_of_planet.get(p.star_lord) == h
        ]
        c = [p.name for p in chart.planets if p.star_lord == sign_lord]
        d = [sign_lord]

        result[h] = {
            "planets_in_star_of_planets_in_house": sorted(set(a)),
            "planets_in_house": sorted(set(b)),
            "planets_in_star_of_house_lord": sorted(set(c)),
            "sign_lord": d,
        }
    return result


def _planet_significator_houses(
    chart: Chart,
    sig_map: dict[int, dict[str, list[str]]],
) -> dict[str, list[int]]:
    """Houses where each planet is an A/B/C/D significator."""
    out: dict[str, list[int]] = {p.name: [] for p in chart.planets}
    for h in range(1, 13):
        cats = sig_map[h]
        names = (
            set(cats["planets_in_star_of_planets_in_house"])
            | set(cats["planets_in_house"])
            | set(cats["planets_in_star_of_house_lord"])
            | set(cats["sign_lord"])
        )
        for name in names:
            if name in out and h not in out[name]:
                out[name].append(h)
    return {k: sorted(v) for k, v in out.items()}


def _cusp_sublord_houses(chart: Chart) -> dict[str, list[int]]:
    """Houses whose cusp sub-lord is the planet."""
    out: dict[str, list[int]] = {p.name: [] for p in chart.planets}
    for c in chart.cusps:
        if c.sub_lord in out:
            out[c.sub_lord].append(c.house)
    return {k: sorted(v) for k, v in out.items()}


def _node_agency(
    chart: Chart,
    sig_houses: dict[str, list[int]],
) -> dict[str, dict[str, list]]:
    """Rahu/Ketu agency exactly as KP Stellar.

    The agents are the node's **star-lord** and the node's **own sign-lord**
    (the lord of the sign the node occupies).  It is *not* the sign-lord of the
    house cusp the node happens to sit in -- those coincide only by accident
    (e.g. Rahu in Aquarius inside a Capricorn 10th), which is why the bug stayed
    invisible for Rahu while corrupting Ketu.
    """
    nodes: dict[str, dict[str, list]] = {}

    for node_name in ("Rahu", "Ketu"):
        node_planet = next(p for p in chart.planets if p.name == node_name)

        agents = list(
            dict.fromkeys([node_planet.star_lord, node_planet.sign_lord])
        )

        houses: set[int] = set()
        for agent in agents:
            houses.update(sig_houses.get(agent, []))

        nodes[node_name] = {
            "houses": sorted(houses),
            "planets": agents,
        }

    return nodes


def chart_to_kp_json(
    chart: Chart,
    dasha_depth: int = 5,
    query_utc: datetime | None = None,
) -> dict:
    """Convert chart to a KP Stellar-compatible dictionary."""
    sig_map = _kp_significator_map(chart)
    sig_houses = _planet_significator_houses(chart, sig_map)
    extra = _cusp_sublord_houses(chart)

    planets: dict[str, dict] = {}
    for p in chart.planets:
        planets[p.name] = {
            "sign": p.sign,
            "house": p.house,
            "degree": _deg_str(p.sign_degree),
            "sign_lord": p.sign_lord,
            "star_lord": p.star_lord,
            "sub_lord": p.sub_lord,
            "sub_sub_lord": p.sub_sub_lord,
            "sublord_of_houses": sig_houses[p.name],
            "extra_significator_houses": extra[p.name],
            "retrograde": bool(p.retrograde),
        }

    cusps: dict[str, dict] = {}
    for c in chart.cusps:
        key = "Ascendant" if c.house == 1 else str(c.house)
        cusps[key] = {
            "sign": c.sign,
            "degree": _deg_str(c.longitude % 30.0),
            "sign_lord": c.sign_lord,
            "star_lord": c.star_lord,
            "sub_lord": c.sub_lord,
            "sub_sub_lord": c.sub_sub_lord,
            "significators": sig_map[c.house],
        }

    moon_lon = chart.planet_lon["Moon"]
    birth_utc = chart.birth.utc_datetime()
    instant = query_utc or chart.effective_query_utc

    periods = deep_current_periods(
        moon_lon, birth_utc, depth=dasha_depth, query_utc=instant
    )
    dasha = {
        "resolved_for_ut": instant.strftime("%Y-%m-%d %H:%M:%S"),
        "birth_ut": birth_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "current_stack": [p.lord for p in periods],
        "levels": [
            {
                "level": p.name,
                "lord": p.lord,
                "start_ut": p.start.strftime("%Y-%m-%d %H:%M:%S"),
                "end_ut": p.end.strftime("%Y-%m-%d %H:%M:%S"),
                "duration_days": round(p.duration_days, 2),
                "balance_days": round(p.balance_days, 2),
            }
            for p in periods
        ],
    }

    return {
        "ayanamsa": format_longitude(chart.ayanamsa),
        "ayanamsa_mode": chart.ayanamsa_mode,
        "node": chart.node,
        "ascendant": format_longitude(chart.ascendant),
        "midheaven": format_longitude(chart.midheaven),
        "planets": planets,
        "cusps": cusps,
        "nodes": _node_agency(chart, sig_houses),
        "vimsottari_dasha": dasha,
        "legend": {
            "R": "Retrograde planet",
            "planets_in_star_of_planets_in_house":
                "A: planets in the star of planets occupying the house",
            "planets_in_house":
                "B: planets occupying the house",
            "planets_in_star_of_house_lord":
                "C: planets in the star of the house sign-lord",
            "sign_lord":
                "D: sign-lord of the house cusp",
            "sublord_of_houses":
                "houses where the planet is a significator (A/B/C/D)",
            "extra_significator_houses":
                "houses whose cusp sub-lord is the planet",
            "resolved_for_ut":
                "UTC instant the dasha stack was evaluated at (not the birth)",
        },
    }


def render_chart_json(
    chart: Chart,
    dasha_depth: int = 5,
    query_utc: datetime | None = None,
    schema: str = "stellar",
    name: str = "KP Chart",
    gender: str = "",
    horary_no: Optional[int] = None,
    timezone: Optional[str] = None,
) -> str:
    """Serialize the KP Stellar-compatible chart dict to clean JSON text.

    ``schema="stellar"`` (the default) emits the KP Stellar printout layout --
    ``horary_details`` / ``vimsottari_dasa`` / ``ruling_planets`` / ``planets``
    / ``cusps`` / ``nodes_representation`` -- which is what
    ``kp_stellar_output.json`` looks like.  ``schema="detailed"`` emits the
    earlier long-form payload (full lord names, absolute Ascendant/MC,
    UTC dasha stamps) that the rest of this library was validated against.
    """
    if schema == "stellar":
        payload = chart_to_kp_stellar_json(
            chart,
            dasha_depth=dasha_depth,
            query_utc=query_utc,
            name=name,
            gender=gender,
            horary_no=horary_no,
            timezone=timezone,
        )
    elif schema == "detailed":
        payload = chart_to_kp_json(
            chart, dasha_depth=dasha_depth, query_utc=query_utc
        )
    else:
        raise ValueError(f"unknown JSON schema {schema!r}; use 'stellar' or 'detailed'")
    payload = _strip_strings(payload)
    return json.dumps(payload, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# JSON export — the KP Stellar printout schema (kp_stellar_output.json)
# ---------------------------------------------------------------------------
#
# This is the schema the commercial KP Stellar app emits: three-letter planet
# keys, ``sg``/``sl``/``sb``/``ss`` lord columns, house-cusp rows named
# ``Asc``/``II``/.../``XII``, a ``horary_details`` panchanga header, and the
# five Vimshottari levels spelled ``dasa``/``bhukti``/``antara``/``sookshma``/
# ``prana``.  It is a *presentation* of the same ``Chart`` object; nothing here
# recomputes a longitude.
#
# Two house-derived conventions are worth recording because they are not
# obvious from the schema alone:
#
# * A planet's ``signifies`` list is emitted in the group order
#   ``star-lord's occupied house, own house, houses the star-lord owns,
#   houses the planet owns`` (deduplicated).  This reproduces 6 of the 9
#   reference rows byte-for-byte; KP Stellar's own row order for the other
#   three is not a function of anything in the chart and is not reproducible.
#   The trailing parenthesised element, e.g. ``"(IV, VIII)"``, is the set of
#   houses whose **cusp sub-lord** is that planet, printed in Roman numerals.
# * The trailing ``nodes_representation`` block is the node's *star-lord* and
#   the *lord of the sign the node occupies* (not the sign-lord of the cusp
#   the node happens to sit in), together with the union of those two agents'
#   significator houses.

#: Vimshottari level -> the key KP Stellar uses in ``vimsottari_dasa``.
_KP_DASHA_KEYS: tuple[str, ...] = (
    "dasa", "bhukti", "antara", "sookshma", "prana", "deha", "jeeva", "karma",
)


def _kp_abbr(name: str) -> str:
    """``"Jupiter"`` -> ``"JUP"`` (identity for anything unmapped)."""
    return KP_PLANET_ABBR.get(name, name)


def _kp_sorted(names: Iterable[str]) -> list[str]:
    """Sort planet names into KP Stellar's fixed planet-table order."""
    return sorted(
        set(names),
        key=lambda n: KP_PLANET_ORDER.index(n) if n in KP_PLANET_ORDER else 99,
    )


def _planet_flags(chart: Chart) -> dict[str, list[str]]:
    """KP Stellar's per-planet flag list.

    ``R`` = retrograde (main planets only; KP Stellar never marks the nodes),
    ``#`` = the planet sits in its own star,
    ``*`` = no planet at all occupies a nakshatra this planet rules.
    """
    star_lords = [p.star_lord for p in chart.planets]
    flags: dict[str, list[str]] = {}
    for p in chart.planets:
        f: list[str] = []
        if p.star_lord == p.name:
            f.append("#")
        if p.name not in star_lords:
            f.append("*")
        if p.retrograde and p.name not in ("Rahu", "Ketu"):
            f.append("R")
        flags[p.name] = f
    return flags


def _signifies_ordered(
    chart: Chart, extra: dict[str, list[int]]
) -> dict[str, list[str]]:
    """KP Stellar ``signifies`` column: house numbers + a Roman-numeral extra."""
    house_of_planet = {p.name: p.house for p in chart.planets}
    star_lord = {p.name: p.star_lord for p in chart.planets}
    cusp_sign_lord = {c.house: c.sign_lord for c in chart.cusps}

    def owns(planet: str) -> list[int]:
        return sorted(h for h, lord in cusp_sign_lord.items() if lord == planet)

    out: dict[str, list[str]] = {}
    for p in chart.planets:
        sl = star_lord[p.name]
        groups: list[list[int]] = [
            [house_of_planet[sl]] if sl in house_of_planet else [],
            [p.house],
            owns(sl) if sl in cusp_sign_lord.values() else [],
            owns(p.name),
        ]
        seen: list[int] = []
        for group in groups:
            for h in group:
                if h not in seen:
                    seen.append(h)
        entry = [str(h) for h in seen]
        if extra[p.name]:
            entry.append("(" + ", ".join(ROMAN[h] for h in extra[p.name]) + ")")
        out[p.name] = entry
    return out


def _dasha_balance_header(chart: Chart) -> str:
    """``"RAH 15y 5m 26d"`` -- balance of the opening mahadasha at birth."""
    moon_lon = chart.planet_lon["Moon"]
    total = mahadasha_days(chart.balance.mahadasha_lord)
    days = balance_days_from_moon(moon_lon, total)
    return dasha_balance_str(_kp_abbr(chart.balance.mahadasha_lord), days)


def _horary_details(
    chart: Chart,
    name: str,
    gender: str,
    horary_no: Optional[int],
    timezone: Optional[str],
) -> dict:
    """The KP Stellar birth-details / panchanga header block."""
    birth = chart.birth
    tz = birth.tz_hours
    # Local midnight of the birth day, expressed as a UT Julian date.  ``jd_ut``
    # already carries the UTC offset, so only the local *clock* time comes off;
    # subtracting ``tz`` again would land a whole offset earlier and return the
    # previous day's sunrise.
    seconds = (
        birth.time.hour * 3600 + birth.time.minute * 60
        + birth.time.second + birth.time.microsecond / 1e6
    )
    jd_midnight = chart.jd_ut - seconds / 86400.0
    rise, sett = sunrise_sunset_clock(
        jd_midnight, birth.latitude, birth.longitude, tz
    )
    sun_lon = chart.planet_lon["Sun"]
    moon_lon = chart.planet_lon["Moon"]
    star_name, _, pada = nakshatra_pada(moon_lon)
    zone = timezone or TZ_ZONE_NAMES.get(tz, f"UTC{tz:+05.2f}".replace(".", ":"))
    return {
        "name": name,
        "gender": gender,
        "date": birth.date.strftime("%a %b %d %Y"),
        "time": birth.time.strftime("%H:%M:%S"),
        "horary_no": f"{horary_no} ({MAX_HORARY_NUMBER})" if horary_no else None,
        "place": birth.place,
        "latitude": birth.latitude,
        "longitude": birth.longitude,
        "timezone": zone,
        "ayanamsa": f"{_deg_str(chart.ayanamsa)} ({AYANAMSA_LABELS.get(chart.ayanamsa_mode, chart.ayanamsa_mode)})",
        "node": f"Using {chart.node.upper()} Node",
        "sunrise": rise,
        "sunset": sett,
        "nakshatra": f"{star_name} ({pada})",
        "tithi": tithi(sun_lon, moon_lon)[0],
        "yoga": nitya_yoga(sun_lon, moon_lon)[0],
        "karana": karana(sun_lon, moon_lon)[0],
        "dasha_balance": _dasha_balance_header(chart),
    }


def chart_to_kp_stellar_json(
    chart: Chart,
    dasha_depth: int = 5,
    query_utc: datetime | None = None,
    name: str = "KP Chart",
    gender: str = "",
    horary_no: Optional[int] = None,
    timezone: Optional[str] = None,
) -> dict:
    """Render ``chart`` in the KP Stellar printout schema.

    ``query_utc`` is the instant the Vimshottari stack is resolved for (KP
    Stellar resolves it at the moment of the query, not at birth).  All
    ``vimsottari_dasa`` end stamps are rendered in the chart's **local** time,
    as KP Stellar does.
    """
    sig_map = _kp_significator_map(chart)
    extra = _cusp_sublord_houses(chart)
    signifies = _signifies_ordered(chart, extra)
    flags = _planet_flags(chart)
    nodes = _node_agency(chart, _planet_significator_houses(chart, sig_map))

    planets: dict[str, dict] = {}
    for pname in KP_PLANET_ORDER:
        p = next(x for x in chart.planets if x.name == pname)
        planets[_kp_abbr(pname)] = {
            "sign": SIGN_ABBR[p.sign],
            "house": p.house,
            "degree": _deg_str(p.sign_degree),
            "sg": _kp_abbr(p.sign_lord),
            "sl": _kp_abbr(p.star_lord),
            "sb": _kp_abbr(p.sub_lord),
            "ss": _kp_abbr(p.sub_sub_lord),
            "signifies": signifies[pname],
            "flags": flags[pname],
        }

    cusps: dict[str, dict] = {}
    for c in chart.cusps:
        cats = sig_map[c.house]
        cusps[str(c.house)] = {
            "name": CUSP_NAMES[c.house - 1],
            "sign": SIGN_ABBR[c.sign],
            "degree": _deg_str(c.longitude % 30.0),
            "sg": _kp_abbr(c.sign_lord),
            "sl": _kp_abbr(c.star_lord),
            "sb": _kp_abbr(c.sub_lord),
            "ss": _kp_abbr(c.sub_sub_lord),
            "signifies_A_B_C_D": [
                [_kp_abbr(n) for n in _kp_sorted(cats["planets_in_star_of_planets_in_house"])],
                [_kp_abbr(n) for n in _kp_sorted(cats["planets_in_house"])],
                [_kp_abbr(n) for n in _kp_sorted(cats["planets_in_star_of_house_lord"])],
                [_kp_abbr(n) for n in _kp_sorted(cats["sign_lord"])],
            ],
        }

    moon_info = point_info(chart.planet_lon["Moon"])
    asc_info = point_info(chart.ascendant)
    tz = chart.birth.tz_hours
    instant = query_utc or chart.effective_query_utc
    periods = deep_current_periods(
        chart.planet_lon["Moon"], chart.birth.utc_datetime(),
        depth=dasha_depth, query_utc=instant,
    )
    dasha: dict[str, dict] = {}
    for i, p in enumerate(periods):
        key = _KP_DASHA_KEYS[i] if i < len(_KP_DASHA_KEYS) else f"level{i + 1}"
        dasha[key] = {
            "lord": _kp_abbr(p.lord),
            "end": local_datetime(p.end, tz).strftime("%d/%b/%Y %H:%M:%S"),
        }

    return {
        "horary_details": _horary_details(chart, name, gender, horary_no, timezone),
        "vimsottari_dasa": dasha,
        "ruling_planets": {
            "lagna": {"sign": _kp_abbr(asc_info.sign_lord), "stl": _kp_abbr(asc_info.star_lord)},
            "moon": {"sign": _kp_abbr(moon_info.sign_lord), "stl": _kp_abbr(moon_info.star_lord)},
            "day_lord": _kp_abbr(day_lord(chart.birth.date)),
            "nodes": None,
        },
        "planets": planets,
        "cusps": cusps,
        "nodes_representation": {
            _kp_abbr(k): {"houses": v["houses"], "planets": [_kp_abbr(p) for p in v["planets"]]}
            for k, v in nodes.items()
        },
        "legend": {
            "sg": "Sign",
            "sl": "Star Lord",
            "sb": "Sub Lord",
            "ss": "Sub Sub Lord",
            "flags": {
                "R": "Retrograde",
                "#": "Planet in self star",
                "*": "Has no planet in its star",
            },
            "signifies_A_B_C_D": [
                "A: Planets in star of planets in house",
                "B: Planet in the house",
                "C: Planet in star of house-lord",
                "D: Sign-lord",
            ],
        },
    }
