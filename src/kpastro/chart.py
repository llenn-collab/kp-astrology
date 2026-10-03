"""A complete KP chart: compute, then render as professional text tables."""
import json
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as DateType, datetime, timedelta, time as TimeType

from .constants import PLANET_ABBR
from .dasha import (
    Balance,
    Period,
    antardashas_of,
    current_periods,
    dasha_balance,
    format_days,
    mahadasha_timeline,
)
from .ephemeris import SwissEphemeris
from .significators import (
    Signification,
    cusp_sub_lords,
    house_significations,
    house_of_longitude,
    planet_significations,
    ruling_planets,
)
from .vedic import format_longitude, point_info
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


def compute_chart(
    birth: BirthInfo,
    ayanamsa: str = "lahiri",
    node: str = "mean",
    eph: SwissEphemeris | None = None,
) -> Chart:
    """Compute every KP layer for a birth chart."""
    eph = eph or SwissEphemeris(ayanamsa=ayanamsa, node=node)
    if eph.ayanamsa_mode != ayanamsa or eph.node != node:
        raise ValueError(
            f"ayanamsa/node do not match the injected eph instance: "
            f"eph uses ayanamsa={eph.ayanamsa_mode!r}, node={eph.node!r}; "
            f"requested ayanamsa={ayanamsa!r}, node={node!r}"
        )
    dt_utc = birth.utc_datetime()
    jd = eph.jd_ut(dt_utc)
    ayan = eph.ayanamsa(jd)
    sider = eph.sidereal_positions(jd)
    cusps, asc, mc, armc = eph.houses(jd, birth.latitude, birth.longitude)

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
    current = current_periods(moon_lon, dt_utc, dt_utc, depth=5)

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


def render_deep_dasha(chart: Chart, depth: int = 5) -> str:
    """Self-contained deep dasha renderer. Does NOT depend on render_dasha."""
    moon_lon = chart.planet_lon["Moon"]
    at_utc = chart.birth.utc_datetime()
    periods = deep_current_periods(moon_lon, at_utc, depth=depth)

    lines = [f" VIMSHOTTARI DASHA - DEEP ({depth} LEVELS)"]
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

    # Mahadasha timeline, inlined so there is no external renderer dependency.
    epoch = chart.birth.utc_datetime()
    lines.append("")
    lines.append(" Mahadasha timeline (1 yr = 365.25 d):")
    lines.append("-" * 46)
    lines.append(f" {'Lord':<10} {'Start':>10} {'End':>10} {'Days':>9}")
    for md in chart.mahadashas:
        start, end = md.as_datetimes(epoch)
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
    """Format longitude as DD°MM'SS\" with zero padding."""
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
            "planets_in_star_of_planets_in_house": a,
            "planets_in_house": b,
            "planets_in_star_of_house_lord": c,
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
    return out


def _cusp_sublord_houses(chart: Chart) -> dict[str, list[int]]:
    """Houses whose cusp sub-lord is the planet."""
    out: dict[str, list[int]] = {p.name: [] for p in chart.planets}
    for c in chart.cusps:
        if c.sub_lord in out:
            out[c.sub_lord].append(c.house)
    return out


def _node_agency(
    chart: Chart,
    sig_houses: dict[str, list[int]],
) -> dict[str, dict[str, list]]:
    """Rahu/Ketu agency: star-lord + occupied-sign lord, and their houses."""
    nodes: dict[str, dict[str, list]] = {}
    for node_name in ("Rahu", "Ketu"):
        node_planet = next(
            p for p in chart.planets if p.name == node_name
        )
        sign_lord = chart.cusps[node_planet.house - 1].sign_lord
        agents = list(dict.fromkeys([node_planet.star_lord, sign_lord]))

        houses: set[int] = set()
        for agent in agents:
            houses.update(sig_houses.get(agent, []))

        nodes[node_name] = {
            "houses": sorted(houses),
            "planets": agents,
        }
    return nodes


def chart_to_kp_json(chart: Chart, dasha_depth: int = 5) -> dict:
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
    periods = deep_current_periods(
        moon_lon, chart.birth.utc_datetime(), depth=dasha_depth
    )
    dasha = {
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
        },
    }


def render_chart_json(chart: Chart, dasha_depth: int = 5) -> str:
    """Serialize the KP Stellar-compatible chart dict to JSON text."""
    return json.dumps(
        chart_to_kp_json(chart, dasha_depth=dasha_depth),
        indent=2,
        ensure_ascii=False,
    )
