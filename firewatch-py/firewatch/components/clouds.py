"""Port of js/component/objects/clouds/index.js: clouds drift along three.js +z (Panda -y) and fade
near both ends. Their positions and sizes come from the world's 'clouds' list (Panda3D coordinates,
x y z sx sy sz); color, speed, opacity and shadows are Sky settings.
"""
import random

from panda3d.core import TransparencyAttrib

from .. import objects, settings, shading, shadow_cache
from ..colors import rgba
from ..update import add_update_callback

MAX_Z = 18  # three.js z range, i.e. Panda -y
MIN_Z = -18
STEP = 0.007  # per 60 fps frame
OPACITY_THRESHOLD = 3
MODEL = 'obj/cloud.obj'


def generate(count, height=(12, 16), spread=16, size=(.25, .9), seed=None):
    """A new random cloud layer in the world's format."""
    rng = random.Random(seed)
    clouds = []
    for _ in range(count):
        scale = rng.uniform(*size)
        clouds.append([rng.uniform(-spread, spread), rng.uniform(-spread, spread), rng.uniform(*height),
                       scale, scale, scale])
    return clouds


class Clouds:
    def __init__(self, app):
        self.app = app
        self.root = app.render.attach_new_node('clouds')
        shading.set_unlit(self.root)  # MeshBasicMaterial
        shading.set_in_depth_prepass(self.root, False)
        self.clouds = []  # [node, x, y, z (three.js), step]
        settings.subscribe(self.apply, 'env.cloud')
        self.apply()
        shadow_cache.set_animated_source('clouds', self.casts_moving_shadows)
        add_update_callback(self.update)

    def casts_moving_shadows(self):
        return bool(self.clouds) and settings.get('env.clouds') and settings.get('env.cloud_shadows') and \
            settings.get('env.cloud_speed') > 0

    def build(self, records):
        for cloud in self.clouds:
            cloud[0].remove_node()
        self.clouds = []
        for x, y, z, sx, sy, sz in records:
            cloud = objects.instance(MODEL)
            cloud.set_pos(x, y, z)
            cloud.set_scale(sx, sy, sz)
            cloud.set_transparency(TransparencyAttrib.M_alpha)
            cloud.reparent_to(self.root)
            # Drift speed depended on the three.js z scale, which is Panda's y scale.
            self.clouds.append([cloud, x, z, -y, STEP / max(sy, 1e-3)])
        shadow_cache.invalidate()

    def apply(self, _keys=None):
        get = settings.get
        self.root.show() if get('env.clouds') else self.root.hide()
        self.root.set_color_scale(rgba(get('env.cloud_color')))  # the model's geoms carry a flat white
        shading.set_cast_shadow(self.root, get('env.cloud_shadows'))
        shadow_cache.invalidate()

    def update(self, delta):
        if not self.clouds or self.root.is_hidden():
            return
        speed = delta * 60 * settings.get('env.cloud_speed')
        opacity = settings.get('env.cloud_opacity')
        for cloud in self.clouds:
            node, x, y, z, step = cloud
            z += step * speed
            if z > MAX_Z:
                z = MIN_Z
            cloud[3] = z
            node.set_pos(x, -z, y)
            fade = min(max((MAX_Z - abs(z)) / OPACITY_THRESHOLD, 0), 1)
            node.set_alpha_scale(fade * opacity)

    def destroy(self):
        self.root.remove_node()
