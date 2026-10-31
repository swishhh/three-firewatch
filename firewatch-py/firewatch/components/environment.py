"""Port of js/component/light.js and objects/fog/index.js, grown into the whole environment:
sky dome, sun / moon, hemisphere world light, fog, terrain color, snow cover, wind, presets and
the time of day.

In 'Time of day' mode the colors in settings.TIME_KEYS come from the presets interpolated by hour
(settings.TIME_KEYFRAMES) and the sun follows the clock; in 'Manual' mode they are the values set
in the Environment tab.
"""
import math

from panda3d.core import GeomNode, Vec3

from .. import registry, settings, shading
from ..colors import rgb
from ..geometry import make_geom, sphere
from ..sun import Sun
from ..update import add_update_callback

SKY_RADIUS = 400  # inside the camera's far plane (500)


def _lerp(a, b, t):
    if isinstance(a, str):
        return rgb(a) * (1 - t) + rgb(b) * t
    return a * (1 - t) + b * t


def _as_rgb(value):
    return rgb(value) if isinstance(value, str) else value


def _smoothstep(edge0, edge1, x):
    t = min(max((x - edge0) / (edge1 - edge0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def direction_from_angles(elevation, azimuth):
    """Towards the sun; azimuth is clockwise from +Y (three.js -Z) when seen from above."""
    elevation, azimuth = math.radians(elevation), math.radians(azimuth)
    return Vec3(math.sin(azimuth) * math.cos(elevation), math.cos(azimuth) * math.cos(elevation), math.sin(elevation))


def sun_angles_for_hour(hour):
    """Rises in the east at 6:00, highest (70 degrees) at noon, sets in the west at 18:00."""
    elevation = 70 * math.sin((hour - 6) / 12 * math.pi)
    azimuth = (90 + (hour - 6) / 12 * 180) % 360
    return elevation, azimuth


def interpolate_time(hour):
    keyframes = settings.TIME_KEYFRAMES
    for (start, first), (end, second) in zip(keyframes, keyframes[1:]):
        if start <= hour <= end:
            t = (hour - start) / (end - start) if end > start else 0
            a, b = settings.ENVIRONMENT_PRESETS[first], settings.ENVIRONMENT_PRESETS[second]
            return {key: _lerp(a[key], b[key], t) for key in settings.TIME_KEYS}
    return {key: settings.ENVIRONMENT_PRESETS[keyframes[0][1]][key] for key in settings.TIME_KEYS}


class Environment:
    def __init__(self, app):
        self.app = app
        self.hour = settings.get('env.time_of_day')
        self.light_direction = Vec3(0, 0, 1)
        self.dirty = True

        self.sun = Sun(app)
        self.sky = self._build_sky()

        settings.subscribe(self._changed, 'env.')
        add_update_callback(self.update)

    def _build_sky(self):
        positions, normals, indices = sphere(SKY_RADIUS, 48, 24)
        node = GeomNode('sky')
        node.add_geom(make_geom(positions, normals, indices))
        sky = self.app.camera.attach_new_node(node)
        sky.set_compass(self.app.render)  # follows the camera, stays aligned with the world
        sky.set_two_sided(True)
        sky.set_bin('background', 0)
        sky.set_depth_write(False)
        sky.set_depth_test(False)
        sky.set_shader(shading.load_shader('sky'))
        shading.set_cast_shadow(sky, False)
        shading.set_in_depth_prepass(sky, False)
        return sky

    def _changed(self, keys):
        if 'env.time_of_day' in keys:
            self.hour = settings.get('env.time_of_day')
        self.dirty = True

    def values(self):
        """The environment as currently shown: settings, or the clock in 'Time of day' mode."""
        values = {key: settings.get(key) for key in settings.SCHEMA if key.startswith('env.')}
        if values['env.time_mode'] == 'time':
            values.update(interpolate_time(self.hour))
            values['env.sun_elevation'], values['env.sun_azimuth'] = sun_angles_for_hour(self.hour)
        return values

    def update(self, delta):
        if settings.get('env.time_mode') == 'time' and settings.get('env.day_cycle'):
            self.hour = (self.hour + delta * 24 / (settings.get('env.day_length') * 60)) % 24
            self.dirty = True
        if self.dirty:
            self.dirty = False
            self.apply(self.values())

    def apply(self, v):
        render = self.app.render

        # Sun by day; below the horizon the light (and the disk) becomes the moon, opposite it.
        elevation = v['env.sun_elevation']
        direction = direction_from_angles(elevation, v['env.sun_azimuth'])
        if elevation < 0 and v['env.time_mode'] == 'time':
            direction = -direction
        fade = _smoothstep(-1, 5, abs(elevation)) if v['env.time_mode'] == 'time' else _smoothstep(-2, 3, elevation)
        self.light_direction = direction
        self.sun.set_direction(direction)

        sun_color = _as_rgb(v['env.sun_color'])
        render.set_shader_input('sun_direction', direction)
        render.set_shader_input('sun_color', Vec3(*(sun_color * v['env.sun_intensity'] * fade)))
        render.set_shader_input('hemi_sky', Vec3(*_as_rgb(v['env.hemi_sky'])))
        render.set_shader_input('hemi_ground', Vec3(*_as_rgb(v['env.hemi_ground'])))
        render.set_shader_input('hemi_intensity', v['env.hemi_intensity'])

        fog_color = _as_rgb(v['env.fog_color'])
        render.set_shader_input('fog_color', Vec3(*fog_color))
        render.set_shader_input('fog_density', v['env.fog_density'])
        render.set_shader_input('use_fog', 1.0 if v['env.fog'] else 0.0)

        render.set_shader_input('snow_cover', v['env.snow_cover'])
        wind = math.radians(v['env.wind_direction'])
        render.set_shader_input('wind_direction', Vec3(math.sin(wind), math.cos(wind), 0))
        render.set_shader_input('wind_strength', v['env.wind_strength'])

        horizon = fog_color if v['env.horizon_from_fog'] else _as_rgb(v['env.sky_horizon'])
        brightness = max(sun_color.max(), 1e-3)
        sky_inputs = {
            'sky_gradient': 1.0 if v['env.sky_mode'] == 'gradient' else 0.0,
            'sky_flat': Vec3(*_as_rgb(v['env.sky_color'])),
            'sky_top': Vec3(*_as_rgb(v['env.sky_top'])),
            'sky_horizon': Vec3(*horizon),
            'sun_direction': direction,
            'disk_color': Vec3(*(sun_color / brightness * min(.5 + v['env.sun_intensity'] / 4, 1.5) * fade)),
            'sun_glow': v['env.sun_glow'],
            'sun_disk': v['env.sun_disk'],
            'stars': v['env.stars'],
        }
        for name, value in sky_inputs.items():
            self.sky.set_shader_input(name, value)

        terrain = registry.get('terrain')
        if terrain is not None:
            terrain.node_path.set_color(*_as_rgb(v['env.terrain_color']), 1)


def draw(app):
    registry.add('environment', Environment(app))
