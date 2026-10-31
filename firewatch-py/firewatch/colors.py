import numpy as np


def rgb(value):
    """'#rrggbb' or 0xrrggbb as floats in 0..1.

    Used without any sRGB conversion: the JS app runs three.js r146 with ColorManagement in legacy
    mode and renders through an EffectComposer whose final FXAA pass skips output encoding, so hex
    values reach the screen untouched.
    """
    if isinstance(value, str):
        value = int(value.lstrip('#'), 16)
    return np.array([(value >> 16) & 255, (value >> 8) & 255, value & 255], dtype=np.float32) / 255


def rgba(value, alpha=1.0):
    r, g, b = rgb(value)
    return float(r), float(g), float(b), alpha
