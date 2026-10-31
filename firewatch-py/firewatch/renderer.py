"""Port of js/component/renderer/index.js: hide `distance_render` models far from the camera."""
from . import registry, settings
from .update import add_update_callback


def init_scene_renderer(app):
    world = registry.get('world')

    def update(_delta):
        camera = app.camera.get_pos(app.render)
        limit = settings.get('gfx.draw_distance') ** 2  # the JS hid them beyond a squared distance of 3000
        for node, anchor, center in world.distance_nodes():
            position = center if center is not None else anchor.get_pos(app.render)
            if (position - camera).length_squared() < limit:
                node.show()
            else:
                node.hide()

    add_update_callback(update)
