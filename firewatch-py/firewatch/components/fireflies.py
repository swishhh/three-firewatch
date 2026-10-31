"""Fireflies drifting around the camp: additive GPU particles bright enough to bloom."""
from panda3d.core import Vec3

from .. import settings
from ..colors import rgba
from ..coords import three_to_panda
from ..particles import FIREFLIES, ParticleSystem

CENTER = three_to_panda(2, 1.2, -3)
BOX_SIZE = Vec3(16, 16, 2.2)
SIZE = .025


def draw(app):
    fireflies = ParticleSystem(app.render, 'fireflies', FIREFLIES, additive=True, seed=2)
    fireflies.set_inputs(box_center=CENTER, box_size=BOX_SIZE, drift=Vec3(0), particle_size=SIZE)

    def apply(_keys=None):
        enabled = settings.get('env.fireflies')
        fireflies.node_path.show() if enabled else fireflies.node_path.hide()
        fireflies.set_count(settings.get('env.firefly_count') if enabled else 0)
        fireflies.set_inputs(particle_color=rgba(settings.get('env.firefly_color')),
                             particle_intensity=settings.get('env.firefly_brightness'))

    settings.subscribe(apply, 'env.firef')
    apply()
