"""The loaded world: builds the scene from a save, keeps it in sync with edits, and saves it.

Game and editor both load the active world (settings.json '_meta.world'); environment settings
changed in either are saved with the world. In the editor every change is autosaved a moment after
the last edit (terrain only once a brush stroke ends).
"""
import copy
import json
import time

import numpy as np

from .. import registry, settings, shadow_cache
from ..components.clouds import Clouds
from ..update import add_update_callback
from . import compiler
from .document import WorldDocument, exists, list_saves, new_foliage, new_object, new_water
from .colliders import ColliderEntity, new_collider
from .entities import WorldObject
from .foliage import FoliageGroup
from .water import WaterBody

AUTOSAVE_DELAY = 1.5
SECTIONS = ('objects', 'foliage', 'water', 'clouds', 'player', 'colliders')


class World:
    def __init__(self, app, mode):
        self.app = app
        self.mode = mode  # 'game' or 'editor'
        self.root = app.render.attach_new_node('world')
        self.document = None
        self.terrain = None
        self.objects = []
        self.foliage = []
        self.water = []
        self.colliders = []  # standalone collider views (editor only; the game reads the records)
        self.clouds = Clouds(app)
        self.compiled = None  # compiler.CompiledWorld when the game runs from a compiled save
        self.listeners = []
        self.busy = False  # True during a brush stroke: postpone autosaving the terrain
        self._dirty = False
        self._dirty_terrain = False
        self._changed_at = 0.0
        self._distance_nodes = None
        self._loading = False
        self._foliage_version = 0
        self._sway_cache = (None, False)
        settings.subscribe(self._environment_changed, settings.WORLD_PREFIX)
        add_update_callback(self._tick)

    # ------------------------------------------------------------------------ properties

    @property
    def data(self):
        return self.document.data

    @property
    def name(self):
        return self.document.name if self.document else ''

    def add_listener(self, callback):
        """`callback(section)` after changes; section is one of SECTIONS, 'terrain', 'environment' or 'loaded'."""
        self.listeners.append(callback)

    def notify(self, section):
        for callback in list(self.listeners):
            callback(section)

    # --------------------------------------------------------------------- load / save

    def load(self, name, use_compiled=False):
        """Replace the current world with a save (created from the JS scene if it is 'default')."""
        if self.document is not None:
            self.flush()
        from .legacy import build_default_world  # imported late: it reads the legacy settings
        if not exists(name):
            if name == 'default' or not list_saves():
                document = build_default_world(name)
                document.save(wait=True)
            else:
                name = list_saves()[0]
        document = WorldDocument.load(name)
        self._clear()
        self.document = document
        self.terrain = document.terrain
        settings.store.set_meta('world', document.name)

        self._loading = True
        settings.store.set_environment(document.data['environment'])
        self._loading = False

        self.compiled = compiler.load(self, document) if use_compiled else None
        if self.compiled is None:
            self.terrain.build(self.root)
        self.terrain.add_listener(self._terrain_changed)
        for record in self.data['objects']:
            if self.compiled is not None and self.compiled.is_baked(record['id']):
                continue
            self.objects.append(WorldObject(self, record))
        self.foliage = [FoliageGroup(self, record) for record in self.data['foliage']
                        if self.compiled is None or record['id'] not in self.compiled.baked_foliage]
        self.water = [WaterBody(self, record, index) for index, record in enumerate(self.data['water'])]
        self._build_colliders()
        self._foliage_version += 1
        self.clouds.build(self.data['clouds'])
        shadow_cache.set_animated_source('foliage', self._foliage_sways)
        shadow_cache.invalidate()
        self._dirty = self._dirty_terrain = False
        self.distance_changed()
        self.notify('loaded')

    def _build_colliders(self):
        for item in self.colliders:
            item.destroy()
        self.colliders = ([ColliderEntity(self, record) for record in self.data['colliders']]
                          if self.mode == 'editor' else [])

    def _clear(self):
        for item in self.objects + self.foliage + self.water + self.colliders:
            item.destroy()
        self.objects, self.foliage, self.water, self.colliders = [], [], [], []
        if self.terrain is not None and self.terrain.root is not None:
            self.terrain.root.remove_node()
        if self.compiled is not None:
            self.compiled.destroy()
            self.compiled = None
        self.root.get_children().detach()

    def save(self, name=None, wait=False):
        """Save now (optionally under a new name, which becomes the active world)."""
        self.data['environment'] = settings.store.environment()
        self.document.save(name, terrain=True, wait=wait)
        settings.store.set_meta('world', self.document.name)
        self._dirty = self._dirty_terrain = False
        self.notify('saved')

    def flush(self):
        if self._dirty or self._dirty_terrain:
            self.data['environment'] = settings.store.environment()
            self.document.save(terrain=self._dirty_terrain, wait=True)
            self._dirty = self._dirty_terrain = False
        if self.document is not None:
            self.document.wait()

    def mark_dirty(self, terrain=False):
        self._dirty = True
        self._dirty_terrain = self._dirty_terrain or terrain
        self._changed_at = time.monotonic()

    def _environment_changed(self, keys):
        if self._loading or self.document is None:
            return
        self.mark_dirty()
        if any(key.startswith(('env.terrain', 'env.snow_cover')) for key in keys) and self.terrain is not None:
            self.terrain.apply_material()
            shadow_cache.invalidate()

    def _tick(self, _delta):
        if self.document is None or not (self._dirty or self._dirty_terrain):
            return
        if time.monotonic() - self._changed_at < AUTOSAVE_DELAY or (self.busy and self._dirty_terrain):
            return
        self.data['environment'] = settings.store.environment()
        self.document.save(terrain=self._dirty_terrain)
        self._dirty = self._dirty_terrain = False
        self.notify('saved')

    @property
    def unsaved(self):
        return self._dirty or self._dirty_terrain

    # ------------------------------------------------------------------- terrain hooks

    def _terrain_changed(self, c0, r0, c1, r1):
        terrain = self.terrain
        x0, x1 = terrain.coords[max(c0 - 1, 0)], terrain.coords[min(c1, terrain.segments)]
        y0, y1 = terrain.coords[max(r0 - 1, 0)], terrain.coords[min(r1, terrain.segments)]
        for group in self.foliage:
            group.terrain_changed(x0 - 4, y0 - 4, x1 + 4, y1 + 4)
        if self.water:
            for body in self.water:
                body.rebuild()
        shadow_cache.invalidate()

    def _foliage_sways(self):
        return settings.get('env.wind_strength') > 0 and any(
            group.data['sway'] > 0 and group.data['cast_shadow'] and len(group.items) for group in self.foliage) or (
            self.compiled is not None and self.compiled.sways and settings.get('env.wind_strength') > 0)

    def sways_near(self, position, radius):
        """Is any wind-swayed, shadow-casting foliage within `radius` of a point?"""
        if settings.get('env.wind_strength') <= 0:
            return False
        key = (round(position.x, 2), round(position.y, 2), round(position.z, 2), radius, self._foliage_version)
        if self._sway_cache[0] != key:
            near = False
            for record in self.data['foliage']:
                if record['sway'] <= 0 or not record['cast_shadow'] or not record['items']:
                    continue
                items = np.asarray(record['items'], np.float64)
                reach = radius + 6 * items[:, 3]  # an instance's crown can lean in from beside the radius
                if (np.hypot(items[:, 0] - position.x, items[:, 1] - position.y) < reach).any():
                    near = True
                    break
            self._sway_cache = (key, near)
        return self._sway_cache[1]

    # --------------------------------------------------------------------------- objects

    def object_by_id(self, identifier):
        for item in self.objects:
            if item.id == identifier:
                return item
        return None

    def add_object(self, model, kind='model', position=(0, 0, 0), defaults=None, record=None):
        if record is None:
            record = new_object(model, kind, position, defaults)
        else:
            record = copy.deepcopy(record)
        record['id'] = self.document.new_id('o')
        if not record.get('name'):
            record['name'] = model.rsplit('/', 1)[-1].rsplit('.', 1)[0]
        self.data['objects'].append(record)
        item = WorldObject(self, record)
        self.objects.append(item)
        self._objects_changed()
        return item

    def take_object(self, item):
        """The player picked an item up: gone from this game session (the save keeps it)."""
        self.objects.remove(item)
        item.destroy()
        self.distance_changed()
        self.notify('objects')

    def drop_object(self, record, position, heading):
        """Put an inventory item back into the world for this session."""
        record = copy.deepcopy(record)
        record['pos'] = [float(v) for v in position]
        record['hpr'] = [float(heading), 0.0, 0.0] if record['item']['type'] != 'flashlight' else \
            [float(heading), -90.0, 0.0]  # lay a flashlight on its side, pointing where you looked
        item = WorldObject(self, record)
        self.objects.append(item)
        self.distance_changed()
        self.notify('objects')
        return item

    def remove_object(self, item):
        self.data['objects'].remove(item.data)
        self.objects.remove(item)
        item.destroy()
        self._objects_changed()

    def update_object(self, item, changes, rebuild=False):
        """Apply changed fields; `rebuild` recreates the model (model or colors changed)."""
        item.data.update(changes)
        if rebuild or {'model', 'colors', 'kind', 'item', 'texture', 'light'} & set(changes):
            item.build()
        elif 'visible' in changes and item.data['kind'] == 'light':
            item.apply_flags()
            from .lights import manager
            manager().clock = 1.0  # re-pick the active lights now
        else:
            if {'pos', 'hpr', 'scale'} & set(changes):
                item.apply_transform()
            item.apply_flags()
        self._objects_changed()

    def _objects_changed(self):
        shadow_cache.invalidate()
        self.distance_changed()
        self.mark_dirty()
        self.notify('objects')

    # --------------------------------------------------------------------------- foliage

    def add_foliage(self, model, name=''):
        record = new_foliage(model, name or model.rsplit('/', 1)[-1].rsplit('.', 1)[0])
        record['id'] = self.document.new_id('f')
        self.data['foliage'].append(record)
        group = FoliageGroup(self, record)
        self.foliage.append(group)
        self.foliage_changed()
        return group

    def remove_foliage(self, group):
        self.data['foliage'].remove(group.data)
        self.foliage.remove(group)
        group.destroy()
        self.foliage_changed()

    def foliage_changed(self):
        self._foliage_version += 1
        shadow_cache.invalidate()
        self.distance_changed()
        self.mark_dirty()
        self.notify('foliage')

    # ------------------------------------------------------------------------- colliders

    def collider_by_id(self, identifier):
        for item in self.colliders:
            if item.id == identifier:
                return item
        return None

    def add_collider(self, shape='box', position=(0, 0, 0), record=None):
        record = copy.deepcopy(record) if record is not None else new_collider(shape, position)
        record['id'] = self.document.new_id('c')
        self.data['colliders'].append(record)
        item = ColliderEntity(self, record) if self.mode == 'editor' else None
        if item is not None:
            self.colliders.append(item)
        self.colliders_changed()
        return item

    def remove_collider(self, item):
        self.data['colliders'].remove(item.data)
        self.colliders.remove(item)
        item.destroy()
        self.colliders_changed()

    def update_collider(self, item, changes):
        rebuild = 'shape' in changes and changes['shape'] != item.data['shape']
        item.data.update(changes)
        item.build() if rebuild else item.apply_transform()
        self.colliders_changed()

    def colliders_changed(self):
        self.mark_dirty()
        self.notify('colliders')

    # ----------------------------------------------------------------------------- water

    def add_water(self, level=0.0):
        record = new_water(f'Water {len(self.water) + 1}', level)
        record['id'] = self.document.new_id('w')
        self.data['water'].append(record)
        body = WaterBody(self, record, len(self.water))
        self.water.append(body)
        self.water_changed()
        return body

    def remove_water(self, body):
        value = body.mask_value
        water = self.terrain.water
        water[water == value] = 0
        water[water > value] -= 1  # later bodies move down one index
        self.data['water'].remove(body.data)
        for item in self.water:
            item.destroy()
        self.water = [WaterBody(self, record, index) for index, record in enumerate(self.data['water'])]
        self.terrain.changed((0, 0, self.terrain.segments + 1, self.terrain.segments + 1), heights=False)
        self.water_changed(terrain=True)

    def water_changed(self, terrain=False):
        self.mark_dirty(terrain)
        self.notify('water')

    def water_level_at(self, x, y):
        """Level of the water body covering a point, or None."""
        body = self.water_at(x, y)
        return float(body['level']) if body is not None else None

    def water_at(self, x, y):
        """Record of the water body covering a point, or None."""
        for body in self.water:
            if body.contains(x, y):
                return body.data
        return None

    # ---------------------------------------------------------------------- clouds, misc

    def set_clouds(self, records):
        self.data['clouds'] = records
        self.clouds.build(records)
        self.mark_dirty()
        self.notify('clouds')

    def set_player_start(self, position, heading):
        self.data['player'] = {'start': [float(v) for v in position], 'heading': float(heading)}
        self.mark_dirty()
        self.notify('player')

    def terrain_edited(self):
        """A brush stroke (or terrain reset) finished."""
        self.mark_dirty(terrain=True)
        self.notify('terrain')

    # ------------------------------------------------------------------ distance culling

    def distance_changed(self):
        self._distance_nodes = None

    def distance_nodes(self):
        """(node to hide, fixed center or None to use the node's position) for draw-distance culling."""
        if self._distance_nodes is None:
            nodes = []
            for item in self.objects:
                if item.data['distance_render'] and item.content is not None:
                    nodes.append((item.content, item.root, None))
            for group in self.foliage:
                if group.data['distance_render']:
                    for node in group.cells.values():
                        nodes.append((node, None, node.get_python_tag('center')))
            if self.compiled is not None:
                nodes.extend(self.compiled.distance_nodes)
            self._distance_nodes = nodes
        return self._distance_nodes

    # --------------------------------------------------------------------- undo support

    def snapshot(self, sections=SECTIONS):
        return {section: json.loads(json.dumps(self.data[section])) for section in sections}

    def restore(self, snapshot):
        """Return sections to a snapshot, rebuilding only what differs."""
        if 'objects' in snapshot:
            records = snapshot['objects']
            current = {item.id: item for item in self.objects}
            wanted_ids = [record['id'] for record in records]
            for item in list(self.objects):
                if item.id not in wanted_ids:
                    self.objects.remove(item)
                    item.destroy()
            ordered = []
            for record in records:
                item = current.get(record['id'])
                if item is None:
                    ordered.append(WorldObject(self, copy.deepcopy(record)))
                    continue
                if item.data != record:
                    model_changed = any(item.data.get(key) != record.get(key)
                                        for key in ('model', 'colors', 'kind', 'texture', 'item', 'light'))
                    item.data.clear()
                    item.data.update(copy.deepcopy(record))
                    if model_changed:
                        item.build()
                    else:
                        item.apply_transform()
                        item.apply_flags()
                ordered.append(item)
            self.objects = ordered
            self.data['objects'] = [item.data for item in ordered]
            self._objects_changed()
        if 'foliage' in snapshot:
            records = snapshot['foliage']
            current = {group.data['id']: group for group in self.foliage}
            groups = []
            for record in records:
                group = current.pop(record['id'], None)
                if group is not None and group.data == record:
                    groups.append(group)
                    continue
                if group is not None:
                    group.destroy()
                groups.append(FoliageGroup(self, copy.deepcopy(record)))
            for group in current.values():
                group.destroy()
            self.foliage = groups
            self.data['foliage'] = [group.data for group in groups]
            self.foliage_changed()
        if 'water' in snapshot:
            self.data['water'] = copy.deepcopy(snapshot['water'])
            for body in self.water:
                body.destroy()
            self.water = [WaterBody(self, record, index) for index, record in enumerate(self.data['water'])]
            self.water_changed()
        if 'clouds' in snapshot:
            self.set_clouds(copy.deepcopy(snapshot['clouds']))
        if 'colliders' in snapshot:
            self.data['colliders'] = copy.deepcopy(snapshot['colliders'])
            self._build_colliders()
            self.colliders_changed()
        if 'player' in snapshot:
            self.data['player'] = copy.deepcopy(snapshot['player'])
            self.mark_dirty()
            self.notify('player')

    # ------------------------------------------------------------------------- stats

    def triangle_counts(self):
        counts = {'terrain': self.terrain.triangle_count() if self.compiled is None else self.compiled.terrain_triangles,
                  'objects': sum(item.triangle_count() for item in self.objects),
                  'foliage': sum(group.triangle_count() for group in self.foliage),
                  'water': sum(body.triangles for body in self.water)}
        if self.compiled is not None:
            counts['baked'] = self.compiled.triangles
        return counts


def draw(app):
    world = World(app, getattr(app, 'mode', 'game'))
    registry.add('world', world)
    name = getattr(app, 'world_name', None) or settings.store.meta.get('world') or 'default'
    world.load(name, use_compiled=world.mode == 'game')
