"""Port of js/component/renderer/index.js: hide `distance_render` models far from the camera."""
from . import settings
from .objects import DISTANCE_RENDER_TAG
from .update import add_update_callback


def init_scene_renderer(app):
    # Every distance_render model exists once the components have drawn, so search the graph once.
    models = list(app.render.find_all_matches(f'**/={DISTANCE_RENDER_TAG}'))

    def update(_delta):
        camera = app.camera.get_pos(app.render)
        limit = settings.get('gfx.draw_distance') ** 2  # the JS hid them beyond a squared distance of 3000
        for model in models:
            if (model.get_pos(app.render) - camera).length_squared() < limit:
                model.show()
            else:
                model.hide()

    add_update_callback(update)
