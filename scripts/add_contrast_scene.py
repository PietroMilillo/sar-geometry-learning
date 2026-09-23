#!/usr/bin/env python
"""Borrow a scene from one target into another target's tab, as a contrast.

Nevado del Ruiz has no acquisition below 48 deg incidence anywhere in the
archive, so its tab can show shadow but never layover. That is a tasking gap,
not a property of the mountain, and a student reading the tab cold would
reasonably conclude the volcano is too gentle to lay over.

Borrowing a low-incidence scene from a comparable volcano fills the gap. The
borrowed record keeps its OWN target name and is flagged `borrowed`, so the page
can mark it as visiting from elsewhere. It is excluded from any statistic that
describes what the host target actually holds.

Gamalama is the right lender for Ruiz: 1722 m of in-footprint relief against
Ruiz's 1484-1593 m, so relief is nearly matched and incidence is left as the
only large difference. Gamalama at 66.7 deg is also a near-twin of Ruiz at
67.0 deg (layover 0.1% both, peak displacement 636 m vs 634 m), which acts as
the control: at matched incidence the two volcanoes behave the same, so the
difference at 16.6 deg can only be the look angle.
"""
import json, os, sys, argparse

ap = argparse.ArgumentParser()
ap.add_argument("--scenes", required=True, help="build/dist/scenes.json")
ap.add_argument("--source", required=True, help="scene id to borrow")
ap.add_argument("--into", required=True, help="group (tab) to place it in")
ap.add_argument("--after", default=None, help="place it after this scene id")
ap.add_argument("--note", default=None)
a = ap.parse_args()

recs = json.load(open(a.scenes))
by_id = {r["id"]: r for r in recs}
if a.source not in by_id:
    sys.exit("no such scene: %s" % a.source)
if not any(r["group"] == a.into for r in recs):
    sys.exit("no such group: %s" % a.into)
if any(r.get("borrowed") and r["id"].startswith(a.source) and r["group"] == a.into for r in recs):
    print("already borrowed into %s, nothing to do" % a.into); sys.exit(0)

src = by_id[a.source]
host = [r for r in recs if r["group"] == a.into and not r.get("borrowed")]
h_inc = sorted(r["geom"]["incidence"] for r in host)

cp = json.loads(json.dumps(src))          # deep copy; images are shared, not duplicated
cp["id"] = src["id"] + "__borrowed_into_" + a.into
cp["group"] = a.into
cp["borrowed"] = True
cp["borrowed_from"] = src["group"]
cp["why"] = a.note or (
    "Borrowed from %s. %s has nothing below %.0f deg anywhere in the archive, so "
    "this is what a steep look does to comparable relief."
    % (src["group"].replace("_", " "), a.into.replace("_", " "), h_inc[0]))

# insert in incidence order so the strip and the chart stay monotonic
out, placed = [], False
for r in recs:
    if r["group"] == a.into and not placed and \
       r["geom"]["incidence"] > cp["geom"]["incidence"]:
        out.append(cp); placed = True
    out.append(r)
if not placed:
    idx = max(i for i, r in enumerate(out) if r["group"] == a.into)
    out.insert(idx + 1, cp)

json.dump(out, open(a.scenes, "w"), indent=1)
print("borrowed %s (inc %.1f, relief %.0f m, layover %.1f%%) into the %s tab"
      % (src["id"], src["geom"]["incidence"], src["terrain"]["relief_m"],
         src["terrain"]["layover_pct"], a.into))
print("  host target keeps %d of its own scenes, incidence %.1f-%.1f"
      % (len(host), h_inc[0], h_inc[-1]))
print("  borrowed record shares the source's imagery - no extra files")
