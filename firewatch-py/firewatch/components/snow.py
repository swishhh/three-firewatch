"""Snowfall, replacing js/component/objects/snow/index.js (disabled in the JS app): GPU particles in
a box that follows the camera, drifting with the wind."""
import math

from panda3d.core import Vec3

from .. import settings
from ..particles import SNOW, ParticleSystem
from ..update import add_update_callback

BOX_SIZE = Vec3(40, 40, 16)
FALL_SPEED = 1.2
COLOR = (1, 1, 1, .75)


def draw(app):
    snow = ParticleSystem(app.render, 'snow', SNOW, seed=1)
    snow.set_inputs(box_size=BOX_SIZE, particle_color=COLOR, particle_intensity=1.0)

    def apply(_keys=None):
        enabled = settings.get('env.snow')
        snow.node_path.show() if enabled else snow.node_path.hide()
        snow.set_count(settings.get('env.snow_amount') if enabled else 0)
        wind = math.radians(settings.get('env.wind_direction'))
        strength = settings.get('env.wind_strength') * 1.5
        snow.set_inputs(
            particle_size=settings.get('env.snow_size'),
            drift=Vec3(math.sin(wind) * strength, math.cos(wind) * strength,
                       -FALL_SPEED * settings.get('env.snow_speed')),
        )

    def follow_camera(_delta):
        snow.set_inputs(box_center=app.camera.get_pos(app.render) + Vec3(0, 0, 2))

    settings.subscribe(apply, 'env.')
    apply()
    add_update_callback(follow_camera)
