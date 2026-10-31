"""Editor tools. Each one fills the left panel (`items()`) and handles the left mouse button in the
3D view; `update()` runs every frame while it is active."""
import math
import time

import numpy as np
from panda3d.core import KeyboardButton, Point3

from .. import library, objects, settings
from ..components.clouds import generate as generate_clouds
from ..settings import Section
from ..ui.widgets import Button, Note, prop
from ..world import water as water_brush
from ..world.items import is_item_model, suggested_scale
from ..world.document import (COLLISION_SHAPES, OBJECT_KINDS, delete as delete_save, list_saves)
from . import overlays

COLLIDER_BOX, COLLIDER_CYLINDER = ':box-collider', ':cylinder-collider'
LIGHT_POINT, LIGHT_SPOT = ':point-light', ':spot-light'
BRUSH_INTERVAL = 1 / 30  # seconds between terrain brush applications while the button is held


def _modifier(editor, button):
    return editor.app.mouseWatcherNode.is_button_down(button)


def shift(editor):
    return _modifier(editor, KeyboardButton.shift())


def control(editor):
    return _modifier(editor, KeyboardButton.control())


def alt(editor):
    return _modifier(editor, KeyboardButton.alt())


def guess_kind(model):
    name = model.lower()
    if 'campfire' in name or 'camp-fire' in name:
        return 'campfire'
    if 'bird' in name:
        return 'bird'
    if is_item_model(model):
        return 'item'  # tools and flashlights: the player can pick them up
    return 'model'


class Tool:
    name = ''
    title = ''
    hint = ''
    brush = False

    def __init__(self, editor):
        self.editor = editor

    @property
    def world(self):
        return self.editor.world

    def items(self):
        return []

    def activate(self):
        pass

    def deactivate(self):
        pass

    def press(self):
        pass

    def release(self):
        pass

    def update(self, delta):
        pass

    def cancel(self):
        """Escape. Return True if handled."""
        return False


# --------------------------------------------------------------------------------- select


class SelectTool(Tool):
    name = 'select'
    title = 'Select'
    hint = ('click: select   drag: move on the ground   shift+drag: up/down   ctrl+drag: rotate   alt+drag: scale   '
            'Del  Ctrl+D  R  End: drop  F: focus')

    def __init__(self, editor):
        super().__init__(editor)
        self.drag = None

    def items(self):
        world = self.world
        player = world.data['player']
        return [
            Section('Selection'),
            Note('Click an object, or a single tree / grass tuft of a foliage group, to select it and edit it on '
                 'the right. Drag it to move it along the ground; shift: height, ctrl: rotation, alt: scale. '
                 'Objects are added with Place (2), foliage is painted with Foliage (5).'),
            Section('Player start'),
            Note('Where the game starts you, facing the arrow (shown in light blue).'),
            Button('Set to the camera position', self.editor.set_player_start_here),
            (prop('Facing (degrees)', 'float', -180, 180, 1), lambda: (player['heading'] + 180) % 360 - 180,
             lambda value: self.editor.set_player_start(heading=value)),
            Section('Compile'),
            Note(f'{sum(1 for i in world.objects if i.data["interactable"])} objects are selectable in the game '
                 f'(click + R there); Compile keeps those separate instead of merging them.'),
            Button('Make all objects mergeable', self.editor.make_all_mergeable),
            Section('Camera & keys'),
            Note(self.editor.help_note.replace('   ', '\n')),
            Section('Objects in the world'),
            *[Button(f'{item.data["name"] or item.id}', (lambda it=item: self.editor.select_and_focus(it)))
              for item in world.objects],
        ]

    def press(self):
        editor = self.editor
        picked = editor.pick_object()
        if picked is None:
            editor.select(None)
            return
        hit = editor.terrain_hit()
        x, y = editor.pointer()
        if isinstance(picked, tuple) and picked[0] == 'collider':
            item = picked[1]
            if item is not editor.selected_collider:
                editor.select_collider(item)
            data = item.data
            self.drag = {
                'kind': 'collider', 'item': item, 'start_pointer': (x, y), 'moved': False,
                'before': self.world.snapshot(('colliders',)), 'pos': list(data['pos']), 'size': list(data['size']),
                'heading': data['heading'],
                'offset': (data['pos'][0] - hit[0], data['pos'][1] - hit[1]) if hit else (0, 0),
                'ground': self.world.terrain.height_at(data['pos'][0], data['pos'][1]),
            }
            return
        if isinstance(picked, tuple):  # a foliage instance
            _, group, index = picked
            editor.select_instance(group, index)
            ix, iy, offset, scale, heading = (float(v) for v in group.items[index])
            self.drag = {
                'kind': 'instance', 'group': group.data['id'], 'index': index, 'start_pointer': (x, y),
                'moved': False, 'before': self.world.snapshot(('foliage',)),
                'values': {'x': ix, 'y': iy, 'offset': offset, 'scale': scale, 'heading': heading},
                'offset': (ix - hit[0], iy - hit[1]) if hit else (0, 0),
            }
            return
        if picked is not editor.selected:
            editor.select(picked)
        record = picked.data
        self.drag = {
            'kind': 'object', 'item': picked, 'start_pointer': (x, y), 'moved': False,
            'before': self.world.snapshot(('objects',)),
            'pos': list(record['pos']), 'hpr': list(record['hpr']), 'scale': list(record['scale']),
            'offset': (record['pos'][0] - hit[0], record['pos'][1] - hit[1]) if hit else (0, 0),
            'ground': self.world.terrain.height_at(record['pos'][0], record['pos'][1]),
        }

    def update(self, delta):
        drag = self.drag
        if drag is None:
            return
        editor = self.editor
        x, y = editor.pointer()
        dx, dy = x - drag['start_pointer'][0], y - drag['start_pointer'][1]
        if not drag['moved'] and math.hypot(dx, dy) < 4:
            return
        drag['moved'] = True
        if drag['kind'] == 'instance':
            self._drag_instance(drag, dx, dy)
            return
        if drag['kind'] == 'collider':
            self._drag_collider(drag, dx, dy)
            return
        item = drag['item']
        changes = {}
        if shift(editor):
            distance = (editor.app.camera.get_pos() - Point3(*drag['pos'])).length()
            changes['pos'] = [drag['pos'][0], drag['pos'][1], drag['pos'][2] - dy * distance * .002]
        elif control(editor):
            changes['hpr'] = [(drag['hpr'][0] - dx * .5) % 360, drag['hpr'][1], drag['hpr'][2]]
        elif alt(editor):
            factor = math.exp(dx * .005)
            changes['scale'] = [max(s * factor, 1e-3) for s in drag['scale']]
        else:
            hit = editor.terrain_hit()
            if hit is None:
                return
            nx, ny = hit[0] + drag['offset'][0], hit[1] + drag['offset'][1]
            z = drag['pos'][2]
            if item.data['follow_terrain']:
                z += self.world.terrain.height_at(nx, ny) - drag['ground']
            changes['pos'] = [nx, ny, z]
        self.world.update_object(item, changes)
        editor.properties_changed()

    def _drag_collider(self, drag, dx, dy):
        editor = self.editor
        item = drag['item']
        if shift(editor):
            changes = {'pos': [drag['pos'][0], drag['pos'][1], drag['pos'][2] - dy * .01]}
        elif control(editor):
            changes = {'heading': (drag['heading'] - dx * .5) % 360}
        elif alt(editor):
            factor = math.exp(dx * .005)
            changes = {'size': [max(v * factor, .02) for v in drag['size']]}
        else:
            hit = editor.terrain_hit()
            if hit is None:
                return
            nx, ny = hit[0] + drag['offset'][0], hit[1] + drag['offset'][1]
            z = drag['pos'][2] + self.world.terrain.height_at(nx, ny) - drag['ground']
            changes = {'pos': [nx, ny, z]}
        self.world.update_collider(item, changes)
        editor.properties_changed()

    def _drag_instance(self, drag, dx, dy):
        editor = self.editor
        found = editor.instance()
        if found is None:
            self.drag = None
            return
        group, index = found
        start = drag['values']
        if shift(editor):
            values = {'offset': start['offset'] - dy * .01}
        elif control(editor):
            values = {'heading': (start['heading'] - dx * .5) % 360}
        elif alt(editor):
            values = {'scale': max(start['scale'] * math.exp(dx * .005), .01)}
        else:
            hit = editor.terrain_hit()
            if hit is None:
                return
            values = {'x': hit[0] + drag['offset'][0], 'y': hit[1] + drag['offset'][1]}
        group.set_item(index, **values)
        editor._update_highlight()
        editor.properties_changed()

    def release(self):
        drag, self.drag = self.drag, None
        if drag is None or not drag['moved']:
            return
        if drag['kind'] == 'instance':
            self.world.foliage_changed()
            self.editor.record_foliage('Move instance', drag['before'])
        elif drag['kind'] == 'collider':
            self.editor.record_colliders('Move collider', drag['before'])
        else:
            self.editor.record_objects('Move', drag['before'])


