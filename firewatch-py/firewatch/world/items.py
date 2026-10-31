"""Pick-up items: world objects of kind 'item' the player can take into the inventory (see
controls/inventory.py). A flashlight item carries a spotlight whose settings are edited in the
editor and saved with the item ('item' in the object record):

  type        'generic' or 'flashlight'
  label       name shown in the inventory
  beam        model axis the light shines along ('+z' = the model's up axis, ...)
  light       color, intensity, range (m), decay, angle (half the cone, degrees), softness (0 hard
              edge .. 1 soft), mode ('steady', 'flicker', 'strobe'), rate (strobe / flicker speed),
              starts_on, battery (minutes, 0 = endless), preview (show it in the editor)
"""
import math
import random

import numpy as np
from panda3d.core import LVector3f, Quat, Spotlight

from .. import library, shading
from ..colors import rgb

ITEM_TYPES = ('generic', 'flashlight', 'axe')
TOOL_AXES = ('auto',) + ('+z', '-z', '+y', '-y', '+x', '-x')
BEAM_AXES = ('+z', '-z', '+y', '-y', '+x', '-x')
LIGHT_MODES = ('steady', 'flicker', 'strobe')
HELD_LENGTH = .28  # meters a held item measures along its beam axis
GLOW_MATERIALS = ('glass', 'lens', 'led', 'bulb', 'light')

_AXIS_VECTORS = {'+x': (1, 0, 0), '-x': (-1, 0, 0), '+y': (0, 1, 0), '-y': (0, -1, 0), '+z': (0, 0, 1), '-z': (0, 0, -1)}


def new_item(item_type='generic', label=''):
    return {
        'type': item_type, 'label': label, 'beam': '+z',
        'light': {'color': '#fff1d6', 'intensity': 8.0, 'range': 25.0, 'decay': 1.5, 'angle': 22.0,
                  'softness': .45, 'mode': 'steady', 'rate': 8.0, 'starts_on': False, 'battery': 0.0,
                  'preview': True, 'shadows': True},
        # Tools (axe): hits dealt per swing, reach from the eye (m), seconds per swing, and which model
        # axes point from the grip to the head and out of the blade ('auto' guesses from the shape).
        'tool': {'damage': 1.0, 'reach': 2.4, 'swing_time': .55, 'head': 'auto', 'edge': 'auto'},
    }


def guess_item_type(model):
    name = model.lower().rsplit('/', 1)[-1]
    if any(word in name for word in ('flash', 'torch', 'lamp', 'lantern')):
        return 'flashlight'
    if 'axe' in name or 'hatchet' in name:
        return 'axe'
    return 'generic'


def is_item_model(model):
    return '/tools/' in model.lower() or guess_item_type(model) == 'flashlight'


def axis_vector(beam):
    return np.array(_AXIS_VECTORS.get(beam, (0, 0, 1)), np.float64)


def beam_tip(model, beam):
    """Model-space point where the light leaves the model: the bounding box end along the beam axis."""
    info = library.stats(model)
    low, high = np.array(info['min'], np.float64), np.array(info['max'], np.float64)
    axis = axis_vector(beam)
    center = (low + high) / 2
    reach = np.where(axis > 0, high, np.where(axis < 0, low, center))
    return np.where(axis != 0, reach, center), axis


def held_scale(model, beam):
    info = library.stats(model)
    length = float(np.abs((np.array(info['max']) - np.array(info['min'])) @ np.abs(axis_vector(beam))))
    return HELD_LENGTH / max(length, 1e-3)


