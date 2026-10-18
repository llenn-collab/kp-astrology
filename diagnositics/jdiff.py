"""Recursive, type-aware diff of two JSON documents with per-path reporting."""
import json, sys, re

def parse_dms(s):
    m = re.match(r"^(\d{1,2})°(\d{2})'(\d{2})\"$", s)
    if not m:
        return None
    d, mi, se = map(int, m.groups())
    return d * 3600 + mi * 60 + se

def parse_hms(s):
    m = re.match(r"^(\d{2}):(\d{2}):(\d{2})$", s)
    return None if not m else int(m[1]) * 3600 + int(m[2]) * 60 + int(m[3])

def walk(ref, act, path, out):
    if isinstance(ref, dict):
        if not isinstance(act, dict):
            out.append(("TYPE", path, type(ref).__name__, type(act).__name__, ref, act)); return
        for k in ref:
            if k not in act:
                out.append(("MISSING", f"{path}.{k}", ref[k], None))
            else:
                walk(ref[k], act[k], f"{path}.{k}", out)
        for k in act:
            if k not in ref:
                out.append(("EXTRA", f"{path}.{k}", None, act[k]))
        return
    if isinstance(ref, list):
        if not isinstance(act, list):
            out.append(("TYPE", path, "list", type(act).__name__, ref, act)); return
        if len(ref) != len(act):
            out.append(("LEN", path, len(ref), len(act), ref, act))
        for i, (a, b) in enumerate(zip(ref, act)):
            walk(a, b, f"{path}[{i}]", out)
        return
    if type(ref) != type(act):
        out.append(("TYPE", path, type(ref).__name__, type(act).__name__, ref, act)); return
    if ref == act:
        return
    if isinstance(ref, str):
        dr, da = parse_dms(ref), parse_dms(act) if isinstance(act, str) else None
        if dr is not None and da is not None:
            out.append(("DMS", path, ref, act, da - dr)); return
        hr, ha = parse_hms(ref), parse_hms(act)
        if hr is not None and ha is not None:
            out.append(("HMS", path, ref, act, ha - hr)); return
        out.append(("VALUE", path, ref, act))
        return
    out.append(("VALUE", path, ref, act))

if __name__ == "__main__":
    ref = json.load(open(sys.argv[1])); act = json.load(open(sys.argv[2]))
    out = []
    walk(ref, act, "$", out)
    total = 0
    def count(x):
        if isinstance(x, dict): return sum(count(v) for v in x.values())
        if isinstance(x, list): return sum(count(v) for v in x) if x and not isinstance(x[0], (int,str,float,bool,type(None))) else 1
        return 1
    total = count(ref)
    print(f"differences: {len(out)}")
    for d in out:
        if d[0] == "DMS":
            print(f"  DMS  {d[1]}: ref={d[2]} act={d[3]} delta={d[4]:+d}\"")
        elif d[0] == "HMS":
            print(f"  HMS  {d[1]}: ref={d[2]} act={d[3]} delta={d[4]:+d}s")
        else:
            print(f"  {d[0]:<7} {d[1]}: ref={d[2]!r} act={d[3]!r}" + (f" | {d[4]!r} vs {d[5]!r}" if len(d)>5 and d[0] in ("VALUE",) else ""))
