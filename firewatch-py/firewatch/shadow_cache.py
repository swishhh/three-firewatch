"""Render shadow maps only when they can have changed.

Every render pass costs CPU time even when it draws little (the campfire's cube map alone is six
passes), and rendering identical shadow maps every frame was most of the app's CPU use. A shadow
map is re-rendered when its light or camera moved, when the world changed (`invalidate()`), or,
while something animated casts shadows (wind-swayed plants, drifting clouds), at
`gfx.shadow_update_rate`.
"""
import math

from . import settings

_version = 0
_animated_sources = {}  # name -> callable returning True while it moves


def invalidate():
    """Something that casts shadows changed: re-render every shadow map on the next frame."""
    global _version
    _version += 1


def version():
    """Changes whenever invalidate() is called (anything that casts shadows changed)."""
    return _version


def set_animated_source(name, is_animated):
    _animated_sources[name] = is_animated


def animated():
    return any(is_animated() for is_animated in _animated_sources.values())


class ShadowSchedule:
    def __init__(self, is_animated=None):
        """`is_animated`: what counts as moving for this map (default: any animated source)."""
        self.version = -1
        self.key = None
        self.elapsed = math.inf
        self.is_animated = is_animated or animated

    def force(self):
        self.version = -1

    def due(self, delta, key):
        """True when the shadow map should be rendered this frame."""
        self.elapsed += delta
        render = self.version != _version or key != self.key
        if not render and self.is_animated():
            rate = settings.get('gfx.shadow_update_rate')
            render = rate == 0 or self.elapsed >= 1 / rate - 1e-4
        if render:
            self.version, self.key, self.elapsed = _version, key, 0.0
        return render