def tool_axes(model, tool):
    """(head axis, edge axis) unit vectors in model space for a held tool: the head is at the end of
    the longest axis whose cross-section is widest, the edge is the head's longest sideways extent."""
    head, edge = tool.get('head', 'auto'), tool.get('edge', 'auto')
    parts = library.load_parts(model)
    points = np.concatenate([part.positions for part in parts]) if parts else np.zeros((1, 3))
    low, high = points.min(axis=0), points.max(axis=0)
    if head == 'auto':
        long_axis = int(np.argmax(high - low))
        length = high[long_axis] - low[long_axis]
        near_low = points[points[:, long_axis] < low[long_axis] + length * .2]
        near_high = points[points[:, long_axis] > high[long_axis] - length * .2]
        spread = lambda chunk: float(np.ptp(np.delete(chunk, long_axis, axis=1), axis=0).max()) if len(chunk) else 0.0
        vector = np.zeros(3)
        vector[long_axis] = -1.0 if spread(near_low) >= spread(near_high) else 1.0
    else:
        vector = axis_vector(head)
    if edge == 'auto':
        axis = int(np.argmax(np.abs(vector)))
        end = points[(points[:, axis] - points[:, axis].mean()) * vector[axis] > 0]
        end = end[np.abs(end[:, axis] - (high[axis] if vector[axis] > 0 else low[axis])) < (high[axis] - low[axis]) * .2]
        center = points.mean(axis=0)
        sideways = [i for i in range(3) if i != axis]
        if len(end):
            extents = {i: (end[:, i].max() - center[i], center[i] - end[:, i].min()) for i in sideways}
            best = max(sideways, key=lambda i: max(extents[i]))
            edge_vector = np.zeros(3)
            edge_vector[best] = 1.0 if extents[best][0] >= extents[best][1] else -1.0
        else:
            edge_vector = np.zeros(3)
            edge_vector[sideways[0]] = 1.0
    else:
        edge_vector = axis_vector(edge)
    return vector, edge_vector


def grip_point(model, head):
    """Model-space end of the handle (opposite the head)."""
    info = library.stats(model)
    low, high = np.array(info['min'], np.float64), np.array(info['max'], np.float64)
    center = (low + high) / 2
    axis = int(np.argmax(np.abs(head)))
    grip = center.copy()
    grip[axis] = low[axis] if head[axis] > 0 else high[axis]
    return grip


def suggested_scale(model):
    """Placement scale so an item model is hand-sized (models often come in meters-tall)."""
    info = library.stats(model)
    longest = float(max(np.array(info['max']) - np.array(info['min'])))
    size = .75 if guess_item_type(model) == 'axe' else .3
    return round(min(size / longest, 1.0), 3) if longest > 0 else 1.0


def aim(node, axis):
    """Rotate `node` so its local forward (+y, a Spotlight's direction) points along model `axis`."""
    quat = Quat()
    forward = LVector3f(0, 1, 0)
    target = LVector3f(*axis)
    rotation_axis = forward.cross(target)
    if rotation_axis.length() < 1e-6:
        quat.set_hpr((0, 0, 0) if target.y > 0 else (180, 0, 0))
    else:
        rotation_axis.normalize()
        quat.set_from_axis_angle(math.degrees(math.acos(max(-1, min(1, forward.dot(target))))), rotation_axis)
    node.set_quat(quat)


