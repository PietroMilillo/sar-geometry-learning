#!/usr/bin/env python
"""Cross-check the derived heading against the TRUE sensor state vector.

The SICD XML lives in a NITF DES segment. We parse the NITF header to seek
straight to it rather than scanning 400 MB over NFS.
"""
import sys, json, math, re, os
import xml.etree.ElementTree as ET
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import norm360, angdiff, look_direction

def nitf_des_xml(path):
    f = open(path, "rb")
    def s(n): return f.read(n).decode("latin-1")
    def i(n): return int(s(n))
    hdr = s(9)
    if not hdr.startswith("NITF"):
        raise RuntimeError("not NITF: %r" % hdr)
    f.seek(0)
    f.read(9+2+4+10+14+80)                       # FHDR..FTITLE
    f.read(1+2+11+2+20+2+8+4+1+8+43+1+40+1+8+15) # security block
    f.read(5+5+1+3+24+18)                        # FSCOP..OPHONE
    FL = i(12); HL = i(6)
    off = HL
    NUMI = i(3)
    for _ in range(NUMI): off += i(6) + i(10)
    NUMS = i(3)
    for _ in range(NUMS): off += i(4) + i(6)
    NUMX = i(3); NUMT = i(3)
    for _ in range(NUMT): off += i(4) + i(5)
    NUMDES = i(3)
    des = []
    for _ in range(NUMDES):
        des.append((i(4), i(9)))
    for sh, dl in des:
        f.seek(off + sh)
        blob = f.read(dl)
        k = blob.find(b"<SICD")
        if k < 0:
            k = blob.find(b"<?xml")
        if k >= 0:
            f.close(); return blob[k:].decode("utf-8", "replace")
        off += sh + dl
    f.close(); raise RuntimeError("no SICD XML in %d DES segments" % NUMDES)

def strip_ns(t):
    for e in t.iter():
        if "}" in e.tag: e.tag = e.tag.split("}", 1)[1]
    return t

def ecef_to_enu_heading(pos, vel):
    """Heading (deg from N) of the velocity vector at the sub-satellite point."""
    x, y, z = pos
    lon = math.atan2(y, x)
    hyp = math.hypot(x, y)
    lat = math.atan2(z, hyp)          # geocentric is plenty for a heading
    sl, cl = math.sin(lat), math.cos(lat)
    so, co = math.sin(lon), math.cos(lon)
    vx, vy, vz = vel
    e = -so*vx + co*vy
    n = -sl*co*vx - sl*so*vy + cl*vz
    return norm360(math.degrees(math.atan2(e, n))), math.degrees(lat), math.degrees(lon)

cat = json.load(open(sys.argv[1]))
S = [r for r in cat["scenes"] if r.get("sicd_local")]
print("scenes with a local SICD NITF: %d\n" % len(S))
for r in S:
    try:
        xml = nitf_des_xml(r["sicd_local"])
        t = strip_ns(ET.fromstring(xml))
    except Exception as ex:
        print("  %-40s FAILED: %s" % (r["stem"], ex)); continue
    arp = t.find(".//SCPCOA/ARPPos"); arv = t.find(".//SCPCOA/ARPVel")
    if arp is None:
        arp = t.find(".//ARPPos"); arv = t.find(".//ARPVel")
    pos = [float(arp.find(k).text) for k in ("X","Y","Z")]
    vel = [float(arv.find(k).text) for k in ("X","Y","Z")]
    true_hdg, slat, slon = ecef_to_enu_heading(pos, vel)
    derived = norm360(look_direction(r["view_azimuth"]) - r["squint_engineering"])
    # SICD also carries its own azimuth/grazing for comparison
    def gv(p):
        e = t.find(p); return float(e.text) if e is not None else None
    sicd_az   = gv(".//SCPCOA/AzimAng")
    sicd_graz = gv(".//SCPCOA/GrazeAng")
    sicd_side = (t.find(".//SCPCOA/SideOfTrack").text
                 if t.find(".//SCPCOA/SideOfTrack") is not None else "?")
    print("  %s  (%s)" % (r["stem"], r["target"]))
    print("     SICD ARP vel heading      %8.3f deg" % true_hdg)
    print("     derived from STAC         %8.3f deg   <-- difference %+.3f deg"
          % (derived, angdiff(derived, true_hdg)))
    print("     STAC view:azimuth %.3f | SICD AzimAng %s" % (r["view_azimuth"], sicd_az))
    print("     STAC grazing %.3f      | SICD GrazeAng %s" % (r["grazing"], sicd_graz))
    print("     STAC look_side %-5s     | SICD SideOfTrack %s" % (r["look_side"], sicd_side))
    print("     sub-satellite %.4f, %.4f" % (slat, slon))
    print()
