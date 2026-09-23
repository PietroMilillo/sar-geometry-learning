#!/usr/bin/env python
"""Render every layer the distortion exercise needs, all on ONE registered grid.

For each scene, on the same north-up local transverse-Mercator grid:

  _sar        the real Umbra amplitude (GEC - geocoded to a constant height)
  _opt        Esri optical over the same box
  _dem        COP30 topography, hypsometric
  _hill       hillshade lit from THIS scene's look direction and grazing angle
  _sim        the simulated GEC product built from the DEM + this geometry
  _mask       layover / shadow overlay (transparent elsewhere)
  _disp       ground-range displacement field, diverging about zero

Everything shares one grid so the student can flip between layers and the
features stay put. Read-only with respect to /bigdata.
"""
import os, sys, json, math, argparse, subprocess, tempfile, urllib.request, glob
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
ASP = "/home/pmilillo/StereoPipeline-3.7.0-alpha-2026-03-05-x86_64-Linux/bin"
os.environ.setdefault("GDAL_DATA", ASP.replace("/bin", "/share/gdal"))

import rasterio, pyproj
from PIL import Image
from sar_simulate import simulate, hillshade, displacement_map
from geometry import look_direction, heading_from_squint

TILE_URL = ("https://services.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}")
UA = {"User-Agent": "sar-teaching-tool/1.0 (UH CIVE; educational)"}


def tmerc(clat, clon):
    return ("+proj=tmerc +lat_0=%.8f +lon_0=%.8f +k=1 +x_0=0 +y_0=0 "
            "+datum=WGS84 +units=m +no_defs" % (clat, clon))


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("%s\n%s" % (" ".join(cmd[:4]), p.stderr[-700:]))
    return p.stdout


def stretch(a, valid, lo=2.0, hi=98.0, gamma=0.85):
    v = a[valid]; v = v[v > 0]
    if v.size < 100:
        return np.zeros(a.shape, np.uint8)
    p1, p2 = np.percentile(v, [lo, hi])
    if p2 <= p1: p2 = p1 + 1.0
    o = np.clip((a.astype(np.float32) - p1) / (p2 - p1), 0, 1) ** gamma
    return (o * 255).astype(np.uint8)


def save_gray(g, alpha, path, q=80):
    Image.fromarray(np.dstack([g, g, g, alpha]), "RGBA").save(path, "WEBP", quality=q, method=5)


def save_rgba(rgba, path, q=80):
    Image.fromarray(rgba, "RGBA").save(path, "WEBP", quality=q, method=5)


def ramp(vals, stops):
    """Piecewise-linear colour ramp. vals in 0..1, stops = [(t,(r,g,b)),...]."""
    out = np.zeros(vals.shape + (3,), np.float32)
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]; t1, c1 = stops[i + 1]
        m = (vals >= t0) & (vals <= t1)
        if not m.any(): continue
        f = ((vals[m] - t0) / max(t1 - t0, 1e-9))[:, None]
        out[m] = np.array(c0, np.float32) * (1 - f) + np.array(c1, np.float32) * f
    out[vals < stops[0][0]] = stops[0][1]
    out[vals > stops[-1][0]] = stops[-1][1]
    return out.astype(np.uint8)


HYPSO = [(0.00, (58, 84, 108)), (0.15, (76, 122, 106)), (0.35, (140, 158, 96)),
         (0.55, (196, 176, 112)), (0.75, (188, 140, 106)), (0.90, (214, 206, 202)),
         (1.00, (252, 252, 252))]
DIVERGE = [(0.0, (36, 92, 140)), (0.35, (122, 170, 200)), (0.5, (238, 238, 236)),
           (0.65, (226, 152, 106)), (1.0, (150, 44, 26))]


def deg2tile(lat, lon, z):
    n = 2.0 ** z
    return ((lon + 180.0) / 360.0 * n,
            (1.0 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2.0 * n)


def tile2deg(x, y, z):
    n = 2.0 ** z
    return (math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n)))),
            x / n * 360.0 - 180.0)


