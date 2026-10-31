"""Graphics and environment settings: schema, presets and the JSON file they persist to.

Components read values with `settings.get(key)` and react to changes with
`settings.subscribe(callback, prefix)`. Changes are written to settings.json (next to main.py)
half a second after the last edit.
"""
import json
from dataclasses import dataclass, field
from .paths import PACKAGE_DIR

FILE = PACKAGE_DIR.parent / 'settings.json'
SAVE_DELAY = .5


@dataclass
class Setting:
    key: str
    label: str
    kind: str  # float, int, bool, choice, color
    default: object
    js: object = None  # value reproducing the three.js app; None = same as default
    min: float = 0
    max: float = 1
    step: float = 0
    options: tuple = ()
    labels: tuple = ()
    restart: bool = False


@dataclass
class Section:
    title: str


@dataclass
class Tab:
    name: str
    items: list = field(default_factory=list)


def F(key, label, default, min, max, js=None, step=0):
    return Setting(key, label, 'float', default, js, min, max, step)


def I(key, label, default, min, max, js=None):
    return Setting(key, label, 'int', default, js, min, max, 1)


def B(key, label, default, js=None, restart=False):
    return Setting(key, label, 'bool', default, js, restart=restart)


def C(key, label, default, options, labels=None, js=None, restart=False):
    return Setting(key, label, 'choice', default, js, options=tuple(options),
                   labels=tuple(labels or (str(option) for option in options)), restart=restart)


def Col(key, label, default, js=None):
    return Setting(key, label, 'color', default, js)


