"""Port of js/component/controls/mouse/select.js: click an interactable to select it (outlined).

With first-person controls the pick ray goes through the crosshair; without them, through the cursor.
"""
from direct.gui.OnscreenText import OnscreenText
from direct.showbase.DirectObject import DirectObject
from panda3d.core import (BitMask32, CollisionHandlerQueue, CollisionNode, CollisionRay, CollisionTraverser,
                          TextNode)

from .. import interactables, registry
from .outline import outline, remove_outline

_selected = None
_select_callbacks = []


def on_select_change(callback):
    _select_callbacks.append(callback)


def select(node_path, force_unselect=False):
    global _selected
    if node_path is not None:
        if _selected is not None and _selected == node_path:
            remove_outline(_selected)
            _selected = None
        else:
            if _selected is not None:
                remove_outline(_selected)
            _selected = node_path
            outline(_selected)
    elif _selected is not None and force_unselect:
        remove_outline(_selected)
        _selected = None

    for callback in _select_callbacks:
        callback(_selected)


def is_selected(node_path):
    return node_path is not None and _selected is not None and node_path == _selected


def get_selected():
    return _selected


class Picker(DirectObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.traverser = CollisionTraverser('select')
        self.queue = CollisionHandlerQueue()
        self.ray = CollisionRay()

        node = CollisionNode('select-ray')
        node.add_solid(self.ray)
        node.set_from_collide_mask(interactables.PICK_MASK)
        node.set_into_collide_mask(BitMask32.all_off())
        self.traverser.add_collider(app.cam.attach_new_node(node), self.queue)

        if registry.get('firstPersonControls'):
            self.accept('first-person-click', self._pick, [0, 0])
        else:
            self.accept('mouse1', self._pick_at_cursor)

        OnscreenText(
            text='click: select   R: rotate selected',
            parent=app.a2dBottomLeft, align=TextNode.A_left, pos=(.05, .11), scale=.04,
            fg=(1, 1, 1, .8), shadow=(0, 0, 0, .6),
        )

    def _pick_at_cursor(self):
        if self.app.mouseWatcherNode.has_mouse():
            mouse = self.app.mouseWatcherNode.get_mouse()
            self._pick(mouse.x, mouse.y)

    def _pick(self, x, y):
        self.ray.set_from_lens(self.app.camNode, x, y)
        self.traverser.traverse(self.app.render)
        self.queue.sort_entries()

        pointed = None
        for entry in self.queue.entries:
            pointed = interactables.find(entry.get_into_node_path())
            if pointed is not None:
                break
        select(pointed)


def draw(app):
    registry.add('select', Picker(app))
