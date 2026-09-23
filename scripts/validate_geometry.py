#!/usr/bin/env python
"""Test the geometry conventions against the whole catalogue, then against the
rasters themselves. Nothing in the teaching tool is drawn from an untested rule."""
import os, json, sys, math, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import (norm360, angdiff, side_sign, look_direction,
                      heading_from_squint, raster_axis_azimuths)

cat = json.load(open(sys.argv[1]))
S = [r for r in cat["scenes"] if r.get("view_azimuth") is not None]
print("scenes with view:azimuth: %d / %d\n" % (len(S), cat["n"]))

# ---------- Test 1: the three squint conventions are algebraically linked ----------
bad_eng, bad_expl = 0, 0
for r in S:
    ob, eng, ex = r["squint_broadside"], r["squint_engineering"], r["squint_exploitation"]
    if None in (ob, eng, ex): continue
    if abs(eng - (90.0 + ex)) > 1e-6: bad_eng += 1
    if abs(abs(ex) - ob)     > 1e-6: bad_expl += 1
print("TEST 1  squint conventions")
print("  engineering == 90 + exploitation      : violations %d/%d" % (bad_eng, len(S)))
print("  |exploitation| == off_broadside       : violations %d/%d" % (bad_expl, len(S)))
sgn = collections.Counter("neg" if r["squint_exploitation"] < 0 else
                          ("pos" if r["squint_exploitation"] > 0 else "zero")
                          for r in S if r["squint_exploitation"] is not None)
print("  sign of exploitation squint           :", dict(sgn))

# ---------- Test 2: derived heading must agree with sat:orbit_state ----------
print("\nTEST 2  derived heading vs sat:orbit_state")
res = collections.Counter(); headings = collections.defaultdict(list)
for r in S:
    if r["squint_engineering"] is None or r["orbit_state"] is None: continue
    h = heading_from_squint(r["view_azimuth"], r["squint_engineering"], r["look_side"])
    northward = abs(angdiff(h, 0.0)) < 90.0
    want_north = (r["orbit_state"] == "ascending")
    res[(r["orbit_state"], "agree" if northward == want_north else "DISAGREE")] += 1
    headings[r["orbit_state"]].append(h)
    r["_heading"] = h
for k in sorted(res): print("   %-12s %-9s %d" % (k[0], k[1], res[k]))
tot = sum(res.values()); ok = sum(v for k,v in res.items() if k[1]=="agree")
print("   agreement: %d/%d = %.1f%%" % (ok, tot, 100.0*ok/max(tot,1)))
for st, hs in headings.items():
    # circular mean
    x = sum(math.cos(math.radians(a)) for a in hs); y = sum(math.sin(math.radians(a)) for a in hs)
    print("   %-11s n=%4d  circular-mean heading %6.1f deg" % (st, len(hs), norm360(math.degrees(math.atan2(y, x)))))

# ---------- Test 3: null model, to prove test 2 is not trivially true ----------
print("\nTEST 3  null model (heading = look_dir, i.e. ignoring squint)")
res2 = collections.Counter()
for r in S:
    if r["orbit_state"] is None: continue
    h = look_direction(r["view_azimuth"])
    northward = abs(angdiff(h, 0.0)) < 90.0
    res2["agree" if northward == (r["orbit_state"]=="ascending") else "DISAGREE"] += 1
t2 = sum(res2.values())
print("   agreement: %d/%d = %.1f%%  (should be far worse than TEST 2)"
      % (res2["agree"], t2, 100.0*res2["agree"]/max(t2,1)))

# ---------- Test 4: raster geotransform vs look direction (no orbit assumption) ----------
print("\nTEST 4  raster +y axis azimuth vs look_dir = view:azimuth - 180")
import rasterio
withtif = [r for r in S if r.get("tif")]
random.seed(7)
sample = random.sample(withtif, min(int(sys.argv[2]) if len(sys.argv)>2 else 40, len(withtif)))
errs, fails = [], 0
for r in sample:
    try:
        with rasterio.open(r["tif"]) as ds:
            lat = (r["bbox"][1] + r["bbox"][3]) / 2.0
            az_x, az_y = raster_axis_azimuths(ds.transform, lat)
    except Exception as e:
        fails += 1; continue
    e_y = angdiff(az_y, look_direction(r["view_azimuth"]))
    errs.append(e_y)
    r["_raster_az_y"] = az_y
if errs:
    errs_s = sorted(abs(e) for e in errs)
    print("   n=%d (open failures %d)" % (len(errs), fails))
    print("   |az(+y) - look_dir|  median %.3f deg   p90 %.3f   max %.3f"
          % (errs_s[len(errs_s)//2], errs_s[int(.9*(len(errs_s)-1))], errs_s[-1]))
    print("   -> GEC rasters are stored with +y (down-image) along the ground-range look direction"
          if errs_s[int(.9*(len(errs_s)-1))] < 2.0 else "   -> NO clean relation; do not rely on raster rotation")
else:
    print("   no rasters read")

json.dump(cat, open(sys.argv[3] if len(sys.argv)>3 else "catalogue_derived.json","w"))
print("\nwrote derived catalogue")
