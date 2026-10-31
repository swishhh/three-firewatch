"""In-game settings overlay (F1): Graphics and Environment tabs generated from settings.TABS,
replacing the JS app's lil-gui panels. Every change applies immediately and is saved to
settings.json."""
import colorsys

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import DirectButton, DirectFrame, DirectLabel, DirectScrolledFrame, DirectSlider
from direct.showbase.DirectObject import DirectObject
from panda3d.core import TextNode

from .. import registry, settings
from ..colors import rgb

WIDTH = 1.25
HEIGHT = 1.94
CANVAS_WIDTH = WIDTH - .1
ROW = .072
SECTION = .1
LABEL_SCALE = .033
CONTROL_X = .58  # left edge of the controls column

BACKGROUND = (.09, .075, .07, .92)
PANEL_TEXT = (.93, .9, .86, 1)
MUTED_TEXT = (.65, .62, .58, 1)
ACCENT = (.95, .55, .22, 1)
TRACK = (.25, .22, .2, 1)
COLOR_TRACK = (.36, .33, .3, 1)  # hue, saturation, value
BUTTON = (.2, .17, .15, 1)
BUTTON_ACTIVE = (.55, .3, .12, 1)

TIME_NOTE = 'In Time of day mode sky, fog, sun and world light colors follow the clock.'


def _label(parent, text, x, y, scale=LABEL_SCALE, color=PANEL_TEXT, align=TextNode.A_left):
    return DirectLabel(parent=parent, text=text, text_scale=scale, text_fg=color, text_align=align,
                       pos=(x, 0, y), frameColor=(0, 0, 0, 0))


def _button(parent, text, x, y, command, width=.2, scale=.03, color=BUTTON):
    return DirectButton(parent=parent, text=text, text_scale=scale, text_fg=PANEL_TEXT, text_pos=(0, -.01),
                        frameSize=(-width / 2, width / 2, -.025, .03), frameColor=color, relief=DGG.FLAT,
                        pos=(x, 0, y), command=command, pressEffect=True)


def _slider(parent, x, width, low, high, value, command, track=TRACK):
    return DirectSlider(parent=parent, range=(low, high), value=value, pageSize=(high - low) / 20, pos=(x, 0, 0),
                        frameSize=(-width / 2, width / 2, -.007, .007), frameColor=track, relief=DGG.FLAT,
                        thumb_frameSize=(-.011, .011, -.022, .022), thumb_relief=DGG.FLAT,
                        thumb_frameColor=ACCENT, command=command)


class Row:
    def __init__(self, parent, setting, y):
        self.setting = setting
        self.root = parent.attach_new_node(setting.key)
        self.root.set_z(y)
        suffix = '  (restart)' if setting.restart else ''
        _label(self.root, setting.label + suffix, .02, -.012)
        self._updating = False

    def refresh(self):
        pass


class SliderRow(Row):
    def __init__(self, parent, setting, y):
        super().__init__(parent, setting, y)
        self.slider = _slider(self.root, CONTROL_X + .2, .4, setting.min, setting.max,
                              settings.get(setting.key), self._changed)
        self.value = _label(self.root, '', CANVAS_WIDTH - .02, -.012, align=TextNode.A_right, color=MUTED_TEXT)
        self.refresh()

    def _format(self, value):
        if self.setting.kind == 'int':
            return str(int(value))
        span = self.setting.max - self.setting.min
        return f'{value:.3f}' if span <= .2 else f'{value:.2f}' if span <= 5 else f'{value:.1f}'

    def _changed(self):
        if self._updating:
            return
        value = self.slider['value']
        if self.setting.kind == 'int':
            value = round(value)
        elif self.setting.step:
            value = round(value / self.setting.step) * self.setting.step
        # The slider stores 32-bit floats and reports programmatic changes back; ignore that echo.
        if abs(value - settings.get(self.setting.key)) > (self.setting.max - self.setting.min) * 1e-6:
            settings.set(self.setting.key, value)

    def refresh(self):
        value = settings.get(self.setting.key)
        self._updating = True
        if abs(self.slider['value'] - value) > 1e-9:
            self.slider['value'] = value
        self._updating = False
        self.value['text'] = self._format(value)


class ToggleRow(Row):
    def __init__(self, parent, setting, y):
        super().__init__(parent, setting, y)
        self.button = _button(self.root, '', CONTROL_X + .1, -.004, self._toggle, width=.16)
        self.refresh()

    def _toggle(self):
        settings.set(self.setting.key, not settings.get(self.setting.key))

    def refresh(self):
        on = settings.get(self.setting.key)
        self.button['text'] = 'On' if on else 'Off'
        self.button['frameColor'] = BUTTON_ACTIVE if on else BUTTON


class ChoiceRow(Row):
    def __init__(self, parent, setting, y):
        super().__init__(parent, setting, y)
        self.previous = _button(self.root, '<', CONTROL_X + .03, -.004, lambda: self._step(-1), width=.06)
        self.next = _button(self.root, '>', CANVAS_WIDTH - .05, -.004, lambda: self._step(1), width=.06)
        self.value = _label(self.root, '', (CONTROL_X + .06 + CANVAS_WIDTH - .08) / 2, -.012,
                            align=TextNode.A_center)
        self.refresh()

    def _step(self, direction):
        options = self.setting.options
        index = options.index(settings.get(self.setting.key))
        settings.set(self.setting.key, options[(index + direction) % len(options)])

    def refresh(self):
        index = self.setting.options.index(settings.get(self.setting.key))
        self.value['text'] = self.setting.labels[index]


