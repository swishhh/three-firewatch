"""Port of js/component/objects/rocks/index.js."""
from .. import interactables, objects, registry
from ..coords import rotation_y_to_heading, three_to_panda

POSITION = (10.2, -.6, -2)
ROTATE_Y_RAD = 90  # the JS passes 90 to rotateY(), which takes radians


def draw(app):
    terrain = registry.get('terrain')

    model = objects.get('rocks')
    model.set_h(rotation_y_to_heading(ROTATE_Y_RAD))
    model.set_pos(three_to_panda(*POSITION))
    model.reparent_to(app.render)

    model = objects.get('rocks-array')
    model.set_scale(1.4)
    model.set_pos(three_to_panda(-10, 0, -5))
    model.reparent_to(app.render)
    interactables.add(model)

    for name, (x, y, z) in (('small-rocks-array', (-3, 0, 5)), ('tiny-rock-vertical', (1, 0, 2))):
        scale = .5
        model = objects.get(name)
        model.set_scale(scale)
        model.set_pos(three_to_panda(x, terrain.relative_y(x, y, z, scale), z))
        model.reparent_to(app.render)
        interactables.add(model)