def fetch_basemap(bbox, z, cache, max_tiles=260):
    w, s, e, n = bbox
    xa, ya = deg2tile(n, w, z); xb, yb = deg2tile(s, e, z)
    tx0, tx1 = int(math.floor(min(xa, xb))), int(math.floor(max(xa, xb)))
    ty0, ty1 = int(math.floor(min(ya, yb))), int(math.floor(max(ya, yb)))
    if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > max_tiles:
        return None
    W, H = (tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256
    mos = Image.new("RGB", (W, H)); got = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            cp = os.path.join(cache, "z%d_%d_%d.jpg" % (z, tx, ty))
            if not os.path.exists(cp):
                try:
                    req = urllib.request.Request(TILE_URL.format(z=z, x=tx, y=ty), headers=UA)
                    with urllib.request.urlopen(req, timeout=25) as r:
                        open(cp, "wb").write(r.read())
                except Exception:
                    continue
            try:
                mos.paste(Image.open(cp).convert("RGB"), ((tx - tx0) * 256, (ty - ty0) * 256)); got += 1
            except Exception:
                pass
    if not got: return None
    latN, lonW = tile2deg(tx0, ty0, z); latS, lonE = tile2deg(tx1 + 1, ty1 + 1, z)
    R = 6378137.0
    merc = lambda la, lo: (math.radians(lo) * R,
                           R * math.log(math.tan(math.pi / 4 + math.radians(la) / 2)))
    xW, yN = merc(latN, lonW); xE, yS = merc(latS, lonE)
    fd, tmp = tempfile.mkstemp(suffix=".tif", dir=cache); os.close(fd)
    arr = np.array(mos)
    tr = rasterio.transform.from_bounds(xW, yS, xE, yN, W, H)
    with rasterio.open(tmp, "w", driver="GTiff", width=W, height=H, count=3,
                       dtype="uint8", crs="EPSG:3857", transform=tr) as ds:
        for i in range(3): ds.write(arr[:, :, i], i + 1)
    return tmp


def find_dem(root, target, bbox, extra_dir):
    """Cached COP30 for the target, else any tile in extra_dir that covers the box."""
    cands = sorted(glob.glob(os.path.join(root, target, "dem_cache", "cop30_*.tif")))
    cands += sorted(glob.glob(os.path.join(extra_dir, "*.tif"))) if extra_dir else []
    w, s, e, n = bbox
    for c in cands:
        try:
            with rasterio.open(c) as ds:
                tf = pyproj.Transformer.from_crs("EPSG:4326", ds.crs, always_xy=True)
                xs, ys = [], []
                for lo, la in ((w, s), (w, n), (e, s), (e, n)):
                    x, y = tf.transform(lo, la); xs.append(x); ys.append(y)
                b = ds.bounds
                if b.left <= min(xs) and b.right >= max(xs) and \
                   b.bottom <= min(ys) and b.top >= max(ys):
                    return c
        except Exception:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--picks", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--dem-dir", default=None)
    ap.add_argument("--size", type=int, default=900)
    ap.add_argument("--pad", type=float, default=0.55,
                    help="widen the box beyond the footprint, so displaced terrain "
                         "has somewhere to land instead of being clipped")
    ap.add_argument("--no-optical", action="store_true")
    a = ap.parse_args()

    cat = json.load(open(a.catalogue)); ROOT = cat["root"]
    by_key = {(r["dir"], r["stem"]): r for r in cat["scenes"]}
    by_stem = {}
    for r in cat["scenes"]: by_stem.setdefault(r["stem"], r)
    picks = json.load(open(a.picks))

    os.makedirs(a.out, exist_ok=True)
    cache = os.path.join(a.out, "_tilecache"); os.makedirs(cache, exist_ok=True)
    tmpd = os.path.join(a.out, "_tmp"); os.makedirs(tmpd, exist_ok=True)

    recs = []
    for pk in picks:
        r = by_key.get((pk.get("dir"), pk["stem"])) or by_stem[pk["stem"]]
        sid = pk["id"]
        print("\n=== %s" % sid, flush=True)
        w, s, e, n = r["bbox"]
        clat, clon = (s + n) / 2, (w + e) / 2
        crs = tmerc(clat, clon)
        tf = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        xs, ys = [], []
        for lo, la in ((w, s), (w, n), (e, s), (e, n)):
            x, y = tf.transform(lo, la); xs.append(x); ys.append(y)
        halfx = (max(xs) - min(xs)) / 2 * (1 + a.pad)
        halfy = (max(ys) - min(ys)) / 2 * (1 + a.pad)
        half = max(halfx, halfy)
        cx, cy = (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2
        te = [cx - half, cy - half, cx + half, cy + half]
        N = a.size
        mpp = (te[2] - te[0]) / N

        # ---- SAR amplitude on the grid ----
        sarw = os.path.join(tmpd, sid + "_sar.tif")
        run([os.path.join(ASP, "gdalwarp"), "-q", "-overwrite", "-t_srs", crs,
             "-te", *[str(v) for v in te], "-ts", str(N), str(N),
             "-r", "average", "-dstalpha", "-wo", "NUM_THREADS=2", r["tif"], sarw])
        with rasterio.open(sarw) as ds:
            amp = ds.read(1); aal = ds.read(ds.count)
        valid = aal > 0
        save_gray(stretch(amp, valid), (valid * 255).astype(np.uint8),
                  os.path.join(a.out, sid + "_sar.webp"))

        # ---- DEM on the identical grid ----
        demsrc = find_dem(ROOT, r["target"], (w, s, e, n), a.dem_dir)
        if demsrc is None:
            print("   !! no DEM covers this scene, skipped"); continue
        demw = os.path.join(tmpd, sid + "_dem.tif")
        run([os.path.join(ASP, "gdalwarp"), "-q", "-overwrite", "-t_srs", crs,
             "-te", *[str(v) for v in te], "-ts", str(N), str(N),
             "-r", "cubic", demsrc, demw])
        with rasterio.open(demw) as ds:
            dem = ds.read(1).astype(np.float64)
            nd = ds.nodata
        if nd is not None: dem[dem == nd] = np.nan
        dem[dem < -500] = np.nan
        if not np.isfinite(dem).any():
            print("   !! DEM all nodata, skipped"); continue
        dem = np.where(np.isfinite(dem), dem, np.nanmedian(dem))

        h_ref = pk["h_ref"]
        inc, look_dir = r["incidence"], look_direction(r["view_azimuth"])
        graz = r["grazing"]

        # ---- topography ----
        lo_, hi_ = np.percentile(dem, [1, 99])
        t = np.clip((dem - lo_) / max(hi_ - lo_, 1e-6), 0, 1)
        save_rgba(np.dstack([ramp(t, HYPSO), np.full(dem.shape, 255, np.uint8)]),
                  os.path.join(a.out, sid + "_dem.webp"))

        # ---- hillshade, lit exactly the way this radar lit the ground ----
        hs = hillshade(dem, mpp, r["view_azimuth"], graz)
        g8 = (np.clip(hs, 0, 1) * 255).astype(np.uint8)
        save_gray(g8, np.full(dem.shape, 255, np.uint8),
                  os.path.join(a.out, sid + "_hill.webp"))

        # ---- the simulation ----
        sim = simulate(dem, mpp, look_dir, inc, h_ref)
        sm = sim["sim"]
        smv = sm[sm > 0]
        p98 = np.percentile(smv, 98) if smv.size else 1.0
        s8 = (np.clip(sm / max(p98, 1e-6), 0, 1) ** 0.75 * 255).astype(np.uint8)
        save_gray(s8, np.full(dem.shape, 255, np.uint8),
                  os.path.join(a.out, sid + "_sim.webp"))

        # ---- layover / shadow overlay on the map grid ----
        lay, shd = sim["layover_map"], sim["shadow_map"]
        ov = np.zeros(dem.shape + (4,), np.uint8)
        ov[lay] = (214, 78, 32, 190)
        ov[shd & ~lay] = (58, 66, 118, 190)
        save_rgba(ov, os.path.join(a.out, sid + "_mask.webp"))

        # ---- displacement field ----
        d = sim["disp_m"]
        lim = max(1.0, float(np.percentile(np.abs(d), 99)))
        dv = np.clip(d / lim, -1, 1) * 0.5 + 0.5
        save_rgba(np.dstack([ramp(dv, DIVERGE), np.full(dem.shape, 255, np.uint8)]),
                  os.path.join(a.out, sid + "_disp.webp"))

        # ---- optical ----
        opt = None
        if not a.no_optical:
            inv = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
            bl = inv.transform(te[0], te[1]); tr_ = inv.transform(te[2], te[3])
            z = max(1, min(19, int(round(math.log2(
                156543.03392 * math.cos(math.radians(clat)) / mpp)))))
            bm = fetch_basemap((bl[0], bl[1], tr_[0], tr_[1]), z, cache)
            if bm:
                ow = os.path.join(tmpd, sid + "_opt.tif")
                try:
                    run([os.path.join(ASP, "gdalwarp"), "-q", "-overwrite", "-t_srs", crs,
                         "-te", *[str(v) for v in te], "-ts", str(N), str(N),
                         "-r", "cubic", bm, ow])
                    with rasterio.open(ow) as ds:
                        rgb = np.dstack([ds.read(i + 1) for i in range(3)])
                    Image.fromarray(rgb, "RGB").save(
                        os.path.join(a.out, sid + "_opt.webp"), "WEBP", quality=78, method=5)
                    opt = sid + "_opt.webp"
                except Exception as ex:
                    print("   optical failed: %s" % ex)
                finally:
                    try: os.remove(bm)
                    except Exception: pass

        rel = float(np.nanmax(dem) - np.nanmin(dem))
        rec = {
            "id": sid, "stem": r["stem"], "group": pk["group"], "target": r["target"],
            "why": pk["why"], "datetime": r["datetime"], "platform": r["platform"],
            "images": {k: v for k, v in (
                ("sar", sid + "_sar.webp"), ("dem", sid + "_dem.webp"),
                ("hill", sid + "_hill.webp"), ("sim", sid + "_sim.webp"),
                ("mask", sid + "_mask.webp"), ("disp", sid + "_disp.webp"),
                ("opt", opt)) if v},
            "geom": {
                "incidence": inc, "grazing": graz, "view_azimuth": r["view_azimuth"],
                "look_dir": look_dir,
                "heading": heading_from_squint(r["view_azimuth"], r["squint_engineering"]),
                "squint_off_broadside": r["squint_broadside"],
                "squint_exploitation": r["squint_exploitation"],
                "squint_engineering": r["squint_engineering"],
                "look_side": r["look_side"], "orbit_state": r["orbit_state"],
                "h_ref": h_ref,
            },
            "terrain": {
                "relief_m": rel, "dem_min": float(np.nanmin(dem)), "dem_max": float(np.nanmax(dem)),
                "cot": 1.0 / math.tan(math.radians(max(inc, 0.5))),
                "disp_max_m": float(np.nanmax(np.abs(d))),
                "disp_max_px": float(np.nanmax(np.abs(d)) / mpp),
                "disp_p99_m": float(np.percentile(np.abs(d), 99)),
                "layover_pct": float(lay.mean() * 100.0),
                "shadow_pct": float(shd.mean() * 100.0),
                "dem_source": os.path.basename(demsrc),
            },
            "grid": {"size": N, "mpp": mpp, "span_m": N * mpp,
                     "lat": clat, "lon": clon, "crs": crs},
        }
        recs.append(rec)
        print("   relief %.0f m  cot %.2f  |disp| max %.0f m (%.0f px)  layover %.1f%%  shadow %.1f%%"
              % (rel, rec["terrain"]["cot"], rec["terrain"]["disp_max_m"],
                 rec["terrain"]["disp_max_px"], rec["terrain"]["layover_pct"],
                 rec["terrain"]["shadow_pct"]), flush=True)

    json.dump(recs, open(os.path.join(a.out, "scenes.json"), "w"), indent=1)
    print("\nwrote %d scene records" % len(recs))


if __name__ == "__main__":
    main()
