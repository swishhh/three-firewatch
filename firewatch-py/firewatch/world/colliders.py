"""Standalone colliders: invisible boxes and cylinders placed on their own (walls, fences, slopes the
player shouldn't climb, a better fit than an object's own collider).

Records in world.json 'colliders': {'id', 'name', 'shape': 'box' | 'cylinder', 'pos': [x, y, bottom z],
'size': [width, depth, height] (a cylinder uses width as its diameter), 'heading'}. The game only
uses them for physics; the editor draws them as see-through blocks you can click and drag.
"""
import math

import numpy as np
from panda3d.core import GeomNode, LineSegs, TransparencyAttrib

from .. import shading
from ..geometry import make_geom
from .entities import EDITOR_PICK_MASK

TAG = 'world_collider'
SHAPES = ('box', 'cylinder')
COLOR = (1, .55, .15)


def new_collider(shape='box', position=(0, 0, 0)):
    size = [2.0, 2.0, 2.0] if shape == 'box' else [1.0, 1.0, 2.0]
    return {'id': '', 'name': f'{shape} collider', 'shape': shape, 'pos': [float(v) for v in position],
            'size': size, 'heading': 0.0}


def physics_shape(record):
    """The record as a collision.py shape tuple."""
    x, y, z = record['pos']
    width, depth, height = (max(float(v), .01) for v in record['size'])
    if record['shape'] == 'cylinder':
        return ('cylinder', x, y, width / 2, z, z + height)
    return ('box', x, y, width / 2, depth / 2, math.radians(record['heading']), z, z + height)


def _unit_box():
    corners = np.array([(x, y, z) for z in (0, 1) for y in (-.5, .5) for x in (-.5, .5)], np.float32)
    faces = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))
    positions, indices = [], []
    for face in faces:
        start = len(positions)
        positions.extend(corners[list(face)])
        indices.extend((start, start + 1, start + 2, start, start + 2, start + 3))
    positions = np.array(positions, np.float32)
    return positions, np.array(indices, np.uint32)


def _unit_cylinder(segments=24):
    angles = np.linspace(0, 2 * np.pi, segments, endpoint=False)
    ring = np.stack((np.cos(angles) * .5, np.sin(angles) * .5), axis=1)
    positions = np.concatenate((np.column_stack((ring, np.zeros(segments))), np.column_stack((ring, np.ones(segments))),
                                [[0, 0, 0], [0, 0, 1]])).astype(np.float32)
    indices = []
    for i in range(segments):
        j = (i + 1) % segments
        indices += [i, j, segments + j, i, segments + j, segments + i]
        indices += [2 * segments, j, i, 2 * segments + 1, segments + i, segments + j]
    return positions, np.array(indices, np.uint32)


_meshes = {}


def _mesh(shape):
    if shape not in _meshes:
        positions, indices = _unit_box() if shape == 'box' else _unit_cylinder()
        normals = np.tile(np.array([0, 0, 1], np.float32), (len(positions), 1))
        _meshes[shape] = (make_geom(positions, normals, indices), positions)
    return _meshes[shape]


class ColliderEntity:
    """Editor view of one standalone collider."""

    def __init__(self, world, data):
        self.world = world
        self.data = data
        self.root = world.root.attach_new_node(f'collider-{data["id"]}')
        self.root.set_tag(TAG, data['id'])
        self.body = None
        self.build()

    @property
    def id(self):
        return self.data['id']

    def build(self):
        if self.body is not None:
            self.body.remove_node()
        geom, positions = _mesh(self.data['shape'])
        self.body = self.root.attach_new_node('body')
        solid = GeomNode('solid')
        solid.add_geom(geom)
        solid_path = self.body.attach_new_node(solid)
        solid_path.set_color(*COLOR, .18)
        solid_path.set_transparency(TransparencyAttrib.M_alpha)
        solid_path.set_two_sided(True)
        solid_path.set_depth_write(False)
        solid_path.set_bin('transparent', 20)
        solid_path.set_shader_input('unlit', 1.0)
        lines = LineSegs('edges')
        lines.set_color(*COLOR, .9)
        lines.set_thickness(1.5)
        if self.data['shape'] == 'box':
            for a, b in ((0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7)):
                corner = [(x, y, z) for z in (0, 1) for y in (-.5, .5) for x in (-.5, .5)]
                lines.move_to(*corner[a])
                lines.draw_to(*corner[b])
        else:
            for z in (0, 1):
                for index in range(25):
                    angle = index / 24 * 2 * math.pi
                    point = (math.cos(angle) * .5, math.sin(angle) * .5, z)
                    lines.draw_to(*point) if index else lines.move_to(*point)
            for index in range(4):
                angle = index / 4 * 2 * math.pi
                lines.move_to(math.cos(angle) * .5, math.sin(angle) * .5, 0)
                lines.draw_to(math.cos(angle) * .5, math.sin(angle) * .5, 1)
        edges = self.body.attach_new_node(lines.create())
        edges.set_shader_off(10)
        edges.set_transparency(TransparencyAttrib.M_alpha)
        shading.set_cast_shadow(self.root, False)
        shading.set_in_depth_prepass(self.root, False)
        self.root.set_collide_mask(EDITOR_PICK_MASK)
        self.apply_transform()

    def apply_transform(self):
        data = self.data
        width, depth, height = (max(float(v), .01) for v in data['size'])
        if data['shape'] == 'cylinder':
            depth = width
        self.root.set_pos(*data['pos'])
        self.root.set_h(data['heading'])
        self.body.set_scale(width, depth, height)

    def apply_flags(self):
        pass

    def destroy(self):
        self.root.remove_node()
