"""Read-only port of js/component/controls/selectionPanel.js.

Shows the selected object's name, transform (in three.js coordinates, so values can be pasted into
the component MAP arrays) and children.
"""
from direct.gui.OnscreenText import OnscreenText
from panda3d.core import TextNode

from ..coords import panda_to_three
from ..update import add_update_callback
from .select import on_select_change


class SelectionPanel:
    def __init__(self, app):
        self.object = None
        self.text = OnscreenText(
            parent=app.a2dTopRight, align=TextNode.A_left, pos=(-.72, -.1), scale=.04,
            fg=(1, 1, 1, 1), bg=(0, 0, 0, .55), mayChange=True,
        )
        self.text.hide()
        on_select_change(self.set_object)
        add_update_callback(self._sync_values)

    def set_object(self, node_path):
        self.object = node_path
        if node_path is None:
            self.text.hide()
        else:
            self._sync_values()
            self.text.show()

    def _sync_values(self, _delta=0):
        if self.object is None:
            return
        x, y, z = panda_to_three(self.object.get_pos())
        children = [child.get_name() for child in self.object.get_children()]
        lines = [
            self.object.get_name(),
            '',
            f'Position  X {x:.2f}  Y {y:.2f}  Z {z:.2f}',
            f'Rotation  Y {self.object.get_h() % 360:.1f}\N{DEGREE SIGN}',
            f'Scale     {self.object.get_scale().x:.3f}',
            '',
            f'Children ({len(children)})' if children else 'Children: none',
            *(f'  - {name}' for name in children),
        ]
        self.text.setText('\n'.join(lines))


def draw(app):
    SelectionPanel(app)
