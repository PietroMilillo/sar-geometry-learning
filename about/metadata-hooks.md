# SAR geometry teaching tool — metadata hooks

Everything the tool draws traces back to one of the fields below. Nothing is
hard-coded and nothing is inferred from a filename. Written 2026-09-16.

## 1. The authoritative source

`<TARGET>/**/<datetime>_<SAT>.stac.v2.json` — the Umbra STAC v2 sidecar.
Found by recursive glob, **not** by assuming `<TARGET>/data/`: scenes fetched by
`sar_vault.py download` land in `<TARGET>/<date>_<ORBIT>_<SAT>_UNK/` instead.
As of 2026-09-16 that is 3 scenes under `EEFIT_Sevilla` out of 1,211, but the
split will grow, so glob both.

Counts on 2026-09-16: **1,211 `_MM.tif`, 1,157 sidecars, 230 targets**,
4 `_SICD_MM.nitf`, 0 `_SICD_MM.xml`.

### Fields read from `properties`

| Field | Used for | Populated |
|---|---|---|
| `view:azimuth` | line of sight; layover direction | 1157/1157 |
| `view:incidence_angle` | incidence; layover threshold; 3D elevation | 1157/1157 |
| `umbra:grazing_angle_degrees` | shadow threshold | 1157/1157 |
| `umbra:squint_angle_engineering_degrees` | **the heading derivation** | 1157/1157 |
| `umbra:squint_angle_exploitation_degrees` | signed squint shown to the student | 1157/1157 |
| `umbra:squint_angle_degrees_off_broadside` | unsigned squint shown to the student | 1157/1157 |
| `sar:observation_direction` | look side; broadside sign | 1157/1157 |
| `sat:orbit_state` | validation of the heading, and the scene label | 1142/1157 |
| `platform` | label | 1157/1157 |
| `datetime` | label; de-duplicating near-identical collects | 1157/1157 |
| `umbra:slant_range_meters` | readout | 1157/1157 |
| `sar:instrument_mode`, `sar:product_type` | readout | 1157/1157 |
| `sar:frequency_band` | readout | 1157/1157 |
| `sar:center_frequency` | readout | **607/1157 — often absent** |
| `sar:resolution_azimuth`, `sar:resolution_range` | readout | 1157/1157 |
| `sar:looks_azimuth`, `sar:looks_range` | readout | 1157/1157 |
| `sar:polarizations` | readout | 1157/1157 |
| `umbra:collect_id` | joining back to the archive | 1157/1157 |

### Fields read from the top level

| Field | Used for |
|---|---|
| `bbox` | scene centre, local projection origin, basemap tile fetch |
| `geometry` | footprint (available for a footprint overlay; not drawn yet) |
| `assets` | locating the SICD hrefs when they are not on disk |

## 2. The GeoTIFF itself

| Hook | Used for |
|---|---|
| affine geotransform (**rotated**) | independent check on the look direction |
| internal overviews (16000 → 500) | fast decimated reads; do not re-derive |
| `nodata = 0` | alpha mask so the footprint shows its true diamond shape |

Umbra GEC rasters are **not north-up**. The grid is rotated so that +y (down the
image) runs along the ground-range look direction. Measured across 40 random
scenes, the azimuth of the +y axis matches `view:azimuth − 180` to a median of
**0.086°** (max 0.19°). The tool therefore warps every scene to a local
transverse Mercator centred on it, which gives north-up and equal metres per
pixel — that is what lets a drawn screen vector convert straight to an azimuth
via `az = atan2(dx, −dy)`.

## 3. The SICD, where it exists locally

Only in the `_UNK` directories. The XML lives in a NITF DES segment; the file
header gives the offset so there is no need to scan 400 MB.

| Hook | Used for |
|---|---|
| `SCPCOA/ARPPos {X,Y,Z}` | sub-satellite point |
| `SCPCOA/ARPVel {X,Y,Z}` | **true** ground-track heading, as a cross-check |
| `SCPCOA/AzimAng` | confirms it is the same number as `view:azimuth` |
| `SCPCOA/GrazeAng` | confirms `umbra:grazing_angle_degrees` |
| `SCPCOA/SideOfTrack` | confirms `sar:observation_direction` |

## 4. Derived geometry

