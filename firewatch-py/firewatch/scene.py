"""Port of js/component/scene.js: every module listed here gets `draw(app)` called once, in order.

The world (terrain, objects, foliage, water, clouds) comes from the active save, see world/runtime.py;
the JS components that placed objects from MAP arrays became world/legacy.py, which builds the
'default' save. Comment a line out to disable a component.
"""
import importlib

from .renderer import init_scene_renderer

COMMON = [
    'components.environment',  # light.js and fog, plus sky, sun and moon, time of day and wind
    'world.runtime',
    'components.snow',
    'components.fireflies',
]

GAME = [
    'controls.first_person',
    'controls.inventory',
    'controls.select',
    'controls.selection_panel',
    'controls.object',
    'controls.outline',
    'components.stats',
    'ui.settings_panel',
]

EDITOR = [
    'controls.outline',
    'components.stats',
    'ui.settings_panel',
    'editor.editor',
]

COMPONENTS = {'game': COMMON + GAME, 'editor': COMMON + EDITOR}


def draw(app):
    for name in COMPONENTS[app.mode]:
        importlib.import_module(f'firewatch.{name}').draw(app)

    init_scene_renderer(app)
