#!/usr/bin/env python
"""Merge catalogue geometry + rendered quicklooks into the payload the tool embeds,
and convert the imagery to WebP so the page stays small enough to actually load."""
import json, os, sys, math, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import (look_direction, heading_from_squint, norm360,
                      broadside_azimuth, side_sign)
from PIL import Image

ap = argparse.ArgumentParser()
ap.add_argument("--catalogue", required=True)
ap.add_argument("--ql", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--webp-quality", type=int, default=82)
a = ap.parse_args()

cat = json.load(open(a.catalogue))
# 166 of 963 stems exist under more than one target directory (neighbouring
# volcanoes whose footprints overlap, plus RULES.md R12 name duplicates), so a
# bare stem lookup silently picks the wrong target name. Key on the directory.
by_key = {(r["dir"], r["stem"]): r for r in cat["scenes"]}
by_stem = {}
for r in cat["scenes"]: by_stem.setdefault(r["stem"], r)
def resolve(rec):
    d = rec.get("dir")
    if d and (d, rec["stem"]) in by_key: return by_key[(d, rec["stem"])]
    return by_stem[rec["stem"]]
rendered = json.load(open(os.path.join(a.ql, "scenes.json")))
os.makedirs(a.out, exist_ok=True)
imgdir = os.path.join(a.out, "img"); os.makedirs(imgdir, exist_ok=True)

QUESTIONS = {
  "flight_direction": {
    "prompt": "Drag on the image to draw the satellite's direction of flight.",
    "hint": "The ground track, not the look direction. Ascending and descending passes point opposite ways.",
    "answer": "heading",
    "answer_label": "ground-track heading",
  },
  "line_of_sight": {
    "prompt": "Drag to draw the radar's line of sight, from the satellite's ground position toward the scene.",
    "hint": "Its azimuth on the ground. Watch the squint - it is only perpendicular to the track at zero squint.",
    "answer": "look_dir",
    "answer_label": "ground-projected line of sight",
  },
  "layover": {
    "prompt": "Drag from a summit or rooftop to show which way it is displaced in this image.",
    "hint": "Tall things lean toward whatever illuminates them. The radar is not the sun.",
    "answer": "layover_dir",
    "answer_label": "layover displacement",
  },
}

def webp(src, dst, q):
    im = Image.open(src)
    if im.mode == "RGBA":
        im.save(dst, "WEBP", quality=q, method=5)
    else:
        im.convert("RGB").save(dst, "WEBP", quality=q, method=5)
    return os.path.getsize(dst)

out, total = [], 0
for rec in rendered:
    r = resolve(rec)
    look_dir = look_direction(r["view_azimuth"])
    heading  = heading_from_squint(r["view_azimuth"], r["squint_engineering"])
    s        = side_sign(r["look_side"])
    imgs = {}
    for key, fn in (("sar", rec.get("sar_png")), ("sar_zoom", rec.get("sar_zoom_png")),
                    ("opt", rec.get("opt_jpg")), ("opt_zoom", rec.get("opt_zoom_jpg"))):
        if not fn: continue
        src = os.path.join(a.ql, fn)
        if not os.path.exists(src): continue
        dst_name = os.path.splitext(fn)[0] + ".webp"
        n = webp(src, os.path.join(imgdir, dst_name), a.webp_quality)
        total += n; imgs[key] = "img/" + dst_name

    q = QUESTIONS[rec["question"]]
    answers = {
        "heading": heading,
        "look_dir": look_dir,
        "layover_dir": norm360(r["view_azimuth"]),   # displacement is TOWARD the sensor
    }
    out.append({
      "id": rec["id"], "target": r["target"].replace("_", " "),
      "datetime": r["datetime"], "platform": r["platform"],
      "question": rec["question"], "note": rec["note"],
      "prompt": q["prompt"], "hint": q["hint"],
      "answer_deg": answers[q["answer"]], "answer_label": q["answer_label"],
      "images": imgs,
      "geom": {
        "incidence": r["incidence"], "grazing": r["grazing"],
        "view_azimuth": r["view_azimuth"], "look_dir": look_dir,
        "heading": heading, "broadside": broadside_azimuth(heading, r["look_side"]),
        "squint_off_broadside": r["squint_broadside"],
        "squint_engineering": r["squint_engineering"],
        "squint_exploitation": r["squint_exploitation"],
        "look_side": r["look_side"], "orbit_state": r["orbit_state"],
        "slant_range_m": r["slant_range_m"],
      },
      "sar": {
        "mode": r["mode"], "band": r["band"], "freq_ghz": r["freq_ghz"],
        "res_az": r["res_az"], "res_rg": r["res_rg"],
        "looks_az": r["looks_az"], "looks_rg": r["looks_rg"],
        "pols": r["pols"], "product_type": r["product_type"],
      },
      "raster": {
        "w": rec["width_px"], "h": rec["height_px"], "mpp": rec["metres_per_px"],
        "lat": rec["centre_lat"], "lon": rec["centre_lon"],
        "span_m": rec["scene_width_m"], "valid": rec["valid_fraction"],
        "zoom_mpp": rec.get("zoom_metres_per_px"), "zoom_span_m": rec.get("zoom_span_m"),
        "zoom_lat": rec.get("zoom_centre_lat"), "zoom_lon": rec.get("zoom_centre_lon"),
        "zoom_looks": rec.get("zoom_looks"),
      },
    })

json.dump(out, open(os.path.join(a.out, "scenes_tool.json"), "w"), indent=1)
print("exported %d scenes, %.1f MB of imagery" % (len(out), total/1e6))
for o in out:
    g = o["geom"]
    print("  %-34s %-16s inc %5.1f  sq %+6.1f  hdg %5.1f  los %5.1f  %-10s %-5s  imgs %d"
          % (o["id"], o["question"], g["incidence"], g["squint_exploitation"],
             g["heading"], g["look_dir"], g["orbit_state"], g["look_side"], len(o["images"])))
