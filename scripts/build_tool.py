#!/usr/bin/env python
"""Assemble the publishable tool: template + scene payload."""
import json, sys, os, argparse
ap = argparse.ArgumentParser()
ap.add_argument("--template", required=True)
ap.add_argument("--scenes", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
tpl = open(a.template).read()
scenes = json.load(open(a.scenes))
# compact, and safe to sit inside a <script type="application/json"> block
payload = json.dumps(scenes, separators=(",", ":")).replace("</", "<\\/")
assert "__SCENES__" in tpl, "template placeholder missing"
html = tpl.replace("__SCENES__", payload)
open(a.out, "w").write(html)
print("wrote %s  (%.1f KB html, %d scenes, payload %.1f KB)"
      % (a.out, len(html)/1024, len(scenes), len(payload)/1024))