# ---------------------------------------------------------------------------------- place


class PlaceTool(Tool):
    name = 'place'
    title = 'Place'
    hint = 'pick a model, then click the ground to place it   Esc: back to Select   [ ]: preview scale'

    def __init__(self, editor):
        super().__init__(editor)
        self.models = library.scan()
        self.model = None
        self.kind = 'model'
        self.preview = None
        self.random_heading = True
        self.scale_jitter = 0.0
        self.scale = 1.0
        self.heading = 0.0
        self.filter = ''

    def items(self):
        shown = [model for model in self.models if self.filter.lower() in model.lower()]
        rows = [
            Section('Place objects'),
            Note(f'Models in obj/ ({len(self.models)}). Click one, then click the ground. Drop new files into the '
                 f'obj folder and press Refresh: no restart needed. For many copies (grass, trees, flowers) '
                 f'paint them with Foliage (5) instead.'),
            Button('Refresh model list', self.refresh),
            (prop('Filter', 'text'), lambda: self.filter, self._set_filter),
            (prop('Kind', 'choice', options=OBJECT_KINDS, labels=('Model', 'Campfire (light, smoke, sound)',
                                                                  'Animated (bird)', 'Item (player picks up)')),
             lambda: self.kind, self._set_kind),
            (prop('Scale', 'float', 0, 5, .01), lambda: self.scale, self._set_scale),
            (prop('Random rotation', 'bool'), lambda: self.random_heading, self._set_random_heading),
            (prop('Random scale +/-', 'float', 0, .5, .01), lambda: self.scale_jitter, self._set_jitter),
            Section('Lights'),
            Note('Point lights shine all around, spot lights in a cone (rotate to aim). Pick one, then click.'),
            Button(('> ' if self.model == LIGHT_POINT else '') + 'Point light', lambda: self.choose(LIGHT_POINT),
                   extra=((('> ' if self.model == LIGHT_SPOT else '') + 'Spot light', lambda: self.choose(LIGHT_SPOT)),)),
            Section('Colliders'),
            Note('Invisible in the game; they block the player. Pick one, then click the ground.'),
            Button(('> ' if self.model == COLLIDER_BOX else '') + 'Box collider', lambda: self.choose(COLLIDER_BOX),
                   extra=((('> ' if self.model == COLLIDER_CYLINDER else '') + 'Cylinder collider',
                           lambda: self.choose(COLLIDER_CYLINDER)),)),
            Section(f'Models{" matching " + repr(self.filter) if self.filter else ""}'),
        ]
        for model in shown:
            marker = '> ' if model == self.model else ''
            rows.append(Button(f'{marker}{library.display_name(model)}', (lambda m=model: self.choose(m))))
        return rows

    def _set_filter(self, value):
        self.filter = value.strip()
        self.editor.rebuild_left()

    def _set_kind(self, value):
        self.kind = value

    def _set_scale(self, value):
        self.scale = min(max(float(value), .001), 5.0)
        self._update_preview_transform()

    def _set_random_heading(self, value):
        self.random_heading = value

    def _set_jitter(self, value):
        self.scale_jitter = value

    def refresh(self):
        self.models = library.scan()
        reloaded = self.editor.reload_changed_models()
        self.editor.status(f'{len(self.models)} models in obj/' + (f', {reloaded} reloaded' if reloaded else ''))
        self.editor.rebuild_left()

    def choose(self, model):
        self.model = model
        if model in (COLLIDER_BOX, COLLIDER_CYLINDER, LIGHT_POINT, LIGHT_SPOT):
            self._remove_preview()
            self.editor.rebuild_left()
            return
        self.kind = guess_kind(model)
        self.scale = objects.model_defaults(model)['scale'] if library.exists(model) else 1.0
        if self.kind == 'item' and library.exists(model):
            self.scale = suggested_scale(model)  # hand-sized
        self.heading = np.random.uniform(0, 360) if self.random_heading else 0.0
        self._make_preview()
        self.editor.rebuild_left()

    def _make_preview(self):
        self._remove_preview()
        if self.model is None or self.model in (COLLIDER_BOX, COLLIDER_CYLINDER, LIGHT_POINT, LIGHT_SPOT):
            return
        try:
            self.preview = overlays.ghost(objects.instance(self.model))
        except Exception as error:
            self.editor.status(f'cannot load {self.model}: {error}')
            self.model = None
            return
        self.preview.reparent_to(self.editor.app.render)
        self._update_preview_transform()

    def _update_preview_transform(self):
        if self.preview is not None:
            self.preview.set_scale(self.scale)
            self.preview.set_h(self.heading)

    def _remove_preview(self):
        if self.preview is not None:
            self.preview.remove_node()
            self.preview = None

    def activate(self):
        self.models = library.scan()
        if self.model is not None:
            self._make_preview()

    def deactivate(self):
        self._remove_preview()

    def update(self, delta):
        if self.preview is None:
            return
        hit = self.editor.terrain_hit()
        if hit is None or self.editor.over_gui():
            self.preview.hide()
            return
        self.preview.show()
        self.preview.set_pos(*hit)

    def press(self):
        hit = self.editor.terrain_hit()
        if self.model is None:
            self.editor.status('choose a model in the list first')
            return
        if hit is None:
            return
        if self.model in (COLLIDER_BOX, COLLIDER_CYLINDER):
            self.editor.add_collider('box' if self.model == COLLIDER_BOX else 'cylinder', hit)
            return
        if self.model in (LIGHT_POINT, LIGHT_SPOT):
            self.editor.add_light('point' if self.model == LIGHT_POINT else 'spot', hit)
            return
        before = self.world.snapshot(('objects',))
        scale = self.scale * (1 + np.random.uniform(-self.scale_jitter, self.scale_jitter))
        item = self.world.add_object(self.model, self.kind, hit, objects.model_defaults(self.model))
        hpr = [self.heading, 0.0, 0.0]
        position = list(hit)
        if self.kind == 'item' and item.data['item']['type'] == 'flashlight':
            # Lie it down (its beam axis along the ground), resting on its side.
            info = library.stats(self.model)
            hpr[1] = -90.0
            position[2] += float(max(info['max'][0] - info['min'][0], info['max'][1] - info['min'][1])) / 2 * scale
        self.world.update_object(item, {'scale': [scale] * 3, 'hpr': hpr, 'pos': position})
        self.editor.record_objects('Place', before)
        self.editor.select(item)
        self.heading = np.random.uniform(0, 360) if self.random_heading else self.heading
        self._update_preview_transform()

    def key_scale(self, factor):
        self._set_scale(self.scale * factor)
        self.editor.rebuild_left()

    def cancel(self):
        self.editor.set_tool('select')
        return True


