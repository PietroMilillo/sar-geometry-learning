#!/usr/bin/env python
"""Attach the measured terrain response to each Look Angle scene.

Look Angle asks the student to draw a direction. That question is well posed
whatever the terrain does - but the LAYOVER question says "layover", and layover
has a threshold: it needs a slope steeper than the incidence angle. Both layover
scenes sit near 45 deg incidence, where the terrain rarely qualifies. The
displacement is real on every scene; true layover mostly is not. Carrying the
numbers lets the page say which is which instead of implying both.
"""
import json, sys, argparse
ap = argparse.ArgumentParser()
ap.add_argument("--scenes", required=True)
ap.add_argument("--terrain", required=True)
a = ap.parse_args()
scenes = json.load(open(a.scenes))
terr = {t["id"]: t for t in json.load(open(a.terrain))}
n = 0
for s in scenes:
    t = terr.get(s["id"])
    if not t:
        continue
    s["terrain"] = {
        "relief_m": t["relief"], "p90_slope": t["p90"], "h_ref": t["h_ref"],
        "disp_max_m": t["disp"], "layover_pct": t["lay"], "shadow_pct": t["shd"],
    }
    n += 1
json.dump(scenes, open(a.scenes, "w"), indent=1)
print("attached measured terrain to %d of %d scenes" % (n, len(scenes)))
have = [s for s in scenes if "terrain" in s]
lay = [s for s in have if s["question"] == "layover"]
print("\nlayover-question scenes:")
for s in lay:
    t = s["terrain"]
    print("  %-20s inc %.1f  p90 slope %.1f  ->  true layover %.2f%% of scene, "
          "displacement up to %.0f m"
          % (s["target"], s["geom"]["incidence"], t["p90_slope"],
             t["layover_pct"], t["disp_max_m"]))
