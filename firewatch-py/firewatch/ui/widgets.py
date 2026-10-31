"""DirectGUI building blocks shared by the settings panel and the editor: property rows bound to a
getter and a setter, and a scrolling list of them.

Row kinds: float / int (slider), bool (toggle), choice (< value >), color (swatch + hue, saturation,
value sliders + hex entry), number (entry with - / + nudges), text (entry), button(s), note.
"""
import colorsys
import time
from dataclasses import dataclass

import numpy as np

from direct.gui import DirectGuiGlobals as DGG
from direct.gui.DirectGui import (DirectButton, DirectEntry, DirectFrame, DirectLabel, DirectScrolledFrame,
                                  DirectSlider)
from panda3d.core import MouseButton, Point3, SamplerState, TextNode, Texture

from ..colors import rgb
from ..settings import Section, Setting

ROW = .072
SECTION = .1
LABEL_SCALE = .033

BACKGROUND = (.09, .075, .07, .92)
PANEL_TEXT = (.93, .9, .86, 1)
MUTED_TEXT = (.65, .62, .58, 1)
ACCENT = (.95, .55, .22, 1)
TRACK = (.25, .22, .2, 1)
COLOR_TRACK = (.36, .33, .3, 1)
BUTTON = (.2, .17, .15, 1)
BUTTON_ACTIVE = (.55, .3, .12, 1)
ENTRY = (.16, .14, .13, 1)

_focused = set()
_entries = []


def typing():
    """True while a text field has keyboard focus (editor hotkeys stay quiet)."""
    return bool(_focused)


def release_focus():
    for entry in list(_entries):
        try:
            if not entry.is_empty():
                entry['focus'] = 0
        except (AssertionError, AttributeError):
            pass
    _focused.clear()


def label(parent, text, x, y, scale=LABEL_SCALE, color=PANEL_TEXT, align=TextNode.A_left, wrap=None):
    return DirectLabel(parent=parent, text=text, text_scale=scale, text_fg=color, text_align=align,
                       text_wordwrap=wrap, pos=(x, 0, y), frameColor=(0, 0, 0, 0), state=DGG.DISABLED)


def button(parent, text, x, y, command, width=.2, scale=.03, color=BUTTON, height=.055, extra_args=None):
    widget = DirectButton(parent=parent, text=text, text_scale=scale, text_fg=PANEL_TEXT, text_pos=(0, -.01),
                          frameSize=(-width / 2, width / 2, -height / 2 + .0025, height / 2 + .0025),
                          frameColor=color, relief=DGG.FLAT, pos=(x, 0, y), command=command, pressEffect=True)
    if extra_args is not None:
        widget['extraArgs'] = extra_args
    return widget


def slider(parent, x, width, low, high, value, command, track=TRACK):
    return DirectSlider(parent=parent, range=(low, high), value=value, pageSize=(high - low) / 20, pos=(x, 0, 0),
                        frameSize=(-width / 2, width / 2, -.009, .009), frameColor=track, relief=DGG.FLAT,
                        thumb_frameSize=(-.014, .014, -.026, .026), thumb_relief=DGG.FLAT,
                        thumb_frameColor=ACCENT, command=command)


def entry(parent, x, width, text, command, scale=.03):
    """Single-line text field; `command(text)` on Enter or when it loses focus."""

    def submit(value=None):
        if value is None:
            value = widget.get()
        _focused.discard(id(widget))
        command(value)

    def focus_in():
        _focused.add(id(widget))

    def focus_out():
        if id(widget) in _focused:
            submit()

    widget = DirectEntry(parent=parent, initialText=str(text), scale=scale, width=width / scale,
                         pos=(x, 0, -.01), frameColor=ENTRY, text_fg=PANEL_TEXT, relief=DGG.FLAT,
                         command=submit, focusInCommand=focus_in, focusOutCommand=focus_out,
                         numLines=1, cursorKeys=1, suppressKeys=1)
    _entries.append(widget)
    return widget


@dataclass
class Button:
    label: str
    command: object
    extra: tuple = ()  # more (label, command) pairs on the same row


@dataclass
class Note:
    text: str


UNBOUNDED = float('inf')


