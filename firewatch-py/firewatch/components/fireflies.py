"""Fireflies drifting around the camp: additive GPU particles bright enough to bloom. They swarm
around the first campfire of the world (or the world's center without one)."""
from panda3d.core import Point3, Vec3

from .. import registry, settings
from ..colors import rgba
from ..coords import three_to_panda
from ..particles import FIREFLIES, ParticleSystem

DEFAULT_CENTER = three_to_panda(2, 1.2, -3)
CAMPFIRE_OFFSET = Vec3(-.7, .5, 1.2)  # the JS box center relative to the JS campfire
BOX_SIZE = Vec3(16, 16, 2.2)
SIZE = .025


def draw(app):
    fireflies = ParticleSystem(app.render, 'fireflies', FIREFLIES, additive=True, seed=2)
    fireflies.set_inputs(box_center=DEFAULT_CENTER, box_size=BOX_SIZE, drift=Vec3(0), particle_size=SIZE)
    world = registry.get('world')

    def apply(_keys=None):
        enabled = settings.get('env.fireflies')
        fireflies.node_path.show() if enabled else fireflies.node_path.hide()
        fireflies.set_count(settings.get('env.firefly_count') if enabled else 0)
        fireflies.set_inputs(particle_color=rgba(settings.get('env.firefly_color')),
                             particle_intensity=settings.get('env.firefly_brightness'))

    def follow_campfire(section='objects'):
        if section not in ('objects', 'loaded'):
            return
        for item in world.objects:
            if item.data['kind'] == 'campfire':
                fireflies.set_inputs(box_center=Point3(*item.data['pos']) + CAMPFIRE_OFFSET)
                return
        fireflies.set_inputs(box_center=Point3(0, 0, world.terrain.height_at(0, 0) + 1.2))

    settings.subscribe(apply, 'env.firef')
    apply()
    world.add_listener(follow_campfire)
    follow_campfire()
