"""Player inventory (game): pick up items placed in the editor (world objects of kind 'item'), carry
them in an 8-slot hotbar, hold the selected one in view and use it.

E picks up the item you look at, 1-8 or the wheel select a slot, G drops the held item in front of
you, F switches a held flashlight on and off (its light settings come from the editor), left click
swings a held axe: what it hits breaks after enough hits (the 'breakable' settings of objects and
foliage groups) and its drops (wood, ...) stack into the hotbar. Picked-up items and broken things
are gone for this session only; the world save is never changed by playing.
"""
import copy
import math

import numpy as np
from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectFrame
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.DirectObject import DirectObject
from panda3d.core import LMatrix3f, NodePath, Point3, Quat, TextNode

from .. import library, objects, registry, settings, shading, shadow_cache
from ..paths import asset, panda_filename
from ..update import add_update_callback
from ..world import breakables, items as item_tools
from .outline import Outline, outline, remove_outline

SLOTS = 8
REACH = 2.6  # meters from the eye
SLOT_SIZE = .15
HELD_OFFSET = (.21, .46, -.22)  # camera space: right, forward, up
HELD_ANGLE = (24, 10, -12)  # heading, pitch, roll: turned so its side shows, not just its tail
AIM_DISTANCE = 12.0  # the beam converges on the crosshair this far ahead
TOOL_OFFSET = (.23, .56, -.42)  # camera space position of the hand holding a tool
TOOL_ANGLE = (0, -15, -32)  # heading, pitch, roll at rest: head up, leaning forward and towards the middle
TOOL_TWIST = 65  # degrees the tool turns about its handle, so the blade shows in profile
TOOL_LENGTH = .47  # meters a held tool measures from grip to head (on screen)
STACK = 99  # resources per slot
# (fraction of the swing, pitch, hand up, hand forward): raise the hand and tip the head back, then drive
# the hand forward and down so the blade cuts through the middle of the view, and recover.
SWING = ((0.0, 0.0, 0.0, 0.0), (.3, 30.0, .2, -.04), (.5, -40.0, .02, .16), (.6, -44.0, -.02, .16),
         (1.0, 0.0, 0.0, 0.0))
IMPACT = .5  # fraction of the swing where the blade lands

EMPTY = (0, 0, 0, .45)
FILLED = (.12, .1, .09, .7)
ACTIVE = (.95, .55, .22, .85)


class Slot:
    def __init__(self, record, count=1):
        self.record = copy.deepcopy(record)
        self.count = count
        self.on = False
        self.drained = 0.0

    @classmethod
    def resource(cls, name, count):
        """A stack of something gathered (wood, ...): no model, just a name and a count."""
        return cls({'name': name, 'model': '', 'colors': {}, 'scale': [1.0] * 3,
                    'item': {'type': 'resource', 'label': name}}, count)

    @property
    def type(self):
        return self.record['item']['type']

    @property
    def name(self):
        item = self.record['item']
        return item['label'] or self.record['name'] or library.display_name(self.record['model'])

    @property
    def label(self):
        return f'{self.name} x{self.count}' if self.type == 'resource' else self.name

    @property
    def is_flashlight(self):
        return self.type == 'flashlight'