# ---------------------------------------------------------------------------------- brushes


class BrushTool(Tool):
    brush = True

    def __init__(self, editor):
        super().__init__(editor)
        self.radius = 3.0
        self.strength = .5
        self.stroke = None
        self._last_apply = 0.0

    def brush_items(self):
        return [
            (prop('Radius  ([ ])', 'float', .2, 40, .1), lambda: self.radius, self._set_radius),
            (prop('Strength', 'float', .01, 1, .01), lambda: self.strength, self._set_strength),
        ]

    def _set_radius(self, value):
        self.radius = value

    def _set_strength(self, value):
        self.strength = value

    def resize(self, factor):
        self.radius = min(max(self.radius * factor, .2), 40)
        self.editor.refresh_left()

    def ring_color(self):
        return (1, .75, .3, 1)

    def update(self, delta):
        editor = self.editor
        hit = editor.terrain_hit()
        if hit is None or editor.over_gui():
            editor.ring.hide()
        else:
            editor.ring.show(hit[0], hit[1], self.radius, self.ring_color())
        if self.stroke is None or hit is None:
            return
        now = time.monotonic()
        elapsed = now - self._last_apply
        if elapsed < BRUSH_INTERVAL:
            return
        self._last_apply = now
        self.apply(hit, min(elapsed, .1))

    def press(self):
        hit = self.editor.terrain_hit()
        if hit is None:
            return
        terrain = self.world.terrain
        self.stroke = {'heights': terrain.heights.copy(), 'paint': terrain.paint.copy(),
                       'water': terrain.water.copy(), 'window': None, 'start': hit,
                       'objects': self.world.snapshot(('objects', 'water'))}
        self.world.busy = True
        self._last_apply = 0.0
        self.begin(hit)
        self._last_apply = time.monotonic()
        self.apply(hit, BRUSH_INTERVAL)

    def grow(self, window):
        if window is None:
            return
        current = self.stroke['window']
        self.stroke['window'] = window if current is None else (
            min(current[0], window[0]), min(current[1], window[1]), max(current[2], window[2]), max(current[3], window[3]))

    def release(self):
        stroke, self.stroke = self.stroke, None
        self.world.busy = False
        if stroke is None or stroke['window'] is None:
            return
        self.end()
        terrain = self.world.terrain
        c0, r0, c1, r1 = stroke['window']
        before = {'window': stroke['window'], 'heights': stroke['heights'][r0:r1, c0:c1].copy(),
                  'paint': stroke['paint'][r0:r1, c0:c1].copy(), 'water': stroke['water'][r0:r1, c0:c1].copy()}
        after = terrain.snapshot(stroke['window'])
        objects_before = stroke['objects']
        objects_after = self.world.snapshot(('objects', 'water'))
        world = self.world

        def undo():
            terrain.restore(before)
            world.restore(objects_before)
            world.terrain_edited()

        def redo():
            terrain.restore(after)
            world.restore(objects_after)
            world.terrain_edited()

        self.editor.undo.push(self.title, undo, redo)
        world.terrain_edited()

    def begin(self, hit):
        pass

    def apply(self, hit, elapsed):
        pass

    def end(self):
        pass


