"""World editor (editor.py at the project root): edits the active world save with the game's
renderer and graphics settings.

Layout: tool bar on top, tool options on the left, the selected object's properties on the right,
status line at the bottom. F1 opens the graphics / environment settings.

Camera: hold the right button to look and fly (WASD, Q/E, Shift), wheel zooms to the cursor, middle
button orbits, Shift + middle button pans, F frames the selection.
"""
import copy
import math
import subprocess
import sys
import time

from direct.showbase.DirectObject import DirectObject
from panda3d.core import (BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay, CollisionTraverser,
                          KeyboardButton, ModifierButtons, Point3, TextNode)

from .. import library, objects, registry, settings
from ..controls.outline import outline, remove_outline
from ..paths import PACKAGE_DIR
from ..settings import Section
from ..ui import widgets
from ..ui.widgets import (ACCENT, BUTTON, BUTTON_ACTIVE, MUTED_TEXT, PANEL_TEXT, Button, Note, PropertyList, button,
                          label, panel, prop)
from ..update import add_update_callback
from ..world import compiler
from ..world.collision import Colliders
from ..world.document import COLLISION_SHAPES, OBJECT_KINDS
from ..world.entities import EDITOR_PICK_MASK
from ..world.colliders import SHAPES as COLLIDER_SHAPES, TAG as COLLIDER_TAG
from ..world.foliage import TAG as FOLIAGE_TAG
from ..world.breakables import TOOL_LABELS as BREAK_TOOL_LABELS, TOOLS as BREAK_TOOLS
from ..world.items import BEAM_AXES, ITEM_TYPES, LIGHT_MODES, TOOL_AXES
from ..world.lights import LIGHT_TYPES, MODES as LIGHT_MODES_PLACED, new_light
from . import benchmark, overlays
from .camera import EditorCamera
from .tools import TOOLS
from .undo import UndoStack

BAR = .09
STATUS = .065
LEFT_WIDTH = .84
RIGHT_WIDTH = .86
TOOL_KEYS = {'1': 'select', '2': 'place', '3': 'sculpt', '4': 'paint', '5': 'foliage', '6': 'water',
             '7': 'environment', '8': 'file'}
HELP = ('RMB: look + WASD/QE fly   wheel: zoom   MMB: orbit   shift+MMB: pan   F: focus   '
        '1-8: tools   Ctrl+Z/Y: undo/redo   Ctrl+S: save   C: colliders   F1: settings')


