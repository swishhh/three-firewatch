"""Port of js/component/controls/object.js: R rotates the selected object by 90 degrees."""
from direct.showbase.DirectObject import DirectObject

from .select import get_selected


class ObjectControls(DirectObject):
    def __init__(self):
        super().__init__()
        self.accept('raw-r-up', self.rotate)

    def rotate(self):
        selected = get_selected()
        if selected is not None:
            selected.set_h(selected.get_h() + 90)


def draw(app):
    ObjectControls()