class SculptTool(BrushTool):
    name = 'sculpt'
    title = 'Sculpt'
    hint = 'drag: sculpt   ctrl: lower   shift: smooth   alt+click: pick flatten height   [ ]: radius'
    MODES = ('raise', 'lower', 'smooth', 'flatten', 'noise')

    def __init__(self, editor):
        super().__init__(editor)
        self.mode = 'raise'
        self.radius = 4.0
        self.strength = .4
        self.target = None
        self.lock_target = False

    def items(self):
        return [
            Section('Sculpt terrain'),
            Note('Smooth falloff: hills blend into the ground without creases. Ctrl lowers, Shift smooths. '
                 'Objects with "Follow terrain" and all foliage move with the ground.'),
            (prop('Brush', 'choice', options=self.MODES, labels=('Raise', 'Lower', 'Smooth', 'Flatten', 'Roughen')),
             lambda: self.mode, self._set_mode),
            *self.brush_items(),
            (prop('Flatten height', 'number', -100, 100, .1), lambda: self.target if self.target is not None else 0.0,
             self._set_target),
            (prop('Keep flatten height', 'bool'), lambda: self.lock_target, self._set_lock),
            Section('Whole terrain'),
            Button('Smooth everything (1 pass)', self.smooth_all),
            Button('Reset: flat', lambda: self.reset('flat'), extra=(('JS hills', lambda: self.reset('hills')),
                                                                     ('JS bumps', lambda: self.reset('bumps')))),
        ]

    def _set_mode(self, value):
        self.mode = value

    def _set_target(self, value):
        self.target = value
        self.lock_target = True

    def _set_lock(self, value):
        self.lock_target = value

    def begin(self, hit):
        terrain = self.world.terrain
        if alt(self.editor):
            self.target = hit[2]
            self.lock_target = True
            self.editor.refresh_left()
        elif not self.lock_target or self.target is None:
            self.target = terrain.height_at(hit[0], hit[1])
            self.editor.refresh_left()

    def apply(self, hit, elapsed):
        if alt(self.editor):
            return
        editor = self.editor
        mode = self.mode
        if shift(editor):
            mode = 'smooth'
        elif control(editor):
            mode = {'raise': 'lower', 'lower': 'raise'}.get(mode, mode)
        x, y = hit[0], hit[1]
        terrain = self.world.terrain
        movers = self._followers(x, y)
        before = [terrain.height_at(item.data['pos'][0], item.data['pos'][1]) for item in movers]
        if mode in ('raise', 'lower'):
            amount = self.strength * 4 * elapsed
        elif mode == 'noise':
            amount = self.strength * .3 * elapsed * 10
        else:
            amount = min(self.strength * elapsed * 10, 1)
        window = terrain.sculpt(mode, x, y, self.radius, amount, self.target)
        self.grow(window)
        for item, old in zip(movers, before):
            pos = item.data['pos']
            delta = terrain.height_at(pos[0], pos[1]) - old
            if abs(delta) > 1e-5:
                item.data['pos'] = [pos[0], pos[1], pos[2] + delta]
                item.apply_transform()

    def _followers(self, x, y):
        reach = self.radius + .5
        return [item for item in self.world.objects
                if item.data['follow_terrain'] and math.hypot(item.data['pos'][0] - x, item.data['pos'][1] - y) < reach]

    def smooth_all(self):
        terrain = self.world.terrain
        everything = (0, 0, terrain.segments + 1, terrain.segments + 1)
        before = terrain.snapshot(everything)
        terrain.set_heights(terrain._blurred(everything, 2))
        self._record_whole('Smooth terrain', before)

    def reset(self, shape):
        from ..world.legacy import CIRCLES
        terrain = self.world.terrain
        everything = (0, 0, terrain.segments + 1, terrain.segments + 1)
        before = terrain.snapshot(everything)
        terrain.heights[:] = 0
        circles = [(x, -z, radius, strength) for x, z, radius, strength in CIRCLES]
        if shape == 'hills':
            terrain.add_hills(circles)
        elif shape == 'bumps':
            terrain.add_js_bumps(circles)
        terrain.changed(everything)
        self._record_whole('Reset terrain', before)

    def _record_whole(self, label, before):
        terrain = self.world.terrain
        after = terrain.snapshot(before['window'])
        world = self.world

        def undo():
            terrain.restore(before)
            world.terrain_edited()

        def redo():
            terrain.restore(after)
            world.terrain_edited()

        self.editor.undo.push(label, undo, redo)
        world.terrain_edited()


class PaintTool(BrushTool):
    name = 'paint'
    title = 'Paint'
    hint = 'drag: paint color   ctrl: erase paint   alt+click: pick color   [ ]: radius'

    def __init__(self, editor):
        super().__init__(editor)
        self.color = '#3b5a1e'
        self.radius = 3.0
        self.strength = .35

    def items(self):
        return [
            Section('Paint terrain'),
            Note('Painted color shows over the terrain base color (World tab of the settings). Ctrl erases '
                 'back to the base color.'),
            (prop('Color', 'color'), lambda: self.color, self._set_color),
            *self.brush_items(),
            Section('Whole terrain'),
            Button('Fill with this color', lambda: self.fill(self.color), extra=(('Clear paint', lambda: self.fill(None)),)),
            (prop('Base color', 'color'), lambda: settings.get('env.terrain_color'),
             lambda value: settings.set('env.terrain_color', value)),
        ]

    def _set_color(self, value):
        self.color = value

    def ring_color(self):
        from ..colors import rgb
        r, g, b = (float(c) for c in rgb(self.color))
        return (r, g, b, 1)

    def begin(self, hit):
        if alt(self.editor):
            self.color = self.world.terrain.color_at(hit[0], hit[1])
            self.editor.refresh_left()

    def apply(self, hit, elapsed):
        if alt(self.editor):
            return
        amount = min(self.strength * elapsed * 12, 1)
        window = self.world.terrain.paint_color(hit[0], hit[1], self.radius, self.color, amount,
                                                erase=control(self.editor))
        self.grow(window)

    def fill(self, color):
        terrain = self.world.terrain
        everything = (0, 0, terrain.segments + 1, terrain.segments + 1)
        before = terrain.snapshot(everything)
        terrain.fill_paint(color)
        after = terrain.snapshot(everything)
        world = self.world

        def undo():
            terrain.restore(before)
            world.terrain_edited()

        def redo():
            terrain.restore(after)
            world.terrain_edited()

        self.editor.undo.push('Fill paint', undo, redo)
        world.terrain_edited()


