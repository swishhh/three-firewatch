"""Foliage groups: many copies of one model (trees, grass, ...) painted onto the terrain with a brush.
Successor of instancing.py (js/component/scene/InstancedManager.js).

Instances are baked into one vertex-colored mesh per 25 m cell, so painting only rebuilds the
cells it touched and cameras cull whole cells. Each instance stands on the lowest ground under it
(terrain.relateY in the JS) plus its own offset, and follows the terrain when it is sculpted.
Vertices carry a wind sway weight (0 at the base) and a per-instance phase (shaders/common.glsl).
"""
import math

import numpy as np
from panda3d.core import GeomNode, Point3

from .. import objects, shading
from ..geometry import make_geom
from ..objects import DISTANCE_RENDER_TAG
from .entities import EDITOR_PICK_MASK

CELL = 25.0
TAG = 'foliage_group'
X, Y, OFFSET, SCALE, HEADING = range(5)


def instance_phase(x, y):
    """Same per-instance phase as the JS-era InstancedManager (three.js x and z)."""
    return (np.sin(x * 12.9898 + (-y) * 78.233) * 43758.5453) % 1 * 2 * math.pi


def bake(parts, items, ground):
    """One mesh's arrays (positions, normals, colors, sway, indices) for `items` (n, 5)."""
    if not len(items) or not parts:
        return None
    bottom = min(float(part.positions[:, 2].min()) for part in parts)
    top = max(float(part.positions[:, 2].max()) for part in parts)
    height = max(top - bottom, 1e-6)

    scale = items[:, SCALE].astype(np.float32)
    angle = np.radians(items[:, HEADING]).astype(np.float32)
    cos, sin = np.cos(angle)[:, None], np.sin(angle)[:, None]
    translation = np.stack((items[:, X], items[:, Y], ground + items[:, OFFSET]), axis=1).astype(np.float32)
    phase = instance_phase(items[:, X], items[:, Y]).astype(np.float32)

    blocks = []
    count = len(items)
    for part in parts:
        p, n = part.positions, part.normals
        vertices = len(p)
        px = p[None, :, 0] * cos - p[None, :, 1] * sin
        py = p[None, :, 0] * sin + p[None, :, 1] * cos
        positions = np.stack((px, py, np.broadcast_to(p[None, :, 2], px.shape)), axis=-1) * scale[:, None, None]
        positions += translation[:, None, :]
        nx = n[None, :, 0] * cos - n[None, :, 1] * sin
        ny = n[None, :, 0] * sin + n[None, :, 1] * cos
        normals = np.stack((nx, ny, np.broadcast_to(n[None, :, 2], nx.shape)), axis=-1)
        weight = ((p[:, 2] - bottom) / height) ** 2
        sway = np.stack((weight[None, :] * scale[:, None], np.broadcast_to(phase[:, None], (count, vertices))), -1)
        colors = np.broadcast_to(np.array(part.color, np.float32), (count * vertices, 4))
        blocks.append((positions.reshape(-1, 3), normals.reshape(-1, 3), colors, sway.reshape(-1, 2),
                       part.indices, vertices))

    positions, normals, colors, sway, indices = [], [], [], [], []
    offset = 0
    for block_positions, block_normals, block_colors, block_sway, part_indices, vertices in blocks:
        positions.append(block_positions)
        normals.append(block_normals)
        colors.append(block_colors)
        sway.append(block_sway)
        starts = offset + np.arange(count, dtype=np.uint32)[:, None] * vertices
        indices.append((part_indices[None, :] + starts).ravel())
        offset += count * vertices
    return (np.concatenate(positions), np.concatenate(normals), np.concatenate(colors), np.concatenate(sway),
            np.concatenate(indices))


