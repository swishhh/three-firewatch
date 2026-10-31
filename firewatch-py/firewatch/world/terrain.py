"""Editable heightfield terrain (replaces components/terrain.py, a port of js/.../terrain/index.js).

Data, all on one vertex grid of (segments + 1)^2 in Panda3D coordinates (row = y, column = x, both
ascending from -size/2):
  heights  float32  meters
  paint    uint8 RGBA, painted color with its weight in alpha (shown over env.terrain_color)
  water    uint8, index + 1 of the water body covering the vertex (0 = none), see water.py

Rendering splits the grid into square chunks so every camera (main, sun shadow, the campfire's six
cube faces) culls what it can't see, and each chunk drops vertices wherever the surface stays within
`gfx.terrain_lod` meters without them: the mostly flat 200 m plane costs a few thousand triangles
instead of two million. Chunk borders snap to the coarser neighbor, so there are no cracks.

Brushes use a smootherstep falloff (flat at the center and at the rim), so raised hills blend into
the ground without a crease, and normals come from central differences of the heights.
"""
import numpy as np
from panda3d.core import GeomNode

from .. import settings, shading
from ..colors import rgb
from ..geometry import make_geom

DEFAULT_SIZE = 200
DEFAULT_SEGMENTS = 960
MAX_CHUNK_SEGMENTS = 128
PAINT_TOLERANCE = 3  # 0-255 color steps a simplified chunk may differ by


def chunk_segments_for(segments):
    """Largest divisor of `segments` up to MAX_CHUNK_SEGMENTS (64-chunk grids for the defaults)."""
    for candidate in range(min(MAX_CHUNK_SEGMENTS, segments), 0, -1):
        if segments % candidate == 0 and candidate % 8 == 0:
            return candidate
    for candidate in range(min(MAX_CHUNK_SEGMENTS, segments), 0, -1):
        if segments % candidate == 0:
            return candidate
    return segments


def smootherstep(t):
    t = np.clip(t, 0, 1)
    return t * t * t * (t * (t * 6 - 15) + 10)


def _upsample_axis(values, step, axis):
    """Linear interpolation of every `step`-th sample back to full resolution along `axis`."""
    values = np.moveaxis(values, axis, -1)
    a, b = values[..., :-1], values[..., 1:]
    t = np.arange(step, dtype=np.float32) / step
    filled = (a[..., np.newaxis] * (1 - t) + b[..., np.newaxis] * t).reshape(*values.shape[:-1], -1)
    filled = np.concatenate((filled, values[..., -1:]), axis=-1)
    return np.moveaxis(filled, -1, axis)


def _upsample(grid, step):
    return _upsample_axis(_upsample_axis(grid, step, 0), step, 1)