def prop(label_text, kind, minimum=None, maximum=None, step=0, options=(), labels=None):
    """A Setting-like spec for rows that aren't settings. Number rows without limits accept any value
    (negative positions, offsets, ...); sliders default to 0..1."""
    if kind == 'number':
        minimum = -UNBOUNDED if minimum is None else minimum
        maximum = UNBOUNDED if maximum is None else maximum
    else:
        minimum = 0 if minimum is None else minimum
        maximum = 1 if maximum is None else maximum
    return Setting(label_text, label_text, kind, None, None, minimum, maximum, step, tuple(options),
                   tuple(labels or (str(option) for option in options)))


class Row:
    def __init__(self, parent, spec, y, get, put, width):
        self.spec = spec
        self.get = get
        self.put = put
        self.width = width
        self.control_x = width * .5
        self.root = parent.attach_new_node(spec.key)
        self.root.set_z(y)
        suffix = '  (restart)' if spec.restart else ''
        label(self.root, spec.label + suffix, .02, -.012)
        self._updating = True  # controls report their initial values while being built: not user edits

    def refresh(self):
        pass

    def destroy(self):
        self.root.remove_node()


class SliderRow(Row):
    """Slider plus a field showing the value; type a number there (Enter) for an exact value."""

    def __init__(self, parent, spec, y, get, put, width):
        super().__init__(parent, spec, y, get, put, width)
        field = .13
        slider_width = width - self.control_x - field - .06
        self.slider = slider(self.root, self.control_x + slider_width / 2, slider_width, spec.min, spec.max,
                             min(max(get(), spec.min), spec.max), self._changed)
        self.value = entry(self.root, width - field - .015, field, self._format(get()), self._entered, scale=.028)
        self.refresh()
        self._updating = False

    def _format(self, value):
        if self.spec.kind == 'int':
            return str(int(value))
        span = self.spec.max - self.spec.min
        return f'{value:.3f}' if span <= .2 else f'{value:.2f}' if span <= 5 else f'{value:.1f}'

    def _entered(self, text):
        try:
            value = float(text)
        except ValueError:
            self.refresh()
            return
        if self.spec.kind == 'int':
            value = int(round(value))
        value = min(max(value, self.spec.min), self.spec.max)
        if not self._updating and abs(value - self.get()) > 1e-9:
            self.put(value)
        self.refresh()

    def _changed(self):
        if self._updating:
            return
        value = self.slider['value']
        if self.spec.kind == 'int':
            value = round(value)
        elif self.spec.step:
            value = round(value / self.spec.step) * self.spec.step
        # The slider stores 32-bit floats and reports programmatic changes back; ignore that echo.
        if abs(value - self.get()) > (self.spec.max - self.spec.min) * 1e-6:
            self.put(value)
            self.value.enterText(self._format(value))

    def refresh(self):
        value = self.get()
        self._updating = True
        if abs(self.slider['value'] - value) > 1e-9:
            self.slider['value'] = min(max(value, self.spec.min), self.spec.max)
        self._updating = False
        if id(self.value) not in _focused:
            self.value.enterText(self._format(value))


class ToggleRow(Row):
    def __init__(self, parent, spec, y, get, put, width):
        super().__init__(parent, spec, y, get, put, width)
        self.button = button(self.root, '', self.control_x + .08, -.004, self._toggle, width=.16)
        self.refresh()
        self._updating = False

    def _toggle(self):
        self.put(not self.get())
        self.refresh()

    def refresh(self):
        on = self.get()
        self.button['text'] = 'On' if on else 'Off'
        self.button['frameColor'] = BUTTON_ACTIVE if on else BUTTON


class ChoiceRow(Row):
    def __init__(self, parent, spec, y, get, put, width):
        super().__init__(parent, spec, y, get, put, width)
        self.previous = button(self.root, '<', self.control_x + .03, -.004, lambda: self._step(-1), width=.06)
        self.next = button(self.root, '>', width - .05, -.004, lambda: self._step(1), width=.06)
        self.value = label(self.root, '', (self.control_x + .06 + width - .08) / 2, -.012, align=TextNode.A_center,
                           scale=.03)
        self.refresh()
        self._updating = False

    def _step(self, direction):
        options = self.spec.options
        current = self.get()
        index = options.index(current) if current in options else -1
        self.put(options[(index + direction) % len(options)])
        self.refresh()

    def refresh(self):
        current = self.get()
        if current in self.spec.options:
            text = self.spec.labels[self.spec.options.index(current)]
        else:
            text = str(current)
        limit = max(int((self.width - self.control_x - .14) / .016), 6)
        self.value['text'] = text if len(text) <= limit else text[:limit - 1] + '\N{HORIZONTAL ELLIPSIS}'