class ColorRow(Row):
    """Swatch plus hue, saturation and value sliders."""

    def __init__(self, parent, setting, y):
        super().__init__(parent, setting, y)
        self.swatch = DirectFrame(parent=self.root, frameSize=(0, .06, -.025, .025), pos=(CONTROL_X, 0, -.002),
                                  relief=DGG.FLAT)
        self.sliders = []
        for index in range(3):
            slider = _slider(self.root, CONTROL_X + .17 + index * .18, .15, 0, 1, 0, self._changed, track=COLOR_TRACK)
            slider.set_z(-.002)
            self.sliders.append(slider)
        self.refresh()

    def _changed(self):
        if self._updating:
            return
        r, g, b = colorsys.hsv_to_rgb(*(slider['value'] for slider in self.sliders))
        settings.set(self.setting.key, '#{:02x}{:02x}{:02x}'.format(*(round(c * 255) for c in (r, g, b))))

    def refresh(self):
        color = [float(c) for c in rgb(settings.get(self.setting.key))]
        self.swatch['frameColor'] = (*color, 1)
        current = colorsys.hsv_to_rgb(*(slider['value'] for slider in self.sliders))
        if max(abs(a - b) for a, b in zip(current, color)) > 1 / 255:
            self._updating = True
            hsv = colorsys.rgb_to_hsv(*color)
            for slider, value in zip(self.sliders, hsv):
                slider['value'] = value
            self._updating = False


ROW_TYPES = {'float': SliderRow, 'int': SliderRow, 'bool': ToggleRow, 'choice': ChoiceRow, 'color': ColorRow}


class SettingsPanel(DirectObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.rows = {}

        self.root = app.a2dTopRight.attach_new_node('settings-panel')
        self.root.set_pos(-WIDTH - .03, 0, -.03)
        DirectFrame(parent=self.root, frameSize=(0, WIDTH, -HEIGHT, 0), frameColor=BACKGROUND, relief=DGG.FLAT)
        _label(self.root, 'Settings', .05, -.075, scale=.05, color=ACCENT)
        _button(self.root, 'x', WIDTH - .06, -.065, self.toggle, width=.06)
        _label(self.root, 'saved to settings.json   F1 / Esc closes', WIDTH / 2, -HEIGHT + .03, scale=.028,
               color=MUTED_TEXT, align=TextNode.A_center)

        self.tab_buttons, self.tab_frames, self.preset_bars = [], [], []
        for index, tab in enumerate(settings.TABS):
            self.tab_buttons.append(_button(self.root, tab.name, .2 + index * .32, -.16, self.select_tab,
                                            width=.3, scale=.036))
            self.tab_buttons[-1]['extraArgs'] = [index]
            bar, preset_rows = self._build_presets(tab)
            self.preset_bars.append(bar)
            self.tab_frames.append(self._build_tab(tab, top=-.24 - .07 * preset_rows - .03))

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
            names = list(settings.GRAPHICS_PRESETS)
            apply = settings.store.apply_graphics_preset
        else:
            names = list(settings.ENVIRONMENT_PRESETS)
            apply = settings.store.apply_environment_preset
        _label(bar, 'Presets', .05, -.245, color=MUTED_TEXT, scale=.03)
        for index, name in enumerate(names):
            row, column = divmod(index, 4)
            _button(bar, name, .3 + column * .27, -.24 - row * .07, apply, width=.26, scale=.027)['extraArgs'] = [name]
        return bar, (len(names) + 3) // 4

    def _build_tab(self, tab, top):
        height = 0
        for item in tab.items:
            height += SECTION if isinstance(item, settings.Section) else ROW
        if tab is settings.ENVIRONMENT:
            height += ROW
        frame = DirectScrolledFrame(
            parent=self.root, frameSize=(.03, WIDTH - .02, -HEIGHT + .07, top),
            canvasSize=(0, CANVAS_WIDTH, -height - .02, 0), frameColor=(0, 0, 0, 0), scrollBarWidth=.025,
            verticalScroll_frameColor=(0, 0, 0, .25), verticalScroll_thumb_frameColor=TRACK,
            verticalScroll_incButton_relief=None, verticalScroll_decButton_relief=None,
            autoHideScrollBars=True, manageScrollBars=True,
        )
        canvas = frame.getCanvas()

        y = -.02
        for item in tab.items:
            if isinstance(item, settings.Section):
                y -= SECTION - ROW
                _label(canvas, item.title.upper(), .02, y - .012, scale=.03, color=ACCENT)
                y -= ROW
                if item.title == 'Time of day':
                    _label(canvas, TIME_NOTE, .02, y - .008, scale=.025, color=MUTED_TEXT)
                    y -= ROW
                continue
            self.rows[item.key] = ROW_TYPES[item.kind](canvas, item, y - ROW / 2 + .012)
            y -= ROW
        frame.content_height = height
        return frame

    def select_tab(self, index):
        for i, (button, frame, presets) in enumerate(zip(self.tab_buttons, self.tab_frames, self.preset_bars)):
            selected = i == index
            button['frameColor'] = BUTTON_ACTIVE if selected else BUTTON
            frame.show() if selected else frame.hide()
            presets.show() if selected else presets.hide()
        self.current = index

    def _scroll(self, direction):
        if not self.visible:
            return
        frame = self.tab_frames[self.current]
        bar = frame.verticalScroll
        visible = frame['frameSize'][3] - frame['frameSize'][2]
        step = ROW * 3 / max(frame.content_height - visible, ROW)
        bar['value'] = min(max(bar['value'] + direction * step, 0), 1)

    def _refresh(self, keys):
        for key in keys:
            row = self.rows.get(key)
            if row is not None:
                row.refresh()

    def toggle(self):
        if self.visible:
            self.close()
        else:
            controls = registry.get('firstPersonControls')
            if controls is not None:
                controls.unlock()
            self.root.show()

    def close(self):
        self.root.hide()


def draw(app):
    registry.add('settingsPanel', SettingsPanel(app))
