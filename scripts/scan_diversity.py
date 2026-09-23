#!/usr/bin/env python
"""Rank every target by line-of-sight DIVERSITY, which is what a geometric-distortion
exercise actually needs: the same ground seen from many different look vectors.

Also reports whether a COP30 tile is cached for the target, because the DTM /
hillshade / SAR-simulation half of the exercise cannot run without one.
"""
import os, sys, json, math, collections, glob

D2R = math.pi/180
cat = json.load(open(sys.argv[1]))
ROOT = cat["root"]

def circ_spread(degs):
    """0 = all looks identical, 1 = looks spread evenly round the compass."""
    if len(degs) < 2: return 0.0
    x = sum(math.cos(d*D2R) for d in degs)/len(degs)
    y = sum(math.sin(d*D2R) for d in degs)/len(degs)
    return 1.0 - math.hypot(x, y)

def max_gap_cover(degs):
    """Largest angular separation between any two looks (deg)."""
    best = 0.0
    for i in range(len(degs)):
        for j in range(i+1, len(degs)):
            d = abs((degs[i]-degs[j]+180) % 360 - 180)
            best = max(best, d)
    return best

by = collections.defaultdict(list)
for r in cat["scenes"]:
    if r.get("view_azimuth") is None or not r.get("tif"): continue
    by[(r["target"], r["dir"])].append(r)

# collapse the duplicate-directory problem: group by target, keep the richest dir
tgt = collections.defaultdict(list)
for (t, d), rs in by.items():
    tgt[t].extend(rs)

dem_cache = {}
for t in tgt:
    p = os.path.join(ROOT, t, "dem_cache")
    dem_cache[t] = len(glob.glob(os.path.join(p, "cop30_*.tif"))) if os.path.isdir(p) else 0

rows = []
for t, rs in tgt.items():
    # de-duplicate identical collects filed twice
    seen, u = set(), []
    for r in rs:
        k = (r["stem"],)
        if k in seen: continue
        seen.add(k); u.append(r)
    if len(u) < 4: continue
    az  = [r["view_azimuth"] for r in u]
    inc = [r["incidence"] for r in u]
    sq  = [r["squint_exploitation"] for r in u]
    orb = collections.Counter(r["orbit_state"] for r in u)
    side= collections.Counter(r["look_side"] for r in u)
    combos = len(set((r["orbit_state"], r["look_side"]) for r in u))
    rows.append({
        "target": t, "n": len(u),
        "az_spread": circ_spread(az), "az_gap": max_gap_cover(az),
        "inc_min": min(inc), "inc_max": max(inc), "inc_rng": max(inc)-min(inc),
        "sq_min": min(sq), "sq_max": max(sq), "sq_rng": max(sq)-min(sq),
        "asc": orb.get("ascending",0), "desc": orb.get("descending",0),
        "left": side.get("left",0), "right": side.get("right",0),
        "combos": combos, "dem": dem_cache.get(t,0),
    })

def score(r):
    return (min(r["az_gap"],180)/180*3.0        # how far apart the looks are
          + r["az_spread"]*2.0                   # how evenly spread
          + min(r["inc_rng"],40)/40*2.0          # incidence range
          + min(r["sq_rng"],80)/80*2.0           # squint range
          + (r["combos"]-1)*0.8                  # asc/desc x left/right
          + min(r["n"],20)/20*1.0)               # sheer volume

rows.sort(key=score, reverse=True)
print("%-30s %4s %5s %6s %11s %13s %4s %4s %5s %4s %s" % (
      "target","n","gap","spread","incidence","squint","asc","desc","L/R","DEM","score"))
print("-"*118)
for r in rows[:28]:
    print("%-30s %4d %5.0f %6.2f  %4.0f-%4.0f°  %+5.0f..%+5.0f°  %4d %4d %2d/%-2d %4d %5.2f" % (
        r["target"][:30], r["n"], r["az_gap"], r["az_spread"],
        r["inc_min"], r["inc_max"], r["sq_min"], r["sq_max"],
        r["asc"], r["desc"], r["left"], r["right"], r["dem"], score(r)))

print("\n--- urban / EEFIT targets ---")
for r in sorted([x for x in rows if "EEFIT" in x["target"]], key=score, reverse=True):
    print("%-30s %4d %5.0f %6.2f  %4.0f-%4.0f°  %+5.0f..%+5.0f°  %4d %4d %2d/%-2d %4d %5.2f" % (
        r["target"][:30], r["n"], r["az_gap"], r["az_spread"],
        r["inc_min"], r["inc_max"], r["sq_min"], r["sq_max"],
        r["asc"], r["desc"], r["left"], r["right"], r["dem"], score(r)))