class FoliageTool(BrushTool):
    name = 'foliage'
    title = 'Foliage'
    hint = 'drag: plant   ctrl+drag: remove   [ ]: radius   pick or create a group on the left'

    def __init__(self, editor):
        super().__init__(editor)
        self.group = None
        self.radius = 2.5
        self.density = 3
        self.spacing = .6
        self.scale_min = .4
        self.scale_max = .7
        self.random_heading = True
        self.new_model = 'obj/grass.obj'
        self.rng = np.random.default_rng()
        self._last_point = None

    def _group(self):
        if self.group not in self.world.foliage:
            self.group = self.world.foliage[0] if self.world.foliage else None
        return self.group

    def items(self):
        group = self._group()
        models = library.scan()
        rows = [
            Section('Foliage groups'),
            Note('A group is one model painted many times (grass, trees, flowers...). Every group is baked '
                 'into a few meshes, so thousands of instances stay cheap.'),
        ]
        for item in self.world.foliage:
            marker = '> ' if item is group else ''
            rows.append(Button(f'{marker}{item.data["name"]}  ({len(item.items)})', (lambda g=item: self._pick(g))))
        rows += [
            (prop('New group model', 'choice', options=models, labels=[library.display_name(m) for m in models]),
             lambda: self.new_model, self._set_new_model),
            Button('Create group', self.create_group),
            Section('Brush'),
            *self.brush_items()[:1],
            (prop('Instances per dab', 'int', 1, 30), lambda: self.density, self._set('density')),
            (prop('Min spacing', 'float', 0, 5, .05), lambda: self.spacing, self._set('spacing')),
            (prop('Scale min', 'float', 0, 5, .01), lambda: self.scale_min, self._set('scale_min')),
            (prop('Scale max', 'float', 0, 5, .01), lambda: self.scale_max, self._set('scale_max')),
            (prop('Random rotation', 'bool'), lambda: self.random_heading, self._set('random_heading')),
        ]
        if group is not None:
            data = group.data
            rows += [
                Section(f'Group: {data["name"]}'),
                (prop('Name', 'text'), lambda: data['name'], self._group_field('name', rebuild=False)),
                (prop('Model', 'choice', options=models, labels=[library.display_name(m) for m in models]),
                 lambda: data['model'], self._group_field('model', reload=True)),
                (prop('Wind sway', 'float', 0, .5, .005), lambda: data['sway'], self._group_field('sway')),
                (prop('Casts shadows', 'bool'), lambda: data['cast_shadow'], self._group_field('cast_shadow')),
                (prop('Receives shadows', 'bool'), lambda: data['receive_shadow'], self._group_field('receive_shadow')),
                (prop('Hide beyond draw distance', 'bool'), lambda: data['distance_render'],
                 self._group_field('distance_render', rebuild=True)),
                (prop('Collision', 'choice', options=('none', 'cylinder'), labels=('None', 'Trunk cylinder')),
                 lambda: data['collision']['shape'], self._collision_field('shape')),
                (prop('Trunk radius (scale 1)', 'float', .02, 3, .01), lambda: data['collision']['radius'],
                 self._collision_field('radius')),
                (prop('Collider height (scale 1)', 'float', .1, 20, .1), lambda: data['collision']['height'],
                 self._collision_field('height')),
            ]
            for material, color in objects.resolved_colors(data['model'], data['colors']).items():
                rows.append((prop(f'Color: {material or "default"}', 'color'),
                             (lambda m=material: objects.resolved_colors(data['model'], data['colors'])[m]),
                             (lambda value, m=material: self._set_color(m, value))))
            placed = sum(1 for item in self.world.objects
                         if item.data['model'] == data['model'] and item.data['kind'] == 'model')
            rows += self.editor._breakable_rows(lambda: group.data['breakable'], self._set_breakable,
                                                f'each {data["name"]} instance')
            rows += [Button('Reset colors', self._reset_colors, extra=(('Delete group', self.delete_group),)),
                     Button('Remove all instances', self.clear_group)]
            if placed:
                rows += [Note(f'{placed} objects placed one by one use this model; as foliage they cost one draw '
                              f'call per 25 m cell instead of one each.'),
                         Button(f'Convert those {placed} objects into this group', self.absorb_objects)]
        return rows

    def _set(self, attribute):
        def put(value):
            setattr(self, attribute, value)
        return put

    def _set_new_model(self, value):
        self.new_model = value

    def _pick(self, group):
        self.group = group
        self.editor.rebuild_left()

    def _snapshot(self):
        return self.world.snapshot(('foliage',))

    def _record(self, label, before, merge_key=None):
        after = self._snapshot()
        world = self.world
        self.editor.undo.push(label, lambda: world.restore(before), lambda: world.restore(after), merge_key)

    def create_group(self):
        before = self._snapshot()
        self.group = self.world.add_foliage(self.new_model)
        defaults = objects.model_defaults(self.new_model)
        self.scale_min = self.scale_max = defaults['scale']
        self._record('New foliage group', before)
        self.editor.rebuild_left()

    def delete_group(self):
        group = self._group()
        if group is None:
            return
        before = self._snapshot()
        self.world.remove_foliage(group)
        self.group = None
        self._record('Delete foliage group', before)
        self.editor.rebuild_left()

    def clear_group(self):
        group = self._group()
        if group is None:
            return
        before = self._snapshot()
        group.items = group.items[:0]
        group.ground = group.ground[:0]
        group.sync()
        group.rebuild()
        self.world.foliage_changed()
        self._record('Clear foliage', before)
        self.editor.rebuild_left()

    def absorb_objects(self):
        group = self._group()
        if group is None:
            return
        before = self.world.snapshot(('objects', 'foliage'))
        terrain = self.world.terrain
        model = group.data['model']
        taken = [item for item in self.world.objects if item.data['model'] == model and item.data['kind'] == 'model']
        rows = []
        for item in taken:
            x, y, z = item.data['pos']
            scale = float(item.data['scale'][0])
            ground = terrain.min_height_in_radius(x, y, max(scale, terrain.spacing))
            rows.append([x, y, z - ground, scale, float(item.data['hpr'][0])])
        if self.editor.selected in taken:
            self.editor.select(None)
        for item in taken:
            self.world.remove_object(item)
        group.items = np.vstack((group.items, np.array(rows))) if rows else group.items
        group.ground = np.zeros(len(group.items))
        group.update_ground()
        group.sync()
        group.rebuild()
        self.world.foliage_changed()
        after = self.world.snapshot(('objects', 'foliage'))
        world = self.world
        self.editor.undo.push('Convert to foliage', lambda: world.restore(before), lambda: world.restore(after))
        self.editor.status(f'{len(rows)} objects are now instances of "{group.data["name"]}"')
        self.editor.rebuild_left()

    def _group_field(self, key, reload=False, rebuild=False):
        def put(value):
            group = self._group()
            before = self._snapshot()
            group.data[key] = value
            if reload:
                group.reload_model()
            elif rebuild:
                group.rebuild()
            else:
                group.apply_flags()
            self.world.foliage_changed()
            self._record('Foliage setting', before, merge_key=('foliage', group.data['id'], key))
            if reload:
                self.editor.rebuild_left()
        return put

    def _collision_field(self, key):
        def put(value):
            group = self._group()
            before = self._snapshot()
            group.data['collision'][key] = value
            self.world.foliage_changed()
            self._record('Foliage collision', before, merge_key=('foliage-collision', group.data['id'], key))
        return put

    def _set_color(self, material, value):
        group = self._group()
        before = self._snapshot()
        group.data['colors'][material] = value
        group.reload_model()
        self.world.foliage_changed()
        self._record('Foliage color', before, merge_key=('foliage-color', group.data['id'], material))

    def _set_breakable(self, record):
        group = self._group()
        before = self._snapshot()
        group.data['breakable'] = record
        self.world.foliage_changed()
        self._record('Foliage breakable', before, merge_key=('foliage-breakable', group.data['id']))

    def _reset_colors(self):
        group = self._group()
        if group is None:
            return
        before = self._snapshot()
        group.data['colors'] = {}
        group.reload_model()
        self.world.foliage_changed()
        self._record('Reset foliage colors', before)
        self.editor.rebuild_left()

    def ring_color(self):
        return (1, .3, .3, 1) if control(self.editor) else (.5, 1, .4, 1)

    # Foliage strokes record a foliage snapshot instead of terrain arrays.
    def press(self):
        group = self._group()
        hit = self.editor.terrain_hit()
        if hit is None:
            return
        if group is None:
            self.editor.status('create a foliage group first')
            return
        self.stroke = {'before': self._snapshot()}
        self._last_point = None
        self._dab(hit)

    def update(self, delta):
        editor = self.editor
        hit = editor.terrain_hit()
        if hit is None or editor.over_gui():
            editor.ring.hide()
        else:
            editor.ring.show(hit[0], hit[1], self.radius, self.ring_color())
        if self.stroke is not None and hit is not None:
            if self._last_point is None or math.hypot(hit[0] - self._last_point[0],
                                                      hit[1] - self._last_point[1]) > max(self.radius * .4, .2):
                self._dab(hit)

    def _dab(self, hit):
        group = self._group()
        self._last_point = hit
        if control(self.editor):
            group.erase(hit[0], hit[1], self.radius)
        else:
            low, high = sorted((self.scale_min, self.scale_max))
            group.paint(hit[0], hit[1], self.radius, self.density, (low, high), self.random_heading, self.spacing,
                        self.rng)

    def release(self):
        stroke, self.stroke = self.stroke, None
        if stroke is None:
            return
        self.world.foliage_changed()
        self._record('Foliage brush', stroke['before'])
        self.editor.rebuild_left()