GRAPHICS = Tab('Graphics', [
    Section('Display'),
    C('gfx.fps_cap', 'Frame cap (F)', 0, (0, 30, 60, 120, 144, 165, 240),
      ('Off', '30', '60', '120', '144', '165', '240')),
    B('gfx.vsync', 'Vsync', False, restart=True),
    F('gfx.fov', 'Field of view', 40, 30, 90, step=1),
    C('gfx.render_scale', 'Render scale', 1.0, (.5, .75, 1.0, 1.25, 1.5, 2.0),
      ('50%', '75%', '100%', '125%', '150%', '200%')),
    B('gfx.overlay', 'Performance overlay', True),

    Section('Anti-aliasing'),
    C('gfx.msaa', 'MSAA', 8, (0, 2, 4, 8), ('Off', '2x', '4x', '8x'), js=0),
    B('gfx.fxaa', 'FXAA', False, js=True),
    F('gfx.sharpen', 'Sharpen', .25, 0, 1, js=0),

    Section('Shadows'),
    B('gfx.shadows', 'Shadows', True),
    C('gfx.shadow_resolution', 'Resolution', 4096, (1024, 2048, 4096, 8192), js=2048),
    C('gfx.shadow_filter', 'Filter', 'pcss', ('hard', 'pcf', 'pcss'),
      ('Hard', 'Soft (PCF)', 'Contact-hardening (PCSS)'), js='pcf'),
    F('gfx.shadow_light_size', 'Sun size (PCSS)', 2.0, .2, 8),  # degrees; bigger = softer far from the caster
    F('gfx.shadow_blur', 'Blur (PCF)', 1.5, .5, 6, js=1.5),  # shadow map texels
    C('gfx.shadow_samples', 'Samples', 32, (8, 16, 32, 64)),
    F('gfx.shadow_distance', 'Distance', 30, 10, 100, js=50, step=1),  # half-size of the shadowed area
    F('gfx.shadow_bias', 'Normal offset', 1.0, 0, 4),
    F('gfx.shadow_strength', 'Darkness', 1.0, 0, 1),
    B('gfx.fire_shadows', 'Campfire shadows', True),
    C('gfx.fire_shadow_resolution', 'Campfire resolution', 512, (256, 512, 1024, 2048)),
    F('gfx.fire_shadow_softness', 'Campfire softness', .03, 0, .15, step=.005),  # filter radius per unit of distance

    Section('Ambient occlusion'),
    B('gfx.ao', 'Ambient occlusion', True, js=False),
    F('gfx.ao_strength', 'Strength', 1.3, 0, 3),
    F('gfx.ao_radius', 'Radius', .7, .1, 3),
    C('gfx.ao_samples', 'Samples', 16, (8, 16, 32)),
    C('gfx.ao_resolution', 'Resolution', 'full', ('half', 'full'), ('Half', 'Full')),
    F('gfx.ao_direct', 'On direct light', .35, 0, 1),

    Section('Contact shadows'),
    B('gfx.contact_shadows', 'Contact shadows', True, js=False),
    F('gfx.contact_length', 'Ray length', .5, .05, 2),
    F('gfx.contact_strength', 'Strength', .85, 0, 1),

    Section('Lighting & detail'),
    B('gfx.smooth_terrain', 'Smooth terrain shading', True, js=False),
    C('gfx.terrain_detail', 'Terrain detail', 960, (480, 960, 1440), ('Low (JS)', 'High', 'Ultra'), js=480,
      restart=True),
    F('gfx.specular', 'Specular', 1.0, 0, 3),
    F('gfx.draw_distance', 'Draw distance', 80, 20, 200, js=54.77, step=1),

    Section('Tone & color'),
    C('gfx.tonemap', 'Tone mapping', 'agx', ('none', 'reinhard', 'aces', 'agx', 'filmic'),
      ('None (JS)', 'Reinhard', 'ACES', 'AgX', 'Filmic'), js='none'),
    F('gfx.exposure', 'Exposure', 1.55, .25, 4, js=1.0),
    F('gfx.temperature', 'Temperature', .25, -1, 1, js=0),
    F('gfx.tint', 'Tint', .05, -1, 1, js=0),
    F('gfx.saturation', 'Saturation', 1.1, 0, 2, js=1.0),
    F('gfx.contrast', 'Contrast', 1.05, .5, 1.5, js=1.0),
    F('gfx.brightness', 'Brightness', 1.0, .5, 1.5),

    Section('Effects'),
    B('gfx.bloom', 'Bloom', True, js=False),
    F('gfx.bloom_intensity', 'Bloom intensity', .7, 0, 3),
    F('gfx.bloom_threshold', 'Bloom threshold', .75, 0, 2),
    F('gfx.bloom_radius', 'Bloom radius', .65, 0, 1),
    F('gfx.vignette', 'Vignette', .35, 0, 1, js=0),
    F('gfx.vignette_softness', 'Vignette softness', .55, .1, 1),
    B('gfx.dof', 'Depth of field', False),
    F('gfx.dof_focus', 'Focus distance', 6, .5, 50),
    F('gfx.dof_range', 'Focus range', 10, .5, 50),
    F('gfx.dof_blur', 'Blur size', 1.0, 0, 3),
    F('gfx.grain', 'Film grain', 0, 0, .1, step=.005),
    B('gfx.dither', 'Dithering (no banding)', True, js=False),

    Section('Selection outline'),
    Col('gfx.outline_color', 'Color', '#ffffff'),
    I('gfx.outline_thickness', 'Thickness', 2, 1, 5),
])

