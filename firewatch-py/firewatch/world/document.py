"""World saves: saves/<name>/world.json (objects, foliage, water bodies, clouds, player start and the
environment settings) plus terrain.npz (heights, paint and water masks), and compiled/ (see
compile.py).

Positions are Panda3D world coordinates (Z up, meters); rotations are heading/pitch/roll in degrees.
Colors are '#rrggbb'. Material colors are stored only where they differ from the model's defaults.
"""
import copy
import json
import re
import shutil
import threading

import numpy as np

from ..paths import PACKAGE_DIR
from .breakables import default_breakable
from .items import guess_item_type, new_item
from .lights import new_light
from .terrain import Terrain

SAVES_DIR = PACKAGE_DIR.parent / 'saves'
VERSION = 1
NAME_PATTERN = re.compile(r'[^A-Za-z0-9 _.-]+')

OBJECT_KINDS = ('model', 'campfire', 'bird', 'item', 'light')
COLLISION_SHAPES = ('none', 'box', 'cylinder', 'mesh')


def clean_name(name):
    name = NAME_PATTERN.sub('', name).strip().strip('.')
    return name[:48] or 'world'


def save_dir(name):
    return SAVES_DIR / clean_name(name)


def list_saves():
    if not SAVES_DIR.is_dir():
        return []
    return sorted((path.name for path in SAVES_DIR.iterdir() if (path / 'world.json').is_file()), key=str.lower)


def exists(name):
    return (save_dir(name) / 'world.json').is_file()


def delete(name):
    path = save_dir(name)
    if path.is_dir() and path.parent == SAVES_DIR:
        shutil.rmtree(path)


SOFT_MODELS = ('grass', 'flower', 'plant', 'fern', 'weed', 'reed', 'mushroom', 'leaf', 'leaves', 'clover', 'moss')


def no_collision_by_default(model):
    """Grass and similar plants are walked through."""
    name = model.rsplit('/', 1)[-1].lower()
    return any(word in name for word in SOFT_MODELS)


def new_object(model, kind='model', position=(0, 0, 0), defaults=None):
    """A world object record with every field present."""
    defaults = defaults or {}
    scale = float(defaults.get('scale', 1.0))
    return {
        'id': '', 'name': '', 'kind': kind, 'model': model,
        'pos': [float(v) for v in position], 'hpr': [0.0, 0.0, 0.0], 'scale': [scale, scale, scale],
        'colors': {},
        'texture': '',  # '' = the model's own textures, 'none', or an image file ('obj/.../texture.png')
        'visible': True,
        'cast_shadow': kind not in ('bird', 'light'),
        'receive_shadow': True,
        'unlit': kind == 'bird',
        'shininess': float(defaults.get('shininess', 0)),
        'roughness': 0.0,  # > 0: physically based (MeshStandardMaterial) instead of Phong
        'distance_render': bool(defaults.get('distance_render', True)) and kind != 'light',
        'interactable': False,  # selectable in the game (click, R rotates); such objects aren't merged when compiling
        'follow_terrain': True,  # moves with the ground when the terrain under it is sculpted
        'collision': {'shape': 'none' if kind in ('bird', 'item', 'light') else defaults.get('collision', 'box'),
                      'scale': [1.0, 1.0, 1.0], 'offset': [0.0, 0.0, 0.0]},
        'item': new_item(guess_item_type(model), model.rsplit('/', 1)[-1].rsplit('.', 1)[0].replace('_', ' ')),
        'breakable': default_breakable(model),
        'light': new_light(),  # kind 'light' (world/lights.py)
    }


def new_foliage(model, name=''):
    return {
        'id': '', 'name': name, 'model': model, 'colors': {}, 'sway': .1,
        'cast_shadow': True, 'receive_shadow': True, 'distance_render': False,
        'collision': {'shape': 'none', 'radius': .25, 'height': 3.0},
        'breakable': default_breakable(model),
        'items': [],  # [x, y, z offset above the lowest ground under it, scale, heading]
    }


def new_water(name='Water', level=0.0):
    return {
        'id': '', 'name': name, 'level': float(level),
        'shallow_color': '#2f6f73', 'deep_color': '#0b2a3a', 'clarity': 1.2,
        'opacity': .2,  # everywhere, even at the shore (1 = solid, e.g. ice)
        'depth_opacity': .8,  # added by depth: deeper water hides more of the bottom
        'walkable': False,  # frozen: the player walks on the surface instead of wading
        'reflectivity': .6, 'specular': 1.0, 'wave_height': .35, 'wave_scale': 1.0, 'wave_speed': 1.0,
        'foam': .6, 'foam_color': '#d8e6ea',
    }


