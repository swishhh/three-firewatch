"""Port of js/component/light.js and objects/fog/index.js, grown into the whole environment:
sky dome, sun and moon, hemisphere world light, fog, snow cover, wind, presets and the time of day.

The sun and the moon are two directional lights, each with its own color, intensity, disk and glow.
One shadow map serves both: it follows whichever casting light is brighter (see `_caster`).

In 'Time of day' mode the colors in settings.TIME_KEYS come from the presets interpolated by hour
(settings.TIME_KEYFRAMES), the sun follows the clock and the moon rises opposite it; in 'Manual'
mode everything is as set in the Lighting and Sky tabs.
"""
import math

from panda3d.core import GeomNode, Vec3

from .. import registry, settings, shading, shadow_cache
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
        if keys & {'env.sun_elevation', 'env.sun_azimuth', 'env.moon_elevation', 'env.moon_azimuth', 'env.time_mode',
                   'env.time_of_day', 'env.sun_shadows', 'env.moon_shadows', 'env.sun_enabled', 'env.moon_enabled'}:
            shadow_cache.invalidate()

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
            shadow_cache.invalidate()
        if self.dirty:
            self.dirty = False
            self.apply(self.values())

    def apply(self, v):
        render = self.app.render
        time_mode = v['env.time_mode'] == 'time'

        # Sun: in Time of day mode it follows the clock; it fades out as it sets.
        sun_elevation = v['env.sun_elevation']
        sun_direction = direction_from_angles(sun_elevation, v['env.sun_azimuth'])
        sun_fade = _smoothstep(-1, 5, sun_elevation) if time_mode else _smoothstep(-2, 3, sun_elevation)
        if not v['env.sun_enabled']:
            sun_fade = 0.0
        sun_rgb = _as_rgb(v['env.sun_color'])
        sun_light = sun_rgb * v['env.sun_intensity'] * sun_fade

        # Moon: its own angles, or opposite the sun in Time of day mode.
        if time_mode:
            moon_elevation, moon_azimuth = -sun_elevation, (v['env.sun_azimuth'] + 180) % 360
        else:
            moon_elevation, moon_azimuth = v['env.moon_elevation'], v['env.moon_azimuth']
        moon_direction = direction_from_angles(moon_elevation, moon_azimuth)
        moon_visible = _smoothstep(-2, 3, moon_elevation) if v['env.moon_enabled'] else 0.0
        # In Time of day mode the moon light takes over once the sun is down.
        moon_fade = moon_visible * (1 - sun_fade) if time_mode else moon_visible
        moon_rgb = _as_rgb(v['env.moon_color'])
        moon_light = moon_rgb * v['env.moon_intensity'] * moon_fade

        caster = self._caster(v, sun_light, moon_light)
        self.light_direction = moon_direction if caster == 'moon' else sun_direction
        self.sun.set_direction(self.light_direction)
        self.sun.set_enabled(caster is not None)

        render.set_shader_input('sun_direction', sun_direction)
        render.set_shader_input('sun_color', Vec3(*sun_light))
        render.set_shader_input('moon_direction', moon_direction)
        render.set_shader_input('moon_color', Vec3(*moon_light))
        render.set_shader_input('sun_casts', 1.0 if caster == 'sun' else 0.0)
        render.set_shader_input('moon_casts', 1.0 if caster == 'moon' else 0.0)
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

        brightness = v['env.sky_brightness']
        horizon = fog_color if v['env.horizon_from_fog'] else _as_rgb(v['env.sky_horizon'])
        top = _as_rgb(v['env.sky_top'])
        # Water reflects the sky (flat mode reflects the flat color).
        if v['env.sky_mode'] == 'gradient':
            render.set_shader_input('reflect_sky_top', Vec3(*(top * brightness)))
            render.set_shader_input('reflect_sky_horizon', Vec3(*(horizon * brightness)))
        else:
            flat = _as_rgb(v['env.sky_color']) * brightness
            render.set_shader_input('reflect_sky_top', Vec3(*flat))
            render.set_shader_input('reflect_sky_horizon', Vec3(*flat))

        sun_max = max(sun_rgb.max(), 1e-3)
        moon_max = max(moon_rgb.max(), 1e-3)
        sun_disk = sun_rgb / sun_max * _as_rgb(v['env.sun_disk_color']) * min(.5 + v['env.sun_intensity'] / 4, 1.5)
        moon_disk = _as_rgb(v['env.moon_disk_color']) * (.6 + .4 * moon_rgb / moon_max) * min(.6 + v['env.moon_intensity'], 1.5)
        sky_inputs = {
            'sky_gradient': 1.0 if v['env.sky_mode'] == 'gradient' else 0.0,
            'sky_flat': Vec3(*_as_rgb(v['env.sky_color'])),
            'sky_top': Vec3(*top),
            'sky_horizon': Vec3(*horizon),
            'sky_curve': v['env.sky_curve'],
            'sky_brightness': brightness,
            'sun_direction': sun_direction,
            'disk_color': Vec3(*(sun_disk * sun_fade)),
            'sun_glow': v['env.sun_glow'],
            'sun_disk': v['env.sun_disk'],
            'moon_direction': moon_direction,
            'moon_disk_color': Vec3(*(moon_disk * moon_visible)),
            'moon_glow': v['env.moon_glow'],
            'moon_disk': v['env.moon_disk'],
            'stars': v['env.stars'],
            'star_density': v['env.star_density'],
        }
        for name, value in sky_inputs.items():
            self.sky.set_shader_input(name, value)

    @staticmethod
    def _caster(v, sun_light, moon_light):
        """The light that owns the shadow map: the brighter of the sun and moon that cast shadows."""
        candidates = []
        if v['env.sun_shadows'] and sun_light.max() > 1e-4:
            candidates.append((float(sun_light.max()), 'sun'))
        if v['env.moon_shadows'] and moon_light.max() > 1e-4:
            candidates.append((float(moon_light.max()), 'moon'))
        return max(candidates)[1] if candidates else None


def draw(app):
    registry.add('environment', Environment(app))
