"""Editor drawings in the 3D view: brush ring, collider wireframes, player start marker and the
placement preview. Unlit, drawn on top, and kept out of shadows and the depth prepass."""
import math

from panda3d.core import LineSegs, TransparencyAttrib

from .. import shading


def _overlay_root(parent, name, on_top=True):
    node = parent.attach_new_node(name)
    node.set_shader_off(10)
    node.set_light_off(10)
    node.set_fog_off(10)
    node.set_texture_off(10)
    if on_top:
        node.set_bin('fixed', 50)
        node.set_depth_test(False)
        node.set_depth_write(False)
    shading.set_cast_shadow(node, False)
    shading.set_in_depth_prepass(node, False)
    return node


class BrushRing:
    def __init__(self, app, terrain_getter):
        self.root = _overlay_root(app.render, 'brush-ring')
        self.terrain = terrain_getter
        self.node = None
        self.key = None

    def show(self, x, y, radius, color=(1, .75, .3, 1), inner=None):
        key = (round(x, 3), round(y, 3), round(radius, 3), color, inner)
        if key == self.key and self.node is not None:
            self.root.show()
            return
        self.key = key
        if self.node is not None:
            self.node.remove_node()
        terrain = self.terrain()
        lines = LineSegs('brush')
        lines.set_thickness(2)
        for ring_radius, ring_color in ((radius, color), (inner, (1, 1, 1, .5)) if inner else (None, None)):
            if not ring_radius:
                continue
            lines.set_color(*ring_color)
            for index in range(65):
                angle = index / 64 * 2 * math.pi
                px, py = x + math.cos(angle) * ring_radius, y + math.sin(angle) * ring_radius
                point = (px, py, terrain.height_at(px, py) + .05)
                lines.draw_to(*point) if index else lines.move_to(*point)
        lines.set_color(*color)
        z = terrain.height_at(x, y)
        lines.move_to(x, y, z)
        lines.draw_to(x, y, z + .6)
        self.node = self.root.attach_new_node(lines.create())
        self.root.show()

    def hide(self):
        self.root.hide()


class ColliderView:
    """Wireframes of every collider (C in the editor)."""

    def __init__(self, app):
        self.root = _overlay_root(app.render, 'collider-view', on_top=False)
        self.root.set_transparency(TransparencyAttrib.M_alpha)
        self.root.hide()

    @property
    def visible(self):
        return not self.root.is_hidden()

    def build(self, shapes, selected=None):
        self.root.get_children().detach()
        lines = LineSegs('colliders')
        lines.set_thickness(1.5)
        for shape in shapes:
            lines.set_color(.3, 1, .4, .9)
            if shape[0] == 'cylinder':
                _, x, y, radius, z0, z1 = shape
                for z in (z0, z1):
                    for index in range(25):
                        angle = index / 24 * 2 * math.pi
                        point = (x + math.cos(angle) * radius, y + math.sin(angle) * radius, z)
                        lines.draw_to(*point) if index else lines.move_to(*point)
                for index in range(4):
                    angle = index / 4 * 2 * math.pi
                    px, py = x + math.cos(angle) * radius, y + math.sin(angle) * radius
                    lines.move_to(px, py, z0)
                    lines.draw_to(px, py, z1)
            else:
                _, x, y, hx, hy, heading, z0, z1 = shape
                cos, sin = math.cos(heading), math.sin(heading)
                corners = [(x + cx * cos - cy * sin, y + cx * sin + cy * cos)
                           for cx, cy in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy))]
                for z in (z0, z1):
                    lines.move_to(*corners[-1], z)
                    for corner in corners:
                        lines.draw_to(*corner, z)
                for corner in corners:
                    lines.move_to(*corner, z0)
                    lines.draw_to(*corner, z1)
        self.root.attach_new_node(lines.create())

    def toggle(self):
        if self.visible:
            self.root.hide()
        else:
            self.root.show()
        return self.visible


class PlayerMarker:
    def __init__(self, app):
        self.root = _overlay_root(app.render, 'player-start', on_top=False)

    def place(self, x, y, z, heading, eye):
        self.root.get_children().detach()
        lines = LineSegs('player')
        lines.set_thickness(3)
        lines.set_color(.3, .8, 1, 1)
        for index in range(17):
            angle = index / 16 * 2 * math.pi
            point = (x + math.cos(angle) * .3, y + math.sin(angle) * .3, z + .02)
            lines.draw_to(*point) if index else lines.move_to(*point)
        lines.move_to(x, y, z)
        lines.draw_to(x, y, z + eye)
        angle = math.radians(heading + 90)
        tip = (x + math.cos(angle) * .9, y + math.sin(angle) * .9, z + eye)
        lines.move_to(x, y, z + eye)
        lines.draw_to(*tip)
        for side in (-.35, .35):
            lines.move_to(*tip)
            lines.draw_to(x + math.cos(angle + side) * .6, y + math.sin(angle + side) * .6, z + eye)
        self.root.attach_new_node(lines.create())


def ghost(node):
    """Turn a model copy into a see-through placement preview."""
    node.set_transparency(TransparencyAttrib.M_alpha)
    node.set_alpha_scale(.55)
    shading.set_cast_shadow(node, False)
    shading.set_in_depth_prepass(node, False)
    node.set_bin('transparent', 5)
    return node
