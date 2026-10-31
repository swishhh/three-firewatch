"""Measure what each expensive graphics feature costs on this machine, in the current view.

Runs uncapped for a few dozen frames per configuration, turning one feature off at a time, then
restores the settings. Times are milliseconds per frame (CPU and GPU together: the loop waits for
whichever is slower).
"""
import os
import time

from .. import settings

WARMUP = 15
FRAMES = 60

CASES = (
    ('everything as set', {}),
    ('without point light shadows', {'gfx.fire_shadows': False}),
    ('without sun shadows', {'gfx.shadows': False}),
    ('without ambient occlusion', {'gfx.ao': False}),
    ('without contact shadows', {'gfx.contact_shadows': False}),
    ('without bloom', {'gfx.bloom': False}),
    ('without MSAA', {'gfx.msaa': 0}),
    ('render scale 100%', {'gfx.render_scale': 1.0}),
    ('shadow filter PCF 16', {'gfx.shadow_filter': 'pcf', 'gfx.shadow_samples': 16}),
    ('without snow / fireflies', {'env.snow': False, 'env.fireflies': False}),
)


class Benchmark:
    def __init__(self, app, done):
        self.app = app
        self.done = done
        self.original = dict(settings.store.values)
        settings.set('gfx.fps_cap', 0)
        self.results = []
        self.case = -1
        self.frame = 0
        self.started = None
        self._next_case()

    def _next_case(self):
        self.case += 1
        settings.store.update({key: self.original[key] for key in settings.store.values
                               if settings.store.values[key] != self.original[key] and key != 'gfx.fps_cap'})
        while self.case < len(CASES):
            changes = CASES[self.case][1]
            if not changes or any(settings.get(key) != value for key, value in changes.items()):
                settings.store.update(changes)
                break
            self.case += 1  # already off: nothing to measure
        self.frame = 0
        self.started = None

    def step(self, _delta):
        if self.case >= len(CASES):
            return
        self.frame += 1
        if self.frame == WARMUP:
            self.started = (time.perf_counter(), os.times())
        elif self.frame == WARMUP + FRAMES:
            wall = (time.perf_counter() - self.started[0]) / FRAMES * 1000
            times = os.times()
            cpu = ((times.user + times.system) - (self.started[1].user + self.started[1].system)) / FRAMES * 1000
            self.results.append((CASES[self.case][0], wall, cpu))
            self._next_case()
            if self.case >= len(CASES):
                self._finish()

    def _finish(self):
        settings.store.update(self.original)
        base = self.results[0][1] if self.results else 0
        lines = [f'{"configuration":32s} {"ms/frame":>9s} {"CPU ms":>8s}  {"saves":>8s}']
        for name, wall, cpu in self.results:
            saving = '' if name == CASES[0][0] else f'{base - wall:+.2f}'
            lines.append(f'{name:32s} {wall:9.2f} {cpu:8.2f}  {saving:>8s}')
        lines += ['', f'Frame cap {settings.get("gfx.fps_cap")} (-1 = display) restored. '
                      f'At {base:.2f} ms the scene could run at {1000 / max(base, 1e-3):.0f} fps uncapped.',
                  'CPU ms close to ms/frame means the CPU (render passes, Python) limits the frame rate; '
                  'much lower means the GPU does.']
        self.done('\n'.join(lines))
