#!/usr/bin/env python
"""SAR acquisition geometry derived from Umbra STAC v2 sidecar fields.

Conventions established and tested in validate_geometry.py:

  look_dir  = ground-projected line of sight, SENSOR -> TARGET, deg from N
            = view:azimuth - 180
    (so view:azimuth is the azimuth TARGET -> SENSOR, i.e. where the satellite
     sits in the target's sky. Verified two independent ways.)

  heading   = platform ground-track direction of flight, deg from N
            = look_dir - umbra:squint_angle_engineering_degrees

    Solved by brute force over all four sign conventions and scored against
    sat:orbit_state: 1142/1142 = 100.00%. Cross-checked against the ARP velocity
    vector in the three local SICD NITFs: agreement 0.14-0.30 deg.

  The engineering squint is signed by look side:  eng = s*90 + exploitation,
  with s = +1 right, -1 left. So for a RIGHT-looking scene eng == 90 is
  broadside, eng < 90 squinted forward, eng > 90 squinted aft; for a LEFT-looking
  scene the whole scale is negated. Do NOT assume eng = 90 + exploitation - that
  holds only on the right-looking half of the archive, and fails on 12 scenes
  near |squint| = 45 deg even there. Always drive the heading off eng directly.
"""
import math

def norm360(a):
    return a % 360.0

def angdiff(a, b):
    """signed smallest difference a-b in (-180,180]"""
    d = (a - b + 180.0) % 360.0 - 180.0
    return d + 360.0 if d <= -180.0 else d

def side_sign(look_side):
    return 1.0 if str(look_side).lower().startswith("r") else -1.0

def look_direction(view_azimuth):
    """Ground-projected LOS azimuth, sensor -> target."""
    return norm360(view_azimuth - 180.0)

def heading_from_squint(view_azimuth, eng_squint, look_side=None):
    """Ground-track heading. look_side is unused - the sign is already carried
    inside the engineering squint - but kept in the signature so callers reading
    the sidecar can pass it without thinking about it."""
    return norm360(look_direction(view_azimuth) - eng_squint)

def broadside_azimuth(heading, look_side):
    """Where the radar would point with zero squint."""
    return norm360(heading + side_sign(look_side) * 90.0)

def los_unit_enu(view_azimuth, incidence):
    """Unit vector from TARGET toward SENSOR in local East-North-Up metres."""
    a = math.radians(view_azimuth)
    # incidence is measured from vertical at the ground
    i = math.radians(incidence)
    return (math.sin(i) * math.sin(a), math.sin(i) * math.cos(a), math.cos(i))

def velocity_unit_enu(heading):
    h = math.radians(heading)
    return (math.sin(h), math.cos(h), 0.0)

def layover(slope_deg, incidence_deg):
    """Layover when the terrain slope facing the radar exceeds the incidence angle."""
    return slope_deg > incidence_deg

def shadow(slope_deg, incidence_deg):
    """Shadow when the slope facing away exceeds the grazing angle (90 - incidence)."""
    return slope_deg > (90.0 - incidence_deg)

def raster_axis_azimuths(transform, lat_deg):
    """Azimuth of the raster +x (right) and +y (down) axes, from an affine transform.

    Umbra GEC rasters are stored rotated so that +y runs down-range; this is an
    independent check on look_dir that uses no orbit assumption at all.
    """
    a, b, c, d, e, f = (transform.a, transform.b, transform.c,
                        transform.d, transform.e, transform.f)
    k = math.cos(math.radians(lat_deg))
    az_x = norm360(math.degrees(math.atan2(a * k, d)))   # +x: dlon=a, dlat=d
    az_y = norm360(math.degrees(math.atan2(b * k, e)))   # +y: dlon=b, dlat=e
    return az_x, az_y