ENVIRONMENT = Tab('Environment', [
    Section('Time of day'),
    C('env.time_mode', 'Mode', 'manual', ('manual', 'time'), ('Manual / preset', 'Time of day')),
    F('env.time_of_day', 'Time (hours)', 18.0, 0, 24),  # used in Time of day mode
    B('env.day_cycle', 'Day-night cycle', False),
    F('env.day_length', 'Day length (min)', 10, 1, 60, step=1),
    F('env.sun_elevation', 'Sun elevation', 54.7, -10, 90, step=.5),
    F('env.sun_azimuth', 'Sun azimuth', 132.3, 0, 360, step=1),
    Col('env.sun_color', 'Sun color', '#758aff'),
    F('env.sun_intensity', 'Sun intensity', 3.9, 0, 10),

    Section('Sky'),
    C('env.sky_mode', 'Sky', 'gradient', ('flat', 'gradient'), ('Flat color (JS)', 'Gradient'), js='flat'),
    Col('env.sky_color', 'Background (flat)', '#b79071'),
    Col('env.sky_top', 'Zenith', '#6f5b86'),
    Col('env.sky_horizon', 'Horizon', '#cc5200'),
    B('env.horizon_from_fog', 'Horizon follows fog', True),
    F('env.sun_glow', 'Sun glow', .8, 0, 3),
    F('env.sun_disk', 'Sun / moon disk', 1.0, 0, 3),
    F('env.stars', 'Stars', 0, 0, 1),

    Section('World light'),
    F('env.hemi_intensity', 'Intensity', .8, 0, 10),
    Col('env.hemi_sky', 'Sky color', '#ffffff'),
    Col('env.hemi_ground', 'Ground color', '#ffffff'),

    Section('Fog'),
    B('env.fog', 'Fog', True),
    F('env.fog_density', 'Density', .028, 0, .15, step=.001),
    Col('env.fog_color', 'Color', '#cc5200'),

    Section('Terrain'),
    Col('env.terrain_color', 'Color', '#002409'),
    C('env.terrain_shape', 'Hills', 'smooth', ('smooth', 'js'), ('Smooth', 'JS bumps'), js='js', restart=True),
    F('env.snow_cover', 'Snow cover', 0, 0, 1),

    Section('Weather & wind'),
    F('env.wind_strength', 'Wind', .4, 0, 2, js=0),
    F('env.wind_direction', 'Wind direction', 60, 0, 360, step=1),
    B('env.clouds', 'Clouds', True),
    F('env.cloud_speed', 'Cloud speed', 1.0, 0, 5),
    F('env.cloud_opacity', 'Cloud opacity', 1.0, 0, 1),
    B('env.snow', 'Snowfall', False),
    I('env.snow_amount', 'Snowflakes', 3000, 100, 12000),
    F('env.snow_speed', 'Fall speed', 1.0, .2, 3),
    F('env.snow_size', 'Flake size', .03, .01, .1, step=.005),

    Section('Campfire'),
    Col('env.fire_color', 'Light color', '#ca4316'),
    F('env.fire_intensity', 'Light intensity', 2, 0, 20),
    F('env.fire_distance', 'Light distance', 10, 0, 50),
    F('env.fire_decay', 'Light decay', .9, -1, 20),
    Col('env.glow_color', 'Glow color', '#992600'),
    F('env.glow_intensity', 'Glow intensity', 3, 0, 20),
    F('env.glow_distance', 'Glow distance', .5, 0, 50),
    F('env.glow_decay', 'Glow decay', 5.2, -1, 20),
    F('env.fire_flicker', 'Flicker', 1.0, 0, 3),
    B('env.smoke', 'Smoke', True),
    Col('env.smoke_color', 'Smoke color', '#000000'),
    F('env.smoke_opacity', 'Smoke opacity', 1.0, 0, 1),

    Section('Ambience'),
    F('env.master_volume', 'Master volume', 1.0, 0, 1),
    F('env.fire_volume', 'Fire volume', .5, 0, 1),
    B('env.fireflies', 'Fireflies', True, js=False),
    I('env.firefly_count', 'Firefly count', 70, 0, 400),
    Col('env.firefly_color', 'Firefly color', '#d6ff7a'),
    F('env.firefly_brightness', 'Firefly brightness', 4, 0, 15),
    B('env.bird', 'Bird', True),
])

TABS = (GRAPHICS, ENVIRONMENT)
SCHEMA = {item.key: item for tab in TABS for item in tab.items if isinstance(item, Setting)}

# Environment values driven by the time of day (interpolated between presets) in 'time' mode.
TIME_KEYS = (
    'env.sky_color', 'env.sky_top', 'env.sky_horizon', 'env.fog_color', 'env.fog_density',
    'env.sun_color', 'env.sun_intensity', 'env.hemi_sky', 'env.hemi_ground', 'env.hemi_intensity',
    'env.sun_glow', 'env.stars',
)

_SUMMER_EVENING = {
    'env.sky_color': '#b79071', 'env.sky_top': '#6f5b86', 'env.sky_horizon': '#cc5200',
    'env.fog_color': '#cc5200', 'env.fog_density': .028, 'env.sun_color': '#758aff', 'env.sun_intensity': 3.9,
    'env.sun_elevation': 54.7, 'env.sun_azimuth': 132.3, 'env.hemi_sky': '#ffffff', 'env.hemi_ground': '#ffffff',
    'env.hemi_intensity': .8, 'env.sun_glow': .8, 'env.stars': 0, 'env.terrain_color': '#002409',
    'env.snow': False, 'env.snow_cover': 0, 'env.fireflies': True,
}

