"""Port of js/app.js: window, camera and the per-frame update loop. Runs the game (first person) or
the world editor, both on the same graphics settings and the same active world save.
"""
import os
import time

# NVIDIA's driver spins a CPU core while it waits for vsync unless told to sleep; must be set before
# the GL library loads.
os.environ.setdefault('__GL_YIELD', 'USLEEP')
# Panda3D's bundled OpenAL Soft has no PipeWire backend, and its PulseAudio backend fails to open a
# stream on PipeWire's Pulse server ("Stream did not get ready"), leaving the game silent. ALSA (routed
# through PipeWire / PulseAudio by the system) works; Pulse and OSS stay as fallbacks.
os.environ.setdefault('ALSOFT_DRIVERS', 'alsa,pulse,oss')

from direct.showbase.ShowBase import ShowBase  # noqa: E402
from panda3d.core import load_prc_file_data  # noqa: E402

from . import registry, scene, settings, shading  # noqa: E402
from .coords import three_to_panda  # noqa: E402
from .pipeline import init_pipeline  # noqa: E402
from .update import add_update_callback, get_update_callbacks  # noqa: E402

# Multisampling happens in the offscreen scene buffer (pipeline.py); the window only shows the result.
CONFIG = """
win-size 1280 720
textures-power-2 none
"""

FRAME_LIMITS = settings.SCHEMA['gfx.fps_cap'].options
DISPLAY = -1  # gfx.fps_cap value: follow the monitor's refresh rate
TITLES = {'game': 'Fire-watch (Panda3D)', 'editor': 'Fire-watch world editor (Panda3D)'}


class App(ShowBase):
    def __init__(self, fps=None, vsync=None, mode='game', world=None):
        self.mode = mode
        self.world_name = world
        settings.store.load()
        overrides = {'gfx.fps_cap': fps, 'gfx.vsync': vsync}
        settings.update({key: value for key, value in overrides.items() if value is not None})

        load_prc_file_data('firewatch', CONFIG + f"window-title {TITLES[mode]}\n"
                                                 f"sync-video {int(settings.get('gfx.vsync'))}\n")
        super().__init__()
        self.disable_mouse()
        manager = self.sfxManagerList[0] if self.sfxManagerList else None
        if manager is None or not manager.is_valid():
            print('audio: no sound device could be opened, the game runs silent. Try another OpenAL backend, '
                  'e.g. ALSOFT_DRIVERS=pulse .venv/bin/python main.py')
        self._next_frame = 0.0
        self.display_rate = self._display_refresh_rate()
        self.focused = True

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
        self.accept('f2', self.cycle_frame_limit)  # (F is the flashlight in the game, focus in the editor)
        self.exitFunc = self._on_exit

    def _display_refresh_rate(self):
        try:
            info = self.pipe.get_display_information()
            index = info.get_current_display_mode_index()
            if index >= 0:
                rate = info.get_display_mode_refresh_rate(index)
                if 20 <= rate <= 500:
                    return rate
        except Exception:
            pass
        return 60

    @property
    def frame_limit(self):
        """Frames per second the loop is capped to now (0 = uncapped)."""
        cap = settings.get('gfx.fps_cap')
        if cap == DISPLAY:
            cap = 0 if settings.get('gfx.vsync') else self.display_rate  # vsync already paces to the display
        background = settings.get('gfx.background_fps')
        if not self.focused and background:
            cap = min(cap, background) if cap else background
        return cap

    def set_frame_limit(self, fps):
        """Cap the frame rate (0 = uncapped, -1 = display refresh rate)."""
        settings.set('gfx.fps_cap', fps)

    def _limit_frame_rate(self, task):
        # Sleep until the next frame is due. (Panda's own M_limited clock busy-waits, which kept
        # a core 60% busy even at 60 fps.)
        if hasattr(self.win, 'get_properties'):  # offscreen buffers have no focus
            properties = self.win.get_properties()
            foreground = properties.get_foreground() if properties.has_foreground() else True
            self.focused = foreground and not (properties.has_minimized() and properties.get_minimized())
        limit = self.frame_limit
        if limit:
            now = time.perf_counter()
            due = max(self._next_frame, now)
            time.sleep(due - now)
            self._next_frame = due + 1 / limit
        return task.cont

    def cycle_frame_limit(self):
        current = settings.get('gfx.fps_cap')
        index = FRAME_LIMITS.index(current) if current in FRAME_LIMITS else -1
        self.set_frame_limit(FRAME_LIMITS[(index + 1) % len(FRAME_LIMITS)])

    def _animate(self, task):
        delta = self.clock.get_dt()
        for callback in list(get_update_callbacks()):
            callback(delta)
        return task.cont

    def _on_exit(self):
        world = registry.get('world')
        if world is not None and world.document is not None:
            world.flush()
        settings.store.save()
