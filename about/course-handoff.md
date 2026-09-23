# Handoff to the CIVE 6359 course-design session

**What this is.** Two finished, verified interactive exercises on SAR acquisition
geometry and geometric distortion, live at
<https://pietromilillo.github.io/sar-geometry-learning/>. Everything is public and
static — no VPN, no login, no install, and no rsde-02 access needed to use or
link to them.

**How to treat this.** This is *evidence for G1*, not finished student-facing
material. The exercises exist and work; whether and how they enter a lecture
package is Pietro's call at the gates. What follows is what you need to write
objectives against them without re-deriving anything.

---

## 1. Where they fit the calendar

| # | Date | Session | Fit |
|---|---|---|---|
| 9 | Tue Sep 22 | SAR modes, geometry, geocoding | **Look Angle** is this content |
| 10 | Thu Sep 24 | **Lab 2** — geocoding, terrain correction, layover/shadow | **Where the Summit Lands** is this content, exactly |
| 15 | Tue Oct 13 | Structured review — two-stage practice problems | both, as retrieval practice |
| 16 | Thu Oct 15 | MIDTERM (covers W1–7) | both are in scope |
| 25 | Tue Nov 17 | APPL: Topography II — bistatic InSAR & radargrammetry | the archive behind these feeds a planned third exercise |

Sessions 9 and 10 have effectively arrived, so for Fall 2026 these land as lab
support and review material rather than as pre-class media.

---

## 2. What a student can actually do afterwards

Written at Bloom levels, phrased so they are measurable. Take, reject or rewrite.

**Exercise 1 — Look Angle** (11 scenes, ~20 min)

1. *Apply.* Given a scene's metadata, determine the ground-track heading and the
   ground-projected line of sight, and mark both on the image.
2. *Analyse.* Distinguish a squinted acquisition from a broadside one and explain
   what breaks if you assume the radar looks perpendicular to the track.
3. *Evaluate.* Given the three squint fields a sidecar reports, select the one
   that is safe to drive a heading from, and justify the choice.

**Exercise 2 — Where the Summit Lands** (20 acquisitions, ~35 min)

4. *Understand.* Explain why a geocoded SAR product is not a map, in terms of the
   height the geocoder assumed.
5. *Apply.* Predict the map displacement of a point of known elevation, and check
   it against the tool.
6. *Analyse.* Given an acquisition and a slope, predict whether it lays over,
   falls in shadow, or neither, and say which threshold decides it.
7. *Evaluate.* Compare one volcano across five look angles and account for why
   layover and shadow trade places.

---

## 3. The physics, in one line

```
r = g·sinθ − h·cosθ            slant range of a point at ground range g, height h
r = g′·sinθ − h_ref·cosθ       what the geocoder solves, assuming one height
⇒  displacement = −(h − h_ref) · cot θ
```

Layover when slope > θ. Shadow when back-slope > (90° − θ). Everything both
exercises teach follows from these three lines.

---

## 4. Numbers you can quote in class

These are measured from the archive, not illustrative.

**The ellipsoid assumption is visible in the metadata.** Every scene's footprint
polygon carries one elevation for all four corners, agreeing to within **7 mm**
across all **1,157** scenes. Fuego alone uses seven different reference planes
(3161–3782 m), and its 17.5° acquisition assumes 3781.8 m — *above* the 3763 m
summit, so the whole volcano sits below its own reference plane.

**One volcano, five acquisitions.** Fuego:

| incidence | cot θ | peak displacement | layover | shadow |
|---|---|---|---|---|
| 17.5° | 3.17 | **8154 m** | 21.9% | 0.0% |
| 22.9° | 2.36 | 5620 m | 25.6% | 0.0% |
| 34.6° | 1.45 | 3096 m | 4.4% | 0.1% |
| 56.7° | 0.66 | 1341 m | 0.1% | 10.2% |
| 67.3° | 0.42 | 844 m | 0.1% | 37.9% |