class FlashlightBeam:
    """A spotlight with flicker / strobe / battery behavior. Attach to a node, call update(dt)."""

    count = 0  # active beams (the scene shader has eight light slots, two used by the campfire)

    def __init__(self, render, parent, settings, held=False):
        self.render = render
        self.settings = settings
        self.held = held  # in the player's hand: gets the shadow map first
        self.light = Spotlight('flashlight')
        self.path = parent.attach_new_node(self.light)
        self.on = False
        self.drained = 0.0  # seconds of battery used
        self.time = random.random() * 10
        self.apply()

    def apply(self):
        light = self.settings
        from .. import spot_shadow
        shadows = spot_shadow.get()
        if shadows is not None and self.on:
            shadows.add(self) if light.get('shadows', True) else shadows.remove(self)
        self.light.get_lens().set_fov(max(min(light['angle'], 85), 1) * 2)
        self.light.get_lens().set_near_far(.05, max(light['range'], .1))
        self.light.set_exponent(min(max(light['softness'], 0), 1))  # scene.frag reads it as the edge softness
        self._set_level(1.0)

    def _set_level(self, level):
        light = self.settings
        shading.set_point_light(self.light, light['color'], light['intensity'] * level, light['range'], light['decay'])

    def set_on(self, on):
        if on == self.on:
            return
        if on and FlashlightBeam.count >= 6:
            return  # no free light slot
        self.on = on
        from .. import spot_shadow
        shadows = spot_shadow.get()
        if on:
            FlashlightBeam.count += 1
            self.render.set_light(self.path)
            if shadows is not None and self.settings.get('shadows', True):
                shadows.add(self)
        else:
            FlashlightBeam.count -= 1
            self.render.clear_light(self.path)
            if shadows is not None:
                shadows.remove(self)

    @property
    def battery_left(self):
        minutes = self.settings['battery']
        return 1.0 if minutes <= 0 else max(1 - self.drained / (minutes * 60), 0)

    def update(self, delta):
        if not self.on:
            return
        light = self.settings
        self.time += delta
        self.drained += delta
        level = 1.0
        battery = self.battery_left
        if battery <= 0:
            self.set_on(False)
            return
        if battery < .1:  # nearly empty: dimmer and sputtering
            level *= .4 + 6 * battery * (.6 + .4 * math.sin(self.time * 23))
        rate = max(light['rate'], .1)
        if light['mode'] == 'strobe':
            level *= 1.0 if (self.time * rate) % 1 < .5 else 0.0
        elif light['mode'] == 'flicker':
            wave = math.sin(self.time * rate * 2.1) * .5 + math.sin(self.time * rate * 5.3 + 1.7) * .3
            level *= .82 + .18 * wave + (-.6 if random.random() < .01 * rate / 8 else 0)
        self._set_level(max(level, 0))

    def destroy(self):
        self.set_on(False)
        self.path.remove_node()


def glow_nodes(node, model):
    """GeomNodes of a model built by objects.instance() whose material looks like a lens / LED."""
    glowing = []
    names = {part.name for part in library.load_parts(model)
             if any(word in part.material.lower() for word in GLOW_MATERIALS)}
    for geom_node in node.find_all_matches('**/+GeomNode'):
        if geom_node.get_name() in names:
            glowing.append(geom_node)
    return glowing


def set_glow(nodes, on, color):
    for node in nodes:
        if on:
            r, g, b = (float(c) for c in rgb(color))
            node.set_color_scale(r * 2.5, g * 2.5, b * 2.5, 1)  # HDR: bright enough to bloom
            node.set_shader_input('unlit', 1.0)
        else:
            node.clear_color_scale()
            node.clear_shader_input('unlit')



class PlacedItem:
    """The flashlight light of an item lying in the world: previewed in the editor, shining in the game
    when it starts switched on."""

    def __init__(self, world, root, record):
        from ..update import add_update_callback
        self.world = world
        self.record = record
        self.beam = None
        self.glow = []
        if record['item']['type'] != 'flashlight':
            return
        tip, axis = beam_tip(record['model'], record['item']['beam'])
        anchor = root.attach_new_node('beam')
        anchor.set_pos(*tip)
        aim(anchor, axis)
        self.beam = FlashlightBeam(world.app.render, anchor, record['item']['light'])
        root.set_light_off(self.beam.path)  # nor is a flashlight lying in the world
        content = root.find('*')
        self.glow = glow_nodes(content, record['model']) if not content.is_empty() else []
        self.refresh()
        add_update_callback(self.update)

    def refresh(self):
        if self.beam is None:
            return
        light = self.record['item']['light']
        self.beam.settings = light
        self.beam.apply()
        on = light['preview'] if self.world.mode == 'editor' else light['starts_on']
        self.beam.set_on(on)
        set_glow(self.glow, self.beam.on, light['color'])

    def update(self, delta):
        if self.beam is not None:
            self.beam.update(delta)

    def destroy(self):
        from ..update import remove_update_callback
        if self.beam is not None:
            remove_update_callback(self.update)
            self.beam.destroy()
            self.beam = None
