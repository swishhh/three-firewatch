"""Snowfall, replacing js/component/objects/snow/index.js (disabled in the JS app): GPU particles in
a box that follows the camera, drifting with the wind.

Flakes land: an orthographic camera above the player renders the depth of everything solid around
it (terrain, objects, tree crowns; see shading.SNOW_CAMERA_MASK) into a small map, re-rendered only
when the player moved a few meters or the world changed. shaders/particles.vert reads that map to
find where each flake's path meets a surface; the flake stops there, fades out over env.snow_melt
seconds (first darkening to env.snow_settled_color) and falls again from the top somewhere else.
"""
import math

from panda3d.core import (Camera, FrameBufferProperties, GraphicsOutput, GraphicsPipe, OrthographicLens,
                          SamplerState, Texture, Vec3, WindowProperties)

from .. import settings, shading, shadow_cache
from ..colors import rgba
from ..particles import SNOW, ParticleSystem
from ..update import add_update_callback

BOX_SIZE = Vec3(40, 40, 16)
FALL_SPEED = 1.2
COLOR = (1, 1, 1, .75)
SHAPES = {'round': 0, 'soft': 1, 'crystal': 2, 'star': 3, 'square': 4}
MAP_SIZE = 512  # texels across the map: about 9 cm each
MAP_ABOVE = 40.0  # the map camera hangs this far above the player
MAP_DEPTH = 90.0  # and sees this far down
RECENTER = 4.0  # meters the player moves before the map follows
MAP_EXTENT = BOX_SIZE.x + 2 * RECENTER  # covers the snow box wherever the player is within RECENTER


class SnowMap:
    def __init__(self, app):
        self.app = app
        self.texture = Texture('snow-surface')
        properties = FrameBufferProperties()
        properties.set_depth_bits(24)
        properties.set_rgba_bits(0, 0, 0, 0)
        self.buffer = app.graphics_engine.make_output(
            app.pipe, 'snow-surface', -1070, properties, WindowProperties.size(MAP_SIZE, MAP_SIZE),
            GraphicsPipe.BF_refuse_window, app.win.get_gsg(), app.win)
        self.buffer.add_render_texture(self.texture, GraphicsOutput.RTM_bind_or_copy, GraphicsOutput.RTP_depth)
        self.buffer.set_clear_depth_active(True)
        self.buffer.set_clear_depth(1)
        self.buffer.set_active(False)
        for setter in (self.texture.set_minfilter, self.texture.set_magfilter):
            setter(SamplerState.FT_linear)
        self.texture.set_wrap_u(SamplerState.WM_clamp)
        self.texture.set_wrap_v(SamplerState.WM_clamp)

        lens = OrthographicLens()
        lens.set_film_size(MAP_EXTENT, MAP_EXTENT)
        lens.set_near_far(1.0, MAP_DEPTH)
        camera = Camera('snow-surface-camera', lens)
        camera.set_camera_mask(shading.SNOW_CAMERA_MASK)
        camera.set_initial_state(shading.depth_state())
        self.camera = app.render.attach_new_node(camera)
        self.camera.set_hpr(0, -90, 0)  # straight down; screen up is +y, right is +x
        self.buffer.make_display_region().set_camera(self.camera)
        self.center = None
        self.version = None
        self.enabled = False

    def update(self):
        """Re-render when the player left the mapped area's middle or the world changed."""
        if not self.enabled:
            self.buffer.set_active(False)
            return
        eye = self.app.camera.get_pos(self.app.render)
        moved = self.center is None or max(abs(eye.x - self.center[0]), abs(eye.y - self.center[1])) > RECENTER
        changed = self.version != shadow_cache.version()
        if moved:
            self.center = (round(eye.x), round(eye.y), eye.z + MAP_ABOVE)
        if moved or changed:
            self.version = shadow_cache.version()
            x, y, top = self.center
            self.camera.set_pos(x, y, top)
            self.buffer.set_active(True)
        else:
            self.buffer.set_active(False)

    def inputs(self):
        x, y, top = self.center if self.center else (0, 0, 0)
        return {'snow_map': self.texture, 'snow_map_area': (x - MAP_EXTENT / 2, y - MAP_EXTENT / 2, MAP_EXTENT,
                                                            MAP_EXTENT),
                'snow_map_depth': (top, 1.0, MAP_DEPTH)}


def draw(app):
    snow = ParticleSystem(app.render, 'snow', SNOW, seed=1)
    snow.set_inputs(box_size=BOX_SIZE, particle_color=COLOR, particle_intensity=1.0)
    surface = SnowMap(app)

    def apply(_keys=None):
        enabled = settings.get('env.snow')
        snow.node_path.show() if enabled else snow.node_path.hide()
        snow.set_count(settings.get('env.snow_amount') if enabled else 0)
        surface.enabled = enabled and settings.get('env.snow_settle')
        wind = math.radians(settings.get('env.wind_direction'))
        strength = settings.get('env.wind_strength') * 1.5
        snow.set_inputs(
            particle_size=settings.get('env.snow_size'),
            drift=Vec3(math.sin(wind) * strength, math.cos(wind) * strength,
                       -FALL_SPEED * settings.get('env.snow_speed')),
            snow_settle=1.0 if surface.enabled else 0.0,
            snow_melt=settings.get('env.snow_melt'),
            particle_color=rgba(settings.get('env.snow_color'), settings.get('env.snow_opacity')),
            settled_color=rgba(settings.get('env.snow_settled_color'), settings.get('env.snow_opacity')),
            snow_shape=SHAPES[settings.get('env.snow_shape')],
            snow_softness=settings.get('env.snow_softness'),
            snow_spin=settings.get('env.snow_spin'),
            snow_streak=settings.get('env.snow_streak'),
        )

    def follow_camera(_delta):
        snow.set_inputs(box_center=app.camera.get_pos(app.render) + Vec3(0, 0, 2))
        surface.update()
        if surface.enabled:
            snow.set_inputs(**surface.inputs())

    snow.set_inputs(snow_settle=0.0, snow_melt=3.0, settled_color=COLOR, snow_shape=0, snow_softness=.5,
                    snow_spin=0.0, snow_streak=0.0, **surface.inputs())
    settings.subscribe(apply, 'env.')
    apply()
    add_update_callback(follow_camera)
