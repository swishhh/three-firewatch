"""Port of js/component/scene.js: every module listed here gets `draw(app)` called once, in order.

Comment a line out to disable a component. Entries marked "not ported" were disabled in the JS app too.
"""
import importlib

from .renderer import init_scene_renderer

COMPONENTS = [
    'components.terrain',
    'components.rocks',
    # 'lampPost',  not ported
    'components.tent',
    'components.clouds',
    'components.tree',
    'components.bush',
    'components.grass',
    # 'water',  not ported
    'components.campfire',
    'components.picnic_table',
    'components.welcome_sign',
    'components.bird',
    # 'house', 'fireWatch', 'fireCamp',  not ported
    'components.environment',  # light.js and fog, plus sky, time of day and wind
    'components.snow',
    'components.fireflies',

    # 'mapControls',  not ported
    'controls.first_person',

    'controls.select',
    'controls.selection_panel',
    'controls.object',
    'controls.outline',
    'components.stats',
    'ui.settings_panel',
]


def draw(app):
    for name in COMPONENTS:
        importlib.import_module(f'firewatch.{name}').draw(app)

    init_scene_renderer(app)
