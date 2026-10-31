"""Placed lights: world objects of kind 'light' (point or spot), with their settings in the record's
'light' entry:

  type       'point' (all around) or 'spot' (a cone along the object's forward axis, +Y)
  enabled    on / off
  color, intensity, range (m), decay
  angle      spot: half the cone, degrees;  softness: spot edge, 0 hard .. 1 soft
  mode       'steady', 'flicker' (blinks: flicker_interval, flicker_random, flicker_duration,
             flicker_burst, flicker_depth, flicker_shimmer), 'strobe' or 'pulse' (at `rate` Hz)
  bounce     0..1 of its intensity re-emitted where the light lands (a spot: where the beam hits; a
             point light: the middle of the room around it), lighting the room around it; bounce_range is how far that
             reaches. Shares the light's shadows setting.
  shadows    cast shadows (walls then keep a lamp's light inside a house). Point lights: the nearest
             three shadow-casting point lights (campfire included) get cube shadow maps; spot lights
             share the flashlight shadow map when no flashlight in hand uses it

The scene shader has 8 light slots and the campfire takes two, so LightManager switches on the
MAX_ACTIVE enabled lights nearest the camera (re-checked a few times a second). The editor shows each
light as a small bulb (and a cone for spots) that can be clicked and dragged; the game shows only
the light.
"""
import math
import random

from panda3d.core import GeomNode, LineSegs, Point3, PointLight, Spotlight, TransparencyAttrib, Vec3

from .. import registry, shading, spot_shadow
from ..colors import rgb
from ..geometry import make_geom, sphere
from ..update import add_update_callback, remove_update_callback

LIGHT_TYPES = ('point', 'spot')
MODES = ('steady', 'flicker', 'strobe', 'pulse')
MAX_ACTIVE = 4
CHOOSE_EVERY = .25  # seconds between re-picking the active lights


def new_light(light_type='point'):
    return {'type': light_type, 'enabled': True, 'color': '#ffd9a0', 'intensity': 6.0 if light_type == 'point' else 12.0,
            'range': 10.0 if light_type == 'point' else 18.0, 'decay': 1.5, 'angle': 30.0, 'softness': .4,
            'mode': 'steady', 'rate': 2.0, 'shadows': light_type == 'spot',
            # flicker mode: blink events about every `flicker_interval` s (randomized by flicker_random:
            # 0 = regular .. 1 = anywhere from 0 to twice the interval), each a burst of 1..flicker_burst
            # blinks of flicker_duration s dimming by flicker_depth, plus a constant shimmer.
            'flicker_interval': 2.0, 'flicker_random': .6, 'flicker_duration': .08, 'flicker_burst': 3,
            'flicker_depth': .85, 'flicker_shimmer': .12,
            # a soft point light where the light lands fakes it bouncing around a room
            'bounce': 0.0, 'bounce_range': 6.0}


