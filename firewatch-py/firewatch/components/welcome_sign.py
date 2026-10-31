"""Port of js/component/objects/welcomeSign/index.js."""
from .. import interactables, objects, registry
from ..coords import rotation_y_to_heading, three_to_panda

ROTATE_Y_RAD = 20  # the JS passes 20 to rotateY(), which takes radians


def draw(app):
    x, y, z = -4.2, 0, 1.7
    scale = .4

    model = objects.get('welcome-sign')
    model.set_h(rotation_y_to_heading(ROTATE_Y_RAD))
    model.set_scale(scale)
    model.set_pos(three_to_panda(x, registry.get('terrain').relative_y(x, y, z, scale), z))
    model.reparent_to(app.render)
    interactables.add(model)