```
look_dir  = view:azimuth − 180                  # ground-projected LOS, sensor → target
heading   = look_dir − squint_engineering       # ground-track direction of flight
broadside = heading + s·90                      # s = +1 right-looking, −1 left
layover_dir = view:azimuth                      # displacement is TOWARD the sensor
layover  when  slope > incidence
shadow   when  back-slope > grazing  (= 90 − incidence)
```

`view:azimuth` is the azimuth **target → sensor** (where the satellite sits in
the target's sky), not sensor → target. Confirmed two ways: it equals SICD
`AzimAng`, and `view:azimuth − 180` reproduces the raster rotation.

### How the heading formula was established

Brute-forced over all four sign conventions rather than assumed:

| Check | Result |
|---|---|
| vs `sat:orbit_state`, all scenes carrying it | **1142/1142 = 100.00%** |
| vs raster geotransform rotation (40 scenes) | median **0.086°** |
| vs SICD ARP velocity vector (3 scenes) | **0.14–0.30°** |

Derived ground tracks cluster at 348.2° ascending and 190.5° descending with
circular concentration R = 0.99 — the shape of a real near-polar orbit.

## 5. Traps — things that look usable and are not

- **`sar_vault.db` `scenes.squint_angle_deg` / `incidence_angle_deg` are empty**
  (0 rows populated). The sidecars are the only geometry source. This matches
  RULES.md R1: that database is authoritative only for `scenes` and `targets`.
- **`engineering = 90 + exploitation` is false on 20% of the archive.** It holds
  on right-looking scenes only; left-looking negates the whole scale, so the
  general form is `engineering = s·90 + exploitation`. Twelve scenes near
  |squint| = 45° (Reykjanes, Kilauea) break even that. **Drive the heading off
  the engineering squint directly** — `heading = look_dir − engineering` is the
  one form that holds everywhere, on both look sides, including those twelve.
- **`sat:orbit_state` is absent on 15 scenes.** Do not key anything on it; it is
  a validation signal here, not an input.
- **`sar:center_frequency` is absent on 550 scenes.** Render it conditionally.
- **A bare `stem` lookup resolves to the wrong target on 166 of 963 scenes.**
  The same collect is filed under more than one target directory. Some are the
  RULES.md R12 name duplicates (`El Chichon` / `El_Chichon`), but many are
  genuinely *different neighbouring volcanoes* whose footprints overlap:
  `Fuego | Pacaya_2026-05`, `Sibayak | Sinabung`, `Bardarbunga | Grimsvotn`,
  `Ijen | Raung`, `EEFIT_Manizales | Nevado_del_Ruiz`. Key every lookup on
  `(dir, stem)`, never on `stem` alone. The geometry is identical either way -
  it is the target label that goes wrong, silently.
- **Never judge a scene by file size** (RULES.md R4) — all of these are ~70 MB
  regardless of how much of the footprint carries signal.

## 6. Where the terrain hooks would plug in

Layover and shadow are currently taught on a synthetic profile in the explorer,
because doing it on the real imagery needs a DEM in the same grid. The pieces
are already on disk:

- `<TARGET>/dem_cache/cop30_*.tif` — cached COP30, present for 132 targets.
- `download_cop30_tiles` and `compute_slope_aspect` in
  `/home/pmilillo/UmbraRadarGrammetryPlanner/umbra_radargrammetry_planner.py`.

To extend: warp the COP30 tile onto the same local transverse Mercator grid the
quicklook already uses (`local_crs` is recorded per scene in `scenes.json`),
compute slope and aspect, then mask `slope > incidence` for layover and
`slope_away > grazing` for shadow, using the scene's own `look_dir` as the
illumination azimuth. Both masks are then in the same pixel space as the SAR
quicklook and can be drawn straight onto the stage as overlays.

## 7. Scripts

| File | Does |
|---|---|
| `build_catalogue.py` | parses every sidecar into `catalogue.json` (threaded — NFS here is latency-bound; serial ran at ~1 file/s, 24 threads at ~66/s) |
| `geometry.py` | the conventions, in one place |
| `validate_geometry.py` | the four tests above |
| `solve_convention.py` | brute-forces the squint sign convention |
| `sicd_check.py` | pulls ARP state vectors out of the SICD NITF |
| `pick_scenes.py` | selects the teaching set as a curriculum |
| `make_quicklooks.py` | north-up quicklooks, multi-looked detail crops, matched optical |
| `export_tool_data.py` | merges geometry + imagery into the tool payload, converts to WebP |
| `build_tool.py` | assembles the final HTML |
| `jscheck.py` | balance check for the page's JavaScript |

All read-only with respect to `/bigdata`, all `nice -n 19`.

Optical imagery is Esri World Imagery, fetched as map tiles over each scene's
footprint and warped onto the SAR grid. Egress from rsde-02 was confirmed before
relying on it. Roughly 250 tiles were fetched in total and cached under
`_tilecache`.

## 8. Hooks the distortion exercise adds

### The geocoding reference height — the field the whole exercise turns on

`geometry.coordinates[0][*][2]` — the **elevation carried by the footprint
polygon**, top level of the sidecar, not in `properties`.

All four corners of every footprint share one elevation to within **7 mm**,
across all 1,157 scenes. That constant is the height the GEC geocoding assumed
for the entire scene. It is the only place in the metadata where the reference
plane is recorded, and nothing in `properties` duplicates it.

Scenes over the same target routinely use **different** reference planes:

| Target | reference heights in use |
|---|---|
| Fuego | 3161, 3211, 3291, 3436, 3455, 3499, 3782 m |
| Nevado del Ruiz (volcano cluster) | 5236 m |
| Gamalama | 1471 m |
| EEFIT Quimbaya | 1362 m |

Fuego's 17.5° scene has `h_ref` = 3781.8 m, which is **above** the 3763 m
summit, so the whole volcano sits below its own reference plane.

### Derived, and what it produces

```
displacement = -(h - h_ref) * cot(incidence)      along look_dir, metres
layover      when slope facing the radar   > incidence
shadow       when slope facing away        > grazing (= 90 - incidence)
hillshade    azimuth = view:azimuth, altitude = umbra:grazing_angle_degrees
```

`hillshade` deliberately takes `view:azimuth` **unmodified** (not `look_dir`),
because a hillshade is lit *from* the light source, and `view:azimuth` already
points from the ground toward the sensor.

### Terrain

| Hook | Used for |
|---|---|
| `<TARGET>/dem_cache/cop30_*.tif` | COP30, already cached for 132 targets. **UTM metres**, not degrees — reproject the scene bbox before testing containment. |
| `data/dem/Copernicus_DSM_COG_10_*.tif` | tiles fetched for targets with no cache (EEFIT Quimbaya) |

COP30 is 30 m, so the simulation resolves nothing finer than ~60 m. It is a
geometry model, not a backscatter model.

**The Copernicus naming trap:** `COG_10` is GLO-30 (1 arcsec, 30 m); `COG_30` is
GLO-90. The `copernicus-dem-30m` bucket holds only GLO-30. See RULES.md R42 —
the planner asked for `COG_30` and silently got nothing for every target.

### Another trap: a target directory can hold several different places

`Nevado_del_Ruiz` contains three distinct footprint clusters — the volcano
(4.890 N, h_ref 5236 m), Manizales (5.056 N, h_ref 1978/2266 m) and Armenia
(4.522 N, h_ref 1427 m). Selecting by directory name alone mixes a volcano with
two cities. `pick_distortion_set.py` clusters by footprint centre and keeps the
cluster sitting highest above the ellipsoid.

And `Pacaya_2026-05` is not Pacaya: all 9 of its scenes are also filed under
Fuego (zero unique) and its footprints are centred at Fuego's coordinates
(14.471 N, 90.881 W), not Pacaya's (14.381 N, 90.601 W).

### Scripts added

| File | Does |
|---|---|
| `sar_simulate.py` | the simulation core, with a self-test that checks displacement against the closed form, both distortion thresholds, and two null cases |
| `pick_distortion_set.py` | chooses contrasting geometries per target, clustering by footprint location |
| `make_distortion_products.py` | renders all seven registered layers per scene |
| `make_demdata.py` | ships each scene's DEM heights to the browser as a 16-bit PNG (R = high byte, G = low byte, B = validity) so the page can answer "where does this point land?" for any pixel |
| `validate_simulation.py` | tests the predicted shadow against real amplitude darkness |
| `make_export.sh` | builds the standalone, copyable bundle |
