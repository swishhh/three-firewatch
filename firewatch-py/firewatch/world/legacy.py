"""The scene of the JS app (and of the first Python version) as a world save: what the component MAP
arrays used to place at startup. Builds the 'default' world on first run, together with the
environment values from a version 1 settings.json.

All MAP data below is in three.js coordinates (Y up), copied from the JS components.
"""
import math

from .. import objects, settings
from ..coords import rotation_y_to_heading, three_scale_to_panda, three_to_panda
from .document import WorldDocument, new_foliage, new_object
from .terrain import DEFAULT_SEGMENTS, DEFAULT_SIZE

# js/component/objects/terrain: (center x, center z, radius, strength)
CIRCLES = [
    # ground
    (-1, 10, 2, .3),
    (-.5, 9, 2, .3),
    (0, 8, 2, .2),
    (1.5, 8, 2, .2),

    (-5, 1, 2, .2),
    (-11, 1, 2, .3),
    (-11, 1.5, 2, .25),
    (-11, 2, 2, .25),
    (-9, 2, 2, .15),
    (-13, 2, 2, .2),
    (-14, 1, 2, .3),

    (-5, 8, 2, .3),
    (-6, 8.5, 2, .25),
    (-7, 8, 2, .25),
    (-8, 8, 2, .2),
    (-7, 9, 2, .25),
    (-8, 8, 2, .3),

    (1, 0, 2, .35),
    (1, 0.5, 2, .15),
    (.5, 1.5, 2, .15),
    (.5, 1.8, 2, .1),
    (7, 1.5, 2, .1),
    (8, 2, 2, .25),
    (8, 3, 2, .3),
    (9, 4, 2, .2),

    (15, 15, 5, .25),
    (14, 14, 4, .25),
    (12, 12, 4, .25),
    (12, 13, 4, .25),
    (15, 11, 4, .25),
    (13, 13, 4, .7),
    (9, 13, 2, .7),
]


# js/component/objects/tree (instanced): [x, y, z, scale]
TREES = [
    [0, 0, 0, 1],
    [5, 0, -9.5],
    [1.6, 0, -0.7, 0.6],
    [1.8, 0, 1.7, 0.4],
    [5.5, 0, .5, 0.6],
    [2.9, 0, -9.5, 0.7],
    [1.8, 0, -11, 1.1],
    [4, 0, -11.4, 1.3],
    [-1.8, 0, -4, 0.9],
    [-1.8, 0, -2.5, 0.5],
    [-.4, 0, -4.5, 0.65],
    [1, 0, -4.5, 0.9],
    [6, 0, -4, 0.81],
    [0, 0, -6.5, 1.2],
    [-2.5, 0, -6.6, 0.9],
    [-10.5, 0, 2.5, 1],
    [-4.5, 0, 0, .8],
    [-6, 0, -7, .4],
    [-6.9, 0, -6.4, .2],
    [-7.3, 0, -7.1, .4],
    [-13, 0, 2, .7],
    [-4.5, 0, -7.4, .74],
    [-4.5, 0, -9, .9],
    [-2.5, 0, -9.3, 1.1],
    [0, 0, -9, 1.3],
    [7.4, 0, -9, 1.2],
    [5.6, 0, -7, .95],
    [12, 0, -7.5, 1.2],
    [-8.3, 0, -3.8, 1],
    [-9, 0, -5.4, .5],
    [-5.5, 0, -12.5, 1.3],
    [-8.5, 0, -13, 1.6],
    [-14, 0, -.5, 1.1],
    [-10.1, 0, -2.2, .9],
    [-11, 0, 0, 1],
    [-5.5, 0, 1.5, .6],
    [-8, 0, 9.5, 1.3],
    [-9, 0, 7, .86],
    [-4.2, 0, 6.4, .77],
    [-6.2, 0, 6.9, 1.1],
    [-2.2, 0, 7.1, 1.3],
    [.3, 0, 7.5, .6],
    [-.5, 0, 9.1, .9],
    [11.6, 0, 2, 1.3],
    [13, 0, -5, 1.5],
    [-17, 0, -2.5, 1.55],
    [-18, 0, -5.5, 1.65],
    [-17.5, 0, -8.5, 1.45],
    [-17.5, 0, -12.5, 1.58],
    [-20.5, 0, -8.5, 1.39],
    [-14, 0, -13.5, 1.68],
    [-11.5, 0, -15, 1.7],
    [12, .1, 12, 1.3],
    [10, 0, 10, 1],
    [8.5, 0, 13, 0.8],
    [15, 0, 9, 1.6],
    [7, 0, 2.5, 0.7],
]


# js/component/objects/grass (instanced): [x, y, z, scale]
GRASS = [
    [1.2, 0, -7.4, .5],
    [0, 0, -7.4, .5],
    [1.2, 0, -3.8, .5],
    [5.6, 0, -4.5, .5],
    [6.3, 0, -3, .5],
    [5.9, 0, -.8, .5],
    [9.6, 0, -0.5, .5],
    [10.6, 0, 1.9, .5],
    [10.6, 0, 3.5, .5],
    [-2.9, 0, -2, .6],
    [-4, 0, -.7, .6],
    [-.5, 0, -3.5, .6],
    [0, 0, 0, .6],
    [1.5, 0, -.7, .6],
    [2, -.1, .8, .6],
    [0, -.05, 1.5, .6],

    [8, 0, 1.3, .6],
    [9, 0, 2.1, .4],
    [8, 0, 2.6, .4],
    [9, 0, 1.3, .7],
    [6.5, 0, 0.7, .7],
    [6.5, -.05, 2.3, .8],
]


