"""Port of js/registry/update.js: per-frame callbacks, each called with the frame delta in seconds."""

_callbacks = []


def add_update_callback(callback):
    _callbacks.append(callback)


def get_update_callbacks():
    return _callbacks


def fixed_step(callback, hz=60):
    """Wrap a callback written for requestAnimationFrame at 60 fps so it runs at that rate on any display."""
    interval = 1 / hz
    elapsed = 0.0

    def step(delta):
        nonlocal elapsed
        elapsed = min(elapsed + delta, interval * 10)
        while elapsed >= interval:
            callback()
            elapsed -= interval

    return step
