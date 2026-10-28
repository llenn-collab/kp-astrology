#!/usr/bin/env python3
"""Normalized V7/V8/V9 comparison: kpastro (full precision, regenerated) vs KP Stellar references.

Normalizes the three differently-shaped KP Stellar reference schemas into a
common internal representation and reports signed residuals (arcseconds /
seconds) against kpastro regenerated with the documented --query-utc.

Usage:
    SE_EPHE_PATH="$HOME/.kpastro/ephe" python diagnositics/v789_comparison.py
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from kpastro.chart import BirthInfo, chart_to_kp_stellar_json, compute_chart
from kpastro.ephemeris import SwissEphemeris
from kpastro.horary import kp_divisions

ROOT = Path(__file__).resolve().parents[1]

SIGN_ABBR = ("ARI", "TAU", "GEM", "CAN", "LEO", "VIR", "LIB", "SCO", "SAG",
             "CAP", "AQU", "PIS")
DMS_RE = re.compile(r"^(\d+)\u00b0(\d+)'([\d.]+)\"?$")
ROMAN_TO_INT = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6,
                "VII": 7, "VIII": 8, "IX": 9, "X": 10, "XI": 11, "XII": 12}


def cusp_key(raw):
    if raw is None:
        return None
    if raw == "Asc":
        return "1"
    if raw in ROMAN_TO_INT:
        return str(ROMAN_TO_INT[raw])
    return str(raw)


def dms_to_deg(text):
    m = DMS_RE.match(text.strip())
    if not m:
        raise ValueError(f"cannot parse DMS {text!r}")
    return int(m.group(1)) + int(m.group(2)) / 60.0 + float(m.group(3)) / 3600.0


def deg_with_sign(text, sign):
    return dms_to_deg(text) + SIGN_ABBR.index(sign) * 30.0


# --------------------------------------------------------------------------- #
# Version specifications: intended inputs per REFERENCE_MANIFEST.md
# --------------------------------------------------------------------------- #

VERSIONS = [
    {
        "id": "V7",
        "label": "2026-10-30 Pune, horary 117",
        "date": "2026-10-30", "time": "12:00:00", "tz": 5.5,
        "lat": 18.4593067, "lon": 73.8654709, "place": "Pune, India",
        "ayanamsa": "kp_new", "node": "mean", "horary_no": 117,
        "query_utc": "2026-10-18 12:00:00",
        "kpastro_file": "kpastro_actual.json",
        "kp_stellar_file": "kp_stellar_output.json",
        "details_key": "horary_details",
        "dasha_key": "vimsottari_dasa",
    },
    {
        "id": "V8",
        "label": "2027-04-30 Pune, horary 117",
        "date": "2027-04-30", "time": "12:00:00", "tz": 5.5,
        "lat": 18.4593067, "lon": 73.8654709, "place": "Pune, India",
        "ayanamsa": "kp_new", "node": "mean", "horary_no": 117,
        "query_utc": "2027-04-18 12:00:00",
        "kpastro_file": "kpastro_actual8_query.json",
        "kp_stellar_file": "kp_stellar_output8.json",
        "details_key": "birth_details",
        "dasha_key": "vimsottari_dasha",
    },
    {
        "id": "V9",
        "label": "2027-10-30 Pune, horary 74",
        "date": "2027-10-30", "time": "12:00:00", "tz": 5.5,
        "lat": 18.4593067, "lon": 73.8654709, "place": "Pune, India",
        "ayanamsa": "kp_new", "node": "mean", "horary_no": 74,
        "query_utc": "2027-10-18 12:00:00",
        "kpastro_file": "kpastro_actual9_query.json",
        "kp_stellar_file": "kp_stellar_output9.json",
        "details_key": "metadata",
        "dasha_key": "vimsottari_dasha",
    },
]


# --------------------------------------------------------------------------- #
# kpastro regeneration (full precision)
# --------------------------------------------------------------------------- #

def build_kpastro(v):
    eph = SwissEphemeris(ayanamsa=v["ayanamsa"], node=v["node"])
    if eph.precision != "full":
        raise RuntimeError(f"{v['id']}: Swiss Ephemeris precision is {eph.precision!r}; "
                           "full precision files required")
    birth = BirthInfo(
        date=datetime.strptime(v["date"], "%Y-%m-%d").date(),
        time=datetime.strptime(v["time"], "%H:%M:%S").time(),
        latitude=v["lat"], longitude=v["lon"], tz_hours=v["tz"], place=v["place"],
    )
    instant = datetime.strptime(v["query_utc"], "%Y-%m-%d %H:%M:%S")
    chart = compute_chart(
        birth, ayanamsa=v["ayanamsa"], node=v["node"], eph=eph,
        query_utc=instant,
        horary_lagna=kp_divisions()[v["horary_no"] - 1].start_deg,
    )
    out = chart_to_kp_stellar_json(
        chart, dasha_depth=5, query_utc=instant,
        name="KPstellar", gender="Male", horary_no=v["horary_no"],
        timezone="Asia/Kolkata",
    )
    return out, eph, chart, instant


# --------------------------------------------------------------------------- #
# KP Stellar reference normalization
# --------------------------------------------------------------------------- #

ABBR_FROM_NAME = {"SUN": "SUN", "MOO": "MOO", "MAR": "MAR", "MER": "MER",
                  "JUP": "JUP", "VEN": "VEN", "SAT": "SAT",
                  "RAH": "RAH", "KET": "KET",
                  "Sun": "SUN", "Moon": "MOO", "Mars": "MAR", "Mercury": "MER",
                  "Jupiter": "JUP", "Venus": "VEN", "Saturn": "SAT",
                  "Rahu": "RAH", "Ketu": "KET"}


def _split_ssl(ssl):
    if isinstance(ssl, str):
        return [x.strip() for x in ssl.split("|")]
    if isinstance(ssl, list):
        return list(ssl)
    return []


def _lords(p):
    """Return (sg, sl, sb, ss) handling both reference layouts.

    V7 (kp_stellar_output.json) stores separate sg/sl/sb/ss fields.
    V8/V9 store a combined sgn_stl_sub_ssl (list or "|"-joined string).
    """
    if any(k in p for k in ("sg", "sl", "sb", "ss")):
        return (p.get("sg"), p.get("sl"), p.get("sb"), p.get("ss"))
    parts = _split_ssl(p.get("sgn_stl_sub_ssl"))
    return tuple(parts[i] if i < len(parts) else None for i in range(4))


def _planets_normalized(ref):
    planets = ref.get("planets", []) or []
    out = {}
    if isinstance(planets, dict):
        for abbr, p in planets.items():
            sg, sl, sb, ss = _lords(p)
            out[str(abbr).upper()] = {
                "degree": p.get("degree"),
                "sign": p.get("sign"),
                "house": p.get("house"),
                "sg": sg, "sl": sl, "sb": sb, "ss": ss,
                "signifies": p.get("significators") or p.get("signifies"),
                "node_represents": p.get("node_represents"),
            }
        return out
    for p in planets:
        name = p.get("planet") or p.get("name") or p.get("pla")
        if not name:
            continue
        name = str(name).replace("*", "").strip()
        abbr = ABBR_FROM_NAME.get(name, name.upper()[:3])
        sg, sl, sb, ss = _lords(p)
        out[abbr] = {
            "degree": p.get("degree") or p.get("deg"),
            "sign": p.get("sign"),
            "house": p.get("house"),
            "sg": sg, "sl": sl, "sb": sb, "ss": ss,
            "signifies": p.get("significators") or p.get("significator")
                         or p.get("signifies"),
            "node_represents": p.get("node_represents"),
        }
    return out


def _cusps_normalized(ref):
    cusps = ref.get("cusps", []) or []
    out = {}
    if isinstance(cusps, dict):
        for raw_key, c in cusps.items():
            key = cusp_key(raw_key)
            sg, sl, sb, ss = _lords(c)
            out[key] = {
                "degree": c.get("degree"),
                "sign": c.get("sign"),
                "sg": sg, "sl": sl, "sb": sb, "ss": ss,
            }
        return out
    for c in cusps:
        key = cusp_key(c.get("cusp"))
        sg, sl, sb, ss = _lords(c)
        out[key] = {
            "degree": c.get("degree"),
            "sign": c.get("sign"),
            "sg": sg, "sl": sl, "sb": sb, "ss": ss,
        }
    return out


def normalize_reference(ref, v):
    details_key = v["details_key"]
    if details_key in ref:
        details = dict(ref[details_key])
    elif "metadata" in ref:
        details = dict(ref["metadata"])
    else:
        details = dict(ref.get("birth_details", {}))

    # V9 nests panchanga fields under a "panchanga" sub-dict; fold them up.
    if "panchanga" in ref and isinstance(ref["panchanga"], dict):
        for k, vv in ref["panchanga"].items():
            details.setdefault(k, vv)

    # Some references label the node field "node_type" (nested under details).
    details.setdefault("node", details.get("node_type") or ref.get("node_type")
                       or details.get("node"))

    dasha = ref.get(v["dasha_key"], {})

    # nodes_representation: top-level or inside the RAH/KET planet entries.
    nodes = ref.get("nodes_representation") or {}
    if not nodes:
        nodes = {}
        for p in ref.get("planets", []) or []:
            nr = p.get("node_represents")
            if nr:
                nm = p.get("planet") or p.get("name")
                nodes[str(nm)] = nr

    return {
        "details": details,
        "dasha": dasha,
        "planets": _planets_normalized(ref),
        "cusps": _cusps_normalized(ref),
        "nodes": nodes,
    }


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #

def fmt_planet(abbr, kp_obj, ks_obj):
    lines = []
    kp_deg = kp_obj.get("degree"); ks_deg = ks_obj.get("degree")
    if kp_deg and ks_deg:
        kp_abs = deg_with_sign(kp_deg, kp_obj.get("sign"))
        ks_abs = deg_with_sign(ks_deg, ks_obj.get("sign"))
        resid_as = (kp_abs - ks_abs) * 3600.0
        lines.append(f"  degree: kp={kp_deg}  ref={ks_deg}  resid={resid_as:+.2f}\"")
    for fld in ("sign", "house", "sg", "sl", "sb", "ss"):
        if kp_obj.get(fld) != ks_obj.get(fld):
            lines.append(f"  {fld}: kp={kp_obj.get(fld)!r}  ref={ks_obj.get(fld)!r}")
    return lines


def fmt_cusp(key, kp_obj, ks_obj):
    lines = []
    kp_deg = kp_obj.get("degree"); ks_deg = ks_obj.get("degree")
    if kp_deg and ks_deg:
        kp_abs = deg_with_sign(kp_deg, kp_obj.get("sign"))
        ks_abs = deg_with_sign(ks_deg, ks_obj.get("sign"))
        resid_as = (kp_abs - ks_abs) * 3600.0
        lines.append(f"  degree: kp={kp_deg}  ref={ks_deg}  resid={resid_as:+.2f}\"")
    for fld in ("sign", "sg", "sl", "sb", "ss"):
        if kp_obj.get(fld) != ks_obj.get(fld):
            lines.append(f"  {fld}: kp={kp_obj.get(fld)!r}  ref={ks_obj.get(fld)!r}")
    return lines


def compare_version(v):
    print(f"\n{'='*72}")
    print(f"### {v['id']} — {v['label']}")
    print(f"{'='*72}")
    print(f" chart   : {v['date']} {v['time']} IST  ({v['lat']}°, {v['lon']}°)  tz {v['tz']}")
    print(f" ayanamsa: {v['ayanamsa']}  node: {v['node']}  horary: {v['horary_no']}")
    print(f" query_utc: {v['query_utc']}")
    print(f" kpastro : {v['kpastro_file']}  (independent regen, full precision)")
    print(f" KP Stellar: {v['kp_stellar_file']}")

    kp, eph, chart, instant = build_kpastro(v)
    ref = json.loads((ROOT / v["kp_stellar_file"]).read_text(encoding="utf-8"))
    rs = normalize_reference(ref, v)

    # ---- header / panchanga ----
    print("\n--- header / panchanga ---")
    kp_d = kp["horary_details"]; rs_d = rs["details"]
    for fld in ("date", "time", "horary_no", "place", "latitude", "longitude",
                "timezone", "ayanamsa", "node", "sunrise", "sunset", "nakshatra",
                "tithi", "yoga", "karana", "dasha_balance"):
        kv = kp_d.get(fld); rv = rs_d.get(fld)
        mark = "OK " if kv == rv else "DIFF"
        print(f"  [{mark}] {fld}: kp={kv!r}  ref={rv!r}")

    # ---- planets ----
    print("\n--- planets ---")
    kp_planets = kp["planets"]
    for abbr in ("SUN", "MOO", "MAR", "MER", "JUP", "VEN", "SAT", "RAH", "KET"):
        kp_obj = kp_planets.get(abbr, {})
        ks_obj = rs["planets"].get(abbr, {})
        if not ks_obj:
            print(f"  {abbr}: MISSING in KP Stellar reference")
            continue
        lines = fmt_planet(abbr, kp_obj, ks_obj)
        if not lines:
            print(f"  {abbr}: exact match (degree {kp_obj.get('degree')})")
        else:
            print(f"  {abbr}:")
            for ln in lines:
                print(ln)

    # ---- cusps ----
    print("\n--- cusps ---")
    kp_cusps = kp["cusps"]
    any_diff = False
    for i in range(1, 13):
        key = str(i)
        kp_obj = kp_cusps.get(key, {})
        ks_obj = rs["cusps"].get(key, {})
        if not ks_obj:
            print(f"  cusp {i}: MISSING in KP Stellar reference")
            any_diff = True
            continue
        kp_deg = kp_obj.get("degree"); ks_deg = ks_obj.get("degree")
        lines = fmt_cusp(key, kp_obj, ks_obj)
        deg_diff = bool(kp_deg and ks_deg and
                        abs((deg_with_sign(kp_deg, kp_obj.get("sign"))
                             - deg_with_sign(ks_deg, ks_obj.get("sign"))) * 3600.0) > 0.005)
        lord_diff = [ln for ln in lines if not ln.startswith("  degree:")]
        tag = "  <-- degree differs" if deg_diff else (
              "  <-- lord differs" if lord_diff else "")
        print(f"  cusp {i}: kp={kp_obj.get('degree')}  ref={ks_obj.get('degree')}{tag}")
        for ln in lines:
            print("    " + ln)
        if deg_diff or lord_diff:
            any_diff = True
    if not any_diff:
        print("  all cusps exact")

    # ---- nodes representation ----
    print("\n--- nodes representation ---")
    for node in ("RAH", "KET"):
        kp_n = kp["nodes_representation"].get(node, {})
        ks_n = rs["nodes"].get(node, {})
        print(f"  {node}: kp planets={kp_n.get('planets')} houses={kp_n.get('houses')}")
        print(f"         ref planets={ks_n.get('planets')} houses={ks_n.get('houses')}")

    # ---- dasha balance + active stack ----
    print("\n--- dasha ---")
    print(f"  balance header: kp={kp_d.get('dasha_balance')!r}  ref={rs_d.get('dasha_balance')!r}")
    kp_dasa = kp["vimsottari_dasa"]; rs_dasa = rs["dasha"]
    for lvl in ("dasa", "bhukti", "antara", "sookshma", "prana"):
        kl = kp_dasa.get(lvl, {}); rl = rs_dasa.get(lvl, {})
        print(f"  {lvl:9s}: kp lord={kl.get('lord')} end={kl.get('end')} | "
              f"ref lord={rl.get('planet') or rl.get('lord')} end={rl.get('ends') or rl.get('end')}")

    # ---- schema keys ----
    print("\n--- top-level schema keys ---")
    print(f"  kpastro : {sorted(kp.keys())}")
    print(f"  KP Stellar: {sorted(ref.keys())}")

    return kp, rs


def main():
    eph = SwissEphemeris(ayanamsa="kp_new", node="mean")
    print(f"ephemeris precision: {eph.precision}")
    assert eph.precision == "full", "full ephemeris required"
    for v in VERSIONS:
        compare_version(v)
    print("\n\nDone. Compare the DIFF/residual lines above; only those are real residuals.")


if __name__ == "__main__":
    main()
