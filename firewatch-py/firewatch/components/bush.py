"""Port of js/component/objects/bush/index.js."""
from .. import interactables, objects, shading
from ..coords import three_to_panda

MAP = [
    [11, 0, 4],
    [6.5, 0, -2.6],
    [1.7, 0, -8.7],
    [-2.9, 0, -2.4],
]


def draw(app):
    for x, y, z in MAP:
        model = objects.get('bush-tree-harvest')
        model.set_pos(three_to_panda(x, y, z))
        # The JS set `recieveShadow` (sic), so bushes never received shadows.
        shading.set_receive_shadow(model, False)
        interactables.add(model)
        model.reparent_to(app.render)