class WaterTool(BrushTool):
    name = 'water'
    title = 'Water'
    hint = 'drag: paint water   ctrl: erase   alt+click: set the level to the clicked ground   [ ]: radius'

    def __init__(self, editor):
        super().__init__(editor)
        self.body = None
        self.radius = 3.0
        self.carve = .6

    def _body(self):
        if self.body not in self.world.water:
            self.body = self.world.water[0] if self.world.water else None
        return self.body

    def items(self):
        body = self._body()
        rows = [
            Section('Water'),
            Note('Paint where a water body is. Its surface sits at the level; ground above the level hides it, '
                 'so "Carve depth" digs the ground below the level as you paint.'),
        ]
        for item in self.world.water:
            marker = '> ' if item is body else ''
            rows.append(Button(f'{marker}{item.data["name"]}', (lambda b=item: self._pick(b))))
        rows += [
            Button('New water body', self.create, extra=(('Delete', self.delete),)),
            Section('Brush'),
            (prop('Radius  ([ ])', 'float', .2, 40, .1), lambda: self.radius, self._set_radius),
            (prop('Carve depth', 'float', 0, 5, .05), lambda: self.carve, self._set_carve),
        ]
        if body is not None:
            data = body.data
            field = self._field
            rows += [
                Section(f'Body: {data["name"]}'),
                (prop('Name', 'text'), lambda: data['name'], field('name')),
                (prop('Level (height)', 'number', -100, 100, .05), lambda: data['level'], field('level', rebuild=True)),
                (prop('Shallow color', 'color'), lambda: data['shallow_color'], field('shallow_color')),
                (prop('Deep color', 'color'), lambda: data['deep_color'], field('deep_color')),
                Button('Lake', lambda: self.preset('lake'), extra=(('Clear', lambda: self.preset('clear')),
                                                                   ('Murky', lambda: self.preset('murky')),
                                                                   ('Frozen', lambda: self.preset('frozen')))),
                (prop('Opacity (everywhere)', 'float', 0, 1, .01), lambda: data['opacity'], field('opacity')),
                (prop('Opacity added by depth', 'float', 0, 1, .01), lambda: data['depth_opacity'],
                 field('depth_opacity')),
                (prop('Depth to deep color (m)', 'float', .05, 10, .05), lambda: data['clarity'], field('clarity')),
                (prop('Frozen: walk on it', 'bool'), lambda: data['walkable'], field('walkable')),
                (prop('Reflectivity', 'float', 0, 1, .01), lambda: data['reflectivity'], field('reflectivity')),
                (prop('Sun glint', 'float', 0, 4, .05), lambda: data['specular'], field('specular')),
                (prop('Wave height', 'float', 0, 2, .01), lambda: data['wave_height'], field('wave_height')),
                (prop('Wave size', 'float', .2, 5, .05), lambda: data['wave_scale'], field('wave_scale')),
                (prop('Wave speed', 'float', 0, 4, .05), lambda: data['wave_speed'], field('wave_speed')),
                (prop('Shore foam', 'float', 0, 1, .01), lambda: data['foam'], field('foam')),
                (prop('Foam color', 'color'), lambda: data['foam_color'], field('foam_color')),
            ]
        return rows

    def _set_carve(self, value):
        self.carve = value

    def _pick(self, body):
        self.body = body
        self.editor.rebuild_left()

    def _record(self, label, before, merge_key=None):
        after = self.world.snapshot(('water',))
        world = self.world
        self.editor.undo.push(label, lambda: world.restore(before), lambda: world.restore(after), merge_key)

    def _field(self, key, rebuild=False):
        def put(value):
            body = self._body()
            before = self.world.snapshot(('water',))
            body.data[key] = value
            if rebuild:
                body.rebuild()
            else:
                body.apply()
            self.world.water_changed()
            self._record('Water setting', before, merge_key=('water', body.data['id'], key))
            if key == 'name':
                self.editor.rebuild_left()
        return put

    PRESETS = {
        'lake': {'shallow_color': '#2f6f73', 'deep_color': '#0b2a3a', 'opacity': .2, 'depth_opacity': .8,
                 'clarity': 1.2, 'reflectivity': .6, 'specular': 1.0, 'wave_height': .35, 'wave_scale': 1.0,
                 'wave_speed': 1.0, 'foam': .6, 'walkable': False},
        'clear': {'shallow_color': '#5fb3b0', 'deep_color': '#1d5c73', 'opacity': .05, 'depth_opacity': .5,
                  'clarity': 3.0, 'reflectivity': .5, 'specular': 1.2, 'wave_height': .25, 'wave_scale': 1.0,
                  'wave_speed': 1.0, 'foam': .3, 'walkable': False},
        'murky': {'shallow_color': '#4a5a32', 'deep_color': '#1f2a14', 'opacity': .6, 'depth_opacity': 1.0,
                  'clarity': .4, 'reflectivity': .4, 'specular': .6, 'wave_height': .15, 'wave_scale': 1.5,
                  'wave_speed': .5, 'foam': .2, 'walkable': False},
        'frozen': {'shallow_color': '#a9cfe0', 'deep_color': '#5f8fa8', 'opacity': .92, 'depth_opacity': 1.0,
                   'clarity': 2.0, 'reflectivity': .5, 'specular': .6, 'wave_height': 0.0, 'wave_scale': 1.0,
                   'wave_speed': 0.0, 'foam': 0.0, 'walkable': True},
    }

    def preset(self, name):
        body = self._body()
        if body is None:
            return
        before = self.world.snapshot(('water',))
        body.data.update(self.PRESETS[name])
        body.apply()
        self.world.water_changed()
        self._record(f'Water: {name}', before)
        self.editor.refresh_left()

    def create(self):
        camera = self.editor.app.camera.get_pos()
        hit = self.editor.screen_center_hit()
        x, y = (hit[0], hit[1]) if hit else (camera.x, camera.y)
        level = self.world.terrain.height_at(x, y) - .05
        before = self.world.snapshot(('water',))
        self.body = self.world.add_water(level)
        self._record('New water body', before)
        self.editor.rebuild_left()

    def delete(self):
        body = self._body()
        if body is None:
            return
        terrain = self.world.terrain
        everything = (0, 0, terrain.segments + 1, terrain.segments + 1)
        terrain_before = terrain.snapshot(everything)
        before = self.world.snapshot(('water',))
        self.world.remove_water(body)
        terrain_after = terrain.snapshot(everything)
        after = self.world.snapshot(('water',))
        world = self.world

        def undo():
            terrain.restore(terrain_before)
            world.restore(before)
            world.terrain_edited()

        def redo():
            terrain.restore(terrain_after)
            world.restore(after)
            world.terrain_edited()

        self.editor.undo.push('Delete water', undo, redo)
        self.body = None
        self.editor.rebuild_left()

    def ring_color(self):
        return (1, .3, .3, 1) if control(self.editor) else (.4, .8, 1, 1)

    def press(self):
        if self._body() is None:
            self.editor.status('create a water body first')
            return
        super().press()

    def begin(self, hit):
        if alt(self.editor):
            body = self._body()
            body.data['level'] = float(hit[2])
            body.rebuild()
            self.world.water_changed()
            self.editor.refresh_left()

    def apply(self, hit, elapsed):
        if alt(self.editor):
            return
        body = self._body()
        window = water_brush.paint(self.world.terrain, body.mask_value, hit[0], hit[1], self.radius,
                                   erase=control(self.editor), carve=self.carve, level=body.data['level'])
        self.grow(window)
        if self.carve <= 0 or control(self.editor):
            body.rebuild()  # (carving changes heights, which rebuilds the water already)

    def end(self):
        self.world.water_changed(terrain=True)


