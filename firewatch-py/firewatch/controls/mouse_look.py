"""Mouse look from frame-to-frame pointer deltas (portable stand-in for pointer lock).

The pointer is only warped back to the center when it nears the window edge. X11 still delivers
motion events from before a warp afterwards, which read as one large jump back; deltas that big are
dropped instead of applied. (Warping every frame turned those stale events into a jump on every
frame, which made the view shake.)
"""
import math

from panda3d.core import WindowProperties

POINTER_SPEED = 0.002  # radians per pixel, as in PointerLockControls


class MouseLook:
    def __init__(self, app):
        self.app = app
        self.active = False
        self._last = None

    def start(self, confine=True):
        properties = WindowProperties()
        properties.set_cursor_hidden(True)
        if confine:
            properties.set_mouse_mode(WindowProperties.M_confined)
        self.app.win.request_properties(properties)
        self.active = True
        self._last = None

    def stop(self):
        if not self.active:
            return
        properties = WindowProperties()
        properties.set_cursor_hidden(False)
        properties.set_mouse_mode(WindowProperties.M_absolute)
        self.app.win.request_properties(properties)
        self.active = False

    def delta(self):
        """Pointer movement in pixels since the previous call (0, 0 when unknown)."""
        win = self.app.win
        pointer = win.get_pointer(0)
        if not pointer.get_in_window():
            self._last = None
            return 0, 0
        x, y = pointer.get_x(), pointer.get_y()
        edge = min(win.get_x_size(), win.get_y_size()) // 4
        dx = dy = 0
        if self._last is not None:
            dx, dy = x - self._last[0], y - self._last[1]
            if abs(dx) >= edge * .75 or abs(dy) >= edge * .75:
                dx = dy = 0
        self._last = (x, y)
        center_x, center_y = win.get_x_size() // 2, win.get_y_size() // 2
        if abs(x - center_x) > edge or abs(y - center_y) > edge:
            if win.move_pointer(0, center_x, center_y):
                self._last = (center_x, center_y)
        return dx, dy

    def rotate(self, node, speed=POINTER_SPEED):
        dx, dy = self.delta()
        if dx or dy:
            node.set_h(node.get_h() - math.degrees(dx * speed))
            node.set_p(max(-89.9, min(89.9, node.get_p() - math.degrees(dy * speed))))
