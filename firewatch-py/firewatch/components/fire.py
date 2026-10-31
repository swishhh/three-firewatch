"""Animated low-poly campfire flames and rising embers.

Flames: a cluster of faceted flame "tongues" (cones of a few triangles each, in an outer layer and a
bright inner core) built once and animated entirely in shaders/fire.vert: every tongue stretches,
flickers and sways on its own rhythm and leans with the wind. Faces are flat shaded (one color each,
from the core color at the base to the tip color), unlit and bright enough to bloom.

Embers: additive GPU particles (particles.py mode EMBERS) rising from the fire and fading.

Everything is in the World tab's Campfire section (env.flame_*, env.ember_*). Flames are parented to
the campfire, so they move and scale with it; they cast no shadows (they are the light).
"""
import math
import random

import numpy as np
from panda3d.core import Geom, GeomNode, OmniBoundingVolume, Vec3

from .. import settings, shading
from ..colors import rgba
from ..geometry import make_format, make_indexed_geom
from ..particles import EMBERS, ParticleSystem
from ..update import add_update_callback, remove_update_callback

FORMAT = make_format(('vertex', 3, Geom.C_point), ('tongue', 4, Geom.C_other), ('flame', 4, Geom.C_other))
SIDES = 5
# (height fraction, radius fraction) of each ring of a tongue, base to tip
RINGS = ((0.0, 1.0), (.35, .85), (.7, .45), (1.0, 0.0))
BASE = .06  # flame base above the campfire model's origin (its ash bed), in model units
SPREAD = .22  # how far tongues stand from the middle, in model units (times the width setting)


def _tongue(seed, ox, oy, radius, height, layer, twist):
    """Triangles of one tongue: positions in unit tongue space plus per-vertex attributes."""
    rings = []
    for fraction, size in RINGS:
        ring = []
        for side in range(SIDES):
            angle = twist + side / SIDES * 2 * math.pi
            # A little irregularity per vertex keeps the facets from looking machine made.
            jitter = 1 + .18 * math.sin(seed * 31.7 + side * 5.3 + fraction * 9.1)
            ring.append((math.cos(angle) * size * jitter, math.sin(angle) * size * jitter, fraction))
        rings.append(ring)
    triangles = []
    for lower, upper in zip(rings, rings[1:]):
        for side in range(SIDES):
            a, b = lower[side], lower[(side + 1) % SIDES]
            c, d = upper[side], upper[(side + 1) % SIDES]
            triangles.append((a, b, d))
            if c != d:
                triangles.append((a, d, c))
    vertices = []
    for triangle in triangles:
        height_center = sum(point[2] for point in triangle) / 3
        for point in triangle:
            vertices.append((*point, ox, oy, radius, height, seed, height_center, layer, 0.0))
    return vertices


class Flames:
    def __init__(self, app, parent):
        self.app = app
        self.node = parent.attach_new_node(GeomNode('flames'))
        self.node.set_z(BASE)
        self.node.node().set_bounds(OmniBoundingVolume())  # the shader moves the vertices
        self.node.node().set_final(True)
        self.node.set_shader(shading.load_shader('fire'), 20)
        self.node.set_light_off(10)
        shading.set_cast_shadow(self.node, False)
        shading.set_in_depth_prepass(self.node, False)
        self.tongues = None
        self.embers = ParticleSystem(app.render, 'embers', EMBERS, additive=True, seed=random.randint(0, 1000))
        settings.subscribe(self.apply, 'env.')
        self.apply()
        add_update_callback(self.update)

    def _build(self, count):
        rng = random.Random(7)
        vertices = []
        for index in range(count):
            angle = index / max(count, 1) * 2 * math.pi + rng.uniform(-.4, .4)
            distance = 0 if index == 0 else SPREAD * math.sqrt(rng.uniform(.25, 1))
            ox, oy = math.cos(angle) * distance, math.sin(angle) * distance
            # Tongues near the middle are the tallest.
            height = rng.uniform(.55, .9) * (1.15 - .5 * distance / SPREAD)
            radius = rng.uniform(.12, .19)
            vertices += _tongue(rng.uniform(0, 100), ox, oy, radius, height, 0.0, rng.uniform(0, 6.28))
        # A bright inner core: fewer, smaller tongues inside the outer layer.
        for index in range(max(count // 2, 1)):
            angle = rng.uniform(0, 2 * math.pi)
            distance = SPREAD * .45 * math.sqrt(rng.uniform(0, 1))
            vertices += _tongue(rng.uniform(0, 100), math.cos(angle) * distance, math.sin(angle) * distance,
                                rng.uniform(.08, .12), rng.uniform(.35, .55), 1.0, rng.uniform(0, 6.28))
        data = np.array(vertices, np.float32)
        node = self.node.node()
        node.remove_all_geoms()
        node.add_geom(make_indexed_geom(FORMAT, data, np.arange(len(data), dtype=np.uint32)))
        self.tongues = count

    def apply(self, _keys=None):
        get = settings.get
        if get('env.flame_tongues') != self.tongues:
            self._build(get('env.flame_tongues'))
        self.node.show() if get('env.flames') else self.node.hide()
        inputs = {
            'flame_height': get('env.flame_height'), 'flame_width': get('env.flame_width'),
            'flame_speed': get('env.flame_speed'), 'flame_flicker': get('env.flame_flicker'),
            'flame_sway': get('env.flame_sway'), 'flame_brightness': get('env.flame_brightness'),
            'core_color': rgba(get('env.flame_core_color')), 'mid_color': rgba(get('env.flame_mid_color')),
            'tip_color': rgba(get('env.flame_tip_color')),
        }
        for name, value in inputs.items():
            self.node.set_shader_input(name, value)
        embers = get('env.embers')
        self.embers.node_path.show() if embers else self.embers.node_path.hide()
        self.embers.set_count(get('env.ember_count') if embers else 0)
        wind = math.radians(get('env.wind_direction'))
        strength = get('env.wind_strength')
        self.embers.set_inputs(
            particle_size=get('env.ember_size'), particle_color=rgba(get('env.ember_color')),
            particle_intensity=get('env.ember_brightness'),
            drift=Vec3(math.sin(wind) * strength, math.cos(wind) * strength, get('env.ember_speed')),
        )

    def update(self, _delta):
        # Embers rise from the flames' base in world space (the campfire may have moved or scaled).
        render = self.app.render
        base = self.node.get_pos(render)
        scale = self.node.get_sz(render)
        get = settings.get
        self.embers.set_inputs(box_center=base,
                               box_size=Vec3(SPREAD * 2 * scale * get('env.flame_width'),
                                             SPREAD * 2 * scale * get('env.flame_width'), get('env.ember_height')))

    def destroy(self):
        settings.unsubscribe(self.apply)
        remove_update_callback(self.update)
        self.node.remove_node()
        self.embers.node_path.remove_node()
