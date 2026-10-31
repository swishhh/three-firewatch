"""Port of js/component/objects/grass/index.js (instanced grass)."""
from .. import objects, registry
from ..instancing import InstancedManager

SWAY_AMOUNT = .1  # blade tip displacement per unit of wind, see shaders/common.glsl

MAP = [
    [1.2, 0, -7.4, .5],
    [0, 0, -7.4, .5],
    [1.2, 0, -3.8, .5],
    [5.6, 0, -4.5, .5],
    [6.3, 0, -3, .5],
    [5.9, 0, -.8, .5],
    [9.6, 0, -0.5, .5],
    [10.6, 0, 1.9, .5],
    [10.6, 0, 3.5, .5],
    [-2.9, 0, -2, .6],
    [-4, 0, -.7, .6],
    [-.5, 0, -3.5, .6],
    [0, 0, 0, .6],
    [1.5, 0, -.7, .6],
    [2, -.1, .8, .6],
    [0, -.05, 1.5, .6],

    [8, 0, 1.3, .6],
    [9, 0, 2.1, .4],
    [8, 0, 2.6, .4],
    [9, 0, 1.3, .7],
    [6.5, 0, 0.7, .7],
    [6.5, -.05, 2.3, .8],
]


def draw(app):
    terrain = registry.get('terrain')
    instance = InstancedManager(app.render, objects.parts('grass'), MAP)
    instance.set_relate_callback(terrain.relate_y)
    instance.draw().set_shader_input('sway_amount', SWAY_AMOUNT)
    registry.add('grassInstance', instance)
