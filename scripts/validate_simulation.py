#!/usr/bin/env python
"""Does the simulation actually describe the real image?

The exercise asserts three things. Each is testable against the amplitude:

  1. Terrain the simulation puts in SHADOW should be dark in the real image.
  2. Terrain the simulation puts in LAYOVER should be bright in the real image.
  3. The GEC reference height read from the footprint polygon should be the one
     that best registers the simulation to the amplitude - so scanning h_ref
     should show a minimum of the residual near the value in the sidecar.

Test 3 is the one that decides whether the ellipsoid story is right. If some
other h_ref registered better, the sidecar's footprint elevation would not be
the geocoding reference and the whole explanation would need rewriting.
"""
import os, sys, json, math, argparse
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("GDAL_DATA",
    "/home/pmilillo/StereoPipeline-3.7.0-alpha-2026-03-05-x86_64-Linux/share/gdal")
import rasterio
from sar_simulate import simulate


def load_gray(p):
    im = Image.open(p).convert("RGBA")
    a = np.asarray(im).astype(np.float32)
    return a[..., 0], a[..., 3] > 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dist", required=True, help="build/dist directory")
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--scan", action="store_true", help="also run the h_ref scan (slow)")
    a = ap.parse_args()

    recs = json.load(open(os.path.join(a.dist, "scenes.json")))
    tmpd = os.path.join(a.dist, "_tmp")

    print("TEST 1+2  does the simulated geometry predict the real amplitude?")
    print("%-34s %6s %8s %8s %8s %8s" %
          ("scene", "inc", "shadow%", "dark/lit", "layover%", "bright/flat"))
    print("-" * 82)
    ratios_s, ratios_l = [], []
    for rec in recs:
        sar_p = os.path.join(a.dist, rec["images"]["sar"])
        if not os.path.exists(sar_p):
            continue
        amp, valid = load_gray(sar_p)
        dem_t = os.path.join(tmpd, rec["id"] + "_dem.tif")
        if not os.path.exists(dem_t):
            continue
        with rasterio.open(dem_t) as ds:
            dem = ds.read(1).astype(np.float64)
            nd = ds.nodata
        if nd is not None: dem[dem == nd] = np.nan
        dem[dem < -500] = np.nan
        if not np.isfinite(dem).any(): continue
        dem = np.where(np.isfinite(dem), dem, np.nanmedian(dem))

        g = rec["geom"]; grid = rec["grid"]
        sim = simulate(dem, grid["mpp"], g["look_dir"], g["incidence"], g["h_ref"])
        # The amplitude is a PRODUCT, so it must be compared against the masks in
        # PRODUCT space, not against where the terrain actually sits on the
        # ground. Using "layover_map"/"shadow_map" here compares the image with
        # terrain that the GEC geocoding has already moved - at Fuego's 17.5 deg
        # scene, by 8 km. That is the whole point of the exercise, and it is easy
        # to trip over in the validation itself.
        sh, lay = sim["shadow"], sim["layover"]
        m = valid & (amp > 0)
        if m.sum() < 5000: continue

        def mean_in(mask):
            k = m & mask
            return float(amp[k].mean()) if k.sum() > 200 else float("nan")

        lit = mean_in(~sh & ~lay)
        d_sh = mean_in(sh)
        d_la = mean_in(lay)
        rs = d_sh / lit if lit and np.isfinite(d_sh) else float("nan")
        rl = d_la / lit if lit and np.isfinite(d_la) else float("nan")
        if np.isfinite(rs): ratios_s.append(rs)
        if np.isfinite(rl): ratios_l.append(rl)
        print("%-34s %6.1f %8.1f %8s %8.1f %8s" % (
            rec["id"][:34], g["incidence"], rec["terrain"]["shadow_pct"],
            ("%.2f" % rs) if np.isfinite(rs) else "  -",
            rec["terrain"]["layover_pct"],
            ("%.2f" % rl) if np.isfinite(rl) else "  -"))

    print()
    if ratios_s:
        print("  predicted shadow  / lit brightness: median %.2f over %d scenes "
              "(want well below 1.0)" % (float(np.median(ratios_s)), len(ratios_s)))
    if ratios_l:
        print("  predicted layover / lit brightness: median %.2f over %d scenes "
              "(want above 1.0)" % (float(np.median(ratios_l)), len(ratios_l)))

    if not a.scan:
        return
    print("\nTEST 3  is the sidecar's footprint elevation really the geocoding reference?")
    print("Scanning h_ref and scoring shadow-darkness contrast; the best h_ref")
    print("should land near the value the sidecar reports.\n")
    print("%-34s %10s %10s %8s" % ("scene", "sidecar", "best scan", "delta"))
    print("-" * 66)
    for rec in recs:
        if rec["terrain"]["shadow_pct"] < 4.0:
            continue                     # no shadow, nothing to register against
        sar_p = os.path.join(a.dist, rec["images"]["sar"])
        dem_t = os.path.join(tmpd, rec["id"] + "_dem.tif")
        if not (os.path.exists(sar_p) and os.path.exists(dem_t)): continue
        amp, valid = load_gray(sar_p)
        with rasterio.open(dem_t) as ds:
            dem = ds.read(1).astype(np.float64); nd = ds.nodata
        if nd is not None: dem[dem == nd] = np.nan
        dem[dem < -500] = np.nan
        dem = np.where(np.isfinite(dem), dem, np.nanmedian(dem))
        g, grid = rec["geom"], rec["grid"]
        m = valid & (amp > 0)
        base = g["h_ref"]
        best, best_h = None, None
        for dh in range(-1500, 1501, 250):
            h = base + dh
            s = simulate(dem, grid["mpp"], g["look_dir"], g["incidence"], h)
            sh = s["shadow_map"]
            k, k2 = m & sh, m & ~sh
            if k.sum() < 500 or k2.sum() < 500: continue
            contrast = amp[k2].mean() - amp[k].mean()      # want this maximised
            if best is None or contrast > best:
                best, best_h = contrast, h
        if best_h is not None:
            print("%-34s %10.0f %10.0f %8.0f" % (rec["id"][:34], base, best_h, best_h - base))
    print("\nNote: the shadow mask depends on h_ref only through the terrain it")
    print("occludes, so this scan is a weak but non-circular check.")


if __name__ == "__main__":
    main()
