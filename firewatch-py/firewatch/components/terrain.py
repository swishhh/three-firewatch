"""Port of js/component/objects/terrain/index.js.

The heights live in a numpy grid laid out like the THREE.PlaneGeometry position array after
rotateX(-PI / 2): row = z (ascending), column = x (ascending).

Hills use the JS centers, radii and peak heights. The default 'smooth' shape gives each one a
smootherstep bell (flat at the top and at the rim) and blends overlaps with a smooth union; the
'js' shape reproduces the JS bumps: s * (r^2 - d^2)^(1/4) domes, vertical at the rim, combined with
max(). The JS never recomputed normals after raising the bumps, so they all point up; 'Smooth
terrain shading' computes real ones.
"""
import numpy as np
from panda3d.core import GeomNode

from .. import registry, settings, shading
from ..colors import rgba
from ..geometry import make_geom

SIZE = 200
SEGMENTS = 480

TERRAIN_COLOR_WARM_GREEN = 0x002409

# (center x, center z, radius, strength)
CIRCLES = [
    # ground
    (-1, 10, 2, .3),
    (-.5, 9, 2, .3),
    (0, 8, 2, .2),
    (1.5, 8, 2, .2),

    (-5, 1, 2, .2),
    (-11, 1, 2, .3),
    (-11, 1.5, 2, .25),
    (-11, 2, 2, .25),
    (-9, 2, 2, .15),
    (-13, 2, 2, .2),
    (-14, 1, 2, .3),

    (-5, 8, 2, .3),
    (-6, 8.5, 2, .25),
    (-7, 8, 2, .25),
    (-8, 8, 2, .2),
    (-7, 9, 2, .25),
    (-8, 8, 2, .3),

    (1, 0, 2, .35),
    (1, 0.5, 2, .15),
    (.5, 1.5, 2, .15),
    (.5, 1.8, 2, .1),
    (7, 1.5, 2, .1),
    (8, 2, 2, .25),
    (8, 3, 2, .3),
    (9, 4, 2, .2),

    (15, 15, 5, .25),
    (14, 14, 4, .25),
    (12, 12, 4, .25),
    (12, 13, 4, .25),
    (15, 11, 4, .25),
    (13, 13, 4, .7),
    (9, 13, 2, .7),
]


HILL_BLEND = 4  # exponent of the smooth union: higher is closer to max(), lower blends overlaps more
SMOOTHING_PASSES = 4  # [1, 2, 1] filter passes softening the JS bumps' rims for shading normals


def _soften(grid, passes):
    for _ in range(passes):
        for axis in (0, 1):
            padded = np.pad(grid, [(1, 1) if a == axis else (0, 0) for a in (0, 1)], mode='edge')
            before = padded[:-2] if axis == 0 else padded[:, :-2]
            after = padded[2:] if axis == 0 else padded[:, 2:]
            grid = (before + 2 * grid + after) / 4
    return grid


