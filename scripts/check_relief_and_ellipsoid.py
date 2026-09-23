#!/usr/bin/env python
"""Two questions the exercise depends on:

 1. How much RELIEF does each candidate actually have? Geometric distortion is
    invisible on flat ground, so this is the gating number.
 2. Is the GEC product really geocoded to a constant height rather than to the
    terrain? If so, every scene's footprint polygon carries one elevation for all
    corners, and that number will NOT track the terrain underneath.
"""
import os, sys, json, glob, math, collections
import numpy as np, rasterio
from rasterio.enums import Resampling

cat = json.load(open(sys.argv[1])); ROOT = cat["root"]
TARGETS = sys.argv[2].split(",")

by = collections.defaultdict(list)
for r in cat["scenes"]:
    if r.get("view_azimuth") is not None: by[r["target"]].append(r)

print("=== 1. footprint corner elevations: constant, or following terrain? ===")
for t in TARGETS:
    rs = by.get(t, [])[:6]
    if not rs: print("  %-26s no scenes" % t); continue
    print("  %s" % t)
    for r in rs:
        fp = r.get("footprint")
        if not fp: continue
        ring = fp[0]
        zs = [p[2] for p in ring if len(p) > 2]
        if not zs: print("     %-30s no z in footprint" % r["stem"]); continue
        print("     %-30s corners z: %8.2f .. %8.2f   spread %6.3f m"
              % (r["stem"], min(zs), max(zs), max(zs)-min(zs)))

print("\n=== 2. terrain relief under each candidate, from the cached COP30 ===")
print("%-26s %6s %8s %8s %8s %8s %7s" % ("target","tiles","min","max","relief","mean","p95slope"))
for t in TARGETS:
    tiles = sorted(glob.glob(os.path.join(ROOT, t, "dem_cache", "cop30_*.tif")))
    if not tiles:
        print("%-26s %6d   -- no cached COP30 --" % (t, 0)); continue
    try:
        with rasterio.open(tiles[0]) as ds:
            a = ds.read(1, out_shape=(1, min(ds.height,900), min(ds.width,900)),
                        resampling=Resampling.average).astype(np.float32)
            nd = ds.nodata
            if nd is not None: a[a == nd] = np.nan
            a[a < -500] = np.nan
            px = abs(ds.transform.a) * 111320.0 * math.cos(math.radians(
                 (ds.bounds.bottom + ds.bounds.top)/2))
            sy, sx = np.gradient(a, max(px,1e-6))
            slope = np.degrees(np.arctan(np.hypot(sx, sy)))
        v = a[np.isfinite(a)]
        s = slope[np.isfinite(slope)]
        print("%-26s %6d %8.0f %8.0f %8.0f %8.0f %7.1f" % (
            t, len(tiles), np.nanmin(v), np.nanmax(v),
            np.nanmax(v)-np.nanmin(v), np.nanmean(v), np.percentile(s, 95)))
    except Exception as e:
        print("%-26s %6d   read failed: %s" % (t, len(tiles), e))