# --------------------------------------------------------------------------- environment


class EnvironmentTool(Tool):
    name = 'environment'
    title = 'Environment'
    hint = 'light, sun and moon, sky, weather, terrain material and player physics: the panel on the right'

    def __init__(self, editor):
        super().__init__(editor)
        self.cloud_count = 7
        self.cloud_height = 14.0
        self.cloud_spread = 16.0

    def items(self):
        tabs = [tab.name for tab in settings.ENVIRONMENT_TABS]
        rows = [
            Section('Environment'),
            Note('All of these are saved with the world, so the game shows them too. Graphics settings (F1) '
                 'are per machine and shared by the game and the editor.'),
        ]
        for name in tabs:
            rows.append(Button(f'{name} settings', (lambda n=name: self.editor.open_settings(n))))
        rows += [
            Section('Presets'),
            *[Button(name, (lambda n=name: settings.store.apply_environment_preset(n)))
              for name in settings.ENVIRONMENT_PRESETS],
            Section('Sound'),
            (prop('Master volume', 'float', 0, 1, .01), lambda: settings.get('env.master_volume'),
             lambda value: settings.set('env.master_volume', value)),
            (prop('Footstep sounds', 'bool'), lambda: settings.get('env.footsteps'),
             lambda value: settings.set('env.footsteps', value)),
            (prop('Footsteps volume', 'float', 0, 1, .01), lambda: settings.get('env.footstep_volume'),
             lambda value: settings.set('env.footstep_volume', value)),
            (prop('Footsteps louder when running', 'float', 1, 2, .05), lambda: settings.get('env.footstep_run_volume'),
             lambda value: settings.set('env.footstep_run_volume', value)),
            (prop('Campfire volume', 'float', 0, 1, .01), lambda: settings.get('env.fire_volume'),
             lambda value: settings.set('env.fire_volume', value)),
            Section('Clouds'),
            Note(f'{len(self.world.data["clouds"])} clouds now. Color, speed, opacity and shadows are in Sky.'),
            (prop('Count', 'int', 0, 60), lambda: self.cloud_count, self._set('cloud_count')),
            (prop('Height', 'float', 4, 60, .5), lambda: self.cloud_height, self._set('cloud_height')),
            (prop('Spread', 'float', 4, 90, 1), lambda: self.cloud_spread, self._set('cloud_spread')),
            Button('Generate clouds', self.generate, extra=(('Remove clouds', self.clear),)),
        ]
        return rows

    def _set(self, attribute):
        def put(value):
            setattr(self, attribute, value)
        return put

    def activate(self):
        self.editor.open_settings('Lighting')

    def _apply_clouds(self, records, label):
        before = self.world.snapshot(('clouds',))
        self.world.set_clouds(records)
        after = self.world.snapshot(('clouds',))
        world = self.world
        self.editor.undo.push(label, lambda: world.restore(before), lambda: world.restore(after))
        self.editor.rebuild_left()

    def generate(self):
        height = (self.cloud_height - 2, self.cloud_height + 2)
        self._apply_clouds(generate_clouds(self.cloud_count, height, self.cloud_spread), 'Generate clouds')

    def clear(self):
        self._apply_clouds([], 'Remove clouds')


