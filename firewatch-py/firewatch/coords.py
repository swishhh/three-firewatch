"""three.js is Y-up, Panda3D is Z-up.

Positions in the component MAP arrays are kept in three.js coordinates (copied as-is from the
JS version) and converted here, so values can be moved between the two apps unchanged.
"""
import math

import numpy as np
from panda3d.core import Point3, Vec3


def three_to_panda(x, y, z):
    return Point3(x, -z, y)


def panda_to_three(point):
    return point.x, point.z, -point.y


def three_scale_to_panda(x, y, z):
    return Vec3(x, z, y)


def rotation_y_to_heading(radians):
    """three.js `rotateY(radians)` is a Panda3D heading in degrees (both counter-clockwise from above)."""
    return math.degrees(radians)


def three_array_to_panda(array):
    return np.stack((array[:, 0], -array[:, 2], array[:, 1]), axis=1).astype(np.float32)
