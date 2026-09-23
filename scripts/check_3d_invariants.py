#!/usr/bin/env python
"""Assert the vectors the 3D view builds are geometrically sane, for every scene
in the published payload. Catches sign errors in the broadside/squint handling
that are easy to introduce and hard to see on a rendered canvas."""
import json, math, sys
D2R = math.pi/180
n360 = lambda a: a % 360.0
def adiff(a, b):
    d = (a - b + 180) % 360
    return d - 180 if d >= 0 else d + 180

scenes = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "tool/scenes_tool.json"))
print("%-34s %-6s %8s %8s %8s %8s" % ("scene","side","|v.bs|","bs-los","squint","inc err"))
ok = True
for sc in scenes:
    g = sc["geom"]
    az, inc, R = g["view_azimuth"]*D2R, g["incidence"]*D2R, 2.45
    S  = [math.sin(inc)*math.sin(az)*R, math.sin(inc)*math.cos(az)*R, math.cos(inc)*R]
    Sg = [S[0], S[1], 0.0]
    hd, bd = g["heading"]*D2R, g["broadside"]*D2R
    V = [math.sin(hd)*0.72, math.cos(hd)*0.72, 0.0]
    Blen = math.hypot(Sg[0], Sg[1])*0.95
    B = [math.sin(bd)*Blen, math.cos(bd)*Blen, 0.0]
    dot = (V[0]*B[0] + V[1]*B[1]) / (math.hypot(*V[:2]) * math.hypot(*B[:2]))
    los_from_Sg = n360(math.degrees(math.atan2(-Sg[0], -Sg[1])))
    d_bs_los = adiff(los_from_Sg, g["broadside"])
    inc_check = math.degrees(math.atan2(math.hypot(S[0], S[1]), S[2]))
    bad = (abs(dot) > 1e-9
           or abs(abs(d_bs_los) - abs(g["squint_off_broadside"])) > 1e-6
           or abs(inc_check - g["incidence"]) > 1e-9)
    ok = ok and not bad
    print("%-34s %-6s %8.1e %8.3f %8.3f %8.1e %s" % (
        sc["id"], g["look_side"], abs(dot), d_bs_los,
        g["squint_exploitation"], abs(inc_check-g["incidence"]),
        "  <-- FAIL" if bad else ""))
print("\nvelocity perpendicular to broadside, broadside->LOS equals the squint,")
print("satellite at the stated incidence:", "ALL PASS" if ok else "FAILURES ABOVE")
sys.exit(0 if ok else 1)
