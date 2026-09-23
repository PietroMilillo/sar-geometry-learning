# SAR acquisition geometry — two teaching exercises

Two student-facing interactive pages plus the read-only data-prep pipeline that
feeds them, built on the Umbra archive on rsde-02.

**1. Look Angle** (`tool/look-angle.html`) — 11 scenes. Draw the flight
direction, line of sight or layover displacement on a real amplitude image; the
answer is marked against that scene's own sidecar.

**2. Where the Summit Lands** (`tool/summit/where-the-summit-lands.html`) —
19 acquisitions over Fuego, Nevado del Ruiz, Gamalama and EEFIT Quimbaya. Seven
pixel-registered layers per scene (amplitude, optical, COP30 topography,
hillshade lit from that scene's own look vector, the slant-range simulation,
layover/shadow masks, displacement field). Click anywhere on the topography and
it tells you where the GEC product puts that point, and why.

Run `bash scripts/make_export.sh` to produce a standalone, copyable bundle of
both at `export/sar-geometry-exercises/` plus a tarball.

`METADATA_HOOKS.md` lists every metadata field used and how to extend the tool.
Read it before changing anything — it records which conventions are real and
which look real but are not.

## Layout

```
scripts/     the pipeline, in dependency order (below)
data/        catalogue, scene picks, and COP30 tiles fetched for targets
             that had none cached
tool/        the generated pages and their imagery
build/dist/  intermediate rasters for the distortion exercise
export/      standalone bundle + tarball, produced by scripts/make_export.sh
```

## The distortion exercise, end to end

```bash
P=/home/pmilillo/miniconda3/envs/asp/bin/python
nice -n 19 $P scripts/pick_distortion_set.py data/catalogue.json \
    data/picks_distortion.json "Fuego,Nevado_del_Ruiz,Gamalama,EEFIT_Quimbaya" 5
nice -n 19 $P scripts/make_distortion_products.py --catalogue data/catalogue.json \
    --picks data/picks_distortion.json --out build/dist --dem-dir data/dem --pad 0.25
nice -n 19 $P scripts/make_demdata.py --dist build/dist
nice -n 19 $P scripts/validate_simulation.py --dist build/dist --catalogue data/catalogue.json
$P scripts/sar_simulate.py          # self-test of the physics
# Nevado del Ruiz has no acquisition below 48 deg anywhere in the archive, so
# its tab would show shadow but never layover. Borrow a matched-relief scene:
nice -n 19 $P scripts/add_contrast_scene.py --scenes build/dist/scenes.json \
    --source Gamalama_20260421143811 --into Nevado_del_Ruiz
$P scripts/build_tool.py --template tool/distortion_template.html \
    --scenes build/dist/scenes.json --out tool/summit/where-the-summit-lands.html
```

The borrowed record keeps its own target name, is flagged `borrowed`, shares the
lender's imagery (no extra files), and is excluded from every statistic that
describes what the host target actually holds.

`sar_simulate.py` run directly is its own test suite: it checks the displacement
against `-(h - h_ref)*cot(theta)` across six look directions and three incidence
angles, the layover and shadow thresholds on synthetic ramps, and two null cases.
Run it after any change to the geometry.

## Regenerating

Everything is read-only with respect to `/bigdata` and runs `nice -n 19`.
Python is `/home/pmilillo/miniconda3/envs/asp/bin/python`; GDAL binaries come
from the StereoPipeline tree.

```bash
P=/home/pmilillo/miniconda3/envs/asp/bin/python
cd /bigdata/pietro/teaching/sar_geometry_tool
```

**1. Inventory the archive.** Glob recursively — scenes live in
`<TARGET>/data/` *and* in `<TARGET>/<date>_<ORBIT>_<SAT>_UNK/`, depending on
whether the daemon or `sar_vault.py download` fetched them.

```bash
nice -n 19 find /bigdata/pietro/processing/Umbra/radargrammetry -maxdepth 3 \
  \( -name '*.stac.v2.json' -o -name '*_MM.tif' -o -name '*_SICD_MM.nitf' \) > data/inventory.txt
```

**2. Parse every sidecar into one catalogue.** Threaded, because NFS here is
latency-bound: serial ran at about one file per second, 24 threads at sixty-odd.

```bash
nice -n 19 $P scripts/build_catalogue.py data/inventory.txt data/catalogue.json
```

**3. Re-run the geometry validation.** Do this after any archive change — it is
what licenses the tool to claim the angles are right.

```bash
nice -n 19 $P scripts/validate_geometry.py data/catalogue.json 40 data/catalogue_derived.json
nice -n 19 $P scripts/final_check.py data/catalogue.json
nice -n 19 $P scripts/sicd_check.py data/catalogue.json     # needs a local SICD NITF
```

Expect `heading = look_dir − engineering_squint` to agree with
`sat:orbit_state` on 100% of scenes carrying it. If that number drops, the
convention has changed upstream and the tool is wrong until it is re-solved with
`scripts/solve_convention.py`.

**4. Choose the teaching set.** Slots are a curriculum, not statistical
extremes — a same-target ascending/descending pair, broadside, heavy forward and
aft squint, incidence extremes, a left-looking scene, relief and urban layover.

```bash
nice -n 19 $P scripts/pick_scenes.py data/catalogue.json data/picks.json
```

**5. Render.** About one to three minutes per scene depending on NFS load.
Fetches Esri World Imagery tiles for the optical pane; pass `--no-optical` to
skip the network entirely.

```bash
nice -n 19 $P scripts/make_quicklooks.py \
  --catalogue data/catalogue.json --picks data/picks.json --out tool/ql
```

**6. Build the page.**

```bash
nice -n 19 $P scripts/export_tool_data.py \
  --catalogue data/catalogue.json --ql tool/ql --out tool/build
$P scripts/build_tool.py --template tool/tool_template.html \
  --scenes tool/build/scenes_tool.json --out tool/look-angle.html
$P scripts/jscheck.py tool/look-angle.html
```

**7. Attach the measured terrain response.** Look Angle's layover question has a
threshold — layover needs a slope steeper than the incidence angle — so the page
carries the measured number per scene rather than implying the fold is always
there. Needs COP30 covering each scene; `data/dem/all_tiles.vrt` mosaics whatever
has been fetched, for scenes that straddle a tile edge (Fogo does).

```bash
nice -n 19 $P /tmp/la_terrain.py            # writes build/lookangle_terrain.json
$P scripts/add_terrain_to_lookangle.py \
    --scenes tool/scenes_tool.json --terrain build/lookangle_terrain.json
```

The page references its imagery as `img/*.webp` relative to itself, so
`tool/build/` publishes or serves as a unit.

## Adding a question type

Question types live in `QUESTIONS` in `scripts/export_tool_data.py`. Each names
an answer key that must exist in the `answers` dict alongside it, and the page
grades by angular difference, so any new question whose answer is an azimuth
needs no page changes beyond a feedback branch in `grade()`.

## Constraints this respects

- Read-only on `/bigdata`; nothing touches the systemd units or the ordering
  timers.
- `sar_vault.db` is not consulted for geometry — its `squint_angle_deg` and
  `incidence_angle_deg` columns are empty, consistent with RULES.md R1.
- Scene choice prefers bare terrain, because RULES.md R10/R11 record that
  vegetated tropical volcanoes decorrelate badly at X-band.
