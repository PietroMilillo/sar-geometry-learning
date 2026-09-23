#!/usr/bin/env python
"""Choose a teaching set as a curriculum, not as a set of statistical extremes.

Each slot below is a concept the student needs to meet. We take the best real
scene for that concept, preferring terrain that reads clearly on X-band
(RULES.md R10/R11: vegetated tropical volcanoes are noisy; bare rock, lava and
playa are legible).
"""
import json, sys, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import heading_from_squint, look_direction, norm360

cat = json.load(open(sys.argv[1])); OUT = sys.argv[2]

BARE = ["Mojave","Soda","Kilauea","Shasta","Mauna_Loa","Bezymianny","Etna","Fogo",
        "Askja","Bardarbunga","Reykjanes","Lassen","Craters","Pisgah","Amboy",
        "Death","Owens","Lascar","Villarrica","Erta","Nyiragongo","Katla","Hekla",
        "Taal","Alaid","Karymsky","Tolbachik","Kliuchevskoi","Sierra_Negra","Fernandina"]
URBAN = ["EEFIT_"]

S = [r for r in cat["scenes"]
     if r.get("tif") and r.get("orbit_state") and r.get("view_azimuth") is not None
     and r.get("squint_engineering") is not None and r.get("incidence") is not None]
for r in S:
    r["heading"]  = heading_from_squint(r["view_azimuth"], r["squint_engineering"])
    r["look_dir"] = look_direction(r["view_azimuth"])
    r["sq"]       = r["squint_exploitation"]
    r["sq_abs"]   = abs(r["squint_exploitation"])

def bare(r):  return any(k.lower() in r["target"].lower() for k in BARE)
def urban(r): return any(k.lower() in r["target"].lower() for k in URBAN)

# drop near-duplicate collects (same target, same minute) - they teach nothing twice
S.sort(key=lambda r: (r["target"], r["datetime"] or ""))
ded, seen = [], set()
for r in S:
    key = (r["target"], (r["datetime"] or "")[:16], round(r["incidence"], 0))
    if key in seen: continue
    seen.add(key); ded.append(r)
S = ded
print("candidates after de-duplication: %d" % len(S))

used = set(); picks = []
def take(cands, qtype, note, key):
    cands = [c for c in cands if c["stem"] not in used and c["target"] not in
             {p["_target"] for p in picks if p.get("_unique_target")}]
    if not cands: 
        print("   !! no candidate for: %s" % note); return None
    r = min(cands, key=key)
    used.add(r["stem"])
    sid = "%s_%s" % (r["target"].replace(" ","_").replace("'","").replace("(","").replace(")",""),
                     (r["datetime"] or "")[:19].replace("-","").replace(":","").replace("T",""))
    picks.append({"id": sid, "stem": r["stem"], "dir": r["dir"], "question": qtype,
                  "note": note, "_target": r["target"], "_unique_target": False})
    return r

Sb = [r for r in S if bare(r)]
Su = [r for r in S if urban(r)]
print("bare-terrain candidates %d,  urban %d" % (len(Sb), len(Su)))

# --- slot 1+2: one target, ascending and descending, ideally opposite look sides
best_pair, best_score = None, -1
bytar = collections.defaultdict(list)
for r in Sb: bytar[r["target"]].append(r)
for t, rs in bytar.items():
    asc = [r for r in rs if r["orbit_state"]=="ascending"]
    des = [r for r in rs if r["orbit_state"]=="descending"]
    for a in asc:
        for d in des:
            # reward: opposite look sides, modest squint on both, similar incidence
            sc = (2.0 if a["look_side"] != d["look_side"] else 0.0) \
                 - 0.05*(a["sq_abs"] + d["sq_abs"]) - 0.02*abs(a["incidence"]-d["incidence"])
            if sc > best_score: best_score, best_pair = sc, (t, a, d)
if best_pair:
    t, a, d = best_pair
    for r, lbl in ((d, "descending"), (a, "ascending")):
        used.add(r["stem"])
        sid = "%s_%s" % (t.replace(" ","_"), (r["datetime"] or "")[:19].replace("-","").replace(":","").replace("T",""))
        picks.append({"id": sid, "stem": r["stem"], "dir": r["dir"], "question": "flight_direction",
                      "note": "%s pass over %s. Its twin in this set is the opposite pass over the same ground - compare the two headings." % (lbl.capitalize(), t),
                      "_target": t})

# --- slot 3: near-broadside, the textbook default
take([r for r in Sb if r["sq_abs"] < 2.0 and 55 <= r["incidence"] <= 70],
     "line_of_sight", "Near-broadside: the line of sight is almost exactly perpendicular to the ground track.",
     key=lambda r: r["sq_abs"])
# --- slot 4: strong forward squint
take([r for r in Sb if r["sq"] < -25],
     "flight_direction", "Strongly squinted FORWARD. The look direction is nowhere near perpendicular to the track, so the usual perpendicular shortcut fails here.",
     key=lambda r: r["sq"])
# --- slot 5: strong aft squint
take([r for r in Sb if r["sq"] > 25],
     "flight_direction", "Strongly squinted AFT - the opposite sign of the same convention.",
     key=lambda r: -r["sq"])
# --- slot 6: shallow incidence / steep look
take([r for r in Sb if r["incidence"] < 30 and r["sq_abs"] < 25],
     "line_of_sight", "Steep look (low incidence). Relief is compressed and layover is likely on any slope steeper than the incidence angle.",
     key=lambda r: r["incidence"])
# --- slot 7: steep incidence / shallow grazing
take([r for r in Sb if r["incidence"] > 68 and r["sq_abs"] < 20],
     "line_of_sight", "Shallow grazing (high incidence). Long radar shadows; layover needs a very steep slope.",
     key=lambda r: -r["incidence"])
# --- slot 8: left-looking
take([r for r in Sb if r["look_side"]=="left" and r["sq_abs"] < 25],
     "line_of_sight", "LEFT-looking. Most of this archive looks right, so the line of sight falls on the other side of the track.",
     key=lambda r: r["sq_abs"])
# --- slot 9+10: relief for layover, and a city for building-scale layover
take([r for r in Sb if 30 <= r["incidence"] <= 60 and r["sq_abs"] < 30
      and any(k in r["target"] for k in ("Kilauea","Shasta","Bezymianny","Etna","Lascar","Villarrica","Mauna"))],
     "layover", "Volcanic relief: layover pushes the summit toward the radar, not toward the sun.",
     key=lambda r: abs(r["incidence"]-45))
take(Su, "layover",
     "Earthquake-response city scene. At this resolution whole buildings lay over toward the sensor.",
     key=lambda r: abs(r["incidence"]-45))
take([r for r in Su if r["stem"] not in used],
     "line_of_sight", "A second city scene with different geometry - the same ground, a different look.",
     key=lambda r: -r["sq_abs"])

for p in picks: p.pop("_unique_target", None)
json.dump(picks, open(OUT,"w"), indent=1)
bys = {r["stem"]: r for r in S}
print("\nPICKED %d" % len(picks))
print("  %-38s %-16s %6s %7s %7s %6s %5s" % ("id","question","inc","sq_expl","hdg","orbit","side"))
for p in picks:
    r = bys[p["stem"]]
    print("  %-38s %-16s %6.1f %+7.1f %7.1f %6s %5s"
          % (p["id"], p["question"], r["incidence"], r["sq"], r["heading"],
             r["orbit_state"][:4], r["look_side"]))
