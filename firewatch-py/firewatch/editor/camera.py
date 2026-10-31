"""Editor fly camera.

Hold the right mouse button to look around and fly with WASD (Q / E down / up, Shift faster, wheel
while flying changes the speed). Wheel zooms towards the point under the cursor, the middle button
pans, Alt + left button orbits around the point under the cursor, F frames the selection.
"""
import math

from panda3d.core import KeyboardButton, MouseButton, Point3, Vec3

from ..controls.mouse_look import MouseLook

MIN_SPEED, MAX_SPEED = 1.0, 80.0


class EditorCamera:
    def __init__(self, editor):
        self.editor = editor
        self.app = editor.app
        self.look = MouseLook(self.app)
        self.speed = 8.0
        self.flying = False
        self.panning = None  # last pointer position
        self.orbit = None  # (pivot, last pointer)

    def _key(self, name):
        watcher = self.app.mouseWatcherNode
        return watcher.is_button_down(KeyboardButton.ascii_key(name))

    def start_fly(self):
        self.flying = True
        self.look.start(confine=False)

    def stop_fly(self):
        self.flying = False
        self.look.stop()

    def start_pan(self):
        self.panning = self._pointer()

    def stop_pan(self):
        self.panning = None

    def start_orbit(self, pivot):
        self.orbit = (Point3(*pivot), self._pointer())

    def stop_orbit(self):
        self.orbit = None

    def _pointer(self):
        pointer = self.app.win.get_pointer(0)
        return pointer.get_x(), pointer.get_y()

    def zoom(self, direction, target=None):
        camera = self.app.camera
        position = camera.get_pos()
        if target is None:
            forward = camera.get_quat().get_forward()
            camera.set_pos(position + forward * direction * self.speed * .5)
            return
        offset = Point3(*target) - position
        distance = offset.length()
        step = max(distance * .15, .3) * direction
        if direction > 0 and distance - step < .5:
            step = max(distance - .5, 0)
        camera.set_pos(position + offset.normalized() * step)

    def focus(self, center, radius):
        camera = self.app.camera
        forward = camera.get_quat().get_forward()
        camera.set_pos(Point3(*center) - forward * max(radius * 3, 2.5))

    def update(self, delta):
        camera = self.app.camera
        watcher = self.app.mouseWatcherNode
        if self.flying:
            if not watcher.is_button_down(MouseButton.three()):
                self.stop_fly()
            else:
                self.look.rotate(camera)
                quat = camera.get_quat()
                move = Vec3(0)
                if self._key('w'):
                    move += quat.get_forward()
                if self._key('s'):
                    move -= quat.get_forward()
                if self._key('d'):
                    move += quat.get_right()
                if self._key('a'):
                    move -= quat.get_right()
                if self._key('e'):
                    move += Vec3(0, 0, 1)
                if self._key('q'):
                    move -= Vec3(0, 0, 1)
                if move.length_squared() > 0:
                    fast = 3 if watcher.is_button_down(KeyboardButton.shift()) else 1
                    camera.set_pos(camera.get_pos() + move.normalized() * self.speed * fast * delta)
        if self.panning is not None:
            if not watcher.is_button_down(MouseButton.two()):
                self.stop_pan()
            else:
                x, y = self._pointer()
                dx, dy = x - self.panning[0], y - self.panning[1]
                self.panning = (x, y)
                height = max(abs(camera.get_z() - self.editor.ground_height_below_camera()), 2)
                scale = height * .0015
                quat = camera.get_quat()
                camera.set_pos(camera.get_pos() - quat.get_right() * dx * scale + quat.get_up() * dy * scale)
        if self.orbit is not None:
            if not watcher.is_button_down(MouseButton.one()):
                self.stop_orbit()
            else:
                pivot, last = self.orbit
                x, y = self._pointer()
                dx, dy = x - last[0], y - last[1]
                self.orbit = (pivot, (x, y))
                offset = camera.get_pos() - pivot
                distance = offset.length()
                heading = math.atan2(offset.y, offset.x) - dx * .005
                pitch = math.asin(max(-1, min(1, offset.z / max(distance, 1e-6)))) + dy * .005
                pitch = max(math.radians(-85), min(math.radians(85), pitch))
                camera.set_pos(pivot + Vec3(math.cos(heading) * math.cos(pitch), math.sin(heading) * math.cos(pitch),
                                            math.sin(pitch)) * distance)
                camera.look_at(pivot)