class ColorRow(Row):
    """Swatch (click: color picker) and a hex field."""

    def __init__(self, parent, spec, y, get, put, width):
        super().__init__(parent, spec, y, get, put, width)
        self.swatch = DirectButton(parent=self.root, frameSize=(0, .13, -.026, .03), pos=(self.control_x, 0, -.004),
                                   relief=DGG.FLAT, command=self._open, pressEffect=True,
                                   frameColor=(1, 1, 1, 1))
        self.hex = entry(self.root, self.control_x + .15, .18, get(), self._hex_entered, scale=.028)
        self.refresh()
        self._updating = False

    def _open(self):
        ColorPicker.open(self.swatch, self.get, self._picked)

    def _picked(self, value):
        if value != self.get():
            self.put(value)
        self.refresh()

    def _hex_entered(self, text):
        text = text.strip()
        if not text.startswith('#'):
            text = '#' + text
        try:
            int(text[1:], 16)
        except ValueError:
            self.refresh()
            return
        if len(text) == 7 and text.lower() != self.get():
            self.put(text.lower())
        self.refresh()

    def refresh(self):
        value = self.get()
        self.swatch['frameColor'] = (*[float(c) for c in rgb(value)], 1)
        if id(self.hex) not in _focused:
            self.hex.enterText(value)

    def destroy(self):
        ColorPicker.close_for(self.swatch)
        super().destroy()


def _hsv_to_rgb_grid(hue, size):
    """RGB (size, size, 3) for saturation along x and value along y (row 0 = value 0)."""
    s = np.linspace(0, 1, size)[np.newaxis, :]
    v = np.linspace(0, 1, size)[:, np.newaxis]
    r, g, b = colorsys.hsv_to_rgb(hue, 1, 1)
    pure = np.array([r, g, b])
    return (v[..., np.newaxis] * ((1 - s[..., np.newaxis]) + s[..., np.newaxis] * pure))


def _texture(name, pixels):
    """Texture from float RGB rows (bottom row first, as Panda stores them)."""
    height, width, _ = pixels.shape
    texture = Texture(name)
    texture.setup_2d_texture(width, height, Texture.T_unsigned_byte, Texture.F_rgb8)
    data = np.ascontiguousarray((np.clip(pixels, 0, 1) * 255).round().astype(np.uint8)[..., ::-1])
    texture.set_ram_image(data.tobytes())
    texture.set_wrap_u(SamplerState.WM_clamp)
    texture.set_wrap_v(SamplerState.WM_clamp)
    texture.set_minfilter(SamplerState.FT_linear)
    texture.set_magfilter(SamplerState.FT_linear)
    return texture


PALETTE = (
    '#0a1f00', '#1c3312', '#234517', '#3b5a1e', '#6b8e23', '#a3b86c', '#062408', '#2c4a3a', '#7d8f4e', '#c8d6a0',
    '#241302', '#3e2a16', '#5e3c1c', '#8a5a2b', '#b07a48', '#d2b48c', '#291602', '#532d09', '#700b0b', '#c0392b',
    '#000000', '#292929', '#383838', '#505050', '#808080', '#a9a9a9', '#d2d1d1', '#ffffff', '#f5f9ff', '#e8eeff',
    '#0b2a3a', '#2f6f73', '#4d8fd1', '#9cc7e8', '#6f5b86', '#cc5200', '#f0a35e', '#ffb36b', '#ffd27a', '#d6ff7a',
)


