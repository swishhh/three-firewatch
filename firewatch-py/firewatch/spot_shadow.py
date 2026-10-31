"""Flashlight shadows: one perspective shadow map, from the lens of the flashlight that matters most
(the one in the player's hand, else the nearest one switched on), rendered by our own camera like
sun.py. scene.frag finds that spotlight among its light slots by position and filters the map.

The held flashlight moves with the camera, so its map renders every frame while it is on; a
flashlight lying in the world only re-renders when something changed (shadow_cache).
"""
from panda3d.core import (Camera, FrameBufferProperties, GraphicsOutput, GraphicsPipe, PerspectiveLens, SamplerState,
                          Texture, Vec3, WindowProperties)

from . import registry, settings, shading
from .shadow_cache import ShadowSchedule

NEAR = .05


class SpotShadow:
    def __init__(self, app):
        self.app = app
        self.beams = []  # FlashlightBeam objects that are on and want shadows
        self.current = None
        self.schedule = ShadowSchedule()

        self.texture = Texture('flash-shadow-map')
        properties = FrameBufferProperties()
        properties.set_depth_bits(24)
        properties.set_rgba_bits(0, 0, 0, 0)
        size = settings.get('gfx.flash_shadow_resolution')
        self.buffer = app.graphics_engine.make_output(
            app.pipe, 'flash-shadow', -1080, properties, WindowProperties.size(size, size),
            GraphicsPipe.BF_refuse_window | GraphicsPipe.BF_resizeable, app.win.get_gsg(), app.win,
        )
        self.buffer.add_render_texture(self.texture, GraphicsOutput.RTM_bind_or_copy, GraphicsOutput.RTP_depth)
        self.buffer.set_clear_depth_active(True)
        self.buffer.set_clear_depth(1)
        self.buffer.set_active(False)

        self.lens = PerspectiveLens()
        self.lens.set_near_far(NEAR, 25)
        camera = Camera('flash-shadow-camera', self.lens)
        camera.set_camera_mask(shading.SHADOW_CAMERA_MASK)
        camera.set_initial_state(shading.depth_state(reverse_cull=True))
        self.camera = app.render.attach_new_node(camera)
        self.buffer.make_display_region().set_camera(self.camera)

        self.sampler = SamplerState()
        self.sampler.set_minfilter(SamplerState.FT_shadow)
        self.sampler.set_magfilter(SamplerState.FT_shadow)
        self.sampler.set_wrap_u(SamplerState.WM_border_color)
        self.sampler.set_wrap_v(SamplerState.WM_border_color)
        self.sampler.set_border_color((1, 1, 1, 1))  # outside the map: lit

        render = app.render
        render.set_shader_input('flash_shadow_map', self.texture, self.sampler)
        render.set_shader_input('flashshadow', self.camera)  # no underscore: Panda splits trans_*_of_<name> on them
        render.set_shader_input('flash_shadow_enabled', 0.0)
        render.set_shader_input('flash_shadow_position', Vec3(0, 0, -1000))
        settings.subscribe(lambda _keys: self.apply_settings(), 'gfx.flash_shadow')
        self.apply_settings()
        # After every per-frame callback (the player and camera move in those) and before rendering
        # (igLoop, sort 50): the shadow camera must sit exactly where the light is in this frame, or
        # scene.frag can't match the light to its shadow map and drops the shadow while moving.
        app.task_mgr.add(self._sync, 'flash-shadow-sync', sort=45)

    def _sync(self, task):
        self.update(self.app.clock.get_dt())
        return task.cont

    def apply_settings(self):
        size = settings.get('gfx.flash_shadow_resolution')
        if (self.buffer.get_x_size(), self.buffer.get_y_size()) != (size, size):
            self.buffer.set_size(size, size)
        self.app.render.set_shader_input('flash_shadow_softness', settings.get('gfx.flash_shadow_softness'))
        self.app.render.set_shader_input('flash_shadow_texel', 1.0 / size)
        self.schedule.force()

    def add(self, beam):
        if beam not in self.beams:
            self.beams.append(beam)

    def remove(self, beam):
        if beam in self.beams:
            self.beams.remove(beam)

    def _choose(self):
        live = [beam for beam in self.beams if beam.on and not beam.path.is_empty()]
        if not live:
            return None
        held = [beam for beam in live if beam.held]
        if held:
            return held[0]
        eye = self.app.camera.get_pos(self.app.render)
        return min(live, key=lambda beam: (beam.path.get_pos(self.app.render) - eye).length_squared())

    def update(self, delta):
        beam = self._choose() if settings.get('gfx.flash_shadows') else None
        render = self.app.render
        if beam is None:
            if self.current is not None:
                render.set_shader_input('flash_shadow_enabled', 0.0)
                self.current = None
            self.buffer.set_active(False)
            return
        self.current = beam
        light = beam.settings
        self.lens.set_fov(max(min(light['angle'], 85), 1) * 2)
        self.lens.set_near_far(NEAR, max(light['range'], .5))
        self.camera.set_transform(beam.path.get_transform(render))
        position = beam.path.get_pos(render)
        render.set_shader_input('flash_shadow_enabled', 1.0)
        render.set_shader_input('flash_shadow_position', position)
        key = (tuple(round(v, 4) for v in position), tuple(round(v, 5) for v in beam.path.get_quat(render)),
               light['angle'], light['range'])
        self.buffer.set_active(self.schedule.due(delta, key))


def get(app=None):
    shadow = registry.get('flashShadow')
    if shadow is None and app is not None:
        shadow = SpotShadow(app)
        registry.add('flashShadow', shadow)
    return shadow
