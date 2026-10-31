"""Port of js/component/controls/firstPerson.js (PointerLockControls + WASD, jump and gravity).

Click captures the mouse like requestPointerLock(), Escape releases it. While captured, clicks are
forwarded as the 'first-person-click' event so selection can pick at the crosshair.
"""
import math

from direct.gui.OnscreenText import OnscreenText
from direct.showbase.DirectObject import DirectObject
from panda3d.core import TextNode, WindowProperties

from .. import registry
from ..coords import three_to_panda
from ..update import add_update_callback

SPEED = 5
GRAVITY = 20
JUMP_VELOCITY = 8
EYE_HEIGHT = 1.6
POINTER_SPEED = 0.002  # radians per pixel, as in PointerLockControls

KEYS = ('w', 'a', 's', 'd')


class FirstPersonControls(DirectObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.pressed = dict.fromkeys(KEYS, False)
        self.velocity_z = 0.0
        self.on_ground = False
        self.is_locked = False
        self._last_pointer = None

        # camera.rotation.set(0, Math.PI, 0) looks down three's +Z, which is Panda's -Y.
        app.camera.set_pos(three_to_panda(2, EYE_HEIGHT, 2))
        app.camera.set_hpr(180, 0, 0)

        # raw- events follow physical keys like KeyboardEvent.code, regardless of layout.
        for key in KEYS:
            self.accept(f'raw-{key}', self._set_pressed, [key, True])
            self.accept(f'raw-{key}-up', self._set_pressed, [key, False])
        self.accept('raw-space', self._jump)
        self.accept('mouse1', self._click)
        self.accept('escape', self.unlock)
        self.accept('window-event', self._window_event)

        self.crosshair = OnscreenText(text='+', pos=(0, -.02), scale=.06, fg=(1, 1, 1, .8), mayChange=False)
        self.crosshair.hide()
        OnscreenText(
            text='click: capture mouse   WASD: move   space: jump   esc: release   F1: settings',
            parent=app.a2dBottomLeft, align=TextNode.A_left, pos=(.05, .05), scale=.04,
            fg=(1, 1, 1, .8), shadow=(0, 0, 0, .6),
        )

        add_update_callback(self.update)

    def lock(self):
        properties = WindowProperties()
        properties.set_cursor_hidden(True)
        properties.set_mouse_mode(WindowProperties.M_confined)
        self.app.win.request_properties(properties)
        self.is_locked = True
        self._last_pointer = None
        self.crosshair.show()

    def unlock(self):
        if not self.is_locked:
            return
        properties = WindowProperties()
        properties.set_cursor_hidden(False)
        properties.set_mouse_mode(WindowProperties.M_absolute)
        self.app.win.request_properties(properties)
        self.is_locked = False
        self.crosshair.hide()

    def _set_pressed(self, key, value):
        self.pressed[key] = value

    def _jump(self):
        if self.on_ground:
            self.velocity_z = JUMP_VELOCITY
            self.on_ground = False

    def _click(self):
        panel = registry.get('settingsPanel')
        if panel is not None and panel.visible:
            return
        if self.is_locked:
            self.app.messenger.send('first-person-click')
        else:
            self.lock()

    def _window_event(self, window):
        if window == self.app.win and not window.get_properties().get_foreground():
            self.unlock()

    def _look(self):
        """Mouse look from frame-to-frame pointer deltas (portable stand-in for pointer lock).

        The pointer is only warped back to the center when it nears the window edge. X11 still
        delivers motion events from before a warp afterwards, which read as one large jump back;
        deltas that big are dropped instead of applied. (Warping every frame turned those stale
        events into a jump on every frame, which made the view shake.)
        """
        win = self.app.win
        pointer = win.get_pointer(0)
        if not pointer.get_in_window():
            self._last_pointer = None
            return

        x, y = pointer.get_x(), pointer.get_y()
        edge = min(win.get_x_size(), win.get_y_size()) // 4
        if self._last_pointer is not None:
            dx, dy = x - self._last_pointer[0], y - self._last_pointer[1]
            if abs(dx) < edge * .75 and abs(dy) < edge * .75:
                camera = self.app.camera
                camera.set_h(camera.get_h() - math.degrees(dx * POINTER_SPEED))
                camera.set_p(max(-90, min(90, camera.get_p() - math.degrees(dy * POINTER_SPEED))))
        self._last_pointer = (x, y)

        center_x, center_y = win.get_x_size() // 2, win.get_y_size() // 2
        if abs(x - center_x) > edge or abs(y - center_y) > edge:
            if win.move_pointer(0, center_x, center_y):
                self._last_pointer = (center_x, center_y)

    def update(self, delta):
        if not self.is_locked:
            return

        self._look()

        position = self.app.camera.get_pos()
        self.velocity_z -= GRAVITY * delta
        position.z += self.velocity_z * delta
        if position.z < EYE_HEIGHT:
            position.z = EYE_HEIGHT
            self.velocity_z = 0
            self.on_ground = True

        # moveForward()/moveRight() move on the ground plane whatever the pitch is.
        heading = math.radians(self.app.camera.get_h())
        forward = (-math.sin(heading), math.cos(heading))
        right = (math.cos(heading), math.sin(heading))
        if self.pressed['w'] or self.pressed['s']:
            distance = (1 if self.pressed['w'] else -1) * SPEED * delta
            position.x += forward[0] * distance
            position.y += forward[1] * distance
        if self.pressed['a'] or self.pressed['d']:
            distance = (1 if self.pressed['d'] else -1) * SPEED * delta
            position.x += right[0] * distance
            position.y += right[1] * distance

        self.app.camera.set_pos(position)


def draw(app):
    registry.add('firstPersonControls', FirstPersonControls(app))
