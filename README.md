# SAR Geometry — interactive exercises

Two browser-based exercises on synthetic aperture radar acquisition geometry and
geometric distortion, built on real Umbra X-band scenes and Copernicus GLO-30
topography. Written for **CIVE 6359, SAR Remote Sensing**, University of Houston.

**Live: https://pietromilillo.github.io/sar-geometry-learning/**

No login, no install, no VPN. Static HTML and images — there is no server behind
these pages, and nothing a student draws or clicks is recorded or transmitted.

| | |
|---|---|
| **[Look Angle](look-angle/)** | 11 scenes. Draw the flight direction, the line of sight, or the direction relief is displaced; you are marked against that scene's own STAC sidecar. |
| **[Where the Summit Lands](where-the-summit-lands/)** | 20 acquisitions, 7 pixel-registered layers each. Why a geocoded SAR product is not a map, and what that costs in metres. |

## The point

A radar measures time, which gives slant range. For a point at ground range `g`
and height `h` seen at incidence `θ`:

```
r = g·sinθ − h·cosθ
```

Height shortens the range. To turn range back into a map position the processor
must assume a height, and a GEC product assumes **one constant value for the
whole scene**. Subtract the two and the error falls out:

```
displacement = −(h − h_ref) · cot θ
```

That single line generates layover, shadow, foreshortening, and the entire
reason terrain correction exists. On Fuego's 17.5° acquisition it reaches
**8.2 km**.

You can see the assumption in the metadata: every scene's footprint polygon
carries **one elevation for all four corners**, agreeing to within 7 mm across
all 1,157 scenes in the archive this was built from. Fuego alone uses seven
different reference planes, and its 17.5° scene sits at 3781.8 m — *above* the
3763 m summit, so the whole volcano is below its own reference plane.

## What is verified, and how

Nothing in these exercises rests on an assumed convention.

**The look geometry.** The heading is derived as
`view:azimuth − 180 − umbra:squint_angle_engineering_degrees`. That form was
solved by brute force over all four sign conventions, then checked three
independent ways:

| Check | Result |
|---|---|
| vs `sat:orbit_state`, every scene carrying it | **1142/1142 = 100.00%** |
| vs the rotation in each GEC raster's geotransform (40 scenes) | median **0.086°** |
| vs the true ARP velocity vector in the SICD state vectors | **0.14–0.30°** |

**The simulation.** `scripts/sar_simulate.py` run directly is its own test
suite: displacement against the closed form across six look directions and three
incidence angles (**2–15 m error on 462–1716 m displacements**), the layover
threshold (100% below slope, 0% above), the shadow threshold, and two null
cases.

**Against the real imagery.** The simulation uses no radar data at all — only
topography and the sidecar — yet predicted-shadow regions come out at **0.51×**
the brightness of lit terrain across 19 scenes, and predicted-layover at
**1.44×** brighter.

## Repository layout

```
index.html                    landing page
look-angle/                   exercise 1 — page + 44 images
where-the-summit-lands/       exercise 2 — page + 152 images
about/metadata-hooks.md       every metadata field used, and the traps
scripts/                      the data-preparation pipeline (read-only on the archive)
```

The pipeline is not needed to *run* the exercises — they ship pre-rendered. It is
here so the exercises can be rebuilt, extended, or pointed at a different
archive.

## Running locally

Browsers block `canvas.getImageData` on `file://`, and exercise 2 needs it to
read terrain heights when you click the image. So serve the folder rather than
opening the file directly:

```bash
git clone https://github.com/PietroMilillo/sar-geometry-learning.git
cd sar-geometry-learning
python3 -m http.server 8000
```

Then open <http://localhost:8000/>. Exercise 1 works fine from `file://`.

## Data and licence

Amplitude imagery is Umbra X-band spotlight, geocoded ellipsoid corrected,
shipped here as downsampled WebP quicklooks — no raw products, no metadata
sidecars, no credentials.

Topography is Copernicus GLO-30, © DLR e.V. 2010–2014 and © Airbus Defence and
Space GmbH 2014–2018, provided under the Copernicus DEM licence. Optical basemap
is Esri World Imagery.

Course material (pages, text, figures) is released under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the code under the
MIT licence (see `LICENSE`). Imagery remains subject to its providers' terms.

## Citing

If you use these in teaching, please cite the repository. A DOI will be minted
on first release via Zenodo.

---

Pietro Milillo, Department of Civil and Environmental Engineering, University of
Houston — <https://milillo.cive.uh.edu>