ENVIRONMENT_PRESETS = {
    'Summer evening': dict(_SUMMER_EVENING, **{'env.sky_mode': 'gradient', 'env.time_mode': 'manual'}),
    'Summer evening (JS)': dict(_SUMMER_EVENING, **{
        'env.sky_mode': 'flat', 'env.time_mode': 'manual', 'env.wind_strength': 0, 'env.fireflies': False,
    }),
    'Golden hour': {
        'env.time_mode': 'manual', 'env.sky_mode': 'gradient',
        'env.sky_color': '#e0a46c', 'env.sky_top': '#5d7fb0', 'env.sky_horizon': '#f0a35e',
        'env.fog_color': '#e08a45', 'env.fog_density': .022, 'env.sun_color': '#ffb36b', 'env.sun_intensity': 3.6,
        'env.sun_elevation': 14, 'env.sun_azimuth': 245, 'env.hemi_sky': '#c4c9f0', 'env.hemi_ground': '#b07a48',
        'env.hemi_intensity': 1.5, 'env.sun_glow': 1.4, 'env.stars': 0, 'env.terrain_color': '#0a2a08',
        'env.snow': False, 'env.snow_cover': 0, 'env.fireflies': True,
    },
    'Day': {
        'env.time_mode': 'manual', 'env.sky_mode': 'gradient',
        'env.sky_color': '#9cc7e8', 'env.sky_top': '#4d8fd1', 'env.sky_horizon': '#bfd8e6',
        'env.fog_color': '#b6cfdc', 'env.fog_density': .016, 'env.sun_color': '#fff1dc', 'env.sun_intensity': 3.2,
        'env.sun_elevation': 58, 'env.sun_azimuth': 160, 'env.hemi_sky': '#cfe3ff', 'env.hemi_ground': '#6b5a3a',
        'env.hemi_intensity': 1.1, 'env.sun_glow': .5, 'env.stars': 0, 'env.terrain_color': '#1c3312',
        'env.snow': False, 'env.snow_cover': 0, 'env.fireflies': False,
    },
    'Warm blue': {
        'env.time_mode': 'manual', 'env.sky_mode': 'gradient',
        'env.sky_color': '#42a7f5', 'env.sky_top': '#2a64b8', 'env.sky_horizon': '#e8935a',
        'env.fog_color': '#7e8fb0', 'env.fog_density': .026, 'env.sun_color': '#8fb4ff', 'env.sun_intensity': 2.6,
        'env.sun_elevation': 20, 'env.sun_azimuth': 250, 'env.hemi_sky': '#9fbfff', 'env.hemi_ground': '#5a4a4a',
        'env.hemi_intensity': 1.0, 'env.sun_glow': .9, 'env.stars': .15, 'env.terrain_color': '#062a10',
        'env.snow': False, 'env.snow_cover': 0, 'env.fireflies': True,
    },
    'Winter': {
        'env.time_mode': 'manual', 'env.sky_mode': 'gradient',
        'env.sky_color': '#173e4f', 'env.sky_top': '#0f2a3a', 'env.sky_horizon': '#4f7183',
        'env.fog_color': '#3e6273', 'env.fog_density': .04, 'env.sun_color': '#b9d4ff', 'env.sun_intensity': 2.2,
        'env.sun_elevation': 25, 'env.sun_azimuth': 200, 'env.hemi_sky': '#cfe2ff', 'env.hemi_ground': '#8aa0b0',
        'env.hemi_intensity': 1.1, 'env.sun_glow': .3, 'env.stars': 0, 'env.terrain_color': '#2c4a3a',
        'env.snow': True, 'env.snow_cover': .75, 'env.fireflies': False,
    },
    'Night': {
        'env.time_mode': 'manual', 'env.sky_mode': 'gradient',
        'env.sky_color': '#0b1424', 'env.sky_top': '#050a18', 'env.sky_horizon': '#1d2a44',
        'env.fog_color': '#16223a', 'env.fog_density': .03, 'env.sun_color': '#8fb0ff', 'env.sun_intensity': 1.6,
        'env.sun_elevation': 40, 'env.sun_azimuth': 300, 'env.hemi_sky': '#7d93c9', 'env.hemi_ground': '#2a2a36',
        'env.hemi_intensity': .6, 'env.sun_glow': .4, 'env.stars': 1, 'env.terrain_color': '#002409',
        'env.snow': False, 'env.snow_cover': 0, 'env.fireflies': True,
    },
}

