"""Port of js/component/objects/picnicTable/index.js."""
import math

from .. import interactables, objects
from ..coords import rotation_y_to_heading, three_to_panda


def draw(app):
    model = objects.get('picnic-table')
    model.set_h(rotation_y_to_heading(math.pi / 1.2))
    model.set_pos(three_to_panda(4.7, 0, -2))
    model.set_scale(.25)
    model.reparent_to(app.render)
    interactables.add(model)
