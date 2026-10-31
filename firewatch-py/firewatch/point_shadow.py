"""Omnidirectional shadow maps for point lights: the campfire (the JS set campLight.castShadow = true)
and placed point lights with "Casts shadows" (world/lights.py), so a lamp inside a house only
lights the outside through the house's openings.

Each map: six cameras render each caster's distance from the light into a float cube map;
scene.frag compares against it with a soft filter. There are SLOTS maps; PointShadows hands them to
the shadow-casting point lights nearest the camera. A map re-renders only when its light moves or
the world changes (or nearby plants sway), so still lights cost nothing per frame.

Like three.js' PointLightShadow, nothing closer than `near` casts: the campfire uses half a meter so
its own logs don't block its light.
"""
import struct

from panda3d.core import (CullFaceAttrib, FrameBufferProperties, RenderState, SamplerState, ShaderAttrib, Texture,
                          Vec3)

from . import registry, settings, shading
from .shadow_cache import ShadowSchedule
from .update import add_update_callback

SLOTS = 3
CAMPFIRE_NEAR = .5  # three.js PointLightShadow camera near
LAMP_NEAR = .1
CLEAR_DISTANCE = 1000.0
CHOOSE_EVERY = .25


def empty_cube_map():
    """1x1 cube map reading 'no occluder anywhere' (bound to unused shadow slots)."""
    texture = Texture('no-point-shadow')
    texture.setup_cube_map(1, Texture.T_float, Texture.F_r32)
    texture.set_ram_image(struct.pack('<f', CLEAR_DISTANCE) * 6)
    return texture


class PointShadow:
    def __init__(self, app, slot):
        self.app = app
        self.slot = slot
        self.light_path = None
        self.far = 12.0
        self.near = CAMPFIRE_NEAR
        self.rig = app.render.attach_new_node(f'point-shadow-rig-{slot}')
        self.buffer = None
        self.position = None
        self.schedule = ShadowSchedule(self._sway_nearby)
        self._build()
        settings.subscribe(lambda _keys: self._build(), 'gfx.fire_shadow_resolution')
        settings.subscribe(lambda _keys: self.apply_settings(), 'gfx.fire_shadow')
        add_update_callback(self.update)

    def _input(self, name):
        return f'fire_shadow_{name}{self.slot}'

    def _build(self):
        if self.buffer is not None:
            self.app.graphics_engine.remove_window(self.buffer)
            self.rig.get_children().detach()
        properties = FrameBufferProperties()
        properties.set_float_color(True)
        properties.set_rgba_bits(32, 0, 0, 0)
        properties.set_depth_bits(24)
        size = settings.get('gfx.fire_shadow_resolution')
        self.buffer = self.app.win.make_cube_map(f'point-shadow-{self.slot}', size, self.rig,
                                                 shading.SHADOW_CAMERA_MASK, False, properties)
        self.buffer.set_sort(-1050 + self.slot)
        # Each face has its own display region with Panda's default grey clear (0.41), which would
        # read as an occluder 0.41 units away in every empty direction.
        for index in range(self.buffer.get_num_display_regions()):
            region = self.buffer.get_display_region(index)
            region.set_clear_color_active(True)
            region.set_clear_color((CLEAR_DISTANCE, 0, 0, 0))
        self.texture = self.buffer.get_texture()
        self.texture.set_minfilter(SamplerState.FT_linear)
        self.texture.set_magfilter(SamplerState.FT_linear)

        attrib = ShaderAttrib.make(shading.load_shader('distance'), 100)
        state = RenderState.make(attrib, CullFaceAttrib.make_reverse())  # back faces, like the sun's map
        for camera in self.rig.get_children():
            camera.node().get_lens().set_near_far(self.near, self.far)
            camera.node().set_initial_state(state)
        self.position = None  # new cameras need the light position
        self.app.render.set_shader_input(self._input('map'), self.texture)
        self.apply_settings()

    def _sway_nearby(self):
        """Only plants swaying within reach move this map's shadows (drifting clouds can't)."""
        world = registry.get('world')
        if world is None or self.position is None:
            return False
        return world.sways_near(self.position, self.far)

    def set_light(self, light_path, far=12.0, near=CAMPFIRE_NEAR):
        """Follow a light (None: this slot switches off)."""
        if light_path != self.light_path:
            self.light_path = light_path
            self.position = None
        if abs(far - self.far) > 1e-3 or abs(near - self.near) > 1e-6:
            self.far, self.near = far, near
            for camera in self.rig.get_children():
                camera.node().get_lens().set_near_far(near, far)
        self.apply_settings()

    @property
    def enabled(self):
        return settings.get('gfx.fire_shadows') and self.light_path is not None and not self.light_path.is_empty()

    def apply_settings(self):
        self.schedule.force()
        self.buffer.set_active(False)
        render = self.app.render
        render.set_shader_input(self._input('enabled'), 1.0 if self.enabled else 0.0)
        render.set_shader_input('fire_shadow_softness', settings.get('gfx.fire_shadow_softness'))

    def update(self, delta):
        if not self.enabled:
            self.buffer.set_active(False)
            return
        position = self.light_path.get_pos(self.app.render)
        self.buffer.set_active(self.schedule.due(delta, tuple(position)))
        if position == self.position:
            return
        self.position = position
        self.rig.set_pos(position)
        # The distance shader reads its light position from the cameras' state.
        for camera in self.rig.get_children():
            state = camera.node().get_initial_state()
            attrib = state.get_attrib(ShaderAttrib).set_shader_input('point_shadow_position', Vec3(position))
            camera.node().set_initial_state(state.set_attrib(attrib))
        self.app.render.set_shader_input(self._input('position'), Vec3(position))