# -------------------------------------------------------------------------------- file


class FileTool(Tool):
    name = 'file'
    title = 'File'
    hint = 'save, load and create worlds   Ctrl+S saves (changes are also autosaved)'

    def __init__(self, editor):
        super().__init__(editor)
        self.save_name = ''
        self.new_name = 'new world'
        self.new_size = 200
        self.new_segments = 960
        self.pending_delete = None

    def items(self):
        world = self.world
        state = 'unsaved changes (autosaving...)' if world.unsaved else 'all changes saved'
        rows = [
            Section(f'World: {world.name}'),
            Note(f'{state}. The game (main.py) plays the world loaded here.'),
            Button('Save now  (Ctrl+S)', self.editor.save),
            (prop('Save as name', 'text'), lambda: self.save_name or world.name, self._set('save_name')),
            Button('Save as a copy', self.save_as),
            Section('Saved worlds'),
        ]
        for name in list_saves():
            marker = '> ' if name == world.name else ''
            delete_label = 'Confirm delete' if self.pending_delete == name else 'Delete'
            rows.append(Button(f'{marker}{name}', (lambda n=name: self.load(n)),
                               extra=((delete_label, (lambda n=name: self.delete(n))),)))
        rows += [
            Section('New world'),
            (prop('Name', 'text'), lambda: self.new_name, self._set('new_name')),
            (prop('Size (m)', 'choice', options=(100, 200, 400), labels=('100 m', '200 m', '400 m')),
             lambda: self.new_size, self._set('new_size')),
            (prop('Terrain detail', 'choice', options=(480, 960, 1440), labels=('Low', 'High', 'Ultra')),
             lambda: self.new_segments, self._set('new_segments')),
            Button('Create flat world', self.create_flat, extra=(('Copy of the JS scene', self.create_default),)),
        ]
        return rows

    def _set(self, attribute):
        def put(value):
            setattr(self, attribute, value)
        return put

    def save_as(self):
        name = (self.save_name or self.world.name).strip()
        if not name:
            return
        if name == self.world.name:
            name += ' copy'
        self.world.save(name, wait=True)
        self.save_name = ''
        self.editor.status(f'saved as "{self.world.name}"')
        self.editor.world_switched()

    def load(self, name):
        if name == self.world.name:
            return
        self.editor.load_world(name)

    def delete(self, name):
        if name == self.world.name:
            self.editor.status('cannot delete the open world; load another one first')
            return
        if self.pending_delete != name:
            self.pending_delete = name
            self.editor.status(f'click "Confirm delete" to delete "{name}" for good')
            self.editor.rebuild_left()
            return
        delete_save(name)
        self.pending_delete = None
        self.editor.status(f'deleted "{name}"')
        self.editor.rebuild_left()

    def create_flat(self):
        from ..world.document import WorldDocument, clean_name, exists
        name = clean_name(self.new_name)
        if exists(name):
            self.editor.status(f'"{name}" already exists')
            return
        self.world.flush()
        document = WorldDocument.empty(name, self.new_size, self.new_segments)
        document.data['environment'] = settings.store.environment()
        start = document.data['player']
        start['start'] = [0.0, 0.0, 0.0]
        document.save(wait=True)
        self.editor.load_world(name)

    def create_default(self):
        from ..world.document import clean_name, exists
        from ..world.legacy import build_default_world
        name = clean_name(self.new_name)
        if exists(name):
            self.editor.status(f'"{name}" already exists')
            return
        self.world.flush()
        build_default_world(name).save(wait=True)
        self.editor.load_world(name)


TOOLS = (FileTool, SelectTool, PlaceTool, SculptTool, PaintTool, FoliageTool, WaterTool, EnvironmentTool)
SHAPES = COLLISION_SHAPES
