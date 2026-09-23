#!/usr/bin/env python
"""Simulate what a SAR sees over real terrain, and where a GEC product puts it.

THE POINT OF THIS MODULE
------------------------
An Umbra GEC product is "Geocoded Ellipsoid Corrected": every pixel is placed on
the map as if the ground were a single constant-height surface. It is measurable
in the data - every scene's footprint polygon carries ONE elevation for all four
corners, to within 7 mm, and different scenes over the same volcano use different
reference heights.

So the map position of a pixel is wrong by an amount that depends only on how far
the real terrain sits from that reference plane:

    slant range of a real point   r  = g*sin(theta) - h*cos(theta)
    GEC solves for g' assuming h = h_ref:
                                  r  = g'*sin(theta) - h_ref*cos(theta)
    =>  g' - g = -(h - h_ref) / tan(theta)

    DISPLACEMENT = -(h - h_ref) * cot(theta), along the ground-range direction.

Ground above the reference plane moves TOWARD the sensor; ground below moves
away. At Fuego's 17 deg incidence, cot = 3.27, so a summit 1200 m above the
reference plane lands almost 4 km from where it belongs. That is not a rounding
error, it is the whole reason orthorectification exists.

CONVENTIONS
-----------
look_dir : azimuth of the ground-projected line of sight, SENSOR -> TARGET,
           degrees from north. The sensor therefore lies at look_dir + 180.
inc      : incidence angle from vertical, degrees.
h_ref    : the GEC reference height, read from the scene's footprint polygon.
Arrays are north-up with equal metres per pixel (col = east, row = south).
"""
import math
import numpy as np
from scipy import ndimage

D2R = math.pi / 180.0


# --------------------------------------------------------------------------
# frame handling
# --------------------------------------------------------------------------
# A north-up array has col -> east, row -> south. A vector at azimuth A has
# components (east, north) = (sin A, cos A), i.e. (col, row) = (sin A, -cos A).
# ndimage.rotate(a, ang) rotates the CONTENT of the array; the sign that brings
# the look direction onto +col is pinned by the self-test at the bottom of this
# file, which fails loudly if scipy ever changes it.
ROTATE_SIGN = -1.0


def _rot_angle(look_dir_deg):
    """Degrees to pass to ndimage.rotate so that +col becomes the ground-range
    direction (pointing away from the sensor)."""
    return ROTATE_SIGN * (90.0 - look_dir_deg)


def to_range_frame(a, look_dir_deg, cval=np.nan):
    return ndimage.rotate(a, _rot_angle(look_dir_deg), reshape=True, order=1,
                          mode="constant", cval=cval, prefilter=False)


def from_range_frame(a, look_dir_deg, out_shape, cval=np.nan):
    b = ndimage.rotate(a, -_rot_angle(look_dir_deg), reshape=True, order=1,
                       mode="constant", cval=cval, prefilter=False)
    # centre-crop (or pad) back to the original grid
    oh, ow = out_shape
    bh, bw = b.shape
    top, left = (bh - oh) // 2, (bw - ow) // 2
    if top >= 0 and left >= 0:
        return b[top:top + oh, left:left + ow]
    out = np.full(out_shape, cval, dtype=b.dtype)
    t2, l2 = max(0, -top), max(0, -left)
    out[t2:t2 + bh, l2:l2 + bw] = b[:oh, :ow]
    return out


# --------------------------------------------------------------------------
# the physics
# --------------------------------------------------------------------------
def displacement_map(dem, inc_deg, h_ref):
    """Signed ground-range displacement in metres, on the map grid.

    Negative = moved toward the sensor (terrain above the reference plane).
    This is the single number the whole ellipsoid lesson rests on.
    """
    cot = 1.0 / math.tan(max(inc_deg, 0.5) * D2R)
    return -(dem - h_ref) * cot


