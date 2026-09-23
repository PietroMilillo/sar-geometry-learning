#!/usr/bin/env python
"""Exhaustively solve the squint sign convention instead of assuming it."""
import os, json, sys, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import norm360, angdiff, look_direction

cat = json.load(open(sys.argv[1]))
S = [r for r in cat["scenes"] if r.get("orbit_state") and r.get("squint_exploitation") is not None]
print("scenes with orbit_state + squint: %d\n" % len(S))

# --- 1. is the engineering violation exactly the left-looking set? ---
viol = [r for r in S if abs(r["squint_engineering"] - (90.0 + r["squint_exploitation"])) > 1e-6]
print("engineering != 90+exploitation on %d scenes" % len(viol))
print("   their look_side:", dict(collections.Counter(r["look_side"] for r in viol)))
alt = sum(1 for r in viol if abs(r["squint_engineering"] - (90.0 - r["squint_exploitation"])) < 1e-6)
print("   of those, engineering == 90-exploitation: %d/%d" % (alt, len(viol)))
lefts = [r for r in S if r["look_side"] == "left"]
print("   left-looking scenes total: %d" % len(lefts))
lviol = sum(1 for r in lefts if abs(r["squint_engineering"] - (90.0 + r["squint_exploitation"])) > 1e-6)
print("   left-looking that violate: %d/%d" % (lviol, len(lefts)))

# --- 2. brute force the heading formula, scored against sat:orbit_state ---
print("\nbrute force: heading = look_dir - s*(90 + k*exploitation)")
print("   s = +1 right / -1 left ;  k tried per look side\n")
best = {}
for side in ("right", "left"):
    sub = [r for r in S if r["look_side"] == side]
    s = 1.0 if side == "right" else -1.0
    print("  %-6s n=%d" % (side, len(sub)))
    for sflip in (1.0, -1.0):
        for k in (1.0, -1.0):
            ok = 0
            for r in sub:
                h = norm360(look_direction(r["view_azimuth"]) - s*sflip*(90.0 + k*r["squint_exploitation"]))
                north = abs(angdiff(h, 0.0)) < 90.0
                if north == (r["orbit_state"] == "ascending"):
                    ok += 1
            tag = "s*%+d, k=%+d" % (sflip, k)
            print("      %-14s agreement %4d/%4d = %5.1f%%" % (tag, ok, len(sub), 100.0*ok/len(sub)))
            key = (side, sflip, k)
            best[key] = ok/len(sub)

print("\nbest per side:")
for side in ("right","left"):
    b = max(((k,v) for k,v in best.items() if k[0]==side), key=lambda kv: kv[1])
    print("   %-6s sflip=%+d k=%+d  -> %.1f%%" % (side, b[0][1], b[0][2], 100*b[1]))