class FoliageGroup:
    def __init__(self, world, data):
        self.world = world
        self.data = data
        self.root = world.root.attach_new_node(f'foliage-{data["id"]}')
        self.root.set_tag(TAG, data['id'])
        self.items = np.array(data['items'], np.float64).reshape(-1, 5)
        self.ground = np.zeros(len(self.items))
        self.cells = {}  # (i, j) -> NodePath
        self.parts = []
        self.reload_model()

    # ------------------------------------------------------------------------- building

    def reload_model(self):
        try:
            self.parts = objects.colored_parts(self.data['model'], self.data['colors'])
        except (OSError, ValueError, KeyError) as error:
            print(f'foliage {self.data["name"]}: cannot load {self.data["model"]}: {error}')
            self.parts = []
        self.update_ground()
        self.rebuild()

    def apply_flags(self):
        data = self.data
        self.root.set_shader_input('sway_amount', float(data['sway']))
        shading.set_cast_shadow(self.root, data['cast_shadow'])
        shading.set_receive_shadow(self.root, data['receive_shadow'])
        self.world.distance_changed()

    def update_ground(self, mask=None):
        terrain = self.world.terrain
        indices = range(len(self.items)) if mask is None else np.nonzero(mask)[0]
        for index in indices:
            x, y, _offset, scale, _heading = self.items[index]
            self.ground[index] = terrain.min_height_in_radius(x, y, max(scale, terrain.spacing))

    def cell_of(self, x, y):
        half = self.world.terrain.half
        return int((x + half) // CELL), int((y + half) // CELL)

    def _cell_keys(self):
        if not len(self.items):
            return np.zeros((0, 2), np.int64)
        half = self.world.terrain.half
        return np.stack(((self.items[:, X] + half) // CELL, (self.items[:, Y] + half) // CELL), axis=1).astype(np.int64)

    def rebuild(self, cells=None):
        keys = self._cell_keys()
        if cells is None:
            for node in self.cells.values():
                node.remove_node()
            self.cells = {}
            cells = {tuple(key) for key in keys}
        for cell in cells:
            node = self.cells.pop(cell, None)
            if node is not None:
                node.remove_node()
            mask = (keys[:, 0] == cell[0]) & (keys[:, 1] == cell[1]) if len(keys) else np.zeros(0, bool)
            arrays = bake(self.parts, self.items[mask], self.ground[mask]) if mask.any() else None
            if arrays is None:
                continue
            positions, normals, colors, sway, indices = arrays
            geom_node = GeomNode(f'cell-{cell[0]}-{cell[1]}')
            geom_node.add_geom(make_geom(positions, normals, indices, colors, sway))
            node = self.root.attach_new_node(geom_node)
            half = self.world.terrain.half
            node.set_python_tag('center', Point3((cell[0] + .5) * CELL - half, (cell[1] + .5) * CELL - half, 0))
            if self.data['distance_render']:
                node.set_tag(DISTANCE_RENDER_TAG, '1')
            if self.world.mode == 'editor':
                node.set_collide_mask(EDITOR_PICK_MASK)  # single instances can be picked and edited
            self.cells[cell] = node
        self.apply_flags()

    def sync(self):
        self.data['items'] = [[round(float(v), 4) for v in item] for item in self.items]

    def destroy(self):
        self.root.remove_node()
        self.cells = {}

    # -------------------------------------------------------------------------- brushes

    def paint(self, x, y, radius, count, scale_range, random_heading, spacing, rng):
        """Scatter up to `count` instances in the disk, at least `spacing` apart. Returns touched cells."""
        terrain = self.world.terrain
        added, cells = [], set()
        existing = self.items[:, :2] if len(self.items) else np.zeros((0, 2))
        if len(existing):
            existing = existing[np.hypot(existing[:, 0] - x, existing[:, 1] - y) < radius + spacing]
        taken = [tuple(point) for point in existing]
        for _ in range(count * 4):
            if len(added) >= count:
                break
            angle, distance = rng.uniform(0, 2 * math.pi), radius * math.sqrt(rng.uniform())
            px, py = x + math.cos(angle) * distance, y + math.sin(angle) * distance
            if not terrain.contains(px, py):
                continue
            if taken and spacing > 0:
                points = np.array(taken)
                if np.hypot(points[:, 0] - px, points[:, 1] - py).min() < spacing:
                    continue
            taken.append((px, py))
            scale = rng.uniform(*scale_range) if scale_range[1] > scale_range[0] else scale_range[0]
            heading = rng.uniform(0, 360) if random_heading else 0.0
            added.append([px, py, 0.0, scale, heading])
            cells.add(self.cell_of(px, py))
        if added:
            start = len(self.items)
            self.items = np.vstack((self.items, np.array(added)))
            self.ground = np.concatenate((self.ground, np.zeros(len(added))))
            mask = np.zeros(len(self.items), bool)
            mask[start:] = True
            self.update_ground(mask)
            self.rebuild(cells)
            self.sync()
        return cells

    def erase(self, x, y, radius):
        if not len(self.items):
            return set()
        inside = np.hypot(self.items[:, X] - x, self.items[:, Y] - y) < radius
        if not inside.any():
            return set()
        cells = {self.cell_of(px, py) for px, py in self.items[inside][:, :2]}
        self.items = self.items[~inside]
        self.ground = self.ground[~inside]
        self.rebuild(cells)
        self.sync()
        return cells

    def terrain_changed(self, x0, y0, x1, y1):
        """Re-seat the instances standing in a changed terrain window (world coordinates)."""
        if not len(self.items):
            return
        mask = ((self.items[:, X] >= x0) & (self.items[:, X] <= x1) &
                (self.items[:, Y] >= y0) & (self.items[:, Y] <= y1))
        if mask.any():
            self.update_ground(mask)
            self.rebuild({self.cell_of(px, py) for px, py in self.items[mask][:, :2]})

    # ----------------------------------------------------------------- single instances

    def nearest(self, x, y, reach=6.0):
        """Index of the instance whose trunk is closest to (x, y) relative to its size, or None."""
        if not len(self.items):
            return None
        distance = np.hypot(self.items[:, X] - x, self.items[:, Y] - y)
        candidates = np.nonzero(distance < reach)[0]
        if not len(candidates):
            return None
        relative = distance[candidates] / np.maximum(self.items[candidates, SCALE], .05)
        return int(candidates[np.argmin(relative)])

    def position(self, index):
        x, y, offset, _scale, _heading = self.items[index]
        return float(x), float(y), float(self.ground[index] + offset)

    def set_item(self, index, **values):
        """Change one instance: x, y, offset, scale and/or heading."""
        before = self.cell_of(*self.items[index, :2])
        columns = {'x': X, 'y': Y, 'offset': OFFSET, 'scale': SCALE, 'heading': HEADING}
        for name, value in values.items():
            self.items[index, columns[name]] = float(value)
        mask = np.zeros(len(self.items), bool)
        mask[index] = True
        self.update_ground(mask)
        self.rebuild({before, self.cell_of(*self.items[index, :2])})
        self.sync()

    def add_item(self, x, y, offset, scale, heading):
        self.items = np.vstack((self.items, [[x, y, offset, scale, heading]]))
        self.ground = np.concatenate((self.ground, [0.0]))
        mask = np.zeros(len(self.items), bool)
        mask[-1] = True
        self.update_ground(mask)
        self.rebuild({self.cell_of(x, y)})
        self.sync()
        return len(self.items) - 1

    def remove_item(self, index, persist=True):
        """Remove one instance; persist=False (the game) leaves the saved record alone."""
        cell = self.cell_of(*self.items[index, :2])
        self.items = np.delete(self.items, index, axis=0)
        self.ground = np.delete(self.ground, index)
        self.rebuild({cell})
        if persist:
            self.sync()

    def triangle_count(self):
        per_instance = sum(len(part.indices) // 3 for part in self.parts)
        return per_instance * len(self.items)