class PointShadows:
    """Gives the SLOTS shadow maps to the shadow-casting point lights nearest the camera: campfires
    (their main light) and placed point lights with shadows switched on."""

    def __init__(self, app):
        self.app = app
        self.slots = [PointShadow(app, slot) for slot in range(SLOTS)]
        self.clock = CHOOSE_EVERY
        add_update_callback(self.update)

    def candidates(self):
        """(light node, far, near) of every point light that wants a shadow."""
        from .components.campfire import CampfireRig
        found = []
        for rig in CampfireRig.instances:
            if rig.lights:
                found.append((rig.lights[0], 12.0, CAMPFIRE_NEAR))
        lights = registry.get('lightManager')
        if lights is not None:
            for light in lights.lights:
                settings_ = light.record['light']
                if light.on and settings_['type'] == 'point' and settings_['shadows']:
                    found.append((light.path, max(settings_['range'], 1.0), LAMP_NEAR))
                if light.on and light.bounce is not None and settings_['shadows']:
                    found.append((light.bounce, max(settings_.get('bounce_range', 6.0), 1.0), LAMP_NEAR))
        return [candidate for candidate in found if not candidate[0].is_empty()]

    def update(self, delta):
        self.clock += delta
        if self.clock < CHOOSE_EVERY:
            return
        self.clock = 0.0
        eye = self.app.camera.get_pos(self.app.render)
        chosen = sorted(self.candidates(),
                        key=lambda candidate: (candidate[0].get_pos(self.app.render) - eye).length_squared())[:SLOTS]
        # Lights keep their slot while chosen, so their maps don't re-render for nothing.
        paths = [candidate[0] for candidate in chosen]
        free = [slot for slot in self.slots if slot.light_path not in paths]
        for path, far, near in chosen:
            current = next((slot for slot in self.slots if slot.light_path == path), None)
            if current is None:
                current = free.pop(0)
            current.set_light(path, far, near)
        for slot in free:
            if slot.light_path is not None:
                slot.set_light(None)


def get(app=None):
    shadows = registry.get('pointShadows')
    if shadows is None and app is not None:
        shadows = PointShadows(app)
        registry.add('pointShadows', shadows)
    return shadows