class ColorPicker:
    """Popup color picker: saturation / brightness square, hue bar, palette, recent colors, hex field.
    Changes apply live while dragging."""

    WIDTH, HEIGHT = .74, 1.2
    SQUARE = .46
    recent = []
    current = None

    @classmethod
    def open(cls, anchor, get, put):
        if cls.current is not None:
            same = cls.current.anchor == anchor
            cls.current.close()
            if same:
                return  # clicking the swatch again closes the picker
        cls.current = cls(anchor, get, put)

    @classmethod
    def close_for(cls, anchor):
        if cls.current is not None and cls.current.anchor == anchor:
            cls.current.close()

    def __init__(self, anchor, get, put):
        from direct.showbase import ShowBaseGlobal
        self.base = ShowBaseGlobal.base
        self.anchor = anchor
        self.get = get
        self.put = put
        self.hue, self.saturation, self.value = colorsys.rgb_to_hsv(*[float(c) for c in rgb(get())])
        self.dragging = None
        self._last_put = 0.0
        self._pending = None

        aspect = self.base.aspect2d
        self.root = aspect.attach_new_node('color-picker')
        self.root.set_bin('gui-popup', 10)
        x, _, z = anchor.get_pos(aspect)
        left, right = self.base.a2dLeft + .02, self.base.a2dRight - self.WIDTH - .02
        self.root.set_pos(min(max(x - self.WIDTH / 2, left), right), 0,
                          min(max(z - .05, -1 + self.HEIGHT + .02), .98))
        panel(self.root, (0, self.WIDTH, -self.HEIGHT, 0), color=(.07, .06, .055, .98))
        label(self.root, 'Color', .04, -.06, scale=.035, color=ACCENT)
        button(self.root, 'Done', self.WIDTH - .1, -.05, self.close, width=.14)

        top, square = -.1, self.SQUARE
        self.square = DirectFrame(parent=self.root, frameSize=(.04, .04 + square, top - square, top),
                                  frameColor=(1, 1, 1, 1), relief=DGG.FLAT, state=DGG.NORMAL)
        self.square.bind(DGG.B1PRESS, lambda _event: self._start('square'))
        hue_left = .04 + square + .04
        hues = np.array([colorsys.hsv_to_rgb(h, 1, 1) for h in np.linspace(0, 1, 128)])[:, np.newaxis, :]
        self.hue_bar = DirectFrame(parent=self.root, frameSize=(hue_left, hue_left + .07, top - square, top),
                                   frameColor=(1, 1, 1, 1), relief=DGG.FLAT, state=DGG.NORMAL,
                                   frameTexture=_texture('hues', hues))
        self.hue_bar.bind(DGG.B1PRESS, lambda _event: self._start('hue'))
        self.square_marker = DirectFrame(parent=self.root, frameSize=(-.012, .012, -.012, .012),
                                         frameColor=(1, 1, 1, 1), relief=DGG.RIDGE, borderWidth=(.004, .004),
                                         state=DGG.DISABLED)
        self.hue_marker = DirectFrame(parent=self.root, frameSize=(hue_left - .01, hue_left + .08, -.004, .004),
                                      frameColor=(1, 1, 1, 1), relief=DGG.FLAT, state=DGG.DISABLED)
        self.geometry = (top, square, hue_left)

        y = top - square - .05
        self.preview = DirectFrame(parent=self.root, frameSize=(.04, .2, y - .05, y + .02), relief=DGG.FLAT,
                                   state=DGG.DISABLED)
        self.hex = entry(self.root, .24, .2, get(), self._hex_entered, scale=.03)
        self.hex.set_z(y - .005)

        y -= .1
        y = self._swatches(y, PALETTE, 'Palette')
        self._swatches(y, ColorPicker.recent[:10], 'Recent')
        self._apply_marker()
        self.task = self.base.task_mgr.add(self._drag_task, 'color-picker-drag')

    def _swatches(self, y, colors, title):
        label(self.root, title, .04, y, scale=.026, color=MUTED_TEXT)
        y -= .02
        size = (self.WIDTH - .08) / 10
        for index, color in enumerate(colors):
            row, column = divmod(index, 10)
            left, top = .04 + column * size, y - row * size
            DirectButton(parent=self.root, frameSize=(left + .004, left + size - .004, top - size + .004, top - .004),
                         frameColor=(*[float(c) for c in rgb(color)], 1), relief=DGG.FLAT,
                         command=self._choose, extraArgs=[color], pressEffect=True)
        return y - size * ((len(colors) + 9) // 10) - .04

    def _choose(self, color):
        self.hue, self.saturation, self.value = colorsys.rgb_to_hsv(*[float(c) for c in rgb(color)])
        self._apply_marker()
        self._emit(color, force=True)

    def _hex_entered(self, text):
        text = text.strip()
        if not text.startswith('#'):
            text = '#' + text
        if len(text) == 7:
            try:
                int(text[1:], 16)
                self._choose(text.lower())
                return
            except ValueError:
                pass
        self.hex.enterText(self.get())

    def _start(self, target):
        self.dragging = target
        self._update_from_mouse()

    def _update_from_mouse(self):
        watcher = self.base.mouseWatcherNode
        if not watcher.has_mouse():
            return
        mouse = watcher.get_mouse()
        point = self.root.get_relative_point(self.base.render2d, Point3(mouse.x, 0, mouse.y))
        top, square, hue_left = self.geometry
        vertical = min(max((point.z - (top - square)) / square, 0), 1)
        if self.dragging == 'square':
            self.saturation = min(max((point.x - .04) / square, 0), 1)
            self.value = vertical
        elif self.dragging == 'hue':
            self.hue = vertical
        self._apply_marker()
        self._emit(self._color())

    def _color(self):
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)
        return '#{:02x}{:02x}{:02x}'.format(*(round(c * 255) for c in (r, g, b)))

    def _apply_marker(self):
        top, square, hue_left = self.geometry
        self.square['frameTexture'] = _texture('saturation-value', _hsv_to_rgb_grid(self.hue, 48))
        self.square_marker.set_pos(.04 + self.saturation * square, 0, top - square + self.value * square)
        self.hue_marker.set_z(top - square + self.hue * square)
        r, g, b = colorsys.hsv_to_rgb(self.hue, self.saturation, self.value)
        self.preview['frameColor'] = (r, g, b, 1)
        if id(self.hex) not in _focused:
            self.hex.enterText(self._color())

    def _emit(self, color, force=False):
        """Apply live, at most ~15 times a second while dragging (each change may rebuild a model)."""
        now = time.monotonic()
        if force or now - self._last_put > .07:
            self._last_put = now
            self._pending = None
            self.put(color)
        else:
            self._pending = color

    def _drag_task(self, task):
        if self.dragging is not None:
            if self.base.mouseWatcherNode.is_button_down(MouseButton.one()):
                self._update_from_mouse()
            else:
                self.dragging = None
                self._emit(self._color(), force=True)
        elif self._pending is not None:
            self._emit(self._pending, force=True)
        return task.cont

    def close(self):
        if self._pending is not None:
            self.put(self._pending)
        color = self.get()
        if color in ColorPicker.recent:
            ColorPicker.recent.remove(color)
        ColorPicker.recent.insert(0, color)
        del ColorPicker.recent[20:]
        self.base.task_mgr.remove(self.task)
        if self.hex in _entries:
            _entries.remove(self.hex)
        _focused.discard(id(self.hex))
        self.root.remove_node()
        if ColorPicker.current is self:
            ColorPicker.current = None


