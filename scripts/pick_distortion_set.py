#!/usr/bin/env python
"""Choose the scene set for the geometric-distortion exercise.

The exercise needs, for each target, the SAME GROUND seen through geometries
that disagree as much as possible - because the whole lesson is that the map
position of a summit depends on the acquisition, not on the mountain.

So per target we take, in priority order:
  - the shallowest incidence available   (largest displacement, most layover)
  - the steepest incidence available     (smallest displacement, most shadow)
  - the widest look-direction contrast   (ascending vs descending, or L vs R)
  - a heavily squinted scene             (line of sight far off broadside)
"""
import os, sys, json, math, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import heading_from_squint, look_direction, norm360, broadside_azimuth

cat = json.load(open(sys.argv[1]))
OUT = sys.argv[2]
TARGETS = sys.argv[3].split(",")
PER = int(sys.argv[4]) if len(sys.argv) > 4 else 4

S = [r for r in cat["scenes"]
     if r.get("tif") and r.get("view_azimuth") is not None
     and r.get("squint_engineering") is not None and r.get("orbit_state")]
for r in S:
    r["heading"] = heading_from_squint(r["view_azimuth"], r["squint_engineering"])
    r["look_dir"] = look_direction(r["view_azimuth"])
    r["sq"] = r["squint_exploitation"]
    fp = r.get("footprint")
    r["h_ref"] = (fp[0][0][2] if fp and len(fp[0][0]) > 2 else None)

by = collections.defaultdict(list)
for r in S:
    by[r["target"]].append(r)

picks, used_stems = [], set()

def sid_for(r):
    t = r["target"].replace(" ", "_").replace("'", "").replace("(", "").replace(")", "")
    return "%s_%s" % (t, (r["datetime"] or "")[:19].replace("-", "").replace(":", "").replace("T", ""))

def clusters(rs, deg=0.08):
    """A target directory can hold scenes over completely different places.
    Nevado_del_Ruiz holds three: the volcano, Manizales, and Armenia. Cluster
    by footprint centre so we never mix them."""
    out = []
    for r in rs:
        w, s_, e, n = r["bbox"]
        c = ((w + e) / 2.0, (s_ + n) / 2.0)
        for g in out:
            if abs(c[0] - g["c"][0]) < deg and abs(c[1] - g["c"][1]) < deg:
                g["rs"].append(r); break
        else:
            out.append({"c": c, "rs": [r]})
    return out


for t in TARGETS:
    rs = [r for r in by.get(t, []) if r["h_ref"] is not None]
    # a scene filed under two targets must not appear twice in the exercise
    rs = [r for r in rs if r["stem"] not in used_stems]
    if rs:
        cl = clusters(rs)
        if len(cl) > 1:
            # the mountain is the cluster sitting highest above the ellipsoid
            cl.sort(key=lambda g: -sorted(x["h_ref"] for x in g["rs"])[len(g["rs"]) // 2])
            print("   %s: %d separate locations in this directory, keeping the one at "
                  "%.3f,%.3f (%d scenes, h_ref ~%.0f m)"
                  % (t, len(cl), cl[0]["c"][1], cl[0]["c"][0], len(cl[0]["rs"]),
                     sorted(x["h_ref"] for x in cl[0]["rs"])[len(cl[0]["rs"]) // 2]))
        rs = cl[0]["rs"]
    # and drop repeat collects of the same minute
    seen, u = set(), []
    for r in sorted(rs, key=lambda r: r["datetime"] or ""):
        k = (r["datetime"] or "")[:16]
        if k in seen: continue
        seen.add(k); u.append(r)
    if len(u) < 2:
        print("!! %s: only %d usable scenes, skipping" % (t, len(u))); continue

    chosen = []
    def take(r, why):
        if r is None or r["stem"] in used_stems: return
        used_stems.add(r["stem"]); r["_why"] = why; chosen.append(r)

    take(min(u, key=lambda r: r["incidence"]), "shallowest incidence here - the largest terrain displacement")
    take(max(u, key=lambda r: r["incidence"]), "steepest incidence here - displacement at its smallest")
    # widest look-direction contrast against what we already have
    if chosen:
        ref = chosen[0]["look_dir"]
        rest = [r for r in u if r["stem"] not in used_stems]
        if rest:
            take(max(rest, key=lambda r: abs(((r["look_dir"] - ref + 180) % 360) - 180)),
                 "look direction furthest from the other passes over this target")
    rest = [r for r in u if r["stem"] not in used_stems]
    if rest:
        take(max(rest, key=lambda r: abs(r["sq"])), "most heavily squinted pass available here")
    while len(chosen) < PER:
        rest = [r for r in u if r["stem"] not in used_stems]
        if not rest: break
        take(max(rest, key=lambda r: abs(r["incidence"] - sum(c["incidence"] for c in chosen)/len(chosen))),
             "fills the incidence range between the others")

    hrefs = sorted(set(round(r["h_ref"], 1) for r in chosen))
    for r in chosen:
        picks.append({
            "id": sid_for(r), "stem": r["stem"], "dir": r["dir"],
            "target": r["target"], "group": t,
            "why": r["_why"],
            "h_ref": r["h_ref"],
            "target_href_count": len(hrefs),
        })
    print("%-18s %d scenes  inc %.0f-%.0f  squint %+.0f..%+.0f  href %s"
          % (t, len(chosen), min(c["incidence"] for c in chosen),
             max(c["incidence"] for c in chosen),
             min(c["sq"] for c in chosen), max(c["sq"] for c in chosen),
             "/".join("%.0f" % h for h in hrefs)))

json.dump(picks, open(OUT, "w"), indent=1)
print("\nTOTAL %d scenes across %d targets" % (len(picks), len(set(p["group"] for p in picks))))
bys = {r["stem"]: r for r in S}
print("%-34s %-16s %6s %8s %8s %8s %9s" % ("id","group","inc","squint","look","heading","h_ref"))
for p in picks:
    r = bys[p["stem"]]
    print("%-34s %-16s %6.1f %+8.1f %8.1f %8.1f %9.1f"
          % (p["id"], p["group"], r["incidence"], r["sq"], r["look_dir"], r["heading"], r["h_ref"]))
