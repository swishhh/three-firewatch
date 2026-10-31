"""Minimal Wavefront OBJ reader matching what three.js' OBJLoader produced for the JS app.

The JS object manager never applied the .mtl files (MTLLoader was registered but unused), so
materials only contribute their names; colors come from the overrides in objects.py.
"""
import numpy as np

from ..coords import three_array_to_panda
from ..geometry import MeshPart


def _resolve(index, count):
    index = int(index)
    return index - 1 if index > 0 else count + index


def load_obj(path):
    positions, normals = [], []
    corners = {}  # (object name, material name) -> list of (position index, normal index)
    object_name, material = '', ''

    with open(path) as file:
        for line in file:
            if line.startswith('v '):
                positions.append(line.split()[1:4])
            elif line.startswith('vn '):
                normals.append(line.split()[1:4])
            elif line.startswith('f '):
                face = []
                for token in line.split()[1:]:
                    parts = token.split('/')
                    normal = _resolve(parts[2], len(normals)) if len(parts) > 2 and parts[2] else -1
                    face.append((_resolve(parts[0], len(positions)), normal))
                group = corners.setdefault((object_name, material), [])
                for i in range(1, len(face) - 1):  # fan triangulation, like OBJLoader
                    group += (face[0], face[i], face[i + 1])
            elif line.startswith(('o ', 'g ')):
                object_name = line[2:].strip()
            elif line.startswith('usemtl '):
                material = line[7:].strip()

    positions = np.array(positions, dtype=np.float32)
    normals = np.array(normals, dtype=np.float32).reshape(-1, 3)

    parts = []
    for (name, material_name), group in corners.items():
        indices = np.array(group, dtype=np.int64)
        part_positions = positions[indices[:, 0]]
        part_normals = _face_normals(part_positions)
        has_normal = indices[:, 1] >= 0
        part_normals[has_normal] = normals[indices[has_normal, 1]]

        parts.append(MeshPart(
            name=name,
            material=material_name,
            positions=three_array_to_panda(part_positions),
            normals=three_array_to_panda(part_normals),
            indices=np.arange(len(indices), dtype=np.uint32),
        ))
    return parts


def _face_normals(triangle_positions):
    """Flat normals for faces without `vn`, as OBJLoader's computeVertexNormals() gives them."""
    a, b, c = triangle_positions[0::3], triangle_positions[1::3], triangle_positions[2::3]
    normal = np.cross(b - a, c - a)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    return np.repeat(normal, 3, axis=0).astype(np.float32)
