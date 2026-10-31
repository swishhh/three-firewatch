"""Port of js/component/stats.js: frames-per-second counter, plus CPU and GPU usage graphs."""
from collections import deque

from direct.gui.OnscreenText import OnscreenText
from panda3d.core import CardMaker, LineSegs, TextNode, TransparencyAttrib

from .. import settings
from ..usage import CpuUsage, GpuUsage

INTERVAL = .25  # seconds between samples
HISTORY = 60    # samples per graph (15 s)
WIDTH = .82
HEIGHT = .14
MARGIN = .05

CPU_COLOR = (.35, .8, 1, 1)
GPU_COLOR = (.55, 1, .45, 1)


class UsageGraph:
    def __init__(self, parent, x, color):
        self.color = color
        self.samples = deque(maxlen=HISTORY)
        self.root = parent.attach_new_node('usage-graph')
        self.root.set_pos(x, 0, -MARGIN - .04 - HEIGHT)

        background = CardMaker('background')
        background.set_frame(0, WIDTH, 0, HEIGHT)
        card = self.root.attach_new_node(background.generate())
        card.set_color(0, 0, 0, .55)
        card.set_transparency(TransparencyAttrib.M_alpha)

        self.label = OnscreenText(
            parent=self.root, pos=(0, HEIGHT + .015), scale=.036, align=TextNode.A_left,
            fg=color, shadow=(0, 0, 0, .8), mayChange=True,
        )
        self.line = self.root.attach_new_node('line')

    def push(self, percent, text):
        self.label.setText(text)
        if percent is None:
            return
        self.samples.append(min(max(percent, 0), 100))

        segments = LineSegs('line')
        segments.set_color(self.color)
        segments.set_thickness(1.5)
        start = HISTORY - len(self.samples)
        for i, value in enumerate(self.samples):
            point = (WIDTH * (start + i) / (HISTORY - 1), 0, HEIGHT * value / 100)
            segments.draw_to(point) if i else segments.move_to(point)

        self.line.remove_node()
        self.line = self.root.attach_new_node(segments.create())


def draw(app):
    cpu, gpu = CpuUsage(), GpuUsage()
    cpu_graph = UsageGraph(app.a2dTopLeft, MARGIN, CPU_COLOR)
    gpu_graph = UsageGraph(app.a2dTopLeft, MARGIN * 2 + WIDTH, GPU_COLOR)

    def show(_keys=None):
        visible = settings.get('gfx.overlay')
        app.set_frame_rate_meter(visible)
        for graph in (cpu_graph, gpu_graph):
            graph.root.show() if visible else graph.root.hide()

    settings.subscribe(show, 'gfx.overlay')
    show()

    def sample(task):
        system, process = cpu.sample()
        cap = f'{app.frame_limit} fps' if app.frame_limit else 'off'
        cpu_graph.push(system, f'CPU {system:3.0f}%   app {process:.0f}% of a core   cap: {cap} (F)')
        busy = gpu.sample()
        gpu_graph.push(busy, 'GPU n/a' if busy is None else f'GPU {busy:3.0f}%')
        return task.again

    app.task_mgr.do_method_later(INTERVAL, sample, 'usage-graphs')
