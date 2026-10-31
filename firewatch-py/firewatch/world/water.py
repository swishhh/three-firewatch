"""Water bodies: flat surfaces at a set level over the terrain cells painted with the water brush
(terrain.water holds the body index + 1 per vertex).

Shore lines come from the terrain itself: the surface is drawn wherever it is painted, and the
ground rising above the level hides it. shaders/water.frag colors by the depth of water under each
pixel (read from the depth prepass, which water stays out of), with animated waves, sky reflection,
sun / moon glints and shore foam.
"""
import numpy as np
from panda3d.core import GeomNode, TransparencyAttrib

from .. import shading
from ..colors import rgb
from ..geometry import make_geom

SHOW_MARGIN = .02  # cells whose ground is entirely this far above the level are never visible
EDGE_PASSES = 3  # blur passes softening the painted mask into the edge contour


class WaterBody:
    def __init__(self, world, data, index):
        self.world = world
        self.data = data
        self.index = index  # value in terrain.water is index + 1
        self.node = None
        self.triangles = 0
        self.rebuild()

    @property
    def mask_value(self):
        return self.index + 1

    def rebuild(self):
        if self.node is not None:
            self.node.remove_node()
            self.node = None
        terrain = self.world.terrain
        level = float(self.data['level'])
        inside = terrain.water == self.mask_value
        if not inside.any():
            self.triangles = 0
            return
        # Soft coverage (a blurred mask) per vertex: the shader fades the surface out around 0.5, so
        # the edge follows a smooth contour instead of the grid cells' stair steps.
        rows_any, columns_any = np.nonzero(inside)
        pad = EDGE_PASSES + 2
        r0, r1 = max(rows_any.min() - pad, 0), min(rows_any.max() + pad + 1, terrain.segments + 1)
        c0, c1 = max(columns_any.min() - pad, 0), min(columns_any.max() + pad + 1, terrain.segments + 1)
        coverage = inside[r0:r1, c0:c1].astype(np.float32)
        for _ in range(EDGE_PASSES):
            for axis in (0, 1):
                padded = np.pad(coverage, [(1, 1) if a == axis else (0, 0) for a in (0, 1)], mode='edge')
                before = padded[:-2] if axis == 0 else padded[:, :-2]
                after = padded[2:] if axis == 0 else padded[:, 2:]
                coverage = (before + 2 * coverage + after) / 4
        covered = coverage > .02
        cells = covered[:-1, :-1] | covered[1:, :-1] | covered[:-1, 1:] | covered[1:, 1:]
        h = terrain.heights[r0:r1, c0:c1]
        lowest = np.minimum(np.minimum(h[:-1, :-1], h[1:, :-1]), np.minimum(h[:-1, 1:], h[1:, 1:]))
        cells &= lowest < level + SHOW_MARGIN  # cells buried under the ground are never visible
        rows, columns = np.nonzero(cells)
        self.triangles = 2 * len(rows)
        if not len(rows):
            return

        width = c1 - c0
        corners = np.stack((rows * width + columns, rows * width + columns + 1,
                            (rows + 1) * width + columns + 1, (rows + 1) * width + columns), axis=1)
        used, remap = np.unique(corners.ravel(), return_inverse=True)
        remap = remap.reshape(-1, 4).astype(np.uint32)
        vertex_rows, vertex_columns = np.divmod(used, width)
        positions = np.stack((terrain.coords[vertex_columns + c0], terrain.coords[vertex_rows + r0],
                              np.full(len(used), level)), axis=1).astype(np.float32)
        normals = np.broadcast_to(np.array([0, 0, 1], np.float32), positions.shape)
        colors = np.ones((len(used), 4), np.float32)
        colors[:, 3] = coverage[vertex_rows, vertex_columns]
        indices = np.stack((remap[:, 0], remap[:, 1], remap[:, 2], remap[:, 0], remap[:, 2], remap[:, 3]), 1).ravel()

        node = GeomNode(f'water-{self.data["id"]}')
        node.add_geom(make_geom(positions, np.ascontiguousarray(normals), indices, colors))
        self.node = self.world.root.attach_new_node(node)
        self.node.set_shader(shading.load_shader('water'), 10)
        self.node.set_transparency(TransparencyAttrib.M_alpha)
        self.node.set_bin('transparent', 0)
        self.node.set_depth_write(True)
        shading.set_cast_shadow(self.node, False)
        shading.set_in_depth_prepass(self.node, False)
        self.apply()

    def apply(self):
        if self.node is None:
            return
        data = self.data
        inputs = {
            'shallow_color': rgb(data['shallow_color']), 'deep_color': rgb(data['deep_color']),
            'foam_color': rgb(data['foam_color']),
            'opacity': data['opacity'], 'depth_opacity': data['depth_opacity'],
            'clarity': data['clarity'], 'reflectivity': data['reflectivity'],
            'water_specular': data['specular'], 'wave_height': data['wave_height'],
            'wave_scale': data['wave_scale'], 'wave_speed': data['wave_speed'], 'foam': data['foam'],
        }
        for name, value in inputs.items():
            if isinstance(value, np.ndarray):
                value = tuple(float(v) for v in value)
            self.node.set_shader_input(name, value)

    def contains(self, x, y):
        terrain = self.world.terrain
        if not terrain.contains(x, y):
            return False
        column, row = terrain.index_of(x, y)
        return terrain.water[int(round(row)), int(round(column))] == self.mask_value

    def destroy(self):
        if self.node is not None:
            self.node.remove_node()
            self.node = None


def paint(terrain, value, x, y, radius, erase=False, carve=0.0, level=0.0):
    """Paint (or erase) water body `value` under a brush; optionally carve the ground below the
    level so the water shows. Returns the changed vertex window."""
    window, weight = terrain.brush_window(x, y, radius)
    c0, r0, c1, r1 = window
    if c1 <= c0 or r1 <= r0:
        return None
    inside = weight > .02
    region = terrain.water[r0:r1, c0:c1]
    if erase:
        region[inside & (region == value)] = 0
    else:
        region[inside] = value
        if carve > 0:
            heights = terrain.heights[r0:r1, c0:c1]
            target = level - carve
            lowered = heights + (target - heights) * weight
            np.minimum(heights, lowered.astype(np.float32), out=heights)
    terrain.changed(window, heights=carve > 0 and not erase)
    return window