class Editor(DirectObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.world = registry.get('world')
        self.selected = None
        self.selected_instance = None  # (foliage group id, index) of a selected foliage instance
        self.selected_collider = None  # a standalone collider (world/colliders.py)
        self.undo = UndoStack(self._undo_changed)
        self.camera = EditorCamera(self)
        self.ring = overlays.BrushRing(app, lambda: self.world.terrain)
        self.collider_view = overlays.ColliderView(app)
        self.colliders = Colliders(self.world)
        self.player_marker = overlays.PlayerMarker(app)
        # Outlines draw what is under a node; this hidden parent holds a copy of the selected foliage
        # instance so it gets an outline without being drawn twice.
        self._highlight_parent = app.render.attach_new_node('instance-highlight')
        self._highlight_parent.hide()
        self._highlight = None
        self._hit_cache = None
        self._message = ''
        self._message_until = 0.0
        self._props_dirty = False
        self._fps = 0.0
        self.report_window = None
        self.model_stamps = {}
        self.benchmark = None

        if app.mouseWatcherNode is None:  # offscreen (tests): no mouse, nothing held
            from panda3d.core import MouseWatcher
            app.mouseWatcherNode = MouseWatcher('no-mouse')
        # Modifiers are checked by hand, so plain events fire whatever is held (no 'shift-mouse1').
        for thrower in app.buttonThrowers or []:
            thrower.node().set_modifier_buttons(ModifierButtons())
        app.set_frame_rate_meter(False)

        self.tools = {tool.name: tool(self) for tool in TOOLS}
        self.tool = None
        self._build_ui()

        self.picker = CollisionTraverser('editor-pick')
        self.pick_queue = CollisionHandlerQueue()
        self.pick_ray = CollisionRay()
        node = CollisionNode('editor-pick-ray')
        node.add_solid(self.pick_ray)
        node.set_from_collide_mask(EDITOR_PICK_MASK)
        node.set_into_collide_mask(BitMask32.all_off())
        self.picker.add_collider(app.cam.attach_new_node(node), self.pick_queue)

        self._bind_input()
        self.world.add_listener(self._world_changed)
        self.app.accept('settings-panel', self._settings_panel_toggled)
        add_update_callback(self.update)

        app.camera.set_pos(8, -16, 10)
        app.camera.look_at(2, 2, 0)
        self._record_model_stamps()
        self._update_player_marker()
        self.set_tool('select')

    # ------------------------------------------------------------------------------- UI

    def _build_ui(self):
        app = self.app
        bar = app.a2dTopLeft.attach_new_node('editor-bar')
        panel(bar, (0, 6, -BAR, 0))
        self.tool_buttons = {}
        x = .03
        order = ('file', 'select', 'place', 'sculpt', 'paint', 'foliage', 'water', 'environment')
        for name in order:
            tool = self.tools[name]
            key = next((k for k, v in TOOL_KEYS.items() if v == name), '')
            text = f'{tool.title} {key}' if key else tool.title
            width = .045 + len(text) * .0155
            self.tool_buttons[name] = button(bar, text, x + width / 2, -BAR / 2, self.set_tool, width=width,
                                             scale=.027, extra_args=[name])
            x += width + .012

        right = app.a2dTopRight.attach_new_node('editor-actions')
        actions = (('Play', self.play), ('Compile', self.compile), ('Analyze', self.analyze),
                   ('Benchmark', self.run_benchmark), ('Save', self.save), ('Redo', self.redo), ('Undo', self.undo_action),
                   ('Colliders C', self.toggle_colliders), ('Settings F1', self.toggle_settings))
        x = -.03
        self.action_buttons = {}
        for text, command in actions:
            width = .045 + len(text) * .0155
            self.action_buttons[text] = button(right, text, x - width / 2, -BAR / 2, command, width=width, scale=.027)
            x -= width + .012

        self.left_root = app.a2dTopLeft.attach_new_node('editor-left')
        panel(self.left_root, (0, LEFT_WIDTH, -2 + STATUS + .005, -BAR - .005))
        self.left_list = None

        self.right_root = app.a2dTopRight.attach_new_node('editor-right')
        self.right_root.set_x(-RIGHT_WIDTH)
        panel(self.right_root, (0, RIGHT_WIDTH, -2 + STATUS + .005, -BAR - .005))
        self.right_list = None
        self.right_root.hide()

        status = app.a2dBottomLeft.attach_new_node('editor-status')
        panel(status, (0, 6, 0, STATUS))
        self.hint_text = label(status, '', .03, .022, scale=.028, color=MUTED_TEXT)
        right_status = app.a2dBottomRight.attach_new_node('editor-status-right')
        self.status_text = label(right_status, '', -.03, .022, scale=.03, color=PANEL_TEXT, align=TextNode.A_right)
        self.help_note = HELP

    def rebuild_left(self):
        if self.left_list is not None:
            self.left_list.destroy()
        items = self.tool.items() if self.tool else []
        self.left_list = PropertyList(self.left_root, (.005, LEFT_WIDTH - .005, -2 + STATUS + .01, -BAR - .01),
                                      items, LEFT_WIDTH - .04)

    def refresh_left(self):
        if self.left_list is not None:
            self.left_list.refresh()

    def rebuild_right(self):
        if self.right_list is not None:
            self.right_list.destroy()
            self.right_list = None
        panel_open = registry.get('settingsPanel') is not None and registry.get('settingsPanel').visible
        found = self.instance()
        collider = self.selected_collider
        if (self.selected is None and found is None and collider is None) or panel_open:
            self.right_root.hide()
            return
        self.right_root.show()
        if self.selected is not None:
            items = self._object_items(self.selected)
        elif collider is not None:
            items = self._collider_items(collider)
        else:
            items = self._instance_items(*found)
        self.right_list = PropertyList(self.right_root, (.005, RIGHT_WIDTH - .005, -2 + STATUS + .01, -BAR - .01),
                                       items, RIGHT_WIDTH - .04)

    def properties_changed(self):
        self._props_dirty = True

    def status(self, message, seconds=4.0):
        self._message = message
        self._message_until = time.monotonic() + seconds

    def show_report(self, title, text):
        if self.report_window is not None:
            self.report_window.remove_node()
        root = self.app.aspect2d.attach_new_node('report')
        root.set_bin('gui-popup', 0)
        width, height = 1.9, 1.55
        panel(root, (-width / 2, width / 2, -height / 2, height / 2), color=(.07, .06, .055, .97))
        label(root, title, -width / 2 + .05, height / 2 - .08, scale=.045, color=ACCENT)
        button(root, 'Close', width / 2 - .12, height / 2 - .065, self.close_report, width=.16)
        lines = text.split('\n')
        line_height = .036
        content = len(lines) * line_height + .1
        from direct.gui.DirectGui import DirectScrolledFrame
        frame = DirectScrolledFrame(parent=root, frameSize=(-width / 2 + .03, width / 2 - .03, -height / 2 + .03,
                                                            height / 2 - .13),
                                    canvasSize=(0, width - .12, -content, 0), frameColor=(0, 0, 0, 0),
                                    scrollBarWidth=.025, autoHideScrollBars=True, manageScrollBars=True,
                                    verticalScroll_frameColor=(0, 0, 0, .25),
                                    horizontalScroll_relief=None, horizontalScroll_frameSize=(0, 0, 0, 0))
        label(frame.getCanvas(), text, .02, -.05, scale=.03, color=PANEL_TEXT, wrap=(width - .2) / .03)
        frame.set_pos(0, 0, 0)
        self.report_window = root
        self.report_frame = frame
        self.report_height = (content, height - .16)

    def close_report(self):
        if self.report_window is not None:
            self.report_window.remove_node()
            self.report_window = None

    # ------------------------------------------------------------------------- tools

    def set_tool(self, name):
        if self.tool is not None and self.tool.name == name:
            return
        if self.tool is not None:
            self.tool.release()
            self.tool.deactivate()
        self.ring.hide()
        self.tool = self.tools[name]
        for tool_name, widget in self.tool_buttons.items():
            widget['frameColor'] = BUTTON_ACTIVE if tool_name == name else BUTTON
        if name != 'environment':
            panel_widget = registry.get('settingsPanel')
            if panel_widget is not None and panel_widget.visible:
                panel_widget.close()
        self.tool.activate()
        self.rebuild_left()
        self.hint_text['text'] = self.tool.hint

    def open_settings(self, tab):
        panel_widget = registry.get('settingsPanel')
        if panel_widget is not None:
            panel_widget.open(tab)

    def toggle_settings(self):
        panel_widget = registry.get('settingsPanel')
        if panel_widget is not None:
            panel_widget.toggle()

    def _settings_panel_toggled(self, _visible):
        self.rebuild_right()

    # ---------------------------------------------------------------------- selection

    def select(self, item):
        if item is not None or self.selected_instance is not None:
            self._clear_instance()
        if self.selected_collider is not None:
            self._clear_collider()
        if item is self.selected:
            self.rebuild_right()
            return
        if self.selected is not None and not self.selected.root.is_empty():
            remove_outline(self.selected.root)
        self.selected = item
        if item is not None:
            outline(item.root)
        self.rebuild_right()
        if self.collider_view.visible:
            self._rebuild_colliders()

    def instance(self):
        """(group, index) of the selected foliage instance, or None."""
        if self.selected_instance is None:
            return None
        group_id, index = self.selected_instance
        for group in self.world.foliage:
            if group.data['id'] == group_id and 0 <= index < len(group.items):
                return group, index
        return None

    def select_instance(self, group, index):
        if self.selected is not None:
            self.select(None)
        self._clear_collider()
        self.selected_instance = (group.data['id'], index)
        self._update_highlight()
        self.rebuild_right()

    def select_collider(self, item):
        if self.selected is not None:
            self.select(None)
        self._clear_instance()
        self._clear_collider()
        self.selected_collider = item
        if item is not None:
            outline(item.root)
        self.rebuild_right()

    def _clear_collider(self):
        if self.selected_collider is not None:
            if not self.selected_collider.root.is_empty():
                remove_outline(self.selected_collider.root)
            self.selected_collider = None
            self.rebuild_right()

    def _clear_instance(self):
        self.selected_instance = None
        if self._highlight is not None:
            remove_outline(self._highlight)
            self._highlight.remove_node()
            self._highlight = None

    def _update_highlight(self):
        if self._highlight is not None:
            remove_outline(self._highlight)
            self._highlight.remove_node()
            self._highlight = None
        found = self.instance()
        if found is None:
            return
        group, index = found
        try:
            node = objects.instance(group.data['model'], group.data['colors'])
        except Exception:
            return
        x, y, z = group.position(index)
        node.reparent_to(self._highlight_parent)
        node.set_pos(x, y, z)
        node.set_h(float(group.items[index, 4]))
        node.set_scale(float(group.items[index, 3]))
        self._highlight = node
        outline(node)

    def select_and_focus(self, item):
        self.select(item)
        self.focus_selected()

    def focus_selected(self):
        if self.selected_collider is not None:
            data = self.selected_collider.data
            x, y, z = data['pos']
            self.camera.focus(Point3(x, y, z + data['size'][2] / 2), max(max(data['size']) * .6, .5))
            return
        found = self.instance()
        if found is not None:
            group, index = found
            x, y, z = group.position(index)
            scale = float(group.items[index, 3])
            self.camera.focus(Point3(x, y, z + scale), max(scale * 1.5, .5))
            return
        if self.selected is None:
            return
        bounds = self.selected.root.get_bounds()
        center = self.selected.root.get_pos(self.app.render)
        radius = 1.0
        if not bounds.is_empty():
            center = bounds.get_center()
            center = self.app.render.get_relative_point(self.selected.root.get_parent(), center)
            radius = max(bounds.get_radius(), .3)
        self.camera.focus(center, radius)

    # ------------------------------------------------------------------- view queries

    def pointer(self):
        pointer = self.app.win.get_pointer(0)
        return pointer.get_x(), pointer.get_y()

    def mouse_ray(self):
        watcher = self.app.mouseWatcherNode
        if not watcher.has_mouse():
            return None
        return self._ray(watcher.get_mouse())

    def _ray(self, screen):
        near, far = Point3(), Point3()
        if not self.app.camLens.extrude(screen, near, far):
            return None
        render = self.app.render
        origin = render.get_relative_point(self.app.cam, near)
        target = render.get_relative_point(self.app.cam, far)
        return origin, target - origin

    def terrain_hit(self):
        if self._hit_cache is None:
            ray = self.mouse_ray()
            hit = self.world.terrain.raycast(ray[0], ray[1]) if ray else None
            self._hit_cache = (hit,)
        return self._hit_cache[0]

    def screen_center_hit(self):
        from panda3d.core import Point2
        ray = self._ray(Point2(0, 0))
        return self.world.terrain.raycast(ray[0], ray[1]) if ray else None

    def ground_height_below_camera(self):
        position = self.app.camera.get_pos()
        return self.world.terrain.height_at(position.x, position.y)

    def pick_object(self, screen=None):
        """The world object under the pointer (or `screen` point, -1..1), or a foliage instance as
        ('foliage', group, index), or None."""
        watcher = self.app.mouseWatcherNode
        if screen is None:
            if not watcher.has_mouse():
                return None
            screen = watcher.get_mouse()
        self.pick_ray.set_from_lens(self.app.camNode, screen[0], screen[1])
        self.picker.traverse(self.world.root)
        if not self.pick_queue.get_num_entries():
            return None
        self.pick_queue.sort_entries()
        terrain = self.terrain_hit()
        camera = self.app.camera.get_pos(self.app.render)
        terrain_distance = (Point3(*terrain) - camera).length() if terrain else float('inf')
        for entry in self.pick_queue.entries:
            hit = entry.get_surface_point(self.app.render)
            if (hit - camera).length() > terrain_distance + .05:
                break  # behind the ground
            into = entry.get_into_node_path()
            owner = into.find_net_tag(COLLIDER_TAG)
            if not owner.is_empty():
                item = self.world.collider_by_id(owner.get_tag(COLLIDER_TAG))
                if item is not None:
                    return ('collider', item)
            owner = into.find_net_tag('world_object')
            if not owner.is_empty():
                item = self.world.object_by_id(owner.get_tag('world_object'))
                if item is not None:
                    return item
            owner = into.find_net_tag(FOLIAGE_TAG)
            if not owner.is_empty():
                for group in self.world.foliage:
                    if group.data['id'] == owner.get_tag(FOLIAGE_TAG):
                        index = group.nearest(hit.x, hit.y)
                        if index is not None:
                            return ('foliage', group, index)
        return None

    def over_gui(self):
        watcher = self.app.mouseWatcherNode
        return watcher.has_mouse() and watcher.is_over_region()

    # --------------------------------------------------------------------------- input

    def _bind_input(self):
        self.accept('mouse1', self._mouse1)
        self.accept('mouse1-up', self._mouse1_up)
        self.accept('mouse3', self._mouse3)
        self.accept('mouse2', self._mouse2)
        self.accept('wheel_up', self._wheel, [1])
        self.accept('wheel_down', self._wheel, [-1])
        for key, tool in TOOL_KEYS.items():
            self.accept(key, self._hotkey, [lambda name=tool: self.set_tool(name)])
        self.accept('z', self._hotkey, [self._z])
        self.accept('y', self._hotkey, [lambda: self.redo() if self._ctrl() else None])
        self.accept('s', self._hotkey, [lambda: self.save() if self._ctrl() else None])
        self.accept('d', self._hotkey, [lambda: self.duplicate_selected() if self._ctrl() else None])
        self.accept('delete', self._hotkey, [self.delete_selected])
        self.accept('r', self._hotkey, [self._rotate_key])
        self.accept('end', self._hotkey, [self.drop_selected])
        self.accept('f', self._hotkey, [self.focus_selected])
        self.accept('c', self._hotkey, [lambda: None if self._ctrl() else self.toggle_colliders()])
        self.accept('[', self._hotkey, [lambda: self._resize(1 / 1.15)])
        self.accept(']', self._hotkey, [lambda: self._resize(1.15)])
        self.accept('escape', self._escape)

    def _held(self, button):
        return self.app.mouseWatcherNode.is_button_down(button)

    def _ctrl(self):
        return self._held(KeyboardButton.control())

    def _hotkey(self, action):
        if widgets.typing() or self.camera.flying or self.benchmark is not None:
            return
        action()

    def _z(self):
        if self._ctrl():
            if self._held(KeyboardButton.shift()):
                self.redo()
            else:
                self.undo_action()

    def _rotate_key(self):
        if self._ctrl():
            return
        step = -15 if self._held(KeyboardButton.shift()) else 15
        if self.selected_collider is not None:
            heading = (self.selected_collider.data['heading'] + step) % 360
            self.edit_collider({'heading': heading}, 'Rotate collider', ('collider-rotate',))
            return
        found = self.instance()
        if found is not None:
            group, index = found
            self.edit_instance(heading=(float(group.items[index, 4]) + step) % 360)
            return
        if self.selected is None:
            return
        hpr = list(self.selected.data['hpr'])
        hpr[0] = (hpr[0] + step) % 360
        self.edit_object({'hpr': hpr}, 'Rotate', merge_key=('rotate', self.selected.id))

    def _resize(self, factor):
        if hasattr(self.tool, 'resize'):
            self.tool.resize(factor)
        elif hasattr(self.tool, 'key_scale'):
            self.tool.key_scale(factor)

    def _escape(self):
        if widgets.typing():
            return
        if widgets.ColorPicker.current is not None:
            widgets.ColorPicker.current.close()
        elif self.report_window is not None:
            self.close_report()
        elif self.tool is not None and self.tool.cancel():
            pass
        elif self.selected is not None:
            self.select(None)

    def _mouse1(self):
        if self.over_gui() or self.benchmark is not None:
            return
        widgets.release_focus()
        if self.report_window is not None:
            return
        self._hit_cache = None
        self.tool.press()

    def _mouse1_up(self):
        if self.tool is not None:
            self.tool.release()

    def _mouse3(self):
        if self.over_gui():
            return
        widgets.release_focus()
        self.camera.start_fly()

    def _mouse2(self):
        if self.over_gui():
            return
        if self._held(KeyboardButton.shift()):
            self.camera.start_pan()
        else:
            hit = self.terrain_hit() or self.screen_center_hit()
            if hit is not None:
                self.camera.start_orbit(hit)

    def _wheel(self, direction):
        if self.report_window is not None:
            bar = self.report_frame.verticalScroll
            content, visible = self.report_height
            if content > visible:
                bar['value'] = min(max(bar['value'] - direction * .1 * visible / content * 3, 0), 1)
            return
        panel_widget = registry.get('settingsPanel')
        for property_list in (self.left_list, self.right_list):
            if property_list is not None and property_list.contains(self.app.mouseWatcherNode):
                property_list.scroll(-direction)
                return
        if panel_widget is not None and panel_widget.over():
            return  # the panel scrolls itself
        if self.over_gui():
            return
        if self.camera.flying:
            self.camera.speed = min(max(self.camera.speed * (1.2 if direction > 0 else 1 / 1.2), 1), 80)
            self.status(f'fly speed {self.camera.speed:.1f} m/s', 1.5)
            return
        self.camera.zoom(direction, self.terrain_hit())

    # ------------------------------------------------------------------ object edits

    def record_objects(self, label_text, before, merge_key=None):
        after = self.world.snapshot(('objects',))
        world = self.world

        def undo():
            world.restore(before)
            self._after_restore()

        def redo():
            world.restore(after)
            self._after_restore()

        self.undo.push(label_text, undo, redo, merge_key)

    def _after_restore(self):
        if self.selected is not None and self.selected not in self.world.objects:
            self.selected = None
        self.rebuild_right()

    def edit_object(self, changes, label_text='Edit', merge_key=None, rebuild=False):
        item = self.selected
        if item is None:
            return
        before = self.world.snapshot(('objects',))
        self.world.update_object(item, changes, rebuild=rebuild)
        self.record_objects(label_text, before, merge_key)
        self.properties_changed()

    def delete_selected(self):
        if self.selected_collider is not None:
            item = self.selected_collider
            before = self.world.snapshot(('colliders',))
            self._clear_collider()
            self.world.remove_collider(item)
            self.record_colliders('Delete collider', before)
            return
        found = self.instance()
        if found is not None:
            group, index = found
            before = self.world.snapshot(('foliage',))
            self._clear_instance()
            group.remove_item(index)
            self.world.foliage_changed()
            self.record_foliage('Delete instance', before)
            self.rebuild_right()
            self.status(f'removed one {group.data["name"]} instance  (Ctrl+Z restores it)')
            return
        item = self.selected
        if item is None:
            return
        before = self.world.snapshot(('objects',))
        self.select(None)
        self.world.remove_object(item)
        self.record_objects('Delete', before)
        self.status(f'deleted {item.data["name"] or item.id}  (Ctrl+Z restores it)')

    def duplicate_selected(self):
        if self.selected_collider is not None:
            record = dict(self.selected_collider.data)
            record['pos'] = [record['pos'][0] + 1, record['pos'][1] + 1, record['pos'][2]]
            before = self.world.snapshot(('colliders',))
            item = self.world.add_collider(record=record)
            self.record_colliders('Duplicate collider', before)
            self.select_collider(item)
            return
        found = self.instance()
        if found is not None:
            group, index = found
            before = self.world.snapshot(('foliage',))
            x, y, offset, scale, heading = (float(v) for v in group.items[index])
            new_index = group.add_item(x + 1, y + 1, offset, scale, heading)
            self.world.foliage_changed()
            self.record_foliage('Duplicate instance', before)
            self.select_instance(group, new_index)
            return
        item = self.selected
        if item is None:
            return
        before = self.world.snapshot(('objects',))
        record = dict(item.data)
        record['pos'] = [record['pos'][0] + 1, record['pos'][1] + 1, record['pos'][2]]
        record['name'] = (record.get('name') or 'object') + ' copy'
        copy = self.world.add_object(record['model'], record['kind'], record=record)
        if copy.data['follow_terrain']:
            self._drop(copy, keep_offset=True, source=item)
        self.record_objects('Duplicate', before)
        self.select(copy)

    def _drop(self, item, keep_offset=False, source=None):
        terrain = self.world.terrain
        x, y, z = item.data['pos']
        if keep_offset and source is not None:
            sx, sy, sz = source.data['pos']
            z = terrain.height_at(x, y) + (sz - terrain.height_at(sx, sy))
        else:
            z = terrain.height_at(x, y)
            if item.local_bounds is not None:
                z -= item.local_bounds[0][2] * abs(item.data['scale'][2])
        self.world.update_object(item, {'pos': [x, y, z]})

    def drop_selected(self):
        if self.selected_collider is not None:
            x, y, _z = self.selected_collider.data['pos']
            self.edit_collider({'pos': [x, y, self.world.terrain.min_height_in_radius(x, y, 1.0)]}, 'Drop collider')
            return
        if self.instance() is not None:
            self.edit_instance(offset=0.0)
            return
        if self.selected is None:
            return
        before = self.world.snapshot(('objects',))
        self._drop(self.selected)
        self.record_objects('Drop to ground', before)
        self.properties_changed()

    def record_colliders(self, label_text, before, merge_key=None):
        after = self.world.snapshot(('colliders',))
        world = self.world

        def restore(snapshot):
            identifier = self.selected_collider.id if self.selected_collider is not None else None
            self._clear_collider()
            world.restore(snapshot)
            if identifier is not None and world.collider_by_id(identifier) is not None:
                self.select_collider(world.collider_by_id(identifier))
            self._rebuild_colliders_if_visible()

        self.undo.push(label_text, lambda: restore(before), lambda: restore(after), merge_key)
        self._rebuild_colliders_if_visible()

    def _rebuild_colliders_if_visible(self):
        if self.collider_view.visible:
            self._rebuild_colliders()

    def edit_collider(self, changes, label_text='Edit collider', merge_key=None):
        item = self.selected_collider
        if item is None:
            return
        before = self.world.snapshot(('colliders',))
        self.world.update_collider(item, changes)
        self.record_colliders(label_text, before, merge_key and (item.id,) + tuple(merge_key))
        self.properties_changed()

    def add_collider(self, shape, position):
        before = self.world.snapshot(('colliders',))
        item = self.world.add_collider(shape, position)
        self.record_colliders('Add collider', before)
        self.select_collider(item)
        return item

    def detach_collider(self):
        """Turn the selected object's box / cylinder collider into a standalone collider."""
        item = self.selected
        if item is None:
            return
        shapes = item.collision_shapes()
        if not shapes or item.data['collision']['shape'] == 'mesh':
            self.status('only box and cylinder colliders can be detached')
            return
        shape = shapes[0]
        if shape[0] == 'cylinder':
            _, x, y, radius, z0, z1 = shape
            record = {'name': f'{item.data["name"]} collider', 'shape': 'cylinder', 'pos': [x, y, z0],
                      'size': [radius * 2, radius * 2, z1 - z0], 'heading': 0.0}
        else:
            _, x, y, hx, hy, heading, z0, z1 = shape
            record = {'name': f'{item.data["name"]} collider', 'shape': 'box', 'pos': [x, y, z0],
                      'size': [hx * 2, hy * 2, z1 - z0], 'heading': math.degrees(heading)}
        before = self.world.snapshot(('objects', 'colliders'))
        self.world.update_object(item, {'collision': dict(item.data['collision'], shape='none')})
        collider = self.world.add_collider(record=record)
        after = self.world.snapshot(('objects', 'colliders'))
        world = self.world

        def restore(snapshot):
            self.select(None)
            world.restore(snapshot)
            self._rebuild_colliders_if_visible()

        self.undo.push('Detach collider', lambda: restore(before), lambda: restore(after))
        self.select_collider(collider)
        self.status('the collider is now separate: drag it, resize it on the right; the object has no collider')

    def _collider_items(self, item):
        data = item.data

        def vector(key, index):
            def put(value):
                values = list(data[key])
                values[index] = float(value)
                self.edit_collider({key: values}, f'Collider {key}', (key, index))
            return put

        def size(index):
            def put(value):
                values = list(data['size'])
                values[index] = max(float(value), .02)
                if data['shape'] == 'cylinder' and index == 0:
                    values[1] = values[0]
                self.edit_collider({'size': values}, 'Resize collider', ('size', index))
            return put

        cylinder = data['shape'] == 'cylinder'
        rows = [
            Section(data['name'] or item.id),
            Note('A standalone collider: invisible in the game, it only blocks the player (and can be stood on). '
                 'Drag to move, shift+drag height, ctrl+drag rotate, alt+drag resize. Del, Ctrl+D, R, End.'),
            (prop('Name', 'text'), lambda: data['name'],
             lambda value: self.edit_collider({'name': value}, 'Rename collider')),
            (prop('Shape', 'choice', options=COLLIDER_SHAPES, labels=('Box', 'Cylinder')), lambda: data['shape'],
             lambda value: (self.edit_collider({'shape': value}, 'Collider shape'), self.rebuild_right())),
            Section('Position'),
            (prop('X', 'number', step=.1), lambda: data['pos'][0], vector('pos', 0)),
            (prop('Y', 'number', step=.1), lambda: data['pos'][1], vector('pos', 1)),
            (prop('Bottom (Z)', 'number', step=.05), lambda: data['pos'][2], vector('pos', 2)),
            Section('Size'),
            (prop('Diameter' if cylinder else 'Width (X)', 'number', .02, 500, .1), lambda: data['size'][0], size(0)),
        ]
        if not cylinder:
            rows.append((prop('Depth (Y)', 'number', .02, 500, .1), lambda: data['size'][1], size(1)))
        rows += [
            (prop('Height', 'number', .02, 500, .1), lambda: data['size'][2], size(2)),
        ]
        if not cylinder:
            rows.append((prop('Rotation around Z (degrees)', 'float', -180, 180, 1), lambda: wrap_angle(data['heading']),
                         lambda value: self.edit_collider({'heading': wrap_angle(value)}, 'Rotate collider',
                                                          ('heading',))))
        rows.append(Button('Drop to ground  End', self.drop_selected,
                           extra=(('Duplicate  ^D', self.duplicate_selected), ('Delete  Del', self.delete_selected))))
        return rows

    def record_foliage(self, label_text, before, merge_key=None):
        after = self.world.snapshot(('foliage',))
        world = self.world

        def undo():
            world.restore(before)
            self._after_foliage_restore()

        def redo():
            world.restore(after)
            self._after_foliage_restore()

        self.undo.push(label_text, undo, redo, merge_key)

    def _after_foliage_restore(self):
        if self.selected_instance is not None and self.instance() is None:
            self._clear_instance()
        else:
            self._update_highlight()
        self.rebuild_right()

    def edit_instance(self, label_text='Edit instance', merge=True, **values):
        found = self.instance()
        if found is None:
            return
        group, index = found
        before = self.world.snapshot(('foliage',))
        group.set_item(index, **values)
        self.world.foliage_changed()
        key = ('instance', group.data['id'], index, tuple(sorted(values))) if merge else None
        self.record_foliage(label_text, before, key)
        self._update_highlight()
        self.properties_changed()

    def edit_group(self, changes, collision=False, label_text='Foliage group'):
        found = self.instance()
        if found is None:
            return
        group, index = found
        before = self.world.snapshot(('foliage',))
        if collision:
            group.data['collision'].update(changes)
        else:
            group.data.update(changes)
            if {'model', 'colors'} & set(changes):
                group.reload_model()
            elif 'distance_render' in changes:
                group.rebuild()
            else:
                group.apply_flags()
        self.world.foliage_changed()
        self.record_foliage(label_text, before, ('group', group.data['id'], tuple(sorted(changes))))
        if collision and self.collider_view.visible:
            self._rebuild_colliders()

    def instance_to_object(self):
        """Replace the selected foliage instance with a regular object (every property editable)."""
        found = self.instance()
        if found is None:
            return
        group, index = found
        data = group.data
        x, y, z = group.position(index)
        _x, _y, _offset, scale, heading = (float(v) for v in group.items[index])
        before = self.world.snapshot(('objects', 'foliage'))
        self._clear_instance()
        group.remove_item(index)
        self.world.foliage_changed()
        defaults = objects.model_defaults(data['model'])
        item = self.world.add_object(data['model'], 'model', (x, y, z), defaults)
        changes = {'name': data['name'].rstrip('s') or data['name'], 'colors': dict(data['colors']),
                   'scale': [scale] * 3, 'hpr': [heading, 0.0, 0.0], 'cast_shadow': data['cast_shadow'],
                   'receive_shadow': data['receive_shadow'], 'distance_render': data['distance_render']}
        collision = data['collision']
        if collision['shape'] == 'cylinder' and item.local_bounds is not None:
            low, high = item.local_bounds
            crown = max(high[0] - low[0], high[1] - low[1]) / 2 or 1
            height = (high[2] - low[2]) or 1
            factor_xy = collision['radius'] / crown
            factor_z = min(collision['height'] / height, 1)
            changes['collision'] = {'shape': 'cylinder', 'scale': [factor_xy, factor_xy, factor_z],
                                    'offset': [0.0, 0.0, -(1 - factor_z) * height * scale / 2]}
        else:
            changes['collision'] = {'shape': 'none', 'scale': [1.0, 1.0, 1.0], 'offset': [0.0, 0.0, 0.0]}
        self.world.update_object(item, changes, rebuild=True)
        after = self.world.snapshot(('objects', 'foliage'))
        world = self.world

        def undo():
            world.restore(before)
            self._after_restore()
            self._after_foliage_restore()

        def redo():
            world.restore(after)
            self._after_restore()
            self._after_foliage_restore()

        self.undo.push('Convert to object', undo, redo)
        self.select(item)
        self.status('now a regular object: every property, including its own collision, is on the right')

    def _instance_items(self, group, index):
        data = group.data
        identifier = data['id']

        def item_value(column):
            def get():
                found = self.instance()
                return float(found[0].items[found[1], column]) if found else 0.0
            return get

        def put(name):
            return lambda value: self.edit_instance(**{name: value})

        collision = data['collision']
        return [
            Section(f'{data["name"]} instance {index + 1} of {len(group.items)}'),
            Note('One instance of a foliage group (painted with the Foliage tool, baked with the others). '
                 'Drag it like an object; Del, Ctrl+D, R, End work too. Look and collision are shared by the '
                 'whole group; "Convert to object" makes it a regular object with its own settings.'),
            Button('Convert to object', self.instance_to_object,
                   extra=(('Edit group', lambda: self._open_group(identifier)),)),
            Section('Transform'),
            (prop('Position X', 'number', step=.1), item_value(0), put('x')),
            (prop('Position Y', 'number', step=.1), item_value(1), put('y')),
            (prop('Height above ground', 'number', step=.05), item_value(2), put('offset')),
            (prop('Rotation around Z (degrees)', 'float', -180, 180, 1), lambda: wrap_angle(item_value(4)()),
             lambda value: self.edit_instance(heading=wrap_angle(value))),
            (prop('Scale', 'float', 0, 5, .01), item_value(3), put('scale')),
            Button('Drop to ground  End', self.drop_selected, extra=(('Duplicate  ^D', self.duplicate_selected),
                                                                     ('Delete  Del', self.delete_selected))),
            Section(f'Group "{data["name"]}" ({len(group.items)} instances)'),
            (prop('Casts shadows', 'bool'), lambda: data['cast_shadow'],
             lambda value: self.edit_group({'cast_shadow': value})),
            (prop('Receives shadows', 'bool'), lambda: data['receive_shadow'],
             lambda value: self.edit_group({'receive_shadow': value})),
            (prop('Wind sway', 'float', 0, .5, .005), lambda: data['sway'],
             lambda value: self.edit_group({'sway': value})),
            Section('Collision (whole group)'),
            (prop('Shape', 'choice', options=('none', 'cylinder'), labels=('None', 'Trunk cylinder')),
             lambda: collision['shape'], lambda value: self.edit_group({'shape': value}, collision=True)),
            (prop('Trunk radius (scale 1)', 'float', .02, 3, .01), lambda: collision['radius'],
             lambda value: self.edit_group({'radius': value}, collision=True)),
            (prop('Collider height (scale 1)', 'float', .1, 20, .1), lambda: collision['height'],
             lambda value: self.edit_group({'height': value}, collision=True)),
            Note('Each instance gets a cylinder of this radius and height times its scale. Press C to see them. '
                 'For a different collider on one tree, convert it to an object.'),
            *self._breakable_rows(lambda: data['breakable'], lambda record: self.edit_group({'breakable': record}),
                                  f'every {data["name"]} instance'),
        ]

    def _open_group(self, identifier):
        self.set_tool('foliage')
        for group in self.world.foliage:
            if group.data['id'] == identifier:
                self.tool.group = group
        self.rebuild_left()

    def _breakable_rows(self, get, put, what):
        """Rows editing a 'breakable' record (world/breakables.py). `get()` returns it, `put(record)` saves it."""
        def field(key):
            def apply(value):
                record = copy.deepcopy(get())
                record[key] = value
                put(record)
            return apply

        def drop(index, key):
            def apply(value):
                record = copy.deepcopy(get())
                while len(record['drops']) <= index:
                    record['drops'].append({'item': '', 'count': 0})
                record['drops'][index][key] = value.strip() if key == 'item' else int(round(value))
                put(record)
            return apply

        def drop_value(index, key):
            def read():
                drops = get()['drops']
                return drops[index][key] if index < len(drops) else ('' if key == 'item' else 0)
            return read

        return [
            Section('Breakable'),
            Note(f'Whether the player can break {what} in the game, with what, and what it gives. Broken '
                 'things come back when the game restarts (playing never changes the save).'),
            (prop('Can be broken', 'bool'), lambda: get()['enabled'], field('enabled')),
            (prop('Needs', 'choice', options=BREAK_TOOLS, labels=BREAK_TOOL_LABELS), lambda: get()['tool'],
             field('tool')),
            (prop('Hits to break', 'float', 1, 30, 1), lambda: get()['hits'], field('hits')),
            (prop('Gives (item name)', 'text'), drop_value(0, 'item'), drop(0, 'item')),
            (prop('How many', 'int', 0, 50), drop_value(0, 'count'), drop(0, 'count')),
            (prop('Also gives (item name)', 'text'), drop_value(1, 'item'), drop(1, 'item')),
            (prop('How many', 'int', 0, 50), drop_value(1, 'count'), drop(1, 'count')),
        ]

    def _item_rows(self, item):
        """Pick-up item settings: inventory name and, for flashlights, the light."""
        data = item.data
        if data['kind'] != 'item':
            return []
        def item_field(key):
            def put(value):
                changed = dict(data['item'])
                changed[key] = value
                self.edit_object({'item': changed}, 'Item', ('item', item.id, key))
                if key == 'type':
                    self.rebuild_right()
            return put

        def light_field(key):
            def put(value):
                changed = dict(data['item'])
                changed['light'] = dict(data['item']['light'], **{key: value})
                self.edit_object({'item': changed}, 'Flashlight', ('light', item.id, key))
            return put

        rows = [
            Section('Item'),
            Note('The player picks it up with E, carries it in the hotbar (1-8) and drops it with G.'),
            (prop('Inventory name', 'text'), lambda: data['item']['label'], item_field('label')),
            (prop('Type', 'choice', options=ITEM_TYPES, labels=('Generic', 'Flashlight', 'Axe')),
             lambda: data['item']['type'], item_field('type')),
        ]
        if data['item']['type'] == 'axe':
            def tool_field(key):
                def put(value):
                    changed = copy.deepcopy(data['item'])
                    changed['tool'][key] = value
                    self.edit_object({'item': changed}, 'Axe', ('tool', item.id, key))
                return put
            rows += [
                Section('Axe'),
                Note('Left click swings it in the game. What it can break is set on the objects and foliage '
                     'groups themselves (their Breakable section).'),
                (prop('Damage per swing', 'float', .25, 10, .25), lambda: data['item']['tool']['damage'],
                 tool_field('damage')),
                (prop('Reach (m)', 'float', .5, 6, .1), lambda: data['item']['tool']['reach'], tool_field('reach')),
                (prop('Seconds per swing', 'float', .15, 2, .05), lambda: data['item']['tool']['swing_time'],
                 tool_field('swing_time')),
                (prop('Head direction (model)', 'choice', options=TOOL_AXES), lambda: data['item']['tool']['head'],
                 tool_field('head')),
                (prop('Blade direction (model)', 'choice', options=TOOL_AXES), lambda: data['item']['tool']['edge'],
                 tool_field('edge')),
            ]
        if data['item']['type'] == 'flashlight':
            rows += [
                Section('Flashlight light'),
                Note('F switches it on / off in the game. "Show light in the editor" previews it here.'),
                (prop('Show light in the editor', 'bool'), lambda: data['item']['light']['preview'],
                 light_field('preview')),
                (prop('On when found', 'bool'), lambda: data['item']['light']['starts_on'], light_field('starts_on')),
                (prop('Casts shadows', 'bool'), lambda: data['item']['light']['shadows'], light_field('shadows')),
                (prop('Color', 'color'), lambda: data['item']['light']['color'], light_field('color')),
                (prop('Intensity', 'float', 0, 60, .1), lambda: data['item']['light']['intensity'],
                 light_field('intensity')),
                (prop('Range (m)', 'float', 1, 100, .5), lambda: data['item']['light']['range'], light_field('range')),
                (prop('Falloff (decay)', 'float', 0, 4, .05), lambda: data['item']['light']['decay'],
                 light_field('decay')),
                (prop('Beam angle (degrees)', 'float', 2, 80, .5), lambda: data['item']['light']['angle'],
                 light_field('angle')),
                (prop('Edge softness', 'float', 0, 1, .01), lambda: data['item']['light']['softness'],
                 light_field('softness')),
                (prop('Mode', 'choice', options=LIGHT_MODES, labels=('Steady', 'Flicker', 'Strobe / flashing')),
                 lambda: data['item']['light']['mode'], light_field('mode')),
                (prop('Flicker / flash rate (Hz)', 'float', .2, 30, .1), lambda: data['item']['light']['rate'],
                 light_field('rate')),
                (prop('Battery (minutes, 0 = endless)', 'float', 0, 120, .5), lambda: data['item']['light']['battery'],
                 light_field('battery')),
                (prop('Beam along model axis', 'choice', options=BEAM_AXES), lambda: data['item']['beam'],
                 item_field('beam')),
            ]
        return rows

    def add_light(self, light_type, hit):
        """Place a light: a point light 2 m above the ground, a spot light 3.5 m up shining down."""
        before = self.world.snapshot(('objects',))
        position = (hit[0], hit[1], hit[2] + (2.0 if light_type == 'point' else 3.5))
        item = self.world.add_object('', 'light', position)
        changes = {'name': f'{light_type} light', 'light': new_light(light_type)}
        if light_type == 'spot':
            changes['hpr'] = [0.0, -90.0, 0.0]  # forward (+Y) turned down
        self.world.update_object(item, changes)
        self.record_objects('Add light', before)
        self.select(item)
        return item

    def _light_items(self, item):
        data = item.data

        def light_field(key, rebuild_panel=False):
            def put(value):
                changed = dict(data['light'])
                changed[key] = value
                self.edit_object({'light': changed}, 'Light', ('light', item.id, key))
                if rebuild_panel:
                    self.rebuild_right()
            return put

        def vector(key, index):
            def put(value):
                values = list(data[key])
                values[index] = float(value)
                self.edit_object({key: values}, f'Edit {key}', ('vector', item.id, key, index))
            return put

        light = lambda key: (lambda: data['light'][key])
        spot = data['light']['type'] == 'spot'
        rows = [
            Section(data['name'] or item.id),
            (prop('Name', 'text'), lambda: data['name'],
             lambda value: self.edit_object({'name': value}, 'Rename', ('field', item.id, 'name'))),
            Note('A light: shown as a bulb here, only its light in the game. The 4 enabled lights nearest the '
                 'player shine at a time. Drag it like an object; rotate a spot light to aim it.'),
            Section('Light'),
            (prop('Type', 'choice', options=LIGHT_TYPES, labels=('Point (all around)', 'Spot (cone)')),
             light('type'), light_field('type', rebuild_panel=True)),
            (prop('On', 'bool'), light('enabled'), light_field('enabled')),
            (prop('Color', 'color'), light('color'), light_field('color')),
            (prop('Intensity', 'float', 0, 80, .1), light('intensity'), light_field('intensity')),
            (prop('Range (m)', 'float', .5, 100, .5), light('range'), light_field('range')),
            (prop('Falloff (decay)', 'float', 0, 4, .05), light('decay'), light_field('decay')),
        ]
        if spot:
            rows += [
                (prop('Cone angle (degrees)', 'float', 2, 85, .5), light('angle'), light_field('angle')),
                (prop('Edge softness', 'float', 0, 1, .01), light('softness'), light_field('softness')),
            ]
        rows += [
            (prop('Bounce (spread around the room)', 'float', 0, 1, .01), light('bounce'), light_field('bounce')),
            (prop('Bounce reach (m)', 'float', .5, 20, .1), light('bounce_range'), light_field('bounce_range')),
            Note('Bounce adds soft light where the light lands (a spot: where the beam hits; a point light: the '
                 'middle of the room around it), as if it reflected and lit the room. With shadows on, walls keep it '
                 'inside. It uses an extra light slot.'),
        ]
        rows += [
            (prop('Mode', 'choice', options=LIGHT_MODES_PLACED, labels=('Steady', 'Flicker', 'Strobe / flashing',
                                                                       'Pulse')),
             light('mode'), light_field('mode', rebuild_panel=True)),
        ]
        mode = data['light']['mode']
        if mode in ('strobe', 'pulse'):
            rows.append((prop('Rate (Hz)', 'float', .05, 30, .05), light('rate'), light_field('rate')))
        elif mode == 'flicker':
            rows += [
                (prop('Time between blinks (s)', 'float', .05, 30, .05), light('flicker_interval'),
                 light_field('flicker_interval')),
                (prop('Random delay (0 = regular)', 'float', 0, 1, .01), light('flicker_random'),
                 light_field('flicker_random')),
                (prop('Blink length (s)', 'float', .01, 1, .01), light('flicker_duration'),
                 light_field('flicker_duration')),
                (prop('Blinks per burst (up to)', 'int', 1, 8), light('flicker_burst'), light_field('flicker_burst')),
                (prop('Blink darkness (1 = off)', 'float', 0, 1, .01), light('flicker_depth'),
                 light_field('flicker_depth')),
                (prop('Constant shimmer', 'float', 0, .6, .01), light('flicker_shimmer'),
                 light_field('flicker_shimmer')),
            ]
        rows += [
            (prop('Casts shadows', 'bool'), light('shadows'), light_field('shadows')),
            Note('Shadows: one point light (the campfire first) and one spot light (a flashlight in hand first) '
                 'cast them at a time.'),
            Section('Position'),
            (prop('Position X', 'number', step=.1), lambda: data['pos'][0], vector('pos', 0)),
            (prop('Position Y', 'number', step=.1), lambda: data['pos'][1], vector('pos', 1)),
            (prop('Position Z (up)', 'number', step=.1), lambda: data['pos'][2], vector('pos', 2)),
        ]
        if spot:
            rows += [
                (prop('Aim: turn around Z', 'float', -180, 180, 1), lambda: wrap_angle(data['hpr'][0]),
                 lambda value: vector('hpr', 0)(wrap_angle(value))),
                (prop('Aim: tilt (-90 = straight down)', 'float', -90, 90, 1), lambda: max(min(data['hpr'][1], 90), -90),
                 vector('hpr', 1)),
            ]
        rows += [
            (prop('Follow terrain', 'bool'), lambda: data['follow_terrain'],
             lambda value: self.edit_object({'follow_terrain': value}, 'Follow terrain')),
            Button('Duplicate  ^D', self.duplicate_selected, extra=(('Delete  Del', self.delete_selected),)),
        ]
        return rows

    def _object_items(self, item):
        data = item.data
        if data['kind'] == 'light':
            return self._light_items(item)
        models = library.scan()
        if data['model'] not in models:
            models = [data['model']] + models

        def field(key, label_text='Edit', rebuild=False):
            return lambda value: self.edit_object({key: value}, label_text, ('field', item.id, key), rebuild)

        def vector(key, index):
            def put(value):
                values = list(data[key])
                values[index] = min(max(float(value), 1e-3), 5.0) if key == 'scale' else float(value)
                self.edit_object({key: values}, f'Edit {key}', ('vector', item.id, key, index))
            return put

        def rotation(index):
            def put(value):
                values = list(data['hpr'])
                values[index] = wrap_angle(value)
                self.edit_object({'hpr': values}, 'Rotate', ('rotation', item.id, index))
            return put

        def uniform_scale(value):
            value = min(max(float(value), 1e-3), 5.0)
            current = data['scale'][0] or 1
            self.edit_object({'scale': [s * value / current for s in data['scale']]}, 'Scale', ('scale', item.id))

        def collision(key, index=None):
            def put(value):
                values = dict(data['collision'])
                if index is None:
                    values[key] = value
                else:
                    vector_values = list(values[key])
                    vector_values[index] = float(value)
                    values[key] = vector_values
                self.edit_object({'collision': values}, 'Collision', ('collision', item.id, key, index))
                if self.collider_view.visible:
                    self._rebuild_colliders()
            return put

        def color(material):
            def put(value):
                colors = dict(data['colors'])
                colors[material] = value
                self.edit_object({'colors': colors}, 'Color', ('color', item.id, material))
            return put

        try:
            triangles = item.triangle_count()
        except Exception:
            triangles = 0
        rows = [
            Section(data['name'] or item.id),
            (prop('Name', 'text'), lambda: data['name'], field('name', 'Rename')),
            Note(f'{data["model"]}   {triangles:,} triangles' + (f'\nERROR: {item.error}' if item.error else '')),
            (prop('Model', 'choice', options=models, labels=[library.display_name(m) for m in models]),
             lambda: data['model'], field('model', 'Change model', rebuild=True)),
            (prop('Kind', 'choice', options=OBJECT_KINDS, labels=('Model', 'Campfire', 'Animated (bird)', 'Item')),
             lambda: data['kind'], (lambda value: (field('kind', 'Change kind', rebuild=True)(value),
                                                   self.rebuild_right()))),
            *self._item_rows(item),
            Section('Position'),
            (prop('Position X', 'number', step=.1), lambda: data['pos'][0], vector('pos', 0)),
            (prop('Position Y', 'number', step=.1), lambda: data['pos'][1], vector('pos', 1)),
            (prop('Position Z (up)', 'number', step=.05), lambda: data['pos'][2], vector('pos', 2)),
            Section('Rotation (degrees)'),
            (prop('Turn around Z (heading)', 'float', -180, 180, 1), lambda: wrap_angle(data['hpr'][0]),
             rotation(0)),
            (prop('Tilt around X (pitch)', 'float', -180, 180, 1), lambda: wrap_angle(data['hpr'][1]), rotation(1)),
            (prop('Roll around Y (roll)', 'float', -180, 180, 1), lambda: wrap_angle(data['hpr'][2]), rotation(2)),
            Button('Reset rotation', lambda: self.edit_object({'hpr': [0.0, 0.0, 0.0]}, 'Reset rotation'),
                   extra=(('Turn 90\N{DEGREE SIGN}', lambda: rotation(0)(wrap_angle(data['hpr'][0] + 90))),)),
            Section('Scale'),
            (prop('Scale', 'float', 0, 5, .01), lambda: data['scale'][0], uniform_scale),
            (prop('Scale X', 'float', 0, 5, .01), lambda: data['scale'][0], vector('scale', 0)),
            (prop('Scale Y', 'float', 0, 5, .01), lambda: data['scale'][1], vector('scale', 1)),
            (prop('Scale Z', 'float', 0, 5, .01), lambda: data['scale'][2], vector('scale', 2)),
            Button('Drop to ground  End', self.drop_selected, extra=(('Duplicate  ^D', self.duplicate_selected),
                                                                     ('Delete  Del', self.delete_selected))),
            Section('Look'),
        ]
        if library.exists(data['model']):
            for material in objects.resolved_colors(data['model'], data['colors']):
                rows.append((prop(f'{material or "default"}', 'color'),
                             (lambda m=material: objects.resolved_colors(data['model'], data['colors'])[m]),
                             color(material)))
        textures = library.scan_textures()
        current = data.get('texture', '')
        if current not in ('', 'none') and current not in textures:
            textures = [current] + textures
        own = 'Model\'s own' if objects.is_textured(data['model']) else 'Model\'s own (none)'
        rows += [
            (prop('Texture', 'choice', options=['', 'none'] + textures,
                  labels=[own, 'No texture'] + [t.split('/', 1)[-1] for t in textures]),
             lambda: data.get('texture', ''), field('texture', 'Texture', rebuild=True)),
            Note('Textures: images found under obj/ (png, jpg). Material colors tint the texture; white keeps '
                 'it as painted.'),
            Button('Reset colors', lambda: self.edit_object({'colors': {}}, 'Reset colors')),
            (prop('Shininess (Phong)', 'float', 0, 200, 1), lambda: data['shininess'], field('shininess', 'Shininess')),
            (prop('Roughness (PBR if > 0)', 'float', 0, 1, .01), lambda: data['roughness'], field('roughness')),
            (prop('Unlit', 'bool'), lambda: data['unlit'], field('unlit')),
            Section('Rendering'),
            (prop('Visible', 'bool'), lambda: data['visible'], field('visible')),
            (prop('Casts shadows', 'bool'), lambda: data['cast_shadow'], field('cast_shadow')),
            (prop('Receives shadows', 'bool'), lambda: data['receive_shadow'], field('receive_shadow')),
            (prop('Hide beyond draw distance', 'bool'), lambda: data['distance_render'], field('distance_render')),
            Section('Behavior'),
            (prop('Selectable in game', 'bool'), lambda: data['interactable'], field('interactable')),
            (prop('Follow terrain', 'bool'), lambda: data['follow_terrain'], field('follow_terrain')),
            Note('Objects not selectable in the game are merged into a few meshes when compiling.'),
            *self._breakable_rows(lambda: data['breakable'],
                                  lambda record: self.edit_object({'breakable': record}, 'Breakable',
                                                                  ('breakable', item.id)),
                                  'this object'),
            Section('Collision'),
            (prop('Shape', 'choice', options=COLLISION_SHAPES, labels=('None', 'Box', 'Cylinder', 'Mesh footprint')),
             lambda: data['collision']['shape'], collision('shape')),
            (prop('Size X', 'float', .05, 3, .01), lambda: data['collision']['scale'][0], collision('scale', 0)),
            (prop('Size Y', 'float', .05, 3, .01), lambda: data['collision']['scale'][1], collision('scale', 1)),
            (prop('Size Z', 'float', .05, 3, .01), lambda: data['collision']['scale'][2], collision('scale', 2)),
            (prop('Offset X', 'number', step=.05), lambda: data['collision']['offset'][0], collision('offset', 0)),
            (prop('Offset Y', 'number', step=.05), lambda: data['collision']['offset'][1], collision('offset', 1)),
            (prop('Offset Z', 'number', step=.05), lambda: data['collision']['offset'][2], collision('offset', 2)),
            Button('Detach as a separate collider', self.detach_collider),
            Note('Box / cylinder sizes scale the bounding box. Mesh follows the triangles (rock rings, houses); '
                 'offsets apply to all shapes. Detach to move and resize the collider on its own. '
                 'Press C to see all colliders.'),
        ]
        return rows

    # ------------------------------------------------------------------ world actions

    def make_all_mergeable(self):
        before = self.world.snapshot(('objects',))
        changed = 0
        for item in self.world.objects:
            if item.data['interactable']:
                self.world.update_object(item, {'interactable': False})
                changed += 1
        if changed:
            self.record_objects('Make mergeable', before)
        self.status(f'{changed} objects will be merged by Compile')
        self.rebuild_left()
        self.properties_changed()

    def set_player_start_here(self):
        camera = self.app.camera
        position = camera.get_pos()
        self.set_player_start(position=(position.x, position.y, 0.0), heading=camera.get_h())

    def set_player_start(self, position=None, heading=None):
        before = self.world.snapshot(('player',))
        player = self.world.data['player']
        self.world.set_player_start(position if position is not None else player['start'],
                                    heading if heading is not None else player['heading'])
        after = self.world.snapshot(('player',))
        world = self.world
        self.undo.push('Player start', lambda: world.restore(before), lambda: world.restore(after),
                       merge_key=('player',))
        self.refresh_left()

    def _update_player_marker(self):
        player = self.world.data['player']
        x, y, _z = player['start']
        self.player_marker.place(x, y, self.world.terrain.height_at(x, y), player['heading'],
                                 settings.get('env.eye_height'))

    def toggle_colliders(self):
        visible = self.collider_view.toggle()
        if visible:
            self._rebuild_colliders()
        self.status('colliders shown' if visible else 'colliders hidden', 1.5)

    def _rebuild_colliders(self):
        self.colliders.dirty = True
        self.colliders.nearby(0, 0, 0)
        self.collider_view.build(self.colliders.shapes)

    def _world_changed(self, section):
        if section in ('objects', 'foliage', 'loaded', 'terrain', 'colliders'):
            self.colliders.dirty = True
            if self.collider_view.visible:
                self._rebuild_colliders()
        if section in ('player', 'loaded', 'terrain'):
            self._update_player_marker()
        if section in ('terrain', 'loaded') and self.selected_instance is not None:
            if section == 'loaded':
                self._clear_instance()
            else:
                self._update_highlight()
        if section == 'loaded':
            self.selected_collider = None
            self._record_model_stamps()

    def _record_model_stamps(self):
        models = {item.data['model'] for item in self.world.objects} | {g.data['model'] for g in self.world.foliage}
        self.model_stamps = {}
        for model in models:
            try:
                self.model_stamps[model] = library.version(model)
            except OSError:
                pass

    def reload_changed_models(self):
        """Rebuild objects and foliage whose model file changed on disk. Returns how many changed."""
        changed = set()
        for model, stamp in list(self.model_stamps.items()):
            try:
                current = library.version(model)
            except OSError:
                continue
            if current != stamp:
                changed.add(model)
        for item in self.world.objects:
            if item.data['model'] in changed or item.error:
                item.build()
        for group in self.world.foliage:
            if group.data['model'] in changed:
                group.reload_model()
        self._record_model_stamps()
        return len(changed)

    def save(self):
        self.world.save(wait=True)
        self.status(f'saved "{self.world.name}"')
        if self.tool is not None and self.tool.name == 'file':
            self.rebuild_left()

    def load_world(self, name):
        self.select(None)
        self.world.load(name)
        self.undo.clear()
        self.world_switched()
        self.status(f'loaded "{self.world.name}"')

    def world_switched(self):
        self.rebuild_left()
        self.rebuild_right()

    def undo_action(self):
        label_text = self.undo.undo()
        self.status(f'undo: {label_text}' if label_text else 'nothing to undo', 2)

    def redo(self):
        label_text = self.undo.redo()
        self.status(f'redo: {label_text}' if label_text else 'nothing to redo', 2)

    def _undo_changed(self):
        self.properties_changed()
        if self.tool is not None and self.tool.name in ('foliage', 'water', 'environment', 'select'):
            self._left_dirty = True

    def compile(self):
        self.status('compiling...')
        self.app.graphics_engine.render_frame()
        started = time.perf_counter()
        report = compiler.compile_world(self.world)
        self.status(f'compiled in {time.perf_counter() - started:.1f} s; the game now loads the bake')
        self.show_report(f'Compiled "{self.world.name}"', report)

    def analyze(self):
        self.show_report(f'Analysis of "{self.world.name}"', compiler.analyze(self.world))

    def run_benchmark(self):
        if self.benchmark is not None:
            return
        self.close_report()
        self.select(None)
        self.benchmark = benchmark.Benchmark(self.app, self._benchmark_done)
        self.status('benchmarking: about 10 seconds, please wait...', 30)

    def _benchmark_done(self, report):
        self.benchmark = None
        self.status('benchmark done')
        self.show_report('Benchmark', report)

    def play(self):
        self.world.save(wait=True)
        main = PACKAGE_DIR.parent / 'main.py'
        subprocess.Popen([sys.executable, str(main), '--world', self.world.name], cwd=str(PACKAGE_DIR.parent))
        self.status(f'starting the game with "{self.world.name}"...')

    # --------------------------------------------------------------------------- frame

    def update(self, delta):
        self._hit_cache = None
        if self.benchmark is not None:
            self.benchmark.step(delta)
            return
        self.camera.update(delta)
        if self.tool is not None:
            self.tool.update(delta)
        if getattr(self, '_left_dirty', False):
            self._left_dirty = False
            self.rebuild_left()
        if self._props_dirty and self.right_list is not None:
            self._props_dirty = False
            self.right_list.refresh()
        self._fps = self._fps * .95 + (1 / max(delta, 1e-4)) * .05
        self._status_clock = getattr(self, '_status_clock', 0.0) + delta
        if self._status_clock < .2:
            return
        self._status_clock = 0.0
        message = self._message if time.monotonic() < self._message_until else ''
        hit = self.terrain_hit() if not self.over_gui() else None
        where = f'x {hit[0]:.2f}  y {hit[1]:.2f}  z {hit[2]:.2f}' if hit else ''
        saved = 'unsaved' if self.world.unsaved else 'saved'
        parts = [part for part in (message, where, f'{self.world.name} ({saved})', f'{self._fps:.0f} fps') if part]
        self.status_text['text'] = '    '.join(parts)


def wrap_angle(value):
    """Degrees in [-180, 180), as the rotation sliders show them."""
    return (float(value) + 180.0) % 360.0 - 180.0


def draw(app):
    registry.add('editor', Editor(app))