class PlacedLight:
    def __init__(self, world, root, record):
        self.world = world
        self.root = root
        self.record = record
        self.time = random.random() * 10
        settings = record['light']
        if settings['type'] == 'spot':
            self.light = Spotlight('placed-spot')
        else:
            self.light = PointLight('placed-point')
        self.path = root.attach_new_node(self.light)
        # Bounce: a soft point light just in front of where the light lands (a spot's beam; straight down
        # for a point light, whose reflected light mostly comes off the floor), re-placed when it moves.
        self.bounce = None
        if settings.get('bounce', 0) > 0:
            self.bounce = world.root.attach_new_node(PointLight('placed-bounce'))
            self.moved()
        self.on = False
        self.held = False  # (spot_shadow reads it like a flashlight beam's)
        self.next_blink = None  # time of the next flicker burst
        self.blinks = []  # (start, end) of dark moments in the current burst
        self.marker = None
        if world.mode == 'editor':
            self._build_marker()
        self.apply()
        add_update_callback(self.update)
        manager().add(self)

    @property
    def settings(self):
        """(spot_shadow reads `settings` for the cone angle and range.)"""
        return self.record['light']

    @property
    def wanted(self):
        return bool(self.record['light']['enabled']) and bool(self.record['visible'])

    def _build_marker(self):
        settings = self.record['light']
        r, g, b = (float(c) for c in rgb(settings['color']))
        self.marker = self.root.attach_new_node('light-marker')
        positions, normals, indices = sphere(.12, 12, 8)
        bulb = GeomNode('bulb')
        bulb.add_geom(make_geom(positions, normals, indices))
        bulb_path = self.marker.attach_new_node(bulb)
        bulb_path.set_color(r, g, b, 1)
        bulb_path.set_shader_input('unlit', 1.0)
        lines = LineSegs('light-gizmo')
        lines.set_thickness(1.5)
        lines.set_color(r, g, b, .9)
        if settings['type'] == 'spot':
            length = min(settings['range'], 2.5)
            radius = math.tan(math.radians(min(settings['angle'], 85))) * length
            rim = []
            for index in range(25):
                angle = index / 24 * 2 * math.pi
                rim.append((math.cos(angle) * radius, length, math.sin(angle) * radius))
            for index, point in enumerate(rim):
                lines.draw_to(*point) if index else lines.move_to(*point)
            for point in rim[::6]:
                lines.move_to(0, 0, 0)
                lines.draw_to(*point)
        else:
            for axis in range(3):
                for index in range(25):
                    angle = index / 24 * 2 * math.pi
                    point = [0.0, 0.0, 0.0]
                    point[axis], point[(axis + 1) % 3] = math.cos(angle) * .3, math.sin(angle) * .3
                    lines.draw_to(*point) if index else lines.move_to(*point)
        gizmo = self.marker.attach_new_node(lines.create())
        gizmo.set_shader_off(10)
        gizmo.set_transparency(TransparencyAttrib.M_alpha)
        self.marker.set_light_off(10)
        shading.set_cast_shadow(self.marker, False)
        shading.set_in_depth_prepass(self.marker, False)
        # Keep the marker the same size whatever the object's scale.
        self.marker.set_scale(self.root, 1)

    def moved(self):
        """Place the bounce light (see the notes below for spot and point lights)."""
        if self.bounce is None:
            return
        render = self.world.app.render
        origin = self.path.get_pos(render)
        reach = max(self.record['light']['range'], .5)
        if self.record['light']['type'] == 'spot':
            # Where the beam hits, backed off towards the light (about a meter, never past it): light bounced
            # off a floor spreads over the walls around it, not just the floor right under the beam.
            direction = render.get_relative_vector(self.path, Vec3(0, 1, 0)).normalized()
            hit = _first_hit(self.world, origin, direction, reach, exclude=self.root)
            distance = (hit - origin).length() if hit is not None else reach * .5
            self.bounce.set_pos(origin + direction * max(distance - min(1.0, distance * .45), .1))
            return
        # A point light lights the whole room: put the bounce near the middle of the space around it
        # (the walls, floor and ceiling it finds in six directions), so corners and things hidden from the
        # lamp still get some light. In the open the sideways rays find nothing and it sits over the ground.
        points = []
        for direction in (Vec3(1, 0, 0), Vec3(-1, 0, 0), Vec3(0, 1, 0), Vec3(0, -1, 0), Vec3(0, 0, -1), Vec3(0, 0, 1)):
            hit = _first_hit(self.world, origin, direction, reach, exclude=self.root)
            limit = min(reach * .5, 3.0) if direction.z == 0 else min(reach, 2.0)
            distance = min((hit - origin).length(), limit) if hit is not None else limit
            points.append(origin + direction * distance)
        center = Point3(sum((p.x for p in points), 0.0) / 6, sum((p.y for p in points), 0.0) / 6,
                        sum((p.z for p in points), 0.0) / 6)
        self.bounce.set_pos(center + (origin - center) * .25)

    def apply(self, level=1.0):
        settings = self.record['light']
        if self.bounce is not None:
            r, g, b = (float(c) for c in rgb(settings['color']))
            # Light picks up a little warmth bouncing off wood and floors; a gentle falloff (decay 1)
            # spreads it evenly until bounce_range cuts it off.
            bounce = settings.get('bounce', 0) * settings['intensity'] * level * .5
            self.bounce.node().set_color((r * bounce, g * bounce * .95, b * bounce * .85, 1))
            self.bounce.node().set_attenuation((1.0, max(settings.get('bounce_range', 6), .5), 0))
        if settings['type'] == 'spot':
            lens = self.light.get_lens()
            lens.set_fov(max(min(settings['angle'], 85), 1) * 2)
            lens.set_near_far(.05, max(settings['range'], .1))
            self.light.set_exponent(min(max(settings['softness'], 0), 1))
        shading.set_point_light(self.light, settings['color'], settings['intensity'] * level, settings['range'],
                                settings['decay'])

    def set_active(self, active):
        if active == self.on:
            return
        self.on = active
        shadows = spot_shadow.get()
        if active:
            self.world.app.render.set_light(self.path)
            if self.bounce is not None:
                self.world.app.render.set_light(self.bounce)
            if self.record['light']['type'] == 'spot' and self.record['light']['shadows'] and shadows is not None:
                shadows.add(self)
        else:
            self.world.app.render.clear_light(self.path)
            if self.bounce is not None:
                self.world.app.render.clear_light(self.bounce)
            if shadows is not None:
                shadows.remove(self)

    def update(self, delta):
        if not self.on:
            return
        settings = self.record['light']
        self.time += delta
        rate = max(settings['rate'], .05)
        level = 1.0
        if settings['mode'] == 'strobe':
            level = 1.0 if (self.time * rate) % 1 < .5 else 0.0
        elif settings['mode'] == 'pulse':
            level = .55 + .45 * math.sin(self.time * rate * 2 * math.pi)
        elif settings['mode'] == 'flicker':
            level = self._flicker(settings)
        if settings['mode'] != 'steady':
            self.apply(max(level, 0))

    def _flicker(self, settings):
        """Bursts of quick blinks at randomized intervals, over a constant shimmer."""
        now = self.time
        interval = max(settings.get('flicker_interval', 2.0), .05)
        spread = min(max(settings.get('flicker_random', .6), 0), 1)
        if self.next_blink is None:
            self.next_blink = now + interval * random.uniform(1 - spread, 1 + spread)
        if now >= self.next_blink:
            length = max(settings.get('flicker_duration', .08), .01)
            count = random.randint(1, max(int(settings.get('flicker_burst', 3)), 1))
            start, self.blinks = now, []
            for _ in range(count):
                end = start + length * random.uniform(.6, 1.4)
                self.blinks.append((start, end))
                start = end + length * random.uniform(.5, 1.5)  # a short lit gap between blinks of a burst
            # Counted from this burst's start (never before the burst is over).
            self.next_blink = max(now + interval * random.uniform(1 - spread, 1 + spread), start)
        level = 1.0
        if any(start <= now < end for start, end in self.blinks):
            level -= min(max(settings.get('flicker_depth', .85), 0), 1)
        shimmer = settings.get('flicker_shimmer', .12)
        wave = math.sin(now * 13.1) * .5 + math.sin(now * 31.7 + 1.7) * .3 + math.sin(now * 7.3 + .4) * .2
        return level * (1 - shimmer * (.5 + .5 * wave))

    def destroy(self):
        manager().remove(self)
        self.set_active(False)
        remove_update_callback(self.update)
        self.path.remove_node()
        if self.bounce is not None:
            self.bounce.remove_node()
        if self.marker is not None:
            self.marker.remove_node()

    @property
    def slots(self):
        """Shader light slots this light takes when on."""
        return 2 if self.bounce is not None else 1


