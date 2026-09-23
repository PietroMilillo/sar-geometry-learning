#!/usr/bin/env python
"""Ship each scene's DEM to the browser so the page can answer
"this point on the topography - where does the radar put it?" for any pixel.

Heights go into a LOSSLESS png as a 16-bit value split across the red and green
channels (R = high byte, G = low byte), because canvas getImageData only ever
hands back 8 bits per channel. Blue carries a validity flag.

Reads the warped DEMs the product renderer already wrote, so it costs no NFS
traffic and no re-warping.
"""
import os, sys, json, argparse
import numpy as np
from PIL import Image

os.environ.setdefault("GDAL_DATA",
    "/home/pmilillo/StereoPipeline-3.7.0-alpha-2026-03-05-x86_64-Linux/share/gdal")
import rasterio

ap = argparse.ArgumentParser()
ap.add_argument("--dist", required=True)
ap.add_argument("--size", type=int, default=256)
a = ap.parse_args()

recs = json.load(open(os.path.join(a.dist, "scenes.json")))
tmpd = os.path.join(a.dist, "_tmp")
n_ok = 0
for rec in recs:
    src = os.path.join(tmpd, rec["id"] + "_dem.tif")
    if not os.path.exists(src):
        print("  no warped DEM for %s" % rec["id"]); continue
    with rasterio.open(src) as ds:
        dem = ds.read(1, out_shape=(1, a.size, a.size),
                      resampling=rasterio.enums.Resampling.average).astype(np.float64)
        nd = ds.nodata
    if nd is not None: dem[dem == nd] = np.nan
    dem[dem < -500] = np.nan
    ok = np.isfinite(dem)
    if not ok.any():
        print("  DEM empty for %s" % rec["id"]); continue
    lo, hi = float(np.nanmin(dem)), float(np.nanmax(dem))
    span = max(hi - lo, 1e-6)
    q = np.clip(((dem - lo) / span) * 65535.0, 0, 65535)
    q = np.where(ok, q, 0).astype(np.uint16)
    rgb = np.zeros((a.size, a.size, 3), np.uint8)
    rgb[..., 0] = (q >> 8).astype(np.uint8)
    rgb[..., 1] = (q & 0xFF).astype(np.uint8)
    rgb[..., 2] = np.where(ok, 255, 0).astype(np.uint8)
    out = os.path.join(a.dist, rec["id"] + "_demdata.png")
    Image.fromarray(rgb, "RGB").save(out, "PNG", optimize=True)
    rec["demdata"] = {"file": os.path.basename(out), "size": a.size,
                      "min": lo, "max": hi,
                      "note": "height = min + (R*256+G)/65535 * (max-min); B=0 means nodata"}
    n_ok += 1
    print("  %-34s %.0f..%.0f m  %d KB" % (rec["id"], lo, hi, os.path.getsize(out)//1024))

json.dump(recs, open(os.path.join(a.dist, "scenes.json"), "w"), indent=1)
print("\nwrote DEM height rasters for %d/%d scenes" % (n_ok, len(recs)))
