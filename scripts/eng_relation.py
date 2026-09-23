import json, sys, collections
cat = json.load(open(sys.argv[1]))
S = cat["scenes"]
for side in ("right","left"):
    sub=[r for r in S if r["look_side"]==side and r["squint_engineering"] is not None]
    print("=== %s  n=%d" % (side, len(sub)))
    tests = {
        "eng == 90 + expl"      : lambda r: r["squint_engineering"] - (90.0 + r["squint_exploitation"]),
        "eng == 90 - expl"      : lambda r: r["squint_engineering"] - (90.0 - r["squint_exploitation"]),
        "eng == 270 + expl"     : lambda r: r["squint_engineering"] - (270.0 + r["squint_exploitation"]),
        "eng == 270 - expl"     : lambda r: r["squint_engineering"] - (270.0 - r["squint_exploitation"]),
        "eng == 90 + ob"        : lambda r: r["squint_engineering"] - (90.0 + r["squint_broadside"]),
        "eng == 90 - ob"        : lambda r: r["squint_engineering"] - (90.0 - r["squint_broadside"]),
    }
    for name, f in tests.items():
        ok = sum(1 for r in sub if abs(f(r)) < 1e-6)
        if ok: print("   %-22s holds %d/%d" % (name, ok, len(sub)))
    ex = sub[0]
    print("   sample: eng=%.4f expl=%.4f ob=%.4f  -> eng-90=%.4f"
          % (ex["squint_engineering"], ex["squint_exploitation"], ex["squint_broadside"],
             ex["squint_engineering"]-90.0))
    rng = sorted(r["squint_engineering"] for r in sub)
    print("   engineering range: %.2f .. %.2f" % (rng[0], rng[-1]))
