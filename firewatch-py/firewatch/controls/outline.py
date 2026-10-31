"""Port of js/component/action/object/outline.js (OutlinePass).

Outlined objects are instanced into a separate scene that a second camera, following the main one,
renders as a white silhouette mask into an offscreen buffer. A fullscreen card then draws the edge
of that mask over the frame (shaders/outline.frag). Multisampling stands in for the FXAA pass.
"""
from direct.showbase.DirectObject import DirectObject
from panda3d.core import (Camera, CardMaker, FrameBufferProperties, GraphicsOutput, GraphicsPipe, NodePath,
                          Texture, TransparencyAttrib, WindowProperties)

from .. import settings, shading
from ..colors import rgba
from ..update import add_update_callback

_outline = None


class Outline(DirectObject):
    def __init__(self, app, color=None, thickness=None):
        """`color` / `thickness` fix this outline's look; by default it follows gfx.outline_*."""
        super().__init__()
        self.app = app
        self.style = (color, thickness)
        self.objects = {}  # key -> (object, holder in the mask scene)

        self.mask = Texture('outline-mask')
        properties = FrameBufferProperties()
        properties.set_rgba_bits(8, 8, 8, 8)
        self.buffer = app.graphics_engine.make_output(
            app.pipe, 'outline-mask', -10, properties,
            WindowProperties.size(app.win.get_x_size(), app.win.get_y_size()),
            GraphicsPipe.BF_refuse_window | GraphicsPipe.BF_resizeable,
            app.win.get_gsg(), app.win,
        )
        self.buffer.add_render_texture(self.mask, GraphicsOutput.RTM_bind_or_copy)
        self.buffer.set_clear_color((0, 0, 0, 0))
        self.buffer.set_active(False)

        self.scene = NodePath('outline-mask-scene')
        self.scene.set_light_off(1)
        self.scene.set_fog_off(1)
        self.scene.set_shader_off(1)
        self.scene.set_texture_off(1)
        self.scene.set_color((1, 1, 1, 1), 1)
        self.scene.set_color_scale((1, 1, 1, 1), 1)
        self.scene.set_transparency(TransparencyAttrib.M_none, 1)
        self.scene.set_depth_test(False, 1)
        self.scene.set_depth_write(False, 1)

        camera = Camera('outline-mask-camera', app.camLens)
        camera.set_camera_mask(shading.MAIN_CAMERA_MASK)
        self.camera = self.scene.attach_new_node(camera)
        self.buffer.make_display_region().set_camera(self.camera)

        card = CardMaker('outline')
        card.set_frame_fullscreen_quad()
        self.card = app.render2d.attach_new_node(card.generate())
        self.card.set_shader(shading.load_shader('quad', 'outline'))
        self.card.set_shader_input('mask', self.mask)
        settings.subscribe(lambda _keys: self.apply_settings(), 'gfx.outline')
        self.apply_settings()
        self.card.set_transparency(TransparencyAttrib.M_alpha)
        self.card.hide()

        self.accept('window-event', self._resize)
        add_update_callback(self.update)

    def apply_settings(self):
        color, thickness = self.style
        self.card.set_shader_input('edge_color', color if color is not None else rgba(settings.get('gfx.outline_color')))
        self.card.set_shader_input('radius', thickness if thickness is not None else settings.get('gfx.outline_thickness'))

    def _resize(self, window):
        size = window.get_x_size(), window.get_y_size()
        if window == self.app.win and size != (self.buffer.get_x_size(), self.buffer.get_y_size()):
            self.buffer.set_size(*size)

    def set_outlined(self, node_path, outlined):
        key = node_path.get_key()
        if outlined and key not in self.objects:
            holder = self.scene.attach_new_node('holder')
            node_path.instance_to(holder)
            self.objects[key] = (node_path, holder)
        elif not outlined and key in self.objects:
            self.objects.pop(key)[1].remove_node()

        active = bool(self.objects)
        self.buffer.set_active(active)
        self.card.show() if active else self.card.hide()

    def clear(self):
        for key in list(self.objects):
            self.set_outlined(self.objects[key][0], False)

    def update(self, _delta):
        if not self.objects:
            return
        self.camera.set_transform(self.app.cam.get_transform(self.app.render))
        for node_path, holder in self.objects.values():
            holder.set_transform(node_path.get_parent().get_net_transform())


def outline(node_path):
    _outline.set_outlined(node_path, True)


def remove_outline(node_path=None):
    if node_path is None:
        _outline.clear()
    else:
        _outline.set_outlined(node_path, False)


def draw(app):
    global _outline
    _outline = Outline(app)