def simulate(dem, px_m, look_dir_deg, inc_deg, h_ref):
    """Run the full slant-range simulation.

    Returns a dict of arrays on the SAME north-up grid as `dem`:
      sim        simulated GEC amplitude (contributions per output cell)
      layover    terrain that images backwards (range-slope steeper than inc)
      shadow     terrain the radar cannot see at all
      passive    lit, ordered terrain (neither layover nor shadow)
      disp_m     signed ground-range displacement, metres
      disp_px    the same in pixels
    """
    h, w = dem.shape
    inc = max(float(inc_deg), 0.5) * D2R
    st, ct = math.sin(inc), math.cos(inc)
    cot = ct / st

    R = to_range_frame(dem, look_dir_deg)
    valid = np.isfinite(R)
    Rf = np.where(valid, R, 0.0)
    rh, rw = R.shape

    g = np.arange(rw, dtype=np.float64) * px_m           # ground range coord
    gg = np.broadcast_to(g, (rh, rw))

    # --- occlusion: the ray through (g,h) crosses g=0 at height h + g*cot.
    #     A cell is shadowed when an earlier cell's ray passes above it.
    t = Rf + gg * cot
    t_masked = np.where(valid, t, -np.inf)
    horizon = np.maximum.accumulate(t_masked, axis=1)
    prev = np.concatenate([np.full((rh, 1), -np.inf), horizon[:, :-1]], axis=1)
    shadow_r = valid & (t_masked < prev - 1e-9)

    # --- layover: range decreases with ground range, i.e. slope toward the
    #     sensor steeper than the incidence angle.
    dr_dg = st - np.gradient(Rf, px_m, axis=1) * ct
    layover_r = valid & (dr_dg < 0.0)

    # --- where each terrain cell LANDS in the GEC product
    gprime = gg - (Rf - h_ref) * cot
    col = np.rint(gprime / px_m).astype(np.int64)
    ok = valid & ~shadow_r & (col >= 0) & (col < rw)

    rows = np.broadcast_to(np.arange(rh)[:, None], (rh, rw))
    sim_r = np.zeros((rh, rw), dtype=np.float32)
    lay_r = np.zeros((rh, rw), dtype=np.float32)
    np.add.at(sim_r, (rows[ok], col[ok]), 1.0)
    np.add.at(lay_r, (rows[ok & layover_r], col[ok & layover_r]), 1.0)

    # a cell nothing reaches, inside the swath, is shadow in the product
    any_valid_row = valid.any(axis=1)
    sh_r = (sim_r == 0) & any_valid_row[:, None]

    out_shape = (h, w)
    sim = from_range_frame(sim_r, look_dir_deg, out_shape, cval=0.0)
    lay = from_range_frame(lay_r, look_dir_deg, out_shape, cval=0.0)
    shp = from_range_frame(sh_r.astype(np.float32), look_dir_deg, out_shape, cval=0.0)
    # masks in MAP space too, for drawing over the DEM
    lay_map = from_range_frame(layover_r.astype(np.float32), look_dir_deg, out_shape, cval=0.0)
    shd_map = from_range_frame(shadow_r.astype(np.float32), look_dir_deg, out_shape, cval=0.0)

    disp = displacement_map(dem, inc_deg, h_ref)
    return {
        "sim": sim, "layover": lay > 0.5, "shadow": shp > 0.5,
        "layover_map": lay_map > 0.5, "shadow_map": shd_map > 0.5,
        "disp_m": disp, "disp_px": disp / px_m,
    }


