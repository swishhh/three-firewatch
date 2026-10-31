"""Omnidirectional shadow map for the campfire light (the JS set campLight.castShadow = true).

Six cameras render each caster's distance from the light into a float cube map; scene.frag
compares against it with a soft filter. Like three.js' PointLightShadow, nothing closer than NEAR
casts, so the fire's own logs don't block its light.
"""
from panda3d.core import CullFaceAttrib, FrameBufferProperties, RenderState, SamplerState, ShaderAttrib, Vec3

from . import settings, shading
from .update import add_update_callback

NEAR = .5  # three.js PointLightShadow camera near
CLEAR_DISTANCE = 1000.0


class PointShadow:
    def __init__(self, app, light_path, far):
        self.app = app
        self.light_path = light_path
        self.far = far
        self.rig = app.render.attach_new_node('point-shadow-rig')
        self.buffer = None
        self.position = None
        self._build()
        settings.subscribe(lambda _keys: self._build(), 'gfx.fire_shadow_resolution')
        settings.subscribe(lambda _keys: self.apply_settings(), 'gfx.fire_shadow')
        add_update_callback(self.update)

    def _build(self):
        if self.buffer is not None:
            self.app.graphics_engine.remove_window(self.buffer)
            self.rig.get_children().detach()
        properties = FrameBufferProperties()
        properties.set_float_color(True)
        properties.set_rgba_bits(32, 0, 0, 0)
        properties.set_depth_bits(24)
        size = settings.get('gfx.fire_shadow_resolution')
        self.buffer = self.app.win.make_cube_map('point-shadow', size, self.rig, shading.SHADOW_CAMERA_MASK, False,
                                                 properties)
        self.buffer.set_sort(-1050)
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
            camera.node().get_lens().set_near_far(NEAR, self.far)
            camera.node().set_initial_state(state)
        self.position = None  # new cameras need the light position
        self.app.render.set_shader_input('fire_shadow_map', self.texture)
        self.apply_settings()

    def apply_settings(self):
        enabled = settings.get('gfx.fire_shadows')
        self.buffer.set_active(enabled)
        render = self.app.render
        render.set_shader_input('fire_shadow_enabled', 1.0 if enabled else 0.0)
        render.set_shader_input('fire_shadow_softness', settings.get('gfx.fire_shadow_softness'))

    def update(self, _delta):
        position = self.light_path.get_pos(self.app.render)
        if position == self.position:
            return
        self.position = position
        self.rig.set_pos(position)
        # The distance shader reads its light position from the cameras' state.
        for camera in self.rig.get_children():
            state = camera.node().get_initial_state()
            attrib = state.get_attrib(ShaderAttrib).set_shader_input('point_shadow_position', Vec3(position))
            camera.node().set_initial_state(state.set_attrib(attrib))
        self.app.render.set_shader_input('fire_shadow_position', Vec3(position))
