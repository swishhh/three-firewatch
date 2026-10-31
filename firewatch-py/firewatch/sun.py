"""The sun (or moon) shadow map, rendered by our own camera rather than Panda's light system so the
scene shader can read raw depths for contact-hardening shadows (PCSS).

The shadowed area is a square around the camera, snapped to whole shadow-map texels so the
shadows don't shimmer while walking.
"""
import math

from panda3d.core import (Camera, FrameBufferProperties, GraphicsOutput, GraphicsPipe, OrthographicLens, Quat,
                          SamplerState, Texture, Vec3, WindowProperties, look_at)

from . import settings, shading
from .shadow_cache import ShadowSchedule
from .update import add_update_callback

NEAR = .1
FAR = 200
BACK = 100  # distance from the shadowed area's center back towards the sun
SHADOW_MODES = {'hard': 1, 'pcf': 2, 'pcss': 3}


class Sun:
    def __init__(self, app):
        self.app = app
        self.direction = Vec3(0, 0, 1)

        self.texture = Texture('sun-shadow-map')
        properties = FrameBufferProperties()
        properties.set_depth_bits(24)
        properties.set_rgba_bits(0, 0, 0, 0)
        size = settings.get('gfx.shadow_resolution')
        self.buffer = app.graphics_engine.make_output(
            app.pipe, 'sun-shadow', -1100, properties, WindowProperties.size(size, size),
            GraphicsPipe.BF_refuse_window | GraphicsPipe.BF_resizeable, app.win.get_gsg(), app.win,
        )
        self.buffer.add_render_texture(self.texture, GraphicsOutput.RTM_bind_or_copy, GraphicsOutput.RTP_depth)
        self.buffer.set_clear_depth_active(True)
        self.buffer.set_clear_depth(1)

        self.lens = OrthographicLens()
        self.lens.set_near_far(NEAR, FAR)
        camera = Camera('sun-shadow-camera', self.lens)
        camera.set_camera_mask(shading.SHADOW_CAMERA_MASK)
        camera.set_initial_state(shading.depth_state(reverse_cull=True))
        self.camera = app.render.attach_new_node(camera)
        self.buffer.make_display_region().set_camera(self.camera)

        # The same depth texture is read twice: hardware-filtered comparisons for the filter taps
        # and raw depths for the PCSS blocker search.
        compare = SamplerState()
        compare.set_minfilter(SamplerState.FT_shadow)
        compare.set_magfilter(SamplerState.FT_shadow)
        raw = SamplerState()
        raw.set_minfilter(SamplerState.FT_nearest)
        raw.set_magfilter(SamplerState.FT_nearest)
        for sampler in (compare, raw):
            sampler.set_wrap_u(SamplerState.WM_clamp)
            sampler.set_wrap_v(SamplerState.WM_clamp)

        self.samplers = (compare, raw)
        self.schedule = ShadowSchedule()
        self.enabled = True  # False while no sun or moon casts shadows
        self.targets = [app.render]  # the scene reads shadow_mode/strength, ao.frag does the lookups

        settings.subscribe(lambda _keys: self.apply_settings(), 'gfx.shadow')
        self.apply_settings()
        add_update_callback(self.update)

    def apply_settings(self):
        get = settings.get
        size = get('gfx.shadow_resolution')
        if (self.buffer.get_x_size(), self.buffer.get_y_size()) != (size, size):
            self.buffer.set_size(size, size)
        self.film = get('gfx.shadow_distance') * 2
        self.lens.set_film_size(self.film, self.film)
        self.schedule.force()

        inputs = {
            'shadow_mode': SHADOW_MODES[get('gfx.shadow_filter')] if get('gfx.shadows') else 0,
            'shadow_samples': get('gfx.shadow_samples'),
            'shadow_film': self.film,
            'shadow_resolution': float(size),
            'shadow_light_size': math.tan(math.radians(get('gfx.shadow_light_size') / 2)),
            'shadow_blur': get('gfx.shadow_blur'),
            'shadow_bias': get('gfx.shadow_bias'),
            'shadow_strength': get('gfx.shadow_strength'),
        }
        self.inputs = inputs
        for target in self.targets:
            self._bind(target)

    def bind(self, node_path):
        """Give the screen-space mask pass the shadow map and its parameters (replaces the previous
        one when the pipeline rebuilds)."""
        self.targets = [self.app.render, node_path]
        self._bind(node_path)

    def _bind(self, node_path):
        compare, raw = self.samplers
        node_path.set_shader_input('sun_shadow_compare', self.texture, compare)
        node_path.set_shader_input('sun_shadow_depth', self.texture, raw)
        node_path.set_shader_input('sun', self.camera)
        node_path.set_shader_input('shadow_depth_range', FAR - NEAR)
        for name, value in self.inputs.items():
            node_path.set_shader_input(name, value)

    def set_direction(self, direction):
        self.direction = Vec3(direction).normalized()

    def set_enabled(self, enabled):
        if enabled != self.enabled:
            self.enabled = enabled
            self.schedule.force()

    def update(self, delta):
        up = Vec3(0, 1, 0) if abs(self.direction.z) > .99 else Vec3(0, 0, 1)
        rotation = Quat()
        look_at(rotation, -self.direction, up)

        # Center on a point a little ahead of the viewer, snapped to the shadow map's texel grid.
        camera = self.app.camera
        forward = camera.get_quat(self.app.render).get_forward()
        forward.z = 0
        if forward.length_squared() > 1e-6:
            forward.normalize()
        focus = camera.get_pos(self.app.render) + forward * self.film * .25

        local = rotation.conjugate().xform(focus)
        texel = self.film / self.buffer.get_x_size()
        local.x = round(local.x / texel) * texel
        local.z = round(local.z / texel) * texel

        self.camera.set_quat(rotation)
        self.camera.set_pos(rotation.xform(local) + self.direction * BACK)

        active = settings.get('gfx.shadows') and self.enabled
        key = (tuple(round(v, 5) for v in self.camera.get_pos()), tuple(round(v, 6) for v in rotation))
        self.buffer.set_active(bool(active) and self.schedule.due(delta, key))
