from dataclasses import dataclass

import numpy as np
from panda3d.core import (Geom, GeomTriangles, GeomVertexArrayFormat, GeomVertexData, GeomVertexFormat,
                          InternalName)


@dataclass
class MeshPart:
    """One mesh/material pair of a model, already in Panda3D coordinates."""
    name: str
    material: str
    positions: np.ndarray  # (n, 3) float32
    normals: np.ndarray    # (n, 3) float32
    indices: np.ndarray    # (m,) uint32, triangle list
    color: tuple = (1.0, 1.0, 1.0, 1.0)
    uvs: np.ndarray = None  # (n, 2) float32 texture coordinates (Panda: v up), or None
    texture: str = ''       # image file of the material's base color texture (absolute path), or ''
    double_sided: bool = False


_formats = {}


def make_format(*columns):
    """Single-array float32 vertex format from (name, components, contents) columns."""
    if columns not in _formats:
        array = GeomVertexArrayFormat()
        for name, components, contents in columns:
            array.add_column(InternalName.make(name), components, Geom.NT_float32, contents)
        _formats[columns] = GeomVertexFormat.register_format(array)
    return _formats[columns]


VERTEX = ('vertex', 3, Geom.C_point)
NORMAL = ('normal', 3, Geom.C_normal)
COLOR = ('color', 4, Geom.C_color)
SWAY = ('sway', 2, Geom.C_other)  # (weight, phase) for the wind sway in shaders/common.glsl
TEXCOORD = ('texcoord', 2, Geom.C_texcoord)  # p3d_MultiTexCoord0


def make_geom(positions, normals, indices, colors=None, sway=None, uvs=None):
    columns, arrays = [VERTEX, NORMAL], [positions, normals]
    if uvs is not None:
        columns.append(TEXCOORD)
        arrays.append(uvs)
    if colors is not None:
        columns.append(COLOR)
        arrays.append(colors)
    if sway is not None:
        columns.append(SWAY)
        arrays.append(sway)
    return make_indexed_geom(make_format(*columns), np.hstack(arrays), indices)


def make_indexed_geom(vertex_format, vertices, indices):
    vertices = np.ascontiguousarray(vertices, dtype=np.float32)
    data = GeomVertexData('mesh', vertex_format, Geom.UH_static)
    data.unclean_set_num_rows(len(vertices))
    memoryview(data.modify_array(0)).cast('B')[:] = vertices.tobytes()

    triangles = GeomTriangles(Geom.UH_static)
    triangles.set_index_type(Geom.NT_uint32)
    index_data = triangles.modify_vertices()
    index_data.unclean_set_num_rows(len(indices))
    memoryview(index_data).cast('B')[:] = np.ascontiguousarray(indices, dtype=np.uint32).tobytes()

    geom = Geom(data)
    geom.add_primitive(triangles)
    return geom


def sphere(radius, width_segments, height_segments):
    """Same vertex layout as THREE.SphereGeometry (Z-up). Returns positions, normals, indices."""
    phi = np.linspace(0, 2 * np.pi, width_segments + 1)
    theta = np.linspace(0, np.pi, height_segments + 1)
    t, p = np.meshgrid(theta, phi, indexing='ij')
    normals = np.stack((-np.cos(p) * np.sin(t), -np.sin(p) * np.sin(t), np.cos(t)), axis=-1).reshape(-1, 3)

    indices = []
    row = width_segments + 1
    for iy in range(height_segments):
        for ix in range(width_segments):
            a, b = iy * row + ix + 1, iy * row + ix
            c, d = (iy + 1) * row + ix, (iy + 1) * row + ix + 1
            if iy != 0:
                indices += [a, b, d]
            if iy != height_segments - 1:
                indices += [b, c, d]

    normals = normals.astype(np.float32)
    return normals * radius, normals, np.array(indices, dtype=np.uint32)
