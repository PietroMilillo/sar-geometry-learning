import os, json, sys, math, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geometry import norm360, angdiff, look_direction

cat=json.load(open(sys.argv[1])); S=cat["scenes"]
sgn=lambda r: 1.0 if r["look_side"]=="right" else -1.0

print("A. eng == s*90 + expl")
bad=[r for r in S if abs(r["squint_engineering"] - (sgn(r)*90.0 + r["squint_exploitation"]))>1e-6]
print("   violations %d/%d" % (len(bad), len(S)))
for r in bad[:8]:
    print("     %-26s %-5s eng=%9.4f expl=%9.4f ob=%8.4f inc=%.1f"
          % (r["target"][:26], r["look_side"], r["squint_engineering"],
             r["squint_exploitation"], r["squint_broadside"], r["incidence"]))

print("\nB. heading = look_dir - engineering_squint,  scored vs sat:orbit_state")
res=collections.Counter(); hd=collections.defaultdict(list)
for r in S:
    if not r.get("orbit_state"): continue
    h=norm360(look_direction(r["view_azimuth"]) - r["squint_engineering"])
    north=abs(angdiff(h,0.0))<90.0
    res["agree" if north==(r["orbit_state"]=="ascending") else "DISAGREE"]+=1
    hd[r["orbit_state"]].append(h)
n=sum(res.values())
print("   agreement %d/%d = %.2f%%" % (res["agree"], n, 100.0*res["agree"]/n))
for st,hs in hd.items():
    x=sum(math.cos(math.radians(a)) for a in hs); y=sum(math.sin(math.radians(a)) for a in hs)
    R=math.hypot(x,y)/len(hs)
    print("   %-11s n=%4d circ-mean %6.1f deg  concentration R=%.3f" % (st,len(hs),norm360(math.degrees(math.atan2(y,x))),R))

print("\nC. same formula with |squint| only (what you'd get ignoring the sign)")
res2=collections.Counter()
for r in S:
    if not r.get("orbit_state"): continue
    h=norm360(look_direction(r["view_azimuth"]) - (sgn(r)*90.0 + r["squint_broadside"]))
    north=abs(angdiff(h,0.0))<90.0
    res2["agree" if north==(r["orbit_state"]=="ascending") else "DISAGREE"]+=1
n2=sum(res2.values()); print("   agreement %d/%d = %.2f%%" % (res2["agree"],n2,100.0*res2["agree"]/n2))