# js/component/objects/clouds: (position, scale)
CLOUDS = [
    ((-1, 16, 1), (.7, .7, .7)),
    ((-10, 13, -3), (.6, .5, .6)),
    ((5, 14, 4), (.4, .4, .4)),
    ((9, 15, -4), (.8, .8, .8)),
    ((-2, 12.5, -10), (.3, .3, .3)),
    ((-5, 14, 8), (.9, .9, .9)),
    ((8, 13, 10), (.25, .25, .25)),
]


# Single objects: (JS name, kind, three.js position, rotateY radians, scale on top of the library's, height
# rule, extra fields)
# Height rule: None = as given, 'relative' = terrain.addRelativeObject() (first vertex under it).
OBJECTS = [
    ('rocks', 'model', (10.2, -.6, -2), 90, 1, None,  # rotateY(90): radians
     {'interactable': False, 'collision': {'shape': 'mesh', 'scale': [1.0, 1.0, 1.0], 'offset': [0.0, 0.0, 0.0]}}),
    ('rocks-array', 'model', (-10, 0, -5), 0, 1.4, None, {}),
    ('small-rocks-array', 'model', (-3, 0, 5), 0, .5, 'relative', {}),
    ('tiny-rock-vertical', 'model', (1, 0, 2), 0, .5, 'relative', {}),
    ('tent', 'model', (3.5, 0, -6), 0, 1, None, {}),
    # The JS set `recieveShadow` (sic) on bushes and the campfire, so they never received shadows.
    ('bush-tree-harvest', 'model', (11, 0, 4), 0, 1, None, {'receive_shadow': False}),
    ('bush-tree-harvest', 'model', (6.5, 0, -2.6), 0, 1, None, {'receive_shadow': False}),
    ('bush-tree-harvest', 'model', (1.7, 0, -8.7), 0, 1, None, {'receive_shadow': False}),
    ('bush-tree-harvest', 'model', (-2.9, 0, -2.4), 0, 1, None, {'receive_shadow': False}),
    ('picnic-table', 'model', (4.7, 0, -2), math.pi / 1.2, .25, None, {}),
    ('welcome-sign', 'model', (-4.2, 0, 1.7), 20, .4, 'relative', {}),  # rotateY(20): radians
    ('camp-fire', 'campfire', (2.7, 0, -2.5), 0, .7, None, {'receive_shadow': False}),
]

TREE_SWAY = .12
GRASS_SWAY = .1


def _relative_height(terrain, x, y, scale):
    """terrain.addRelativeObject(): the first vertex (three.js buffer order) within `scale`."""
    c0, r0, c1, r1 = terrain._window(x, y, scale)
    best = None
    for row in range(r1 - 1, r0 - 1, -1):  # three.js rows run along +z, which is Panda's -y
        for column in range(c0, c1):
            dx, dy = terrain.coords[column] - x, terrain.coords[row] - y
            if dx * dx + dy * dy < scale * scale:
                best = float(terrain.heights[row, column])
                break
        if best is not None:
            break
    return best or 0.0


def build_default_world(name='default'):
    raw = settings.store.legacy_raw
    segments = raw.get('gfx.terrain_detail', DEFAULT_SEGMENTS)
    if segments not in (480, 960, 1440):
        segments = DEFAULT_SEGMENTS
    document = WorldDocument.empty(name, DEFAULT_SIZE, segments)
    terrain = document.terrain
    circles = [(x, -z, radius, strength) for x, z, radius, strength in CIRCLES]
    if raw.get('env.terrain_shape') == 'js':
        terrain.add_js_bumps(circles)
    else:
        terrain.add_hills(circles)

    data = document.data
    environment = settings.store.defaults(settings.WORLD_PREFIX)
    environment.update(settings.store.legacy_environment)
    data['environment'] = environment

    for js_name, kind, (x, y, z), rotate_y, scale, rule, extra in OBJECTS:
        spec = objects.LIBRARY[js_name]
        position = three_to_panda(x, y, z)
        if rule == 'relative':
            position.z = y + _relative_height(terrain, position.x, position.y, scale)
        record = new_object(spec.path, kind, tuple(position), objects.model_defaults(spec.path))
        record['id'] = document.new_id('o')
        record['name'] = js_name
        record['hpr'][0] = rotation_y_to_heading(rotate_y)
        record['scale'] = [scale * spec.scale] * 3  # objects.get() applied the library scale
        record['interactable'] = True  # the JS registered these as interactable objects
        record.update(extra)
        record['follow_terrain'] = False  # placed like the JS: at y = 0, not on the hills
        data['objects'].append(record)

    bird = new_object('obj/bird-animated.glb', 'bird', tuple(three_to_panda(0, 7, 0)))
    bird.update({'id': document.new_id('o'), 'name': 'bird', 'scale': [.025] * 3, 'follow_terrain': False})
    data['objects'].append(bird)

    for title, model, sway, entries in (('Trees', 'obj/lowpoly-tree-bones.glb', TREE_SWAY, TREES),
                                        ('Grass', 'obj/grass.obj', GRASS_SWAY, GRASS)):
        group = new_foliage(model, title)
        group['id'] = document.new_id('f')
        group['sway'] = sway
        if title == 'Trees':
            group['collision'] = {'shape': 'cylinder', 'radius': .3, 'height': 4.0}
        for entry in entries:
            if len(entry) < 4:
                continue  # the JS build turned a missing scale into NaN, so that instance never rendered
            x, y, z, scale = entry
            group['items'].append([float(x), float(-z), float(y), float(scale), 0.0])
        data['foliage'].append(group)

    for position, scale in CLOUDS:
        data['clouds'].append([*three_to_panda(*position), *three_scale_to_panda(*scale)])

    start = three_to_panda(2, 0, 2)
    data['player'] = {'start': [start.x, start.y, 0.0], 'heading': 180.0}
    return document
