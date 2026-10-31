"""Walking physics for the first-person player: terrain following plus 2.5D colliders.

Colliders are vertical boxes (rotated by heading) and cylinders with a bottom and top height,
configured per object ('collision' in world.json) and per foliage group (a cylinder per instance,
e.g. tree trunks). The player is a vertical cylinder: it stands on the terrain or on any collider
top within step height, and is pushed out of colliders its body overlaps. A spatial hash keeps the
per-frame tests to the colliders nearby.
"""
import math
from collections import defaultdict

from .colliders import physics_shape

CELL = 4.0


class Colliders:
    def __init__(self, world):
        self.world = world
        self.shapes = []
        self.grid = defaultdict(list)
        self.dirty = True
        world.add_listener(self._changed)

    def _changed(self, section):
        if section in ('objects', 'foliage', 'loaded', 'terrain', 'colliders'):
            self.dirty = True

    def _rebuild(self):
        world = self.world
        shapes = []
        for item in world.objects:
            shapes.extend(item.collision_shapes())
        shapes.extend(physics_shape(record) for record in world.data['colliders'])
        if world.compiled is not None:
            shapes.extend(world.compiled.colliders)
        for group in world.foliage:
            collision = group.data['collision']
            if collision['shape'] == 'none' or not len(group.items):
                continue
            for (x, y, offset, scale, _heading), ground in zip(group.items, group.ground):
                bottom = ground + offset
                shapes.append(('cylinder', x, y, collision['radius'] * scale, bottom,
                               bottom + collision['height'] * scale))
        if world.compiled is not None:
            for record in world.data['foliage']:
                if record['id'] not in world.compiled.baked_foliage:
                    continue  # live group, handled above
                collision = record['collision']
                if collision['shape'] == 'none':
                    continue
                for x, y, offset, scale, _heading in record['items']:
                    bottom = world.terrain.min_height_in_radius(x, y, max(scale, world.terrain.spacing)) + offset
                    shapes.append(('cylinder', x, y, collision['radius'] * scale, bottom,
                                   bottom + collision['height'] * scale))
        self.shapes = shapes
        self.grid = defaultdict(list)
        for index, shape in enumerate(shapes):
            x0, y0, x1, y1 = self._extent(shape)
            for i in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
                for j in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
                    self.grid[(i, j)].append(index)
        self.dirty = False

    @staticmethod
    def _extent(shape):
        if shape[0] == 'cylinder':
            _, x, y, radius, _z0, _z1 = shape
            return x - radius, y - radius, x + radius, y + radius
        _, x, y, hx, hy, _heading, _z0, _z1 = shape
        reach = math.hypot(hx, hy)
        return x - reach, y - reach, x + reach, y + reach

    def nearby(self, x, y, radius):
        if self.dirty:
            self._rebuild()
        found = set()
        for i in range(int(math.floor((x - radius) / CELL)), int(math.floor((x + radius) / CELL)) + 1):
            for j in range(int(math.floor((y - radius) / CELL)), int(math.floor((y + radius) / CELL)) + 1):
                found.update(self.grid.get((i, j), ()))
        return [self.shapes[index] for index in found]

    @staticmethod
    def _local(shape, x, y):
        _, cx, cy, _hx, _hy, heading, _z0, _z1 = shape
        cos, sin = math.cos(-heading), math.sin(-heading)
        dx, dy = x - cx, y - cy
        return dx * cos - dy * sin, dx * sin + dy * cos

    def _covers(self, shape, x, y, radius=0.0):
        if shape[0] == 'cylinder':
            return math.hypot(x - shape[1], y - shape[2]) < shape[3] + radius
        lx, ly = self._local(shape, x, y)
        return abs(lx) < shape[3] + radius and abs(ly) < shape[4] + radius

    def ground_height(self, x, y, feet, step, radius=0.0):
        """Highest standing surface under (x, y) reachable from `feet` (terrain or a collider top)."""
        ground = self.world.terrain.height_at(x, y)
        for shape in self.nearby(x, y, radius):
            top = shape[-1]
            if top <= feet + step and top > ground and self._covers(shape, x, y, radius * .5):
                ground = top
        return ground

    def ceiling_height(self, x, y, head, radius):
        """Lowest collider bottom at or above `head` over the player's footprint (what a jump bumps
        into), or None."""
        lowest = None
        for shape in self.nearby(x, y, radius):
            bottom = shape[-2]
            if bottom >= head - .02 and self._covers(shape, x, y, radius * .8):
                lowest = bottom if lowest is None else min(lowest, bottom)
        return lowest

    def resolve(self, x, y, feet, height, radius, step):
        """Push (x, y) out of every collider overlapping the body between feet + step and the head."""
        for _ in range(3):
            moved = False
            for shape in self.nearby(x, y, radius):
                z0, z1 = shape[-2], shape[-1]
                if z1 <= feet + step or z0 >= feet + height:
                    continue
                if shape[0] == 'cylinder':
                    _, cx, cy, r, _z0, _z1 = shape
                    dx, dy = x - cx, y - cy
                    distance = math.hypot(dx, dy)
                    overlap = r + radius - distance
                    if overlap > 0:
                        if distance < 1e-6:
                            dx, dy, distance = 1.0, 0.0, 1.0
                        x += dx / distance * overlap
                        y += dy / distance * overlap
                        moved = True
                    continue
                _, cx, cy, hx, hy, heading, _z0, _z1 = shape
                lx, ly = self._local(shape, x, y)
                qx, qy = max(-hx, min(hx, lx)), max(-hy, min(hy, ly))
                dx, dy = lx - qx, ly - qy
                distance = math.hypot(dx, dy)
                if distance >= radius:
                    continue
                if distance > 1e-6:
                    push_x, push_y = dx / distance * (radius - distance), dy / distance * (radius - distance)
                else:  # center inside the box: leave through the nearest side
                    exits = ((hx - lx + radius, 1, 0), (lx + hx + radius, -1, 0),
                             (hy - ly + radius, 0, 1), (ly + hy + radius, 0, -1))
                    amount, sx, sy = min(exits)
                    push_x, push_y = sx * amount, sy * amount
                cos, sin = math.cos(heading), math.sin(heading)
                x += push_x * cos - push_y * sin
                y += push_x * sin + push_y * cos
                moved = True
            if not moved:
                break
        return x, y
