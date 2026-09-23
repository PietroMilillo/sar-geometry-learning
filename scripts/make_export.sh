#!/bin/bash
# Build a self-contained copy of both exercises that runs from any static server
# (or straight off disk) with no dependency on this machine.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/export/sar-geometry-exercises"
rm -rf "$OUT"; mkdir -p "$OUT/look-angle/img" "$OUT/where-the-summit-lands/img"

cp "$ROOT/tool/look-angle.html"      "$OUT/look-angle/index.html"
cp "$ROOT/tool/img/"*.webp           "$OUT/look-angle/img/" 2>/dev/null || true
cp "$ROOT/tool/summit/where-the-summit-lands.html" "$OUT/where-the-summit-lands/index.html"
cp "$ROOT/tool/summit/"*.webp "$ROOT/tool/summit/"*.png "$OUT/where-the-summit-lands/" 2>/dev/null || true
rmdir "$OUT/where-the-summit-lands/img" 2>/dev/null || true

cp "$ROOT/README.md" "$ROOT/METADATA_HOOKS.md" "$OUT/" 2>/dev/null || true
mkdir -p "$OUT/scripts"; cp "$ROOT/scripts/"*.py "$OUT/scripts/"
mkdir -p "$OUT/data";    cp "$ROOT/data/picks"*.json "$OUT/data/" 2>/dev/null || true

cat > "$OUT/HOW_TO_RUN.md" <<'MD'
# SAR geometry exercises — standalone

Two self-contained pages. Nothing is fetched from the network except the web
fonts, so they work offline apart from slightly plainer type.

    look-angle/index.html                draw the flight direction, line of
                                         sight and layover on real scenes
    where-the-summit-lands/index.html    topography, SAR-lit hillshade, the
                                         slant-range simulation, and the
                                         ellipsoid-geocoding distortion

## Running them

Browsers block `canvas.getImageData` on `file://` URLs, and the second exercise
needs it to read COP30 heights when you click the image. So serve the folder
rather than opening the file directly:

    cd sar-geometry-exercises
    python3 -m http.server 8000

then open http://localhost:8000/where-the-summit-lands/

The first exercise works fine from `file://` if you prefer.

## Putting it on a web server

Copy the whole folder. It is static: HTML plus WebP and PNG images, no build
step, no server code, no API keys.

## What is deliberately NOT in here

The COP30 source tiles. The exercises ship pre-rendered imagery, so the raw DEM
is only needed to REGENERATE them, and a single 1-degree tile is 43 MB. They live
on rsde-02 at:

    <TARGET>/dem_cache/cop30_*.tif                    cached, 132 targets, UTM
    teaching/sar_geometry_tool/data/dem/*.tif         fetched for the rest

`scripts/make_distortion_products.py --dem-dir` takes either.

## Regenerating from the archive

See README.md. The pipeline reads the Umbra archive on rsde-02 and is read-only.
MD
( cd "$ROOT/export" && tar czf sar-geometry-exercises.tar.gz sar-geometry-exercises )
echo "export tree : $OUT"
echo "tarball     : $ROOT/export/sar-geometry-exercises.tar.gz"
du -sh "$OUT" "$ROOT/export/sar-geometry-exercises.tar.gz"
