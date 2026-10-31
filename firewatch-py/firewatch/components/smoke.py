"""Port of js/component/objects/smoke/index.js: small black spheres rising along sine curves."""
import math
import random

from panda3d.core import GeomNode, TransparencyAttrib, Vec3

from .. import settings, shading
from ..colors import rgba
from ..coords import three_to_panda
from ..geometry import make_geom, sphere
from ..update import add_update_callback

SHARPNESS = 15
MAX_SIZE = .1
MIN_SIZE = .05
SPEED = 0.7
DISTANCE = 9
AMPLITUDE = .2
FREQUENCY = .8
COUNT = 20
SALT = .4
FADE_AWAY = True
OPACITY = .5
MIN_OPACITY = .4
RANDOMIZE_OPACITY = True
WIND_LEAN = .25


class SmokeParticle:
    def __init__(self, node_path, x, y, z, opacity):
        self.node_path = node_path
        self.position = [x, y, z]
        self.opacity = opacity
        self.active = False

    wind = Vec3(0)

    def activate(self, salt):
        self.salt = salt
        self.step = SPEED / 100 + random.random() / 1000  # per 60 fps frame
        self.amplitude = (AMPLITUDE * 10) / 2
        self.initial_opacity = self.opacity
        self.offset_x, self.offset_y, self.offset_z = self.position
        self.min = self.offset_y
        self.max = self.offset_y + DISTANCE
        self._create_graph()
        self.active = True
        self.node_path.show()

    def _create_graph(self):
        self.x_mod = -1 if random.random() > 0.5 else 1
        self.z_mod = -1 if random.random() > 0.5 else 1

    def _function(self, y):
        y -= self.offset_y
        return math.sin((y * self.amplitude * self.salt) * (y / (10 / self.amplitude)))

    def update(self, delta):
        y = self.position[1] + self.step * delta * 60
        if y >= self.max:
            y = self.min
            self._create_graph()

        offset = self._function(y)
        self.position = [offset * self.x_mod + self.offset_x, y, offset * self.z_mod + self.offset_z]

        if FADE_AWAY:
            value = self.max - y
            self.opacity = self.initial_opacity if value > self.opacity else value

        # The wind bends the column: the higher a particle rises, the further it drifts.
        lean = self.wind * (y - self.min) * WIND_LEAN
        self.node_path.set_pos(three_to_panda(*self.position) + lean)
        self.node_path.set_alpha_scale(min(max(self.opacity, 0), 1) * settings.get('env.smoke_opacity'))


def create_smoke(app, x, y, z):
    group = app.render.attach_new_node('smoke')
    group.set_transparency(TransparencyAttrib.M_alpha)
    shading.set_unlit(group)  # MeshBasicMaterial
    shading.set_cast_shadow(group, False)
    shading.set_in_depth_prepass(group, False)

    def apply(_keys=None):
        group.show() if settings.get('env.smoke') else group.hide()
        group.set_color(rgba(settings.get('env.smoke_color')))
        wind = math.radians(settings.get('env.wind_direction'))
        SmokeParticle.wind = Vec3(math.sin(wind), math.cos(wind), 0) * settings.get('env.wind_strength')

    settings.subscribe(apply, 'env.')
    apply()

    positions, normals, indices = sphere(1, SHARPNESS, SHARPNESS)
    geom = make_geom(positions, normals, indices)

    particles = []
    for _ in range(COUNT):
        node = GeomNode('smoke-particle')
        node.add_geom(geom)
        node_path = group.attach_new_node(node)
        node_path.set_scale(random.uniform(MIN_SIZE, MAX_SIZE))
        node_path.hide()

        particle = SmokeParticle(
            node_path, x, y + random.random() / 10, z,
            random.uniform(MIN_OPACITY, OPACITY) if RANDOMIZE_OPACITY else OPACITY,
        )
        node_path.set_pos(three_to_panda(*particle.position))
        node_path.set_alpha_scale(particle.opacity)
        particles.append(particle)

    # setInterval(): release one particle every 200 ms
    def release(task):
        inactive = [particle for particle in particles if not particle.active]
        if not inactive:
            return task.done
        inactive[0].activate(SALT * random.random())
        return task.again

    app.task_mgr.do_method_later(1 - FREQUENCY, release, 'smoke-release')

    def update(delta):
        for particle in particles:
            if particle.active:
                particle.update(delta)

    add_update_callback(update)
    return group