# Hour -> preset, interpolated in 'Time of day' mode (TIME_KEYS only).
TIME_KEYFRAMES = (
    (0, 'Night'), (5, 'Night'), (6.5, 'Golden hour'), (9, 'Day'), (15, 'Day'), (17.2, 'Golden hour'),
    (18.3, 'Summer evening'), (19.5, 'Warm blue'), (21, 'Night'), (24, 'Night'),
)

GRAPHICS_PRESETS = {
    'Enhanced': {},  # the defaults
    'Match JS': 'js',
    'Performance': {
        'gfx.msaa': 2, 'gfx.shadow_resolution': 2048, 'gfx.shadow_filter': 'pcf', 'gfx.shadow_samples': 16,
        'gfx.ao_samples': 8, 'gfx.ao_resolution': 'half', 'gfx.bloom': True, 'gfx.dof': False,
        'gfx.render_scale': 1.0,
    },
    'Ultra': {
        'gfx.msaa': 8, 'gfx.shadow_resolution': 8192, 'gfx.shadow_filter': 'pcss', 'gfx.shadow_samples': 64,
        'gfx.ao_samples': 32, 'gfx.ao_resolution': 'full', 'gfx.render_scale': 1.5,
    },
}


def _encode(setting, value):
    if setting.kind == 'float':
        return float(value)
    if setting.kind == 'int':
        return int(round(value))
    if setting.kind == 'bool':
        return bool(value)
    if setting.kind == 'color':
        return value if isinstance(value, str) else f'#{int(value):06x}'
    return value


def _valid(setting, value):
    if setting.kind in ('float', 'int'):
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if setting.kind == 'bool':
        return isinstance(value, bool)
    if setting.kind == 'color':
        return isinstance(value, str) and len(value) == 7 and value.startswith('#')
    return value in setting.options


class Store:
    def __init__(self):
        self.values = {key: _encode(setting, setting.default) for key, setting in SCHEMA.items()}
        self._listeners = []
        self._dirty_since = None
        self._clock = 0.0

    def get(self, key):
        return self.values[key]

    def set(self, key, value):
        self.update({key: value})

    def update(self, changes):
        changed = []  # (the module exports `set`, so avoid the builtin name in here)
        for key, value in changes.items():
            value = _encode(SCHEMA[key], value)
            if self.values[key] != value:
                self.values[key] = value
                changed.append(key)
        if changed:
            self._dirty_since = self._clock
            for prefix, callback in list(self._listeners):
                matching = {key for key in changed if prefix is None or key.startswith(prefix)}
                if matching:
                    callback(matching)
        return changed

    def subscribe(self, callback, prefix=None):
        """`callback(changed_keys)` after any change to keys starting with `prefix`."""
        self._listeners.append((prefix, callback))

    def defaults(self, prefix, js=False):
        return {
            key: (setting.js if js and setting.js is not None else setting.default)
            for key, setting in SCHEMA.items() if key.startswith(prefix)
        }

    def apply_graphics_preset(self, name):
        preset = GRAPHICS_PRESETS[name]
        values = self.defaults('gfx.', js=preset == 'js')
        if isinstance(preset, dict):
            values.update(preset)
        values['gfx.fps_cap'] = self.values['gfx.fps_cap']  # presets don't touch display choices
        values['gfx.vsync'] = self.values['gfx.vsync']
        values['gfx.overlay'] = self.values['gfx.overlay']
        self.update(values)

    def apply_environment_preset(self, name):
        self.update(ENVIRONMENT_PRESETS[name])

    def load(self):
        try:
            stored = json.loads(FILE.read_text())
        except (OSError, ValueError):
            return
        for key, value in stored.items():
            setting = SCHEMA.get(key)
            if setting is not None and _valid(setting, value):
                self.values[key] = _encode(setting, value)

    def save(self):
        FILE.write_text(json.dumps(self.values, indent=2, sort_keys=True) + '\n')
        self._dirty_since = None

    def tick(self, delta):
        """Debounced save, called every frame."""
        self._clock += delta
        if self._dirty_since is not None and self._clock - self._dirty_since >= SAVE_DELAY:
            self.save()


store = Store()
get = store.get
set = store.set
update = store.update
subscribe = store.subscribe
