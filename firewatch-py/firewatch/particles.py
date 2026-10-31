"""GPU particles: camera-facing quads animated entirely in shaders/particles.vert.

(Panda never enables GL_PROGRAM_POINT_SIZE, so point sprites can't size themselves per particle.)
"""
import numpy as np
from panda3d.core import ColorBlendAttrib, Geom, GeomNode, OmniBoundingVolume, TransparencyAttrib

from . import shading
from .geometry import make_format, make_indexed_geom

FORMAT = make_format(('vertex', 4, Geom.C_point), ('corner', 2, Geom.C_other))
CORNERS = np.array([(-1, -1), (1, -1), (1, 1), (-1, 1)], dtype=np.float32)

SNOW = 0
FIREFLIES = 1
EMBERS = 2


class ParticleSystem:
    def __init__(self, parent, name, mode, additive=False, seed=0):
        self.random = np.random.default_rng(seed)
        self.node_path = parent.attach_new_node(GeomNode(name))
        # Particles move in the vertex shader, so their real extent is unknown to culling.
        self.node_path.node().set_bounds(OmniBoundingVolume())
        self.node_path.node().set_final(True)
        self.node_path.set_shader(shading.load_shader('particles'))
        self.node_path.set_shader_input('particle_mode', mode)
        self.node_path.set_depth_write(False)
        self.node_path.set_bin('transparent', 10)
        if additive:
            self.node_path.set_attrib(ColorBlendAttrib.make(ColorBlendAttrib.M_add, ColorBlendAttrib.O_one,
                                                            ColorBlendAttrib.O_one))
        else:
            self.node_path.set_transparency(TransparencyAttrib.M_alpha)
        shading.set_cast_shadow(self.node_path, False)
        shading.set_in_depth_prepass(self.node_path, False)
        self.count = None

    def set_count(self, count):
        if count == self.count:
            return
        self.count = count
        node = self.node_path.node()
        node.remove_all_geoms()
        if count <= 0:
            return
        seeds = np.repeat(self.random.random((count, 4), dtype=np.float32), 4, axis=0)
        corners = np.tile(CORNERS, (count, 1))
        quads = np.arange(count, dtype=np.uint32)[:, np.newaxis] * 4
        indices = (quads + np.array([0, 1, 2, 0, 2, 3], dtype=np.uint32)).ravel()
        node.add_geom(make_indexed_geom(FORMAT, np.hstack((seeds, corners)), indices))

    def set_inputs(self, **inputs):
        for name, value in inputs.items():
            self.node_path.set_shader_input(name, value)