class Terrain:
    def __init__(self, size=DEFAULT_SIZE, segments=DEFAULT_SEGMENTS, heights=None, paint=None, water=None):
        self.size = float(size)
        self.segments = int(segments)
        self.spacing = self.size / self.segments
        count = self.segments + 1
        self.coords = (np.arange(count) * self.spacing - self.size / 2).astype(np.float64)
        self.heights = (np.zeros((count, count), np.float32) if heights is None
                        else np.ascontiguousarray(heights, np.float32))
        if paint is None:
            paint = np.zeros((count, count, 4), np.uint8)
            paint[..., :3] = 255
        self.paint = np.ascontiguousarray(paint, np.uint8)
        self.water = np.zeros((count, count), np.uint8) if water is None else np.ascontiguousarray(water, np.uint8)
        self.normals = np.zeros((count, count, 3), np.float32)
        self._update_normals(0, 0, count, count)

        self.chunk_segments = chunk_segments_for(self.segments)
        self.chunks = self.segments // self.chunk_segments
        self.steps = np.ones((self.chunks, self.chunks), np.int32)
        self.root = None
        self.chunk_nodes = {}
        self._listeners = []  # callback(x0, y0, x1, y1) in vertex indices after height changes

    # ----------------------------------------------------------------- coordinates and queries

    @property
    def half(self):
        return self.size / 2

    def index_of(self, x, y):
        """Fractional grid indices (column, row) of a world position."""
        return (x + self.half) / self.spacing, (y + self.half) / self.spacing

    def contains(self, x, y):
        return -self.half <= x <= self.half and -self.half <= y <= self.half

    def height_at(self, x, y):
        """Height on the rendered triangles' plane (bilinear is within millimeters of it)."""
        column, row = self.index_of(x, y)
        column = min(max(column, 0), self.segments - 1e-6)
        row = min(max(row, 0), self.segments - 1e-6)
        c, r = int(column), int(row)
        fx, fy = column - c, row - r
        h = self.heights
        top = h[r, c] * (1 - fx) + h[r, c + 1] * fx
        bottom = h[r + 1, c] * (1 - fx) + h[r + 1, c + 1] * fx
        return float(top * (1 - fy) + bottom * fy)

    def heights_at(self, xs, ys):
        """Vectorized height_at."""
        columns = np.clip((np.asarray(xs) + self.half) / self.spacing, 0, self.segments - 1e-6)
        rows = np.clip((np.asarray(ys) + self.half) / self.spacing, 0, self.segments - 1e-6)
        c, r = columns.astype(np.int64), rows.astype(np.int64)
        fx, fy = columns - c, rows - r
        h = self.heights
        top = h[r, c] * (1 - fx) + h[r, c + 1] * fx
        bottom = h[r + 1, c] * (1 - fx) + h[r + 1, c + 1] * fx
        return top * (1 - fy) + bottom * fy

    def normal_at(self, x, y):
        column, row = self.index_of(x, y)
        c = int(min(max(round(column), 0), self.segments))
        r = int(min(max(round(row), 0), self.segments))
        return self.normals[r, c]

    def _window(self, x, y, radius):
        column, row = self.index_of(x, y)
        reach = radius / self.spacing
        c0, c1 = int(max(np.floor(column - reach), 0)), int(min(np.ceil(column + reach) + 1, self.segments + 1))
        r0, r1 = int(max(np.floor(row - reach), 0)), int(min(np.ceil(row + reach) + 1, self.segments + 1))
        return c0, r0, c1, r1

    def min_height_in_radius(self, x, y, radius):
        """terrain.relateY(): the lowest vertex within `radius`, or the height at the point."""
        c0, r0, c1, r1 = self._window(x, y, radius)
        if c1 <= c0 or r1 <= r0:
            return self.height_at(x, y)
        dx = self.coords[c0:c1][np.newaxis, :] - x
        dy = self.coords[r0:r1][:, np.newaxis] - y
        inside = dx * dx + dy * dy < radius * radius
        if not inside.any():
            return self.height_at(x, y)
        return float(self.heights[r0:r1, c0:c1][inside].min())

    def raycast(self, origin, direction, max_distance=600.0):
        """First hit of a ray with the surface, as (x, y, z), or None."""
        origin = np.array(origin, np.float64)
        direction = np.array(direction, np.float64)
        length = np.linalg.norm(direction)
        if length < 1e-9:
            return None
        direction /= length
        steps = np.arange(0, max_distance, self.spacing * 1.5)
        points = origin + steps[:, np.newaxis] * direction
        inside = (np.abs(points[:, 0]) <= self.half) & (np.abs(points[:, 1]) <= self.half)
        if not inside.any():
            return None
        heights = self.heights_at(points[:, 0], points[:, 1])
        below = (points[:, 2] <= heights) & inside
        hits = np.nonzero(below)[0]
        if len(hits) == 0:
            return None
        index = hits[0]
        if index == 0:
            return tuple(points[0])
        low, high = steps[index - 1], steps[index]
        for _ in range(20):
            middle = (low + high) / 2
            point = origin + direction * middle
            if point[2] <= self.height_at(point[0], point[1]):
                high = middle
            else:
                low = middle
        point = origin + direction * high
        return float(point[0]), float(point[1]), self.height_at(point[0], point[1])

    # ----------------------------------------------------------------------------- shapes

    def add_hills(self, circles):
        """Smooth bell hills (x, y, radius, strength); overlaps blend as (sum h^4)^(1/4), no creases."""
        x = self.coords[np.newaxis, :]
        y = self.coords[:, np.newaxis]
        total = np.zeros(self.heights.shape)
        for center_x, center_y, radius, strength in circles:
            t = np.minimum(np.sqrt((x - center_x) ** 2 + (y - center_y) ** 2) / radius, 1)
            falloff = 1 - smootherstep(t)
            total += (strength * np.sqrt(radius) * falloff) ** 4
        self.heights = np.maximum(self.heights, (total ** .25).astype(np.float32))
        self._update_normals(0, 0, self.segments + 1, self.segments + 1)

    def add_js_bumps(self, circles):
        """The JS addCircle() domes (vertical at their rims), combined with max()."""
        x = self.coords[np.newaxis, :]
        y = self.coords[:, np.newaxis]
        for center_x, center_y, radius, strength in circles:
            distance_squared = (x - center_x) ** 2 + (y - center_y) ** 2
            inside = distance_squared < radius ** 2
            value = np.sqrt(strength ** 2 * np.sqrt(np.maximum(radius ** 2 - distance_squared, 0)))
            replace = inside & (value > self.heights)
            self.heights[replace] = value[replace]
        self._update_normals(0, 0, self.segments + 1, self.segments + 1)

    # ---------------------------------------------------------------------------- normals

    def _update_normals(self, c0, r0, c1, r1):
        count = self.segments + 1
        ca, cb = max(c0 - 1, 0), min(c1 + 1, count)
        ra, rb = max(r0 - 1, 0), min(r1 + 1, count)
        heights = self.heights[ra:rb, ca:cb].astype(np.float64)
        if heights.shape[0] < 2 or heights.shape[1] < 2:
            return
        slope_y, slope_x = np.gradient(heights, self.spacing)
        normals = np.stack((-slope_x, -slope_y, np.ones_like(slope_x)), axis=-1)
        normals /= np.linalg.norm(normals, axis=-1, keepdims=True)
        self.normals[r0:r1, c0:c1] = normals[r0 - ra:r1 - ra, c0 - ca:c1 - ca]

    # ---------------------------------------------------------------------------- brushes

    def brush_window(self, x, y, radius):
        """(c0, r0, c1, r1) vertex window and the falloff weights (1 at the center, 0 at the rim)."""
        c0, r0, c1, r1 = self._window(x, y, radius)
        dx = self.coords[c0:c1][np.newaxis, :] - x
        dy = self.coords[r0:r1][:, np.newaxis] - y
        distance = np.sqrt(dx * dx + dy * dy) / max(radius, 1e-6)
        return (c0, r0, c1, r1), 1 - smootherstep(distance)

    def snapshot(self, window):
        c0, r0, c1, r1 = window
        return {'window': window, 'heights': self.heights[r0:r1, c0:c1].copy(),
                'paint': self.paint[r0:r1, c0:c1].copy(), 'water': self.water[r0:r1, c0:c1].copy()}

    def restore(self, snapshot):
        c0, r0, c1, r1 = snapshot['window']
        self.heights[r0:r1, c0:c1] = snapshot['heights']
        self.paint[r0:r1, c0:c1] = snapshot['paint']
        self.water[r0:r1, c0:c1] = snapshot['water']
        self.changed(snapshot['window'])

    def sculpt(self, mode, x, y, radius, amount, target=None):
        """One brush application. `amount` is meters (raise/lower) or a 0..1 blend factor."""
        window, weight = self.brush_window(x, y, radius)
        c0, r0, c1, r1 = window
        if c1 <= c0 or r1 <= r0:
            return None
        region = self.heights[r0:r1, c0:c1]
        if mode == 'raise':
            region += (weight * amount).astype(np.float32)
        elif mode == 'lower':
            region -= (weight * amount).astype(np.float32)
        elif mode == 'flatten':
            goal = target if target is not None else self.height_at(x, y)
            region += ((goal - region) * np.clip(weight * amount, 0, 1)).astype(np.float32)
        elif mode == 'smooth':
            blurred = self._blurred(window, max(1, int(radius / self.spacing / 4)))
            region += ((blurred - region) * np.clip(weight * amount, 0, 1)).astype(np.float32)
        elif mode == 'noise':
            rng = np.random.default_rng()
            region += (weight * amount * rng.standard_normal(region.shape) * .5).astype(np.float32)
            blurred = self._blurred(window, 1)
            region += ((blurred - region) * .5 * (weight > 0)).astype(np.float32)
        self.changed(window)
        return window

    def _blurred(self, window, passes):
        c0, r0, c1, r1 = window
        pad = passes + 1
        ca, ra = max(c0 - pad, 0), max(r0 - pad, 0)
        cb, rb = min(c1 + pad, self.segments + 1), min(r1 + pad, self.segments + 1)
        grid = self.heights[ra:rb, ca:cb].astype(np.float64)
        for _ in range(passes):
            for axis in (0, 1):
                padded = np.pad(grid, [(1, 1) if a == axis else (0, 0) for a in (0, 1)], mode='edge')
                before = padded[:-2] if axis == 0 else padded[:, :-2]
                after = padded[2:] if axis == 0 else padded[:, 2:]
                grid = (before + 2 * grid + after) / 4
        return grid[r0 - ra:r1 - ra, c0 - ca:c1 - ca].astype(np.float32)

    def paint_color(self, x, y, radius, color, amount, erase=False):
        window, weight = self.brush_window(x, y, radius)
        c0, r0, c1, r1 = window
        if c1 <= c0 or r1 <= r0:
            return None
        region = self.paint[r0:r1, c0:c1].astype(np.float32)
        blend = np.clip(weight * amount, 0, 1)[..., np.newaxis]
        if erase:
            region[..., 3:] *= 1 - blend
        else:
            goal = np.array([*(rgb(color) * 255), 255], np.float32)
            region += (goal - region) * blend
        self.paint[r0:r1, c0:c1] = np.round(region).astype(np.uint8)
        self.changed(window, heights=False)
        return window

    def color_at(self, x, y):
        """The painted color under a point ('#rrggbb'), or the base color where unpainted."""
        column, row = self.index_of(x, y)
        c = int(min(max(round(column), 0), self.segments))
        r = int(min(max(round(row), 0), self.segments))
        r_, g_, b_, a_ = (float(v) for v in self.paint[r, c])
        base = rgb(settings.get('env.terrain_color')) * 255
        weight = a_ / 255
        color = base * (1 - weight) + np.array([r_, g_, b_]) * weight
        return '#' + ''.join(f'{int(round(v)):02x}' for v in color)

    def fill_paint(self, color=None):
        """Clear the paint layer (color None) or paint everything with one color."""
        if color is None:
            self.paint[..., :3] = 255
            self.paint[..., 3] = 0
        else:
            self.paint[..., :3] = (rgb(color) * 255).round().astype(np.uint8)
            self.paint[..., 3] = 255
        self.changed((0, 0, self.segments + 1, self.segments + 1), heights=False)

    def set_heights(self, heights):
        self.heights = np.ascontiguousarray(heights, np.float32)
        self.changed((0, 0, self.segments + 1, self.segments + 1))

    # -------------------------------------------------------------------------- rendering

    def add_listener(self, callback):
        self._listeners.append(callback)

    def changed(self, window, heights=True):
        c0, r0, c1, r1 = window
        if heights:
            self._update_normals(c0, r0, c1, r1)
        if self.root is not None:
            self.rebuild_window(window)
        if heights:
            for callback in self._listeners:
                callback(c0, r0, c1, r1)

    def build(self, parent):
        if self.root is not None:
            self.root.remove_node()
        self.root = parent.attach_new_node('terrain')
        self.chunk_nodes = {}
        shading.set_cast_shadow(self.root, False)
        self.apply_material()
        self.rebuild_all()
        return self.root

    def apply_material(self):
        if self.root is None:
            return
        get = settings.get
        r, g, b = (float(c) for c in rgb(get('env.terrain_color')))
        self.root.set_shader_input('paint_base', (r, g, b, 1.0))
        shading.set_standard_material(self.root, get('env.terrain_roughness'))  # MeshStandardMaterial
        shading.set_receive_shadow(self.root, get('env.terrain_receive_shadows'))
        shading.set_cast_shadow(self.root, get('env.terrain_cast_shadows'))

    def rebuild_all(self):
        self._choose_steps(0, 0, self.chunks, self.chunks)
        for cy in range(self.chunks):
            for cx in range(self.chunks):
                self._build_chunk(cx, cy)

    def rebuild_window(self, window):
        c0, r0, c1, r1 = window
        cs = self.chunk_segments
        # Normals one vertex outside the window changed too, and border vertices belong to two chunks.
        x0, y0 = max((c0 - 2) // cs, 0), max((r0 - 2) // cs, 0)
        x1, y1 = min((c1 + 1) // cs + 1, self.chunks), min((r1 + 1) // cs + 1, self.chunks)
        before = self.steps.copy()
        self._choose_steps(x0, y0, x1, y1)
        rebuild = {(cx, cy) for cy in range(y0, y1) for cx in range(x0, x1)}
        for cy, cx in zip(*np.nonzero(before != self.steps)):
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                if 0 <= nx < self.chunks and 0 <= ny < self.chunks:
                    rebuild.add((nx, ny))  # neighbors snap their border to this chunk's step
        for cx, cy in rebuild:
            self._build_chunk(cx, cy)

    def _chunk_slice(self, cx, cy):
        cs = self.chunk_segments
        return slice(cy * cs, (cy + 1) * cs + 1), slice(cx * cs, (cx + 1) * cs + 1)

    def _choose_steps(self, x0, y0, x1, y1):
        tolerance = settings.get('gfx.terrain_lod')
        cs = self.chunk_segments
        candidates = [step for step in (32, 16, 8, 4, 2) if cs % step == 0 and step <= cs]
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                self.steps[cy, cx] = 1
                if tolerance <= 0:
                    continue
                rows, columns = self._chunk_slice(cx, cy)
                heights = self.heights[rows, columns]
                paint = self.paint[rows, columns].astype(np.int16)
                water = self.water[rows, columns]
                for step in candidates:
                    if np.abs(_upsample(heights[::step, ::step], step) - heights).max() > tolerance:
                        continue
                    if np.abs(_upsample(paint[::step, ::step].astype(np.float32), step) - paint).max() > PAINT_TOLERANCE:
                        continue
                    if water.any() and (water.min() != water.max()):
                        continue  # keep shore lines exact where water starts
                    self.steps[cy, cx] = step
                    break

    def _build_chunk(self, cx, cy):
        step = int(self.steps[cy, cx])
        rows, columns = self._chunk_slice(cx, cy)
        heights = self.heights[rows, columns][::step, ::step].copy()
        normals = self.normals[rows, columns][::step, ::step]
        paint = self.paint[rows, columns][::step, ::step]
        if not settings.get('gfx.smooth_terrain'):
            normals = np.broadcast_to(np.array([0, 0, 1], np.float32), normals.shape)

        # Snap border vertices to a coarser neighbor's edge so the two meet without a crack.
        last = heights.shape[0] - 1
        for (nx, ny), edge in (((cx - 1, cy), np.s_[:, 0]), ((cx + 1, cy), np.s_[:, last]),
                               ((cx, cy - 1), np.s_[0, :]), ((cx, cy + 1), np.s_[last, :])):
            if not (0 <= nx < self.chunks and 0 <= ny < self.chunks):
                continue
            ratio = int(self.steps[ny, nx]) // step
            if ratio > 1:
                line = heights[edge]
                heights[edge] = _upsample_axis(line[::ratio], ratio, 0)

        count = heights.shape[0]
        xs = self.coords[columns][::step]
        ys = self.coords[rows][::step]
        positions = np.stack((np.broadcast_to(xs[np.newaxis, :], heights.shape),
                              np.broadcast_to(ys[:, np.newaxis], heights.shape), heights), axis=-1)
        grid = np.arange(count * count, dtype=np.uint32).reshape(count, count)
        a, b = grid[:-1, :-1], grid[1:, :-1]
        c, d = grid[1:, 1:], grid[:-1, 1:]
        indices = np.stack((a, d, b, b, d, c), axis=-1).ravel()  # counter-clockwise seen from above
        colors = paint.reshape(-1, 4).astype(np.float32) / 255
        geom = make_geom(positions.reshape(-1, 3).astype(np.float32), np.ascontiguousarray(normals.reshape(-1, 3)),
                         indices, colors)

        key = (cx, cy)
        node = self.chunk_nodes.get(key)
        if node is None:
            geom_node = GeomNode(f'terrain-{cx}-{cy}')
            geom_node.add_geom(geom)
            self.chunk_nodes[key] = self.root.attach_new_node(geom_node)
        else:
            node.node().set_geom(0, geom)

    def triangle_count(self):
        return int(sum(2 * (self.chunk_segments // int(step)) ** 2 for step in self.steps.ravel()))
