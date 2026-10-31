"""In-game settings overlay (F1): one tab per settings.TABS entry (Graphics, Lighting, Sky, World,
Player), generated from the schema, replacing the JS app's lil-gui panels. Every change applies
immediately; graphics go to settings.json, the rest is saved with the world."""
from direct.showbase.DirectObject import DirectObject
from panda3d.core import TextNode

from .. import registry, settings
from . import widgets
from .widgets import ACCENT, BUTTON, BUTTON_ACTIVE, MUTED_TEXT, Note, PropertyList, button, label, panel

WIDTH = 1.25
HEIGHT = 1.94
CANVAS_WIDTH = WIDTH - .1

TIME_NOTE = 'In Time of day mode sky, fog, sun and world light colors follow the clock, and the moon rises opposite the sun.'


class SettingsPanel(DirectObject):
    def __init__(self, app, top=-.03, height=HEIGHT):
        super().__init__()
        self.app = app
        self.lists = []
        self.height = height

        self.root = app.a2dTopRight.attach_new_node('settings-panel')
        self.root.set_pos(-WIDTH - .03, 0, top)
        panel(self.root, (0, WIDTH, -height, 0))
        label(self.root, 'Settings', .05, -.075, scale=.05, color=ACCENT)
        button(self.root, 'x', WIDTH - .06, -.065, self.close, width=.06)
        where = 'graphics: settings.json   world settings: saved with the world'
        label(self.root, where + '   F1 / Esc closes', WIDTH / 2, -height + .03, scale=.025, color=MUTED_TEXT,
              align=TextNode.A_center)

        self.tab_buttons, self.preset_bars = [], []
        tab_width = (WIDTH - .08) / len(settings.TABS)
        for index, tab in enumerate(settings.TABS):
            self.tab_buttons.append(button(self.root, tab.name, .04 + tab_width * (index + .5), -.16, self.select_tab,
                                           width=tab_width - .015, scale=.032, extra_args=[index]))
            bar, preset_rows = self._build_presets(tab)
            self.preset_bars.append(bar)
            top_y = -.24 - .07 * preset_rows - .03
            items = []
            for item in tab.items:
                if isinstance(item, settings.Section):
                    items.append(item)
                    if item.title == 'Time of day':
                        items.append(Note(TIME_NOTE))
                else:
                    items.append((item, (lambda key=item.key: settings.get(key)),
                                  (lambda value, key=item.key: settings.set(key, value))))
            self.lists.append(PropertyList(self.root, (.03, WIDTH - .02, -height + .07, top_y), items, CANVAS_WIDTH))

        settings.subscribe(self._refresh)
        self.select_tab(0)
        self.root.hide()

        self.accept('f1', self.toggle)
        self.accept('escape', self.close)
        self.accept('wheel_up', self._scroll, [-1])
        self.accept('wheel_down', self._scroll, [1])

    @property
    def visible(self):
        return not self.root.is_hidden()

    def _build_presets(self, tab):
        bar = self.root.attach_new_node(f'{tab.name}-presets')
        if tab is settings.GRAPHICS:
            names, apply = list(settings.GRAPHICS_PRESETS), settings.store.apply_graphics_preset
        elif tab is settings.LIGHTING:
            names, apply = list(settings.ENVIRONMENT_PRESETS), settings.store.apply_environment_preset
        else:
            return bar, -1
        label(bar, 'Presets', .05, -.245, color=MUTED_TEXT, scale=.03)
        for index, name in enumerate(names):
            row, column = divmod(index, 4)
            button(bar, name, .3 + column * .27, -.24 - row * .07, apply, width=.26, scale=.027, extra_args=[name])
        return bar, (len(names) + 3) // 4

    def select_tab(self, index):
        for i, (tab_button, property_list, presets) in enumerate(zip(self.tab_buttons, self.lists, self.preset_bars)):
            selected = i == index
            tab_button['frameColor'] = BUTTON_ACTIVE if selected else BUTTON
            property_list.frame.show() if selected else property_list.frame.hide()
            presets.show() if selected else presets.hide()
        self.current = index

    def select_tab_by_name(self, name):
        for index, tab in enumerate(settings.TABS):
            if tab.name == name:
                self.select_tab(index)

    def over(self):
        """Is the pointer over the panel?"""
        return self.visible and self.lists[self.current].contains(self.app.mouseWatcherNode)

    def _scroll(self, direction):
        if self.visible and (self.over() or self.app.mode == 'game'):
            self.lists[self.current].scroll(direction)

    def _refresh(self, _keys):
        if self.visible:
            self.lists[self.current].refresh()

    def toggle(self):
        if self.visible:
            self.close()
        else:
            self.open()

    def open(self, tab=None):
        controls = registry.get('firstPersonControls')
        if controls is not None:
            controls.unlock()
        if tab is not None:
            self.select_tab_by_name(tab)
        self.root.show()
        self.lists[self.current].refresh()
        self.app.messenger.send('settings-panel', [True])

    def close(self):
        if widgets.typing():
            return
        if self.visible:
            self.root.hide()
            self.app.messenger.send('settings-panel', [False])


def draw(app):
    if app.mode == 'editor':
        registry.add('settingsPanel', SettingsPanel(app, top=-.12, height=1.8))
    else:
        registry.add('settingsPanel', SettingsPanel(app))