class Terrain:
    def __init__(self, size=SIZE, segments=SEGMENTS):
        # float32 like the BufferAttribute, so radius tests land on the same vertices.
        coords = (np.arange(segments + 1) * (size / segments) - size / 2).astype(np.float32)
        self.x = coords[np.newaxis, :].astype(np.float64)
        self.z = coords[:, np.newaxis].astype(np.float64)
        self.heights = np.zeros((segments + 1, segments + 1), dtype=np.float32)
        self.shape = 'smooth'
        self.node_path = None

    def add_hills(self, circles):
        """Smooth hills: peak s * sqrt(r) like the JS bumps, a smootherstep bell (flat at the top and
        at the rim), overlaps blended as (sum h^p)^(1/p), so there is no crease anywhere."""
        total = np.zeros(self.heights.shape)
        for center_x, center_z, radius, strength in circles:
            t = np.minimum(np.sqrt((self.x - center_x) ** 2 + (self.z - center_z) ** 2) / radius, 1)
            falloff = 1 - t ** 3 * (t * (t * 6 - 15) + 10)
            total += (strength * np.sqrt(radius) * falloff) ** HILL_BLEND
        self.heights = (total ** (1 / HILL_BLEND)).astype(np.float32)

    def add_circle(self, center_x, center_z, radius, strength, mod=1):
        """addCircle() from the JS: a dome that turns vertical at its rim, combined with max()."""
        distance_squared = (self.x - center_x) ** 2 + (self.z - center_z) ** 2
        inside = distance_squared < radius ** 2
        value = np.sqrt(strength ** 2 * np.sqrt(np.maximum(radius ** 2 - distance_squared, 0)))
        current = self.heights.astype(np.float64)
        replace = inside & (np.abs(value) > np.abs(current) * mod)
        self.heights[replace] = (value * mod)[replace]

    def _inside(self, x, z, radius):
        return (self.x - x) ** 2 + (self.z - z) ** 2 < radius ** 2

    def relate_y(self, x, y, z, scale):
        """terrain.relateY(): lift an instance by the lowest terrain point under it."""
        inside = self._inside(x, z, scale)
        return y + float(self.heights[inside].min()) if inside.any() else y

    def relative_y(self, x, y, z, scale):
        """terrain.addRelativeObject(): lift an object by the first vertex (in buffer order) under it."""
        inside = self._inside(x, z, scale).ravel()
        return y + float(self.heights.ravel()[np.argmax(inside)]) if inside.any() else y

    def normals(self, smooth):
        if not smooth:
            return np.broadcast_to(np.array([0, 0, 1], dtype=np.float32), (self.heights.size, 3))
        spacing = float(self.x[0, 1] - self.x[0, 0])
        heights = self.heights.astype(np.float64)
        if self.shape == 'js':
            # The JS bumps' slope turns vertical at each rim; shading from a softened copy hides the ring.
            heights = _soften(heights, SMOOTHING_PASSES)
        slope_z, slope_x = np.gradient(heights, spacing)
        # Panda's y is three's -z, so the y slope flips sign.
        normals = np.stack((-slope_x, slope_z, np.ones_like(slope_x)), axis=-1).reshape(-1, 3)
        return (normals / np.linalg.norm(normals, axis=1, keepdims=True)).astype(np.float32)

    def geom(self, smooth):
        rows, columns = self.heights.shape
        x = np.broadcast_to(self.x, self.heights.shape)
        z = np.broadcast_to(self.z, self.heights.shape)
        positions = np.stack((x, -z, self.heights), axis=-1).reshape(-1, 3).astype(np.float32)

        grid = np.arange(rows * columns, dtype=np.uint32).reshape(rows, columns)
        a, b = grid[:-1, :-1], grid[1:, :-1]
        c, d = grid[1:, 1:], grid[:-1, 1:]
        indices = np.stack((a, b, d, b, c, d), axis=-1).ravel()
        return make_geom(positions, self.normals(smooth), indices)

    def build(self, color, smooth=False):
        node = GeomNode('terrain')
        node.add_geom(self.geom(smooth))
        self.node_path = registry.get('scene').attach_new_node(node)
        self.node_path.set_color(rgba(color))
        return self.node_path

    def set_smooth(self, smooth):
        self.node_path.node().set_geom(0, self.geom(smooth))


def draw(app):
    # SEGMENTS (480) is the JS grid; finer grids keep hill outlines round. Restart to apply.
    terrain = Terrain(segments=settings.get('gfx.terrain_detail'))
    # Objects are placed on the heights at startup, so the shape only changes on restart.
    terrain.shape = settings.get('env.terrain_shape')
    if terrain.shape == 'js':
        for circle in CIRCLES:
            terrain.add_circle(*circle)
    else:
        terrain.add_hills(CIRCLES)

    node_path = terrain.build(TERRAIN_COLOR_WARM_GREEN, settings.get('gfx.smooth_terrain'))
    shading.set_standard_material(node_path)  # MeshStandardMaterial defaults: roughness 1, metalness 0
    shading.set_cast_shadow(node_path, False)

    settings.subscribe(lambda _keys: terrain.set_smooth(settings.get('gfx.smooth_terrain')), 'gfx.smooth_terrain')
    registry.add('terrain', terrain)