class NumberRow(Row):
    """Free number: type it (Enter), or nudge by the spec's step with - / +."""

    def __init__(self, parent, spec, y, get, put, width):
        super().__init__(parent, spec, y, get, put, width)
        self.entry = entry(self.root, self.control_x, width - self.control_x - .17, self._format(get()),
                           self._entered, scale=.03)
        step = spec.step or .1
        button(self.root, '-', width - .12, -.004, lambda: self._nudge(-step), width=.05)
        button(self.root, '+', width - .05, -.004, lambda: self._nudge(step), width=.05)
        self._updating = False

    @staticmethod
    def _format(value):
        return f'{value:.3f}'.rstrip('0').rstrip('.') if isinstance(value, float) else str(value)

    def _entered(self, text):
        try:
            value = float(eval(text, {'__builtins__': {}}, {})) if text.strip() else self.get()  # allows "2*3"
        except Exception:
            value = self.get()
        value = min(max(value, self.spec.min), self.spec.max)  # (infinite limits: no clamping)
        if value != value or abs(value) == UNBOUNDED:  # NaN / inf typed in
            value = self.get()
        if self._updating:
            return
        if abs(value - self.get()) > 1e-9:
            self.put(value)
        self.refresh()

    def _nudge(self, amount):
        self._entered(str(self.get() + amount))

    def refresh(self):
        if id(self.entry) not in _focused:
            self.entry.enterText(self._format(self.get()))