def hillshade(dem, px_m, azimuth_deg, altitude_deg, z_factor=1.0):
    """Hillshade lit from `azimuth_deg` at `altitude_deg` above the horizon.

    For a SAR scene pass azimuth = view:azimuth (the direction the sensor lies
    in, as seen from the target) and altitude = the grazing angle. The result is
    then lit exactly the way the radar illuminates the ground, which is what
    makes it comparable with the amplitude image.
    """
    dem = np.where(np.isfinite(dem), dem, np.nanmean(dem[np.isfinite(dem)]) if np.isfinite(dem).any() else 0.0)
    dy, dx = np.gradient(dem * z_factor, px_m)
    slope = np.arctan(np.hypot(dx, dy))
    aspect = np.arctan2(-dx, dy)                  # radians, 0 = north, CW
    az = (360.0 - azimuth_deg + 90.0) * D2R
    alt = altitude_deg * D2R
    hs = (np.sin(alt) * np.cos(slope)
          + np.cos(alt) * np.sin(slope) * np.cos(az - (np.pi/2 - aspect)))
    return np.clip(hs, 0.0, 1.0)


# --------------------------------------------------------------------------
# self-test: the simulation must reproduce the closed form it is built on
# --------------------------------------------------------------------------
def _pillar(n, px, height, half_m):
    """Flat ground with one flat-topped pillar. On flat ground at h_ref the
    background does not move at all, so every output cell gets exactly one
    contribution - which makes the pillar's displaced energy trivially
    separable, with no layover caustic to confuse the measurement."""
    c = (n - 1) / 2.0
    y, x = np.mgrid[0:n, 0:n].astype(np.float64)
    dx, dy = (x - c) * px, (y - c) * px
    dem = np.zeros((n, n))
    dem[(np.abs(dx) <= half_m) & (np.abs(dy) <= half_m)] = height
    return dem