def fill_defaults(record, template):
    """Add missing fields (saves from older versions) without touching existing ones."""
    for key, value in template.items():
        if key not in record:
            record[key] = copy.deepcopy(value)
        elif isinstance(value, dict) and isinstance(record[key], dict):
            fill_defaults(record[key], value)
    return record


class WorldDocument:
    """The saved state of one world."""

    def __init__(self, name, data, terrain):
        self.name = clean_name(name)
        self.data = data
        self.terrain = terrain
        self._save_thread = None

    # ------------------------------------------------------------------------- creation

    @classmethod
    def empty(cls, name, size=200, segments=960):
        data = {
            'version': VERSION, 'environment': {}, 'next_id': 1,
            'terrain': {'size': size, 'segments': segments},
            'objects': [], 'foliage': [], 'water': [], 'clouds': [], 'colliders': [],
            'player': {'start': [0.0, 0.0, 0.0], 'heading': 0.0},
        }
        return cls(name, data, Terrain(size, segments))

    @classmethod
    def load(cls, name):
        folder = save_dir(name)
        data = json.loads((folder / 'world.json').read_text())
        size, segments = data['terrain']['size'], data['terrain']['segments']
        try:
            with np.load(folder / 'terrain.npz') as arrays:
                terrain = Terrain(size, segments, arrays['heights'], arrays['paint'], arrays['water'])
        except (OSError, KeyError, ValueError):
            terrain = Terrain(size, segments)
        document = cls(name, data, terrain)
        document._upgrade()
        return document

    def _upgrade(self):
        data = self.data
        for key, value in (('objects', []), ('foliage', []), ('water', []), ('clouds', []), ('colliders', []),
                           ('environment', {}), ('next_id', 1)):
            data.setdefault(key, value)
        data.setdefault('player', {'start': [0.0, 0.0, 0.0], 'heading': 0.0})
        for record in data['objects']:
            fill_defaults(record, new_object(record.get('model', ''), record.get('kind', 'model')))
        for record in data['foliage']:
            fill_defaults(record, new_foliage(record.get('model', '')))
        for record in data['water']:
            if 'depth_opacity' not in record:  # saves before opacity was split: same look, new controls
                record['opacity'] = round(.25 * float(record.get('opacity', .85)), 3)
                record['depth_opacity'] = 1.0
            fill_defaults(record, new_water())
        for record in data['objects']:
            # Grass used to get a box collider when placed; untouched ones get none, like new grass.
            collision = record['collision']
            if (collision['shape'] == 'box' and no_collision_by_default(record['model'])
                    and collision['scale'] == [1.0, 1.0, 1.0] and collision['offset'] == [0.0, 0.0, 0.0]):
                collision['shape'] = 'none'
        data['version'] = VERSION

    # ---------------------------------------------------------------------------- saving

    def new_id(self, prefix):
        identifier = f'{prefix}{self.data["next_id"]}'
        self.data['next_id'] += 1
        return identifier

    def world_json(self):
        return json.dumps(self.data, indent=1)

    def save(self, name=None, terrain=True, wait=False):
        """Write the save. Terrain arrays are copied and compressed on a background thread."""
        if name is not None:
            self.name = clean_name(name)
        folder = save_dir(self.name)
        folder.mkdir(parents=True, exist_ok=True)
        text = self.world_json()
        temporary = folder / 'world.json.tmp'
        temporary.write_text(text)
        temporary.replace(folder / 'world.json')
        if terrain:
            arrays = {'heights': self.terrain.heights.copy(), 'paint': self.terrain.paint.copy(),
                      'water': self.terrain.water.copy()}
            self.wait()
            self._save_thread = threading.Thread(target=self._write_terrain, args=(folder, arrays), daemon=True)
            self._save_thread.start()
            if wait:
                self.wait()

    @staticmethod
    def _write_terrain(folder, arrays):
        temporary = folder / 'terrain.tmp.npz'
        np.savez_compressed(temporary, **arrays)
        temporary.replace(folder / 'terrain.npz')

    def wait(self):
        if self._save_thread is not None:
            self._save_thread.join()
            self._save_thread = None

    @property
    def folder(self):
        return save_dir(self.name)
