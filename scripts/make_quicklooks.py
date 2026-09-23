#!/usr/bin/env python
"""Render teaching quicklooks for selected scenes.

For each scene:
  <id>_sar.png       north-up, local transverse-Mercator, equal metres per pixel,
                     transparent outside the footprint
  <id>_sar_zoom.png  native-resolution detail crop, auto-placed on the most
                     textured part of the scene
  <id>_opt.png       ESRI World Imagery warped onto the SAME grid as _sar.png
  <id>_opt_zoom.png  ESRI World Imagery over the detail crop

Equal metres per pixel + north-up is what lets the student-facing tool convert a
drawn screen vector straight into a geographic azimuth: az = atan2(dx, -dy).

Read-only with respect to /bigdata. All output goes to --out.
"""
import os, sys, json, math, argparse, subprocess, io, urllib.request, tempfile
import numpy as np

ASP = "/home/pmilillo/StereoPipeline-3.7.0-alpha-2026-03-05-x86_64-Linux/bin"
os.environ.setdefault("GDAL_DATA", "/home/pmilillo/StereoPipeline-3.7.0-alpha-2026-03-05-x86_64-Linux/share/gdal")

import rasterio
from rasterio.enums import Resampling
from PIL import Image

TILE_URL = ("https://services.arcgisonline.com/ArcGIS/rest/services/"
            "World_Imagery/MapServer/tile/{z}/{y}/{x}")
UA = {"User-Agent": "sar-teaching-tool/1.0 (UH CIVE; educational)"}


def tmerc(clat, clon):
    return ("+proj=tmerc +lat_0=%.8f +lon_0=%.8f +k=1 +x_0=0 +y_0=0 "
            "+datum=WGS84 +units=m +no_defs" % (clat, clon))


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError("%s\n%s" % (" ".join(cmd[:3]), p.stderr[-800:]))
    return p.stdout


def stretch(a, valid, lo=2.0, hi=98.0, gamma=0.85):
    """Percentile stretch on valid pixels only, then a mild gamma lift.
    SAR amplitude is heavily right-skewed; a straight min/max is unreadable."""
    v = a[valid]
    v = v[v > 0]
    if v.size < 100:
        return np.zeros(a.shape, np.uint8)
    p1, p2 = np.percentile(v, [lo, hi])
    if p2 <= p1:
        p2 = p1 + 1.0
    out = np.clip((a.astype(np.float32) - p1) / (p2 - p1), 0, 1)
    out = np.power(out, gamma)
    return (out * 255.0).astype(np.uint8)


def write_rgba(gray, alpha, path):
    rgba = np.dstack([gray, gray, gray, alpha])
    Image.fromarray(rgba, "RGBA").save(path, optimize=True)


def deg2tile(lat, lon, z):
    n = 2.0 ** z
    x = (lon + 180.0) / 360.0 * n
    la = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(la)) / math.pi) / 2.0 * n
    return x, y


def tile2deg(x, y, z):
    n = 2.0 ** z
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1.0 - 2.0 * y / n))))
    return lat, lon


