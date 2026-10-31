"""Campfire smoke, after js/component/objects/smoke/index.js: small spheres rising along sine curves,
bent by the wind, fading as they rise.

A continuous emitter: every puff runs the same rise over and over, offset in time so the puffs are
spread evenly along the column (the JS released all of them in the first few seconds, so its smoke
came out in one clump followed by a long gap). Amount, size, rise speed and height, sway, growth,
color and opacity are World tab settings (env.smoke_*).
"""
import math
import random

from panda3d.core import GeomNode, Point3, TransparencyAttrib, Vec3

from .. import settings, shading
from ..colors import rgba
from ..geometry import make_geom, sphere
from ..update import add_update_callback, remove_update_callback

SHARPNESS = 15  # sphere segments
MIN_SIZE, MAX_SIZE = .05, .1  # the JS puff radii, before the size setting
BASE_SPEED = .42  # m/s at "rise speed" 1 (the JS: 0.007 per 60 fps frame)
MIN_OPACITY, MAX_OPACITY = .4, .5  # the JS per-puff opacity range, before the opacity setting
WIND_LEAN = .25  # sideways drift per meter risen per unit of wind
FADE_IN = .06  # fraction of the rise over which a new puff appears


class Puff:
    def __init__(self, node, offset):
        self.node = node
        self.offset = offset  # 0..1: where in the rise this puff is at time 0
        self.cycle = None
        self._randomize()

    def _randomize(self):
        self.size = random.uniform(MIN_SIZE, MAX_SIZE)
        self.opacity = random.uniform(MIN_OPACITY, MAX_OPACITY)
        self.salt = random.uniform(.1, .4)  # how quickly its sine curve winds
        self.side = Vec3(random.choice((-1, 1)), random.choice((-1, 1)), 0)
        self.phase = random.uniform(0, 2 * math.pi)

    def place(self, cycle, fraction, origin, height, sway, wind, size, growth, opacity):
        if cycle != self.cycle:  # a new rise: new curve, size and opacity, like the JS
            self.cycle = cycle
            self._randomize()
        up = fraction * height
        # The JS curve: sin(y * salt * y / 10), so the puffs wander more the higher they get.
        wander = math.sin(up * self.salt * up / 10 + self.phase * fraction) * sway
        position = origin + Vec3(self.side.x * wander, self.side.y * wander, up) + wind * up * WIND_LEAN
        self.node.set_pos(position)
        self.node.set_scale(self.size * size * (1 + growth * fraction))
        appear = min(fraction / FADE_IN, 1.0)
        self.node.set_alpha_scale(self.opacity * opacity * appear * (1 - fraction))


class Smoke:
    """A smoke column rising from a world position (Panda3D coordinates); `destroy()` removes it."""

    def __init__(self, app, parent, position):
        self.app = app
        self.origin = Point3(*(float(v) for v in position))
        self.time = random.uniform(0, 100)
        self.group = parent.attach_new_node('smoke')
        self.group.set_transparency(TransparencyAttrib.M_alpha)
        shading.set_unlit(self.group)  # MeshBasicMaterial
        shading.set_cast_shadow(self.group, False)
        shading.set_in_depth_prepass(self.group, False)
        positions, normals, indices = sphere(1, SHARPNESS, SHARPNESS)
        self.geom = make_geom(positions, normals, indices)
        self.puffs = []
        self.wind = Vec3(0)
        settings.subscribe(self.apply, 'env.')
        self.apply()
        add_update_callback(self.update)

    def _set_count(self, count):
        count = max(int(count), 1)
        if count == len(self.puffs):
            return
        for puff in self.puffs:
            puff.node.remove_node()
        self.puffs = []
        for index in range(count):
            node = GeomNode('smoke-puff')
            node.add_geom(self.geom)
            # Evenly spread through the rise (plus a little jitter so it doesn't look like a conveyor).
            offset = (index + random.uniform(-.3, .3)) / count % 1.0
            self.puffs.append(Puff(self.group.attach_new_node(node), offset))

    def move_to(self, position):
        """Move the column's origin (Panda3D coordinates) without restarting it."""
        self.origin = Point3(*(float(v) for v in position))

    def apply(self, _keys=None):
        get = settings.get
        self.group.show() if get('env.smoke') else self.group.hide()
        self.group.set_color(rgba(get('env.smoke_color')))
        self._set_count(get('env.smoke_amount'))
        wind = math.radians(get('env.wind_direction'))
        self.wind = Vec3(math.sin(wind), math.cos(wind), 0) * get('env.wind_strength')

    def update(self, delta):
        if self.group.is_hidden():
            return
        get = settings.get
        height = max(get('env.smoke_height'), .2)
        life = height / max(BASE_SPEED * get('env.smoke_speed'), .01)
        self.time += delta
        size, growth, sway = get('env.smoke_size'), get('env.smoke_growth'), get('env.smoke_spread')
        opacity = get('env.smoke_opacity')
        for puff in self.puffs:
            progress = self.time / life + puff.offset
            cycle = math.floor(progress)
            puff.place(cycle, progress - cycle, self.origin, height, sway, self.wind, size, growth, opacity)

    def destroy(self):
        settings.unsubscribe(self.apply)
        remove_update_callback(self.update)
        self.group.remove_node()