class LightManager:
    """Switches on the nearest enabled placed lights (shader light slots are limited). Point light
    shadows are handed out by point_shadow.PointShadows."""

    def __init__(self, app):
        self.app = app
        self.lights = []
        self.clock = CHOOSE_EVERY
        add_update_callback(self.update)

    def add(self, light):
        self.lights.append(light)
        self.clock = CHOOSE_EVERY  # choose again on the next frame

    def remove(self, light):
        if light in self.lights:
            self.lights.remove(light)
        self.clock = CHOOSE_EVERY

    def update(self, delta):
        self.clock += delta
        if self.clock < CHOOSE_EVERY:
            return
        self.clock = 0.0
        eye = self.app.camera.get_pos(self.app.render)
        wanted = [light for light in self.lights if light.wanted and not light.path.is_empty()]
        wanted.sort(key=lambda light: (light.path.get_pos(self.app.render) - eye).length_squared())
        active, used = set(), 0
        for light in wanted:  # nearest first, within the light slot budget (a bounce takes a slot too)
            if used + light.slots > MAX_ACTIVE:
                break
            active.add(light)
            used += light.slots
        for light in self.lights:
            light.set_active(light in active)


def _first_hit(world, origin, direction, reach, exclude=None):
    """Nearest visible surface (objects, terrain) along a ray, or None."""
    from panda3d.core import (BitMask32, CollisionHandlerQueue, CollisionNode, CollisionSegment,
                              CollisionTraverser, GeomNode)
    from .. import interactables
    from .entities import EDITOR_PICK_MASK, SURFACE_MASK
    segment = CollisionSegment(origin, origin + direction * reach)
    node = CollisionNode('bounce-ray')
    node.add_solid(segment)
    # Visible geometry keeps GeomNode's default mask unless an object was made pickable.
    node.set_from_collide_mask(GeomNode.get_default_collide_mask() | interactables.PICK_MASK | EDITOR_PICK_MASK |
                               SURFACE_MASK)
    node.set_into_collide_mask(BitMask32.all_off())
    ray = world.app.render.attach_new_node(node)
    queue = CollisionHandlerQueue()
    traverser = CollisionTraverser('bounce')
    traverser.add_collider(ray, queue)
    traverser.traverse(world.root)
    ray.remove_node()
    queue.sort_entries()
    for entry in queue.entries:
        into = entry.get_into_node_path()
        if exclude is not None and (into == exclude or exclude.is_ancestor_of(into)):
            continue
        return entry.get_surface_point(world.app.render)
    return None


def manager():
    app = registry.get('app')
    existing = registry.get('lightManager')
    if existing is None:
        existing = LightManager(app)
        registry.add('lightManager', existing)
    return existing