def fetch_basemap(bbox_ll, z, cache, max_tiles=400):
    """Mosaic ESRI World Imagery tiles covering bbox_ll=(w,s,e,n) at zoom z.
    Returns a north-up EPSG:4326-referenced GeoTIFF path, or None."""
    w, s, e, n = bbox_ll
    x0, y0 = deg2tile(n if False else s, w, z)
    xa, ya = deg2tile(n, w, z)
    xb, yb = deg2tile(s, e, z)
    tx0, tx1 = int(math.floor(min(xa, xb))), int(math.floor(max(xa, xb)))
    ty0, ty1 = int(math.floor(min(ya, yb))), int(math.floor(max(ya, yb)))
    nt = (tx1 - tx0 + 1) * (ty1 - ty0 + 1)
    if nt > max_tiles:
        print("      basemap: %d tiles needed at z%d, over cap - skipping" % (nt, z))
        return None
    W, H = (tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256
    mosaic = Image.new("RGB", (W, H))
    got = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            cp = os.path.join(cache, "z%d_%d_%d.jpg" % (z, tx, ty))
            if not os.path.exists(cp):
                url = TILE_URL.format(z=z, x=tx, y=ty)
                try:
                    req = urllib.request.Request(url, headers=UA)
                    with urllib.request.urlopen(req, timeout=25) as r:
                        open(cp, "wb").write(r.read())
                except Exception as ex:
                    print("      tile %d/%d/%d failed: %s" % (z, tx, ty, ex))
                    continue
            try:
                mosaic.paste(Image.open(cp).convert("RGB"),
                             ((tx - tx0) * 256, (ty - ty0) * 256))
                got += 1
            except Exception:
                pass
    if got == 0:
        return None
    # georeference the mosaic in Web Mercator
    latN, lonW = tile2deg(tx0, ty0, z)
    latS, lonE = tile2deg(tx1 + 1, ty1 + 1, z)
    R = 6378137.0
    def merc(lat, lon):
        return (math.radians(lon) * R,
                R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)))
    xW, yN = merc(latN, lonW)
    xE, yS = merc(latS, lonE)
    fd, tmp = tempfile.mkstemp(suffix=".tif", dir=cache); os.close(fd)
    arr = np.array(mosaic)
    tr = rasterio.transform.from_bounds(xW, yS, xE, yN, W, H)
    with rasterio.open(tmp, "w", driver="GTiff", width=W, height=H, count=3,
                       dtype="uint8", crs="EPSG:3857", transform=tr) as ds:
        for i in range(3):
            ds.write(arr[:, :, i], i + 1)
    return tmp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--catalogue", required=True)
    ap.add_argument("--picks", required=True, help="json list of scene stems")
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=1100)
    ap.add_argument("--zoom-px", type=int, default=900)
    ap.add_argument("--no-optical", action="store_true")
    a = ap.parse_args()

    os.makedirs(a.out, exist_ok=True)
    cache = os.path.join(a.out, "_tilecache"); os.makedirs(cache, exist_ok=True)
    tmpd = os.path.join(a.out, "_tmp"); os.makedirs(tmpd, exist_ok=True)

    cat = json.load(open(a.catalogue))
    by_key = {(r["dir"], r["stem"]): r for r in cat["scenes"]}
    by_stem = {}
    for r in cat["scenes"]: by_stem.setdefault(r["stem"], r)
    picks = json.load(open(a.picks))

    out_records = []
    for pk in picks:
        r = by_key.get((pk.get("dir"), pk["stem"])) or by_stem[pk["stem"]]
        sid = pk["id"]
        print("\n=== %s  (%s)" % (sid, r["target"]))
        if not r.get("tif"):
            print("   no local tif, skipped"); continue
        w, s, e, n = r["bbox"]
        clat, clon = (s + n) / 2.0, (w + e) / 2.0
        crs = tmerc(clat, clon)

        # ---- 1. SAR quicklook: warp to north-up local tmerc ----
        warped = os.path.join(tmpd, sid + "_sar.tif")
        run([os.path.join(ASP, "gdalwarp"), "-q", "-overwrite",
             "-t_srs", crs, "-ts", str(a.width), "0", "-r", "average",
             "-dstalpha", "-wo", "NUM_THREADS=2",
             r["tif"], warped])
        with rasterio.open(warped) as ds:
            g = ds.read(1); al = ds.read(ds.count)
            tr = ds.transform; Wpx, Hpx = ds.width, ds.height
            mpp = abs(tr.a)
            x0, y0 = tr.c, tr.f              # top-left in local metres
        valid = al > 0
        png = os.path.join(a.out, sid + "_sar.png")
        write_rgba(stretch(g, valid), (valid * 255).astype(np.uint8), png)
        print("   sar  %dx%d  %.2f m/px  valid %.1f%%"
              % (Wpx, Hpx, mpp, 100.0 * valid.mean()))

        # ---- 2. detail crop: north-up, multi-looked, placed on real structure ----
        # Picking the window on RAW variance finds speckle, not structure, and a
        # single-look native crop of X-band over lava is unreadable noise. So:
        # smooth first, hunt edges, then multi-look the crop like a SAR analyst would.
        from scipy import ndimage
        with rasterio.open(r["tif"]) as ds:
            fullW, fullH = ds.width, ds.height
            ov = ds.read(1, out_shape=(1, 512, 512),
                         resampling=Resampling.average).astype(np.float32)
            ovm = ov > 0
            sm = ndimage.uniform_filter(ov, 5)
            gx = ndimage.sobel(sm, axis=1); gy = ndimage.sobel(sm, axis=0)
            edge = np.hypot(gx, gy)
            edge[~ndimage.binary_erosion(ovm, np.ones((9, 9)))] = 0.0
            score = ndimage.uniform_filter(edge, 24)
            iy, ix = np.unravel_index(np.argmax(score), score.shape)
            fx, fy = (ix + 0.5) / 512.0, (iy + 0.5) / 512.0
            t0 = ds.transform
            px, py = fx * fullW, fy * fullH
            zc_lon = t0.c + px * t0.a + py * t0.b
            zc_lat = t0.f + px * t0.d + py * t0.e
            native_mpp = math.hypot(t0.a, t0.d) * 111320.0 * math.cos(math.radians(clat))

        zspan = max(300.0, min(900.0, native_mpp * 3400.0))   # metres across
        zpx = a.zoom_px
        # centre of the crop in the scene's local metric CRS
        import pyproj
        tf = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        tf_inv = pyproj.Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
        zx, zy = tf.transform(zc_lon, zc_lat)
        zwarp = os.path.join(tmpd, sid + "_zoom.tif")
        run([os.path.join(ASP, "gdalwarp"), "-q", "-overwrite", "-t_srs", crs,
             "-te", str(zx - zspan/2), str(zy - zspan/2),
             str(zx + zspan/2), str(zy + zspan/2),
             "-ts", str(zpx), str(zpx), "-r", "average", "-dstalpha",
             "-wo", "NUM_THREADS=2", r["tif"], zwarp])
        with rasterio.open(zwarp) as ds:
            zg = ds.read(1).astype(np.float32); za = ds.read(ds.count)
        zvalid = za > 0
        # multi-look: a 3x3 spatial average, the standard speckle remedy
        zs = ndimage.uniform_filter(zg, 3)
        write_rgba(stretch(zs, zvalid, lo=1.0, hi=99.0, gamma=0.9),
                   (zvalid * 255).astype(np.uint8),
                   os.path.join(a.out, sid + "_sar_zoom.png"))
        zoom_mpp = zspan / zpx
        print("   zoom %dpx  %.2f m/px  %.0f m across (3-look)  at %.5f,%.5f"
              % (zpx, zoom_mpp, zspan, zc_lat, zc_lon))

        rec = dict(pk)
        rec.update({
            "target": r["target"], "stem": r["stem"],
            "sar_png": os.path.basename(png),
            "sar_zoom_png": sid + "_sar_zoom.png",
            "width_px": Wpx, "height_px": Hpx, "metres_per_px": mpp,
            "scene_width_m": Wpx * mpp, "scene_height_m": Hpx * mpp,
            "centre_lat": clat, "centre_lon": clon,
            "local_crs": crs,
            "zoom_centre_lat": zc_lat, "zoom_centre_lon": zc_lon,
            "zoom_px": zpx, "zoom_metres_per_px": zoom_mpp,
            "zoom_span_m": zspan,
            "zoom_is_north_up": True,
            "zoom_looks": 3,
            "native_metres_per_px": native_mpp,
            "valid_fraction": float(valid.mean()),
        })

        # ---- 3. optical on the identical grid ----
        if not a.no_optical:
            pad = 0.15
            dw, dh = (e - w), (n - s)
            bb = (w - pad * dw, s - pad * dh, e + pad * dw, n + pad * dh)
            z = max(1, min(19, int(round(math.log2(
                156543.03392 * math.cos(math.radians(clat)) / mpp)))))
            print("   optical: zoom z%d for %.2f m/px" % (z, mpp))
            bm = fetch_basemap(bb, z, cache)
            if bm:
                ow = os.path.join(tmpd, sid + "_opt.tif")
                try:
                    run([os.path.join(ASP, "gdalwarp"), "-q", "-overwrite",
                         "-t_srs", crs, "-te",
                         str(x0), str(y0 - Hpx * mpp), str(x0 + Wpx * mpp), str(y0),
                         "-ts", str(Wpx), str(Hpx), "-r", "cubic", bm, ow])
                    with rasterio.open(ow) as ds:
                        rgb = np.dstack([ds.read(i + 1) for i in range(3)])
                    Image.fromarray(rgb, "RGB").save(
                        os.path.join(a.out, sid + "_opt.jpg"), quality=86, optimize=True)
                    rec["opt_jpg"] = sid + "_opt.jpg"
                    print("   optical written")
                    # matching optical detail crop over the same box
                    zb = tf_inv.transform(zx - zspan/2, zy - zspan/2)
                    zt_ = tf_inv.transform(zx + zspan/2, zy + zspan/2)
                    zz = max(1, min(19, int(round(math.log2(
                        156543.03392 * math.cos(math.radians(clat)) / zoom_mpp)))))
                    bm2 = fetch_basemap((zb[0], zb[1], zt_[0], zt_[1]), zz, cache)
                    if bm2:
                        ow2 = os.path.join(tmpd, sid + "_optzoom.tif")
                        try:
                            run([os.path.join(ASP, "gdalwarp"), "-q", "-overwrite",
                                 "-t_srs", crs, "-te",
                                 str(zx - zspan/2), str(zy - zspan/2),
                                 str(zx + zspan/2), str(zy + zspan/2),
                                 "-ts", str(zpx), str(zpx), "-r", "cubic", bm2, ow2])
                            with rasterio.open(ow2) as ds:
                                rgb2 = np.dstack([ds.read(i + 1) for i in range(3)])
                            Image.fromarray(rgb2, "RGB").save(
                                os.path.join(a.out, sid + "_opt_zoom.jpg"),
                                quality=86, optimize=True)
                            rec["opt_zoom_jpg"] = sid + "_opt_zoom.jpg"
                            print("   optical detail written (z%d)" % zz)
                        except Exception as ex:
                            print("   optical zoom failed: %s" % ex)
                        finally:
                            try: os.remove(bm2)
                            except Exception: pass
                except Exception as ex:
                    print("   optical warp failed: %s" % ex)
                finally:
                    try: os.remove(bm)
                    except Exception: pass
        out_records.append(rec)

    json.dump(out_records, open(os.path.join(a.out, "scenes.json"), "w"), indent=1)
    print("\nwrote %d scene records" % len(out_records))


if __name__ == "__main__":
    main()