class Inventory(DirectObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.world = registry.get('world')
        self.slots = [None] * SLOTS
        self.current = 0
        self.target = None
        self.held = None  # (pivot node, beam, glow nodes) of the selected item
        self.view_root = app.camera.attach_new_node('held-item')
        self.view_root.set_pos(*HELD_OFFSET)
        self.view_root.set_hpr(*HELD_ANGLE)
        shading.set_cast_shadow(self.view_root, False)
        self.tool_root = app.camera.attach_new_node('held-tool')
        self.tool_root.set_pos(*TOOL_OFFSET)
        self.tool_root.set_hpr(*TOOL_ANGLE)
        self.swing_node = self.tool_root.attach_new_node('swing')
        shading.set_cast_shadow(self.tool_root, False)
        shading.set_snow_catcher(self.view_root, False)  # held items don't catch falling snow
        shading.set_snow_catcher(self.tool_root, False)
        self.swing = None  # seconds into the current swing
        self.hit_done = False
        self.damage = {}  # target key -> damage taken this session
        self.chop_target = None
        # Outline of what the axe would hit: (key, outlined node, temporary copy or None). A foliage
        # instance is part of a baked mesh, so a copy of it under a hidden parent gets the outline.
        self.chop_outline = None
        # A fainter, thinner outline marks the item whose pick-up hint is showing.
        self.hint_outline = Outline(app, color=(1, 1, 1, .45), thickness=1)
        self.hinted = None
        self._outline_parent = app.render.attach_new_node('chop-outline')
        self._outline_parent.hide()
        self.sounds = {name: self._sound(path) for name, path in (('hit', 'sound/player/axe_hit.mp3'),
                                                                  ('break', 'sound/player/break.mp3'))}

        bar = app.a2dBottomCenter.attach_new_node('hotbar')
        width = SLOTS * SLOT_SIZE + (SLOTS - 1) * .012
        bar.set_pos(-width / 2, 0, .1)
        self.frames, self.labels = [], []
        for index in range(SLOTS):
            x = index * (SLOT_SIZE + .012)
            frame = DirectFrame(parent=bar, frameSize=(x, x + SLOT_SIZE, 0, SLOT_SIZE * .7), frameColor=EMPTY,
                                relief=DGG.FLAT, state=DGG.DISABLED)
            OnscreenText(parent=bar, text=str(index + 1), pos=(x + .015, SLOT_SIZE * .7 - .03), scale=.03,
                         align=TextNode.A_left, fg=(1, 1, 1, .6), mayChange=False)
            self.labels.append(OnscreenText(parent=bar, text='', pos=(x + SLOT_SIZE / 2, .035), scale=.027,
                                            fg=(1, 1, 1, .95), shadow=(0, 0, 0, .8), mayChange=True,
                                            wordwrap=SLOT_SIZE / .027 * .95))
            self.frames.append(frame)
        self.prompt = OnscreenText(text='', pos=(0, -.12), scale=.045, fg=(1, 1, 1, .95), shadow=(0, 0, 0, .8),
                                   mayChange=True)
        self.status = OnscreenText(text='', pos=(0, .1 + SLOT_SIZE * .7 + .04), scale=.035, fg=(1, .9, .7, .9),
                                   shadow=(0, 0, 0, .8), mayChange=True, parent=app.a2dBottomCenter)
        self._status_time = 0.0

        self.accept('e', self.pick_up)
        self.accept('g', self.drop)
        self.accept('f', self.toggle_light)
        for index in range(SLOTS):
            self.accept(str(index + 1), self.select, [index])
        self.accept('wheel_up', self._wheel, [-1])
        self.accept('wheel_down', self._wheel, [1])
        self.world.add_listener(self._world_changed)
        self._refresh_bar()
        add_update_callback(self.update)

    # ------------------------------------------------------------------------- slots

    def _panel_open(self):
        panel = registry.get('settingsPanel')
        return panel is not None and panel.visible

    def _wheel(self, direction):
        if not self._panel_open():
            self.select((self.current + direction) % SLOTS)

    def select(self, index):
        if self._panel_open():
            return
        self._store_held()
        self.current = index
        self._show_held()
        self._refresh_bar()

    def _refresh_bar(self):
        for index, (frame, text) in enumerate(zip(self.frames, self.labels)):
            slot = self.slots[index]
            frame['frameColor'] = ACTIVE if index == self.current else (FILLED if slot else EMPTY)
            label = slot.label if slot else ''
            if slot and slot.is_flashlight:
                label += '\n(on)' if slot.on else ''
            text.setText(label)

    def _say(self, text, seconds=2.5):
        self.status.setText(text)
        self._status_time = seconds

    # --------------------------------------------------------------------- pick up

    def _find_target(self):
        camera = self.app.camera
        eye = camera.get_pos(self.app.render)
        forward = camera.get_quat(self.app.render).get_forward()
        best, best_score = None, -1.0
        for item in self.world.objects:
            if item.data['kind'] != 'item' or not item.data['visible']:
                continue
            bounds = item.root.get_bounds()
            if bounds.is_empty():
                continue
            center = self.app.render.get_relative_point(item.root.get_parent(), bounds.get_center())
            offset = center - eye
            distance = offset.length()
            radius = bounds.get_radius()
            if distance - radius > REACH or distance < 1e-3:
                continue
            cosine = forward.dot(offset / distance)
            allowed = math.cos(min(math.radians(14) + math.atan2(radius, distance), math.radians(60)))
            if cosine > allowed and cosine > best_score:
                best, best_score = item, cosine
        return best

    def pick_up(self):
        if self._panel_open() or self.target is None:
            return
        free = self.current if self.slots[self.current] is None else next(
            (index for index, slot in enumerate(self.slots) if slot is None), None)
        if free is None:
            self._say('inventory full: drop something first (G)')
            return
        item = self.target
        self._set_hint_outline(None)  # before the item leaves the world
        slot = Slot(item.data)
        light = slot.record['item']['light']
        if slot.is_flashlight and item.prefab is not None and getattr(item.prefab, 'beam', None) is not None:
            slot.on = item.prefab.beam.on
            slot.drained = item.prefab.beam.drained
        elif slot.is_flashlight:
            slot.on = light['starts_on']
        self.world.take_object(item)
        self.target = None
        self._store_held()
        self.slots[free] = slot
        self.current = free
        self._show_held()
        self._refresh_bar()
        hint = '   F: switch on / off' if slot.is_flashlight else ''
        self._say(f'picked up {slot.label}{hint}')

    def drop(self):
        slot = self.slots[self.current]
        if slot is None or self._panel_open():
            return
        if slot.type == 'resource':
            self._say(f'{slot.name} has no model to drop yet')
            return
        self._store_held()
        camera = self.app.camera
        heading = camera.get_h(self.app.render)
        forward = camera.get_quat(self.app.render).get_forward()
        forward.z = 0
        forward = forward.normalized() if forward.length() > 1e-6 else forward
        eye = camera.get_pos(self.app.render)
        x, y = eye.x + forward.x * 1.1, eye.y + forward.y * 1.1
        record = copy.deepcopy(slot.record)
        info = library.stats(record['model'])
        scale = record['scale'][0]
        if slot.is_flashlight:
            axis = np.abs(item_tools.axis_vector(record['item']['beam']))
            extent = (np.array(info['max']) - np.array(info['min'])) * (1 - axis)
            lift = float(extent.max()) / 2 * scale
            record['item']['light']['starts_on'] = slot.on
        else:
            lift = -float(info['min'][2]) * scale
        z = self.world.terrain.height_at(x, y) + lift
        dropped = self.world.drop_object(record, (x, y, z), heading)
        if slot.is_flashlight and dropped.prefab is not None and getattr(dropped.prefab, 'beam', None) is not None:
            dropped.prefab.beam.drained = slot.drained
        self.slots[self.current] = None
        self._refresh_bar()
        self._say(f'dropped {slot.label}')

    # ------------------------------------------------------------------------ held

    def _show_held(self):
        slot = self.slots[self.current]
        if slot is None:
            return
        record = slot.record
        if slot.type == 'resource':
            return
        try:
            model = objects.instance(record['model'], record['colors'])
        except Exception as error:
            self._say(f'cannot show {slot.label}: {error}')
            return
        if slot.type == 'axe':
            self._show_tool(slot, model)
            return
        beam_axis = item_tools.axis_vector(record['item']['beam'])
        info = library.stats(record['model'])
        center = (np.array(info['min']) + np.array(info['max'])) / 2
        pivot = self.view_root.attach_new_node('held-pivot')
        helper = NodePath('aim')
        item_tools.aim(helper, beam_axis)
        pivot.set_quat(Quat(helper.get_quat()).conjugate())  # the beam axis points where you look
        pivot.set_scale(item_tools.held_scale(record['model'], record['item']['beam']))
        model.reparent_to(pivot)
        model.set_pos(*(-center))
        beam, glow = None, []
        if slot.is_flashlight:
            tip, _axis = item_tools.beam_tip(record['model'], record['item']['beam'])
            # The light starts at the lens but hangs off the camera aimed at the crosshair, so the tilted
            # model and its sway don't throw the beam around.
            camera = self.app.camera
            anchor = camera.attach_new_node('held-beam')
            anchor.set_pos(camera.get_relative_point(model, Point3(*(float(v) for v in tip))))
            anchor.look_at(0, AIM_DISTANCE, 0)
            pivot.set_python_tag('beam_anchor', anchor)
            beam = item_tools.FlashlightBeam(self.app.render, anchor, record['item']['light'], held=True)
            pivot.set_light_off(beam.path)  # the flashlight in your hand isn't lit by its own beam
            beam.drained = slot.drained
            beam.set_on(slot.on)
            glow = item_tools.glow_nodes(model, record['model'])
            item_tools.set_glow(glow, beam.on, record['item']['light']['color'])
        self.held = (pivot, beam, glow)

    def _show_tool(self, slot, model):
        """Hold a tool by its grip, head up, blade facing forward, ready to swing."""
        record = slot.record
        tool = record['item']['tool']
        head, edge = item_tools.tool_axes(record['model'], tool)
        side = np.cross(head, edge)
        target = np.column_stack(((0, 0, 1), (0, 1, 0), np.cross((0, 0, 1), (0, 1, 0))))
        source = np.column_stack((head, edge, side))
        rotation = target @ source.T  # model axes -> hand axes
        twist = self.swing_node.attach_new_node('held-twist')
        twist.set_h(TOOL_TWIST)
        pivot = twist.attach_new_node('held-pivot')
        quat = Quat()
        quat.set_from_matrix(LMatrix3f(*rotation.T.ravel()))  # Panda multiplies row vectors
        pivot.set_quat(quat)
        info = library.stats(record['model'])
        length = float(np.abs((np.array(info['max']) - np.array(info['min'])) @ np.abs(head)))
        pivot.set_scale(TOOL_LENGTH / max(length, 1e-3))
        model.reparent_to(pivot)
        model.set_pos(*(-item_tools.grip_point(record['model'], head)))
        self.held = (twist, None, [])

    def _store_held(self):
        self._set_chop_outline(None)
        self.swing = None
        self.swing_node.set_pos_hpr(0, 0, 0, 0, 0, 0)
        if self.held is None:
            return
        pivot, beam, _glow = self.held
        slot = self.slots[self.current]
        if beam is not None:
            if slot is not None:
                slot.on, slot.drained = beam.on, beam.drained
            beam.destroy()
        anchor = pivot.get_python_tag('beam_anchor')
        if anchor is not None:
            anchor.remove_node()
        pivot.remove_node()
        self.held = None

    def toggle_light(self):
        if self._panel_open() or self.held is None or self.held[1] is None:
            return
        slot = self.slots[self.current]
        pivot, beam, glow = self.held
        if beam.battery_left <= 0:
            self._say('the battery is empty')
            return
        beam.set_on(not beam.on)
        slot.on = beam.on
        item_tools.set_glow(glow, beam.on, slot.record['item']['light']['color'])
        self._refresh_bar()

    # ------------------------------------------------------------------- tools

    def _sound(self, relative):
        path = asset(relative)
        if not path.is_file():
            return None  # optional: drop the file in to get the sound
        try:
            return self.app.loader.load_sfx(panda_filename(path))
        except Exception:
            return None

    def _play(self, name):
        sound = self.sounds.get(name)
        if sound is not None:
            sound.play()

    def held_type(self):
        slot = self.slots[self.current]
        return slot.type if slot is not None and slot.type != 'resource' else None

    def use(self):
        """Left click while the mouse is captured. Returns True when the held item used it."""
        if self._panel_open() or self.held_type() != 'axe':
            return False
        if self.swing is None:
            self.swing = 0.0
            self.hit_done = False
        return True

    def _find_breakable(self):
        """The breakable thing the held item can hit: ('object', item) or ('foliage', group, index)."""
        held = self.held_type()
        slot = self.slots[self.current]
        reach = slot.record['item']['tool']['reach'] if held == 'axe' else 1.6
        camera = self.app.camera
        eye = camera.get_pos(self.app.render)
        forward = camera.get_quat(self.app.render).get_forward()
        flat = np.array([forward.x, forward.y])
        flat /= max(np.linalg.norm(flat), 1e-6)
        best, best_angle = None, math.radians(28)

        def consider(target, x, y, radius, bottom, top):
            nonlocal best, best_angle
            offset = np.array([x - eye.x, y - eye.y])
            distance = float(np.linalg.norm(offset))
            if distance - radius > reach or bottom > eye.z + .5 or top < eye.z - 2.2:
                return
            if distance < 1e-3:
                angle = 0.0
            else:
                angle = math.acos(max(-1, min(1, float(offset @ flat) / distance)))
                angle = max(angle - math.atan2(radius, distance), 0)
            if angle < best_angle:
                best, best_angle = target, angle

        for item in self.world.objects:
            if not breakables.accepts(item.data.get('breakable', {}), held) or item.local_bounds is None:
                continue
            bounds = item.root.get_bounds()
            if bounds.is_empty():
                continue
            center = self.app.render.get_relative_point(item.root.get_parent(), bounds.get_center())
            radius = bounds.get_radius()
            consider(('object', item), center.x, center.y, radius * .5, center.z - radius, center.z + radius)
        for group in self.world.foliage:
            if not breakables.accepts(group.data.get('breakable', {}), held) or not len(group.items):
                continue
            near = np.nonzero(np.hypot(group.items[:, 0] - eye.x, group.items[:, 1] - eye.y) < reach + 3)[0]
            trunk = max(group.data['collision'].get('radius', .3), .15)
            height = group.data['collision'].get('height', 3.0)
            for index in near:
                x, y, offset, scale, _heading = group.items[index]
                bottom = group.ground[index] + offset
                consider(('foliage', group, int(index)), x, y, trunk * scale, bottom, bottom + height * scale)
        return best

    def _target_info(self, target):
        """(key, label, breakable record) of a target."""
        if target[0] == 'object':
            item = target[1]
            return (('object', item.id), item.data['name'] or library.display_name(item.data['model']),
                    item.data['breakable'])
        _, group, index = target
        x, y = group.items[index, 0], group.items[index, 1]
        name = group.data['name']
        label = name[:-1] if name.endswith('s') and len(name) > 3 else name
        return (('foliage', group.data['id'], round(float(x), 3), round(float(y), 3)), label, group.data['breakable'])

    def _set_hint_outline(self, item):
        """Faintly outline the item the pick-up hint is about (or nothing)."""
        if item is self.hinted:
            return
        if self.hinted is not None and not self.hinted.root.is_empty():
            self.hint_outline.set_outlined(self.hinted.root, False)
        self.hinted = item
        if item is not None:
            self.hint_outline.set_outlined(item.root, True)

    def _set_chop_outline(self, target):
        key = self._target_info(target)[0] if target is not None else None
        if self.chop_outline is not None and self.chop_outline[0] == key:
            return
        if self.chop_outline is not None:
            _key, node, copy_node = self.chop_outline
            if not node.is_empty():
                remove_outline(node)
            if copy_node is not None:
                copy_node.remove_node()
            self.chop_outline = None
        if target is None:
            return
        if target[0] == 'object':
            node = target[1].root
            outline(node)
            self.chop_outline = (key, node, None)
            return
        _, group, index = target
        try:
            node = objects.instance(group.data['model'], group.data['colors'])
        except Exception:
            return
        x, y, z = group.position(index)
        node.reparent_to(self._outline_parent)
        node.set_pos(x, y, z)
        node.set_h(float(group.items[index, 4]))
        node.set_scale(float(group.items[index, 3]))
        outline(node)
        self.chop_outline = (key, node, node)

    def _hit(self):
        target = self._find_breakable()
        if target is None:
            return
        key, label, breakable = self._target_info(target)
        slot = self.slots[self.current]
        damage = slot.record['item']['tool']['damage'] if slot is not None and slot.type == 'axe' else 1.0
        taken = self.damage.get(key, 0.0) + damage
        hits = max(breakable['hits'], .01)
        controls = registry.get('firstPersonControls')
        if controls is not None:
            controls.landing = max(controls.landing, .12)  # a jolt on impact
        if taken < hits - 1e-6:
            self.damage[key] = taken
            self._play('hit')
            self._say(f'{label}: {math.ceil(taken / damage)} / {math.ceil(hits / damage)}', 1.5)
            if target[0] == 'object':
                self._wobble(target[1].root)
            return
        self.damage.pop(key, None)
        self._set_chop_outline(None)  # before the node goes away
        self._play('break')
        if target[0] == 'object':
            self.world.take_object(target[1])
        else:
            _, group, index = target
            group.remove_item(index, persist=False)  # this session only
            self.world.notify('foliage')  # colliders and shadows follow
            shadow_cache.invalidate()
        gained = []
        for name, count in breakables.drops(breakable):
            left = self.add_resource(name, count)
            gained.append(f'+{count - left} {name}' + (' (inventory full)' if left else ''))
        self._say(f'{label} broken  ' + '  '.join(gained) if gained else f'{label} broken')

    def _wobble(self, node):
        start = node.get_r()

        def shake(task):
            if node.is_empty():
                return task.done
            if task.time > .35:
                node.set_r(start)
                return task.done
            node.set_r(start + math.sin(task.time * 45) * 4 * (1 - task.time / .35))
            return task.cont

        self.app.task_mgr.add(shake, 'wobble')

    def add_resource(self, name, count):
        """Stack `count` of a resource into the hotbar. Returns how many didn't fit."""
        for slot in self.slots:
            if slot is not None and slot.type == 'resource' and slot.name == name and slot.count < STACK:
                moved = min(count, STACK - slot.count)
                slot.count += moved
                count -= moved
        while count > 0:
            free = next((index for index, slot in enumerate(self.slots) if slot is None), None)
            if free is None:
                break
            moved = min(count, STACK)
            self.slots[free] = Slot.resource(name, moved)
            count -= moved
        self._refresh_bar()
        return count

    def _update_swing(self, delta):
        if self.swing is None:
            return
        slot = self.slots[self.current]
        duration = max(slot.record['item']['tool']['swing_time'], .15) if slot is not None else .5
        self.swing += delta
        t = min(self.swing / duration, 1.0)
        for (t0, p0, up0, fw0), (t1, p1, up1, fw1) in zip(SWING, SWING[1:]):
            if t0 <= t <= t1:
                k = (t - t0) / max(t1 - t0, 1e-6)
                k = k * k * (3 - 2 * k)
                self.swing_node.set_p(p0 + (p1 - p0) * k)
                # Hand movement in camera space (up / forward), whatever the tool's resting tilt.
                offset = self.tool_root.get_relative_vector(self.app.camera, (0, fw0 + (fw1 - fw0) * k,
                                                                               up0 + (up1 - up0) * k))
                self.swing_node.set_pos(offset)
                break
        if not self.hit_done and t >= IMPACT:
            self.hit_done = True
            self._hit()
        if t >= 1.0:
            self.swing = None
            self.swing_node.set_pos_hpr(0, 0, 0, 0, 0, 0)

    # ---------------------------------------------------------------------- frame

    def _world_changed(self, section):
        if section == 'loaded':
            for _key, (_node, holder) in list(self.hint_outline.objects.items()):
                holder.remove_node()  # the outlined item is gone with the old world
            self.hint_outline.objects.clear()
            self.hint_outline.set_outlined(self.app.render.attach_new_node('none'), False)
            self.hinted = None
            self._store_held()
            self.slots = [None] * SLOTS
            self._refresh_bar()

    def update(self, delta):
        self.target = self._find_target() if not self._panel_open() else None
        self._update_swing(delta)
        # What the axe would hit, outlined for as long as an axe is in hand.
        holding_axe = self.held_type() == 'axe' and not self._panel_open() and self.target is None
        chop = self._find_breakable() if holding_axe else None
        self._set_chop_outline(chop)
        self._set_hint_outline(self.target)
        if self.target is not None:
            data = self.target.data
            name = data['item']['label'] or data['name'] or library.display_name(data['model'])
            self.prompt.setText(f'E   pick up {name}')
        elif chop is not None:
            self.prompt.setText(f'click   chop {self._target_info(chop)[1]}')
        else:
            self.prompt.setText('')
        if self.held is not None and self.held[1] is not None:
            pivot, beam, glow = self.held
            was_on = beam.on
            beam.update(delta)
            if was_on and not beam.on:  # battery ran out
                slot = self.slots[self.current]
                slot.on = False
                item_tools.set_glow(glow, False, slot.record['item']['light']['color'])
                self._refresh_bar()
                self._say('the flashlight battery ran out')
        if self.held is not None:
            # A gentle sway while walking keeps the held item from looking glued to the screen.
            controls = registry.get('firstPersonControls')
            moving = controls is not None and any(controls.pressed[key] for key in 'wasd')
            self._bob = getattr(self, '_bob', 0.0) + delta * (7 if moving else 1.2)
            amount = (.012 if moving else .004) if settings.get('env.head_bob') else 0.0
            self.view_root.set_pos(HELD_OFFSET[0] + math.sin(self._bob) * amount * .6, HELD_OFFSET[1],
                                   HELD_OFFSET[2] + abs(math.cos(self._bob)) * amount)
            self.tool_root.set_pos(TOOL_OFFSET[0] + math.sin(self._bob) * amount * .6, TOOL_OFFSET[1],
                                   TOOL_OFFSET[2] + abs(math.cos(self._bob)) * amount)
        if self._status_time > 0:
            self._status_time -= delta
            if self._status_time <= 0:
                self.status.setText('')


def draw(app):
    registry.add('inventory', Inventory(app))

