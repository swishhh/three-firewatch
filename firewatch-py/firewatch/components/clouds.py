"""Port of js/component/objects/clouds/index.js: clouds drift along z and fade near both ends."""
from panda3d.core import TransparencyAttrib

from .. import objects, settings, shading
from ..coords import three_scale_to_panda, three_to_panda
from ..update import add_update_callback

# (position, scale) in three.js coordinates
MAP = [
    ((-1, 16, 1), (.7, .7, .7)),
    ((-10, 13, -3), (.6, .5, .6)),
    ((5, 14, 4), (.4, .4, .4)),
    ((9, 15, -4), (.8, .8, .8)),
    ((-2, 12.5, -10), (.3, .3, .3)),
    ((-5, 14, 8), (.9, .9, .9)),
    ((8, 13, 10), (.25, .25, .25)),
]

MAX_Z = 18
MIN_Z = -18
STEP = 0.007  # per 60 fps frame
OPACITY_THRESHOLD = 3


def make_cloud_movable(cloud, position, scale_z):
    x, y, z = position
    step = STEP / scale_z

    def update(delta):
        nonlocal z
        z += step * delta * 60 * settings.get('env.cloud_speed')
        if z > MAX_Z:
            z = MIN_Z
        cloud.set_pos(three_to_panda(x, y, z))
        fade = min(max((MAX_Z - abs(z)) / OPACITY_THRESHOLD, 0), 1)
        cloud.set_alpha_scale(fade * settings.get('env.cloud_opacity'))

    add_update_callback(update)


def draw(app):
    clouds = app.render.attach_new_node('clouds')
    shading.set_unlit(clouds)  # MeshBasicMaterial
    shading.set_in_depth_prepass(clouds, False)
    settings.subscribe(lambda _keys: clouds.show() if settings.get('env.clouds') else clouds.hide(), 'env.clouds')
    if not settings.get('env.clouds'):
        clouds.hide()

    for position, scale in MAP:
        cloud = objects.get('cloud')
        cloud.set_pos(three_to_panda(*position))
        cloud.set_scale(three_scale_to_panda(*scale))
        cloud.set_transparency(TransparencyAttrib.M_alpha)
        cloud.reparent_to(clouds)
        make_cloud_movable(cloud, position, scale[2])