def _self_test(verbose=True):
    """An isolated pillar on flat ground, h_ref = 0.

    Its echo must land exactly h*cot(theta) from its true position, in the
    direction of the SENSOR (look_dir + 180). Because the background sits at the
    reference height it contributes exactly one count per cell, so the pillar's
    piled-up contributions stand out as sim >= 2 and their centroid is an
    unambiguous measurement of the displacement.
    """
    n, px, H, half = 401, 20.0, 800.0, 120.0
    dem = _pillar(n, px, H, half)
    c = (n - 1) / 2.0
    fails = []
    for look_dir in (0.0, 45.0, 90.0, 180.0, 235.0, 300.0):
        for inc in (25.0, 40.0, 60.0):
            out = simulate(dem, px, look_dir, inc, h_ref=0.0)
            sim = out["sim"]
            pile = sim >= 2.0
            if not pile.any():
                fails.append((look_dir, inc, "no piled-up cells")); continue
            yy, xx = np.nonzero(pile)
            wgt = sim[pile]
            cx_, cy_ = (xx * wgt).sum() / wgt.sum(), (yy * wgt).sum() / wgt.sum()
            dx_px, dy_px = cx_ - c, cy_ - c
            exp_m = H / math.tan(inc * D2R)
            a = (look_dir + 180.0) * D2R
            ex_px = math.sin(a) * exp_m / px
            ey_px = -math.cos(a) * exp_m / px
            err = math.hypot(dx_px - ex_px, dy_px - ey_px) * px
            tol = max(2.5 * px, 0.06 * exp_m)
            if err >= tol:
                fails.append((look_dir, inc, "err %.0f m > tol %.0f m" % (err, tol)))
            if verbose:
                print("   look %5.0f  inc %4.0f  expect %7.0f m  measured (%+6.1f,%+6.1f) px"
                      "  vs (%+6.1f,%+6.1f)  err %5.0f m  %s"
                      % (look_dir, inc, exp_m, dx_px, dy_px, ex_px, ey_px, err,
                         "ok " if err < tol else "FAIL"))
    # flat ground: no distortion of any kind
    flat = np.zeros((201, 201))
    o = simulate(flat, px, 123.0, 35.0, h_ref=0.0)
    if o["layover_map"].any(): fails.append(("flat", "-", "layover on flat ground"))
    if o["shadow_map"].any():  fails.append(("flat", "-", "shadow on flat ground"))
    if np.nanmax(np.abs(o["disp_m"])) > 1e-9:
        fails.append(("flat", "-", "displacement on flat ground"))
    # terrain AT the reference height must not move
    o2 = simulate(dem, px, 200.0, 30.0, h_ref=H)
    top = dem >= H - 1e-6
    if np.nanmax(np.abs(o2["disp_m"][top])) > 1e-6:
        fails.append(("h=h_ref", "-", "top moved although it sits at the reference height"))
    # Layover must switch on exactly when the slope facing the radar beats the
    # incidence angle - the single rule the whole exercise turns on. A uniform
    # 40 deg ramp rising toward the sensor should lay over below 40 deg
    # incidence and not above it.
    slope_deg = 40.0
    rise = (200 * px) * math.tan(slope_deg * D2R)
    ramp = np.tile(np.linspace(0.0, rise, 201), (201, 1))   # rises toward +east
    inner = (slice(50, -50), slice(50, -50))
    # The NEAR slope - the one that lays over - is the slope that RISES as you
    # move away from the radar. With the ramp rising toward +east, that means
    # look_dir 90 (line of sight pointing east, sensor to the west).
    steep   = simulate(ramp, px, 90.0, slope_deg - 12.0, h_ref=0.0)   # inc 28
    shallow = simulate(ramp, px, 90.0, slope_deg + 12.0, h_ref=0.0)   # inc 52
    f_steep = steep["layover_map"][inner].mean()
    f_shal  = shallow["layover_map"][inner].mean()
    if f_shal > 0.02:
        fails.append(("ramp", "-", "layover at inc %.0f > slope %.0f (%.0f%%)"
                      % (slope_deg + 12, slope_deg, 100 * f_shal)))
    if f_steep < 0.90:
        fails.append(("ramp", "-", "no layover at inc %.0f < slope %.0f (%.0f%%)"
                      % (slope_deg - 12, slope_deg, 100 * f_steep)))
    # Turn the same ramp away from the radar (look_dir 270, so the ramp now
    # FALLS away from the sensor) and it goes into shadow once it drops faster
    # than the grazing angle.
    away  = simulate(ramp, px, 270.0, 90.0 - slope_deg - 12.0, h_ref=0.0)  # graz 52 > 40: lit
    away2 = simulate(ramp, px, 270.0, 90.0 - slope_deg + 12.0, h_ref=0.0)  # graz 28 < 40: shadow
    s1 = away["shadow_map"][inner].mean(); s2 = away2["shadow_map"][inner].mean()
    if s1 > 0.02:
        fails.append(("ramp", "-", "shadow where backslope < grazing (%.0f%%)" % (100*s1)))
    if s2 < 0.90:
        fails.append(("ramp", "-", "no shadow where backslope > grazing (%.0f%%)" % (100*s2)))
    if verbose:
        print("\n   uniform %.0f deg ramp facing the radar:" % slope_deg)
        print("      inc %.0f (< slope) -> layover on %3.0f%% of the ramp   (want ~100%%)"
              % (slope_deg - 12, 100 * f_steep))
        print("      inc %.0f (> slope) -> layover on %3.0f%% of the ramp   (want 0%%)"
              % (slope_deg + 12, 100 * f_shal))
        print("   same ramp facing away:")
        print("      grazing %.0f (> slope) -> shadow on %3.0f%%   (want 0%%)"
              % (slope_deg + 12, 100 * s1))
        print("      grazing %.0f (< slope) -> shadow on %3.0f%%   (want ~100%%)"
              % (slope_deg - 12, 100 * s2))
    return fails


if __name__ == "__main__":
    print("self-test: does the simulation reproduce disp = -(h - h_ref)*cot(theta)?")
    f = _self_test()
    print()
    if f:
        print("FAILURES:")
        for x in f:
            print("  ", x)
        raise SystemExit(1)
    print("PASS - displacement direction and magnitude match the closed form,")
    print("       flat ground produces no distortion, and terrain at the")
    print("       reference height does not move.")
