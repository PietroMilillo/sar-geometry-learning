#!/usr/bin/env python
"""Parse every STAC v2 sidecar named in inventory.txt into one geometry catalogue.

Read-only; touches only the small JSON sidecars, never the TIFFs (NFS).
"""
import json, os, sys, collections, time
from concurrent.futures import ThreadPoolExecutor

INV = sys.argv[1]; OUT = sys.argv[2]
ROOT = "/bigdata/pietro/processing/Umbra/radargrammetry"

paths = [l.strip() for l in open(INV) if l.strip().endswith(".stac.v2.json")]
tifs  = set(l.strip() for l in open(INV) if l.strip().endswith("_MM.tif"))
sicds = set(l.strip() for l in open(INV) if l.strip().endswith("_SICD_MM.nitf"))

FIELDS = [
    ("orbit_state","sat:orbit_state"), ("view_azimuth","view:azimuth"),
    ("incidence","view:incidence_angle"), ("grazing","umbra:grazing_angle_degrees"),
    ("squint_broadside","umbra:squint_angle_degrees_off_broadside"),
    ("squint_engineering","umbra:squint_angle_engineering_degrees"),
    ("squint_exploitation","umbra:squint_angle_exploitation_degrees"),
    ("look_side","sar:observation_direction"), ("mode","sar:instrument_mode"),
    ("band","sar:frequency_band"), ("freq_ghz","sar:center_frequency"),
    ("looks_az","sar:looks_azimuth"), ("looks_rg","sar:looks_range"),
    ("res_az","sar:resolution_azimuth"), ("res_rg","sar:resolution_range"),
    ("pols","sar:polarizations"), ("platform","platform"),
    ("product_type","sar:product_type"), ("slant_range_m","umbra:slant_range_meters"),
    ("datetime","datetime"), ("collect_id","umbra:collect_id"),
]

def parse_one(p):
    # NFS here is latency-bound, not bandwidth-bound: serial reads ran at ~1
    # file/s under pipeline load, a thread pool at ~100x that. Threads are the
    # right tool because the GIL is released across the read syscall.
    d = os.path.dirname(p)
    stem = os.path.basename(p)[: -len(".stac.v2.json")]
    try:
        with open(p) as fh:
            s = json.load(fh)
    except Exception:
        return None
    pr = s.get("properties", {})
    tif  = os.path.join(d, stem + "_MM.tif")
    sicd = os.path.join(d, stem + "_SICD_MM.nitf")
    r = {"target": os.path.relpath(d, ROOT).split(os.sep)[0],
         "stem": stem, "dir": d,
         "tif": tif if tif in tifs else None,
         "sicd_local": sicd if sicd in sicds else None,
         "from_unk_dir": d.endswith("_UNK"),
         "bbox": s.get("bbox"),
         "footprint": (s.get("geometry") or {}).get("coordinates")}
    for k, key in FIELDS:
        r[k] = pr.get(key)
    return r

t0 = time.time()
with ThreadPoolExecutor(max_workers=24) as ex:
    out = list(ex.map(parse_one, paths))
recs = [r for r in out if r is not None]
bad = len(out) - len(recs)
print("parsed %d sidecars in %.1fs" % (len(recs), time.time() - t0))

json.dump({"root": ROOT, "n": len(recs), "scenes": recs}, open(OUT, "w"))

print("sidecars parsed %d  (unparseable %d)" % (len(recs), bad))
print("  with local _MM.tif : %d" % sum(1 for r in recs if r["tif"]))
print("  with local SICD    : %d" % sum(1 for r in recs if r["sicd_local"]))
print("  targets            : %d" % len(set(r["target"] for r in recs)))
print("\nfield population:")
for k,_ in FIELDS:
    print("   %-20s %d/%d" % (k, sum(1 for r in recs if r.get(k) is not None), len(recs)))
print("\norbit_state:", collections.Counter(r["orbit_state"] for r in recs))
print("look_side  :", collections.Counter(r["look_side"] for r in recs))
print("mode       :", collections.Counter(r["mode"] for r in recs))
inc = sorted(r["incidence"] for r in recs if r["incidence"] is not None)
sq  = sorted(abs(r["squint_broadside"]) for r in recs if r["squint_broadside"] is not None)
def q(a,f): return a[int(f*(len(a)-1))]
print("incidence  min/p25/med/p75/max: %.1f %.1f %.1f %.1f %.1f" % (q(inc,0),q(inc,.25),q(inc,.5),q(inc,.75),q(inc,1)))
print("|squint|   min/p25/med/p75/max: %.1f %.1f %.1f %.1f %.1f" % (q(sq,0),q(sq,.25),q(sq,.5),q(sq,.75),q(sq,1)))
