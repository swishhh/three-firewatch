"""Port of js/component/objects/tent/index.js."""
from .. import interactables, objects
from ..coords import three_to_panda


def draw(app):
    model = objects.get('tent')
    model.set_pos(three_to_panda(3.5, 0, -6))
    interactables.add(model)
    model.reparent_to(app.render)
