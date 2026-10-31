"""Port of js/app.js: window, camera and the per-frame update loop."""
import time

from direct.showbase.ShowBase import ShowBase
from panda3d.core import load_prc_file_data

from . import registry, scene, settings, shading
from .coords import three_to_panda
from .pipeline import init_pipeline
from .update import add_update_callback, get_update_callbacks

# Multisampling happens in the offscreen scene buffer (pipeline.py); the window only shows the result.
CONFIG = """
window-title Three js fire-watch (Panda3D)
win-size 1280 720
textures-power-2 none
"""

FRAME_LIMITS = settings.SCHEMA['gfx.fps_cap'].options


class App(ShowBase):
    def __init__(self, fps=None, vsync=None):
        settings.store.load()
        overrides = {'gfx.fps_cap': fps, 'gfx.vsync': vsync}
        settings.update({key: value for key, value in overrides.items() if value is not None})

        load_prc_file_data('firewatch', CONFIG + f"sync-video {int(settings.get('gfx.vsync'))}\n")
        super().__init__()
        self.disable_mouse()
        self._next_frame = 0.0

        # THREE.PerspectiveCamera(40, aspect, 0.1, 500): the field of view is vertical.
        self.camLens.set_near_far(0.1, 500)
        self.camera.set_pos(three_to_panda(0, 15, 15))
        self.camera.look_at(0, 0, 0)
        settings.subscribe(lambda _keys: self.camLens.set_min_fov(settings.get('gfx.fov')), 'gfx.fov')
        self.camLens.set_min_fov(settings.get('gfx.fov'))

        shading.init(self)
        registry.add('app', self)
        registry.add('scene', self.render)
        registry.add('camera', self.camera)

        scene.draw(self)
        init_pipeline(self)

        add_update_callback(settings.store.tick)
        self.task_mgr.add(self._animate, 'animate')
        self.task_mgr.add(self._limit_frame_rate, 'limit-frame-rate', sort=-100)
        self.accept('raw-f', self.cycle_frame_limit)

    @property
    def frame_limit(self):
        return settings.get('gfx.fps_cap')

    def set_frame_limit(self, fps):
        """Cap the frame rate (0 = uncapped)."""
        settings.set('gfx.fps_cap', fps)

    def _limit_frame_rate(self, task):
        # Sleep until the next frame is due. (Panda's own M_limited clock busy-waits, which kept
        # a core 60% busy even at 60 fps.)
        if self.frame_limit:
            now = time.perf_counter()
            due = max(self._next_frame, now)
            time.sleep(due - now)
            self._next_frame = due + 1 / self.frame_limit
        return task.cont

    def cycle_frame_limit(self):
        index = FRAME_LIMITS.index(self.frame_limit) if self.frame_limit in FRAME_LIMITS else -1
        self.set_frame_limit(FRAME_LIMITS[(index + 1) % len(FRAME_LIMITS)])

    def _animate(self, task):
        delta = self.clock.get_dt()
        for callback in get_update_callbacks():
            callback(delta)
        return task.cont