class TextRow(Row):
    def __init__(self, parent, spec, y, get, put, width):
        super().__init__(parent, spec, y, get, put, width)
        self.entry = entry(self.root, self.control_x, width - self.control_x - .03, get(), self._entered, scale=.03)
        self._updating = False

    def _entered(self, text):
        if text != self.get():
            self.put(text)

    def refresh(self):
        if id(self.entry) not in _focused:
            self.entry.enterText(str(self.get()))


ROW_TYPES = {'float': SliderRow, 'int': SliderRow, 'bool': ToggleRow, 'choice': ChoiceRow, 'color': ColorRow,
             'number': NumberRow, 'text': TextRow}


class PropertyList:
    """A scrolling column of rows. `items`: Section, Note, Button, or (spec, get, put)."""

    def __init__(self, parent, frame, items, width):
        left, right, bottom, top = frame
        self.frame_size = frame
        self.width = width
        self.rows = []
        height = sum(self._height(item) for item in items) + .04
        self.frame = DirectScrolledFrame(
            parent=parent, frameSize=frame, canvasSize=(0, width, -height, 0), frameColor=(0, 0, 0, 0),
            scrollBarWidth=.025, verticalScroll_frameColor=(0, 0, 0, .25), verticalScroll_thumb_frameColor=TRACK,
            verticalScroll_incButton_relief=None, verticalScroll_decButton_relief=None,
            horizontalScroll_relief=None, horizontalScroll_frameSize=(0, 0, 0, 0),
            autoHideScrollBars=True, manageScrollBars=True,
        )
        self.content_height = height
        canvas = self.frame.getCanvas()
        y = -.02
        for item in items:
            if isinstance(item, Section):
                y -= SECTION - ROW
                label(canvas, item.title.upper(), .02, y - .012, scale=.03, color=ACCENT)
                y -= ROW
            elif isinstance(item, Note):
                lines = self._note_lines(item.text)
                label(canvas, item.text, .02, y - .01, scale=.026, color=MUTED_TEXT, wrap=(width - .05) / .026)
                y -= ROW * .55 * lines + ROW * .3
            elif isinstance(item, Button):
                buttons = [(item.label, item.command)] + list(item.extra)
                slot = (width - .04) / len(buttons)
                for index, (text, command) in enumerate(buttons):
                    button(canvas, text, .02 + slot * (index + .5), y - ROW / 2 + .008, command, width=slot - .02,
                           scale=.028)
                y -= ROW
            else:
                spec, get, put = item
                self.rows.append(ROW_TYPES[spec.kind](canvas, spec, y - ROW / 2 + .012, get, put, width))
                y -= self._height(item)

    def _note_lines(self, text):
        per_line = max(int((self.width - .05) / .026 * 1.9), 10)
        return sum(max(1, -(-len(part) // per_line)) for part in text.split('\n'))

    def _height(self, item):
        if isinstance(item, Section):
            return SECTION
        if isinstance(item, Note):
            return ROW * .55 * self._note_lines(item.text) + ROW * .3
        return ROW

    def refresh(self):
        for row in self.rows:
            row.refresh()

    def scroll(self, direction):
        bar = self.frame.verticalScroll
        left, right, bottom, top = self.frame_size
        visible = top - bottom
        if self.content_height <= visible:
            return
        step = ROW * 3 / max(self.content_height - visible, ROW)
        bar['value'] = min(max(bar['value'] + direction * step, 0), 1)

    def contains(self, mouse_watcher):
        """Is the pointer over this list (in its parent's aspect2d coordinates)?"""
        if self.frame.is_hidden() or not mouse_watcher.has_mouse():
            return False
        mouse = mouse_watcher.get_mouse()
        point = self.frame.get_relative_point(self.frame.get_top(), Point3(mouse.x, 0, mouse.y))
        left, right, bottom, top = self.frame_size
        return left <= point.x <= right and bottom <= point.z <= top

    def destroy(self):
        for row in self.rows:
            for name in ('entry', 'hex', 'value'):
                widget = getattr(row, name, None)
                if widget in _entries:
                    _entries.remove(widget)
            if isinstance(row, ColorRow):
                ColorPicker.close_for(row.swatch)
        self.frame.destroy()
        self.rows = []


def panel(parent, frame, color=BACKGROUND):
    """Background card that also blocks clicks from reaching the 3D view."""
    return DirectFrame(parent=parent, frameSize=frame, frameColor=color, relief=DGG.FLAT, state=DGG.NORMAL)