A ten-fold swing in displacement, with layover and shadow trading places — same
mountain, different look angle. This is the single best in-class discussion
object in the set.

**A tasking gap worth teaching.** Nevado del Ruiz has no acquisition below 48°
anywhere in the archive, so it shows shadow but never layover. That is a property
of how it was tasked, not of the mountain — its mean slope is 17.8°, so a
steeper-looking pass *would* lay over. The tool says so explicitly and borrows a
matched-relief Gamalama scene for contrast.

---

## 5. Assessment hooks

Items that can be written straight off the tools, with unambiguous keys:

- **Numeric.** "A point sits 600 m above the reference plane, incidence 30°. How
  far, and which way, does the GEC product move it?" → 1039 m toward the sensor.
  Variant pool: vary height and incidence; the key is `−(h−h_ref)·cot θ`.
- **Threshold.** "Slope 35° facing the radar, incidence 28°. Layover or not?" →
  yes, 35 > 28. Vary both; half the pool should be *no*.
- **Discrimination.** Give the three squint values from one sidecar and ask which
  yields the heading. Tests a real confusion, not recall.
- **Interpretation.** Show two Fuego scenes side by side and ask why one is full
  of shadow and the other full of layover.
- **Misconception probe.** "Nevado del Ruiz shows almost no layover. Is it too
  gentle to lay over?" → no; nothing steep enough was ever tasked.

The layover question in Exercise 1 is deliberately precise: displacement happens
at *every* slope, but true layover needs slope > incidence, and both layover
scenes sit near 45° where the terrain rarely qualifies (Bezymianny 1.69%,
Manizales 0.26%). In the city the *buildings* lay over — a wall is vertical, and
90° beats any incidence — but COP30 is 30 m and cannot see them. That distinction
is worth a RAT item on its own.

---

## 6. What is verified, so you can cite it without hedging

| Claim | How checked | Result |
|---|---|---|
| Heading derivation | vs `sat:orbit_state` | **1142/1142 = 100.00%** |
| Heading derivation | vs each GEC raster's geotransform rotation | median **0.086°** |
| Heading derivation | vs true SICD ARP velocity vectors | **0.14–0.30°** |
| Displacement model | closed form, 6 look directions × 3 incidences | **2–15 m** error on 462–1716 m |
| Layover threshold | synthetic 40° ramp | 100% below slope, 0% above |
| Simulation vs reality | predicted shadow, 19 scenes | **0.51×** lit brightness |
| Simulation vs reality | predicted layover, 7 scenes | **1.44×** brighter |

The simulation uses no radar data — only topography and the sidecar — so the last
two rows are genuine out-of-sample confirmation.

---

## 7. Caveats to state in class

- COP30 is 30 m, so the simulation resolves nothing finer than ~60 m. It is a
  **geometry model, not a backscatter model** — it predicts where energy lands,
  not how bright it is.
- The amplitude imagery is X-band over partly vegetated volcanoes. Speckle and
  vegetation decorrelation are real and visible; they are not errors in the tool.
- Layover and shadow masks are computed from terrain only. Buildings, canopy and
  anything younger than COP30 are invisible to the model.

---

## 8. Provenance

Built 16–23 September 2026 from the Umbra archive on rsde-02
(`/bigdata/pietro/processing/Umbra/radargrammetry`, 1,211 GeoTIFFs, 1,157 STAC
sidecars, 230 targets), read-only. Topography from Copernicus GLO-30. Optical
basemap from Esri World Imagery.

Source, pipeline and tests: <https://github.com/PietroMilillo/sar-geometry-learning>
Metadata fields used, and the traps found: [`metadata-hooks.md`](metadata-hooks.md)

Two findings from this work were logged as rules in the SAR Vault rule diary on
rsde-02 (R41 on the squint conventions, R42 on a broken COP30 URL in the
planner), and one bug was fixed in
`umbra_radargrammetry_planner.py`. Those are engineering notes, not course
material, but they are why the numbers above can be stated without hedging.
