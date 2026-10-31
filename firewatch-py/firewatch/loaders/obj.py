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


def _material_maps(path, library):
    """material name -> absolute path of its map_Kd image (when the file exists)."""
    maps = {}
    file = path.parent / library
    if not file.is_file():
        return maps
    name = None
    for line in file.read_text(errors='replace').splitlines():
        line = line.strip()
        if line.startswith('newmtl '):
            name = line[7:].strip()
        elif line.startswith('map_Kd ') and name is not None:
            image = path.parent / line.split()[-1]
            if image.is_file():
                maps[name] = str(image)
    return maps


def load_obj(path):
    positions, normals, uvs = [], [], []
    corners = {}  # (object name, material name) -> list of (position index, normal index, uv index)
    object_name, material = '', ''
    maps = {}

    with open(path) as file:
        for line in file:
            if line.startswith('v '):
                positions.append(line.split()[1:4])
            elif line.startswith('vn '):
                normals.append(line.split()[1:4])
            elif line.startswith('vt '):
                uvs.append((line.split() + ['0', '0'])[1:3])
            elif line.startswith('mtllib '):
                maps.update(_material_maps(path, line[7:].strip()))
            elif line.startswith('f '):
                face = []
                for token in line.split()[1:]:
                    parts = token.split('/')
                    normal = _resolve(parts[2], len(normals)) if len(parts) > 2 and parts[2] else -1
                    uv = _resolve(parts[1], len(uvs)) if len(parts) > 1 and parts[1] else -1
                    face.append((_resolve(parts[0], len(positions)), normal, uv))
                group = corners.setdefault((object_name, material), [])
                for i in range(1, len(face) - 1):  # fan triangulation, like OBJLoader
                    group += (face[0], face[i], face[i + 1])
            elif line.startswith(('o ', 'g ')):
                object_name = line[2:].strip()
            elif line.startswith('usemtl '):
                material = line[7:].strip()

    positions = np.array(positions, dtype=np.float32)
    normals = np.array(normals, dtype=np.float32).reshape(-1, 3)
    uvs = np.array(uvs, dtype=np.float32).reshape(-1, 2)

    parts = []
    for (name, material_name), group in corners.items():
        indices = np.array(group, dtype=np.int64)
        part_positions = positions[indices[:, 0]]
        part_normals = _face_normals(part_positions)
        has_normal = indices[:, 1] >= 0
        part_normals[has_normal] = normals[indices[has_normal, 1]]
        part_uvs = None
        if len(uvs) and (indices[:, 2] >= 0).any():
            part_uvs = np.zeros((len(indices), 2), np.float32)
            has_uv = indices[:, 2] >= 0
            part_uvs[has_uv] = uvs[indices[has_uv, 2]]

        parts.append(MeshPart(
            name=name,
            material=material_name,
            positions=three_array_to_panda(part_positions),
            normals=three_array_to_panda(part_normals),
            indices=np.arange(len(indices), dtype=np.uint32),
            uvs=part_uvs,
            texture=maps.get(material_name, '') if part_uvs is not None else '',
        ))
    return parts


def _face_normals(triangle_positions):
    """Flat normals for faces without `vn`, as OBJLoader's computeVertexNormals() gives them."""
    a, b, c = triangle_positions[0::3], triangle_positions[1::3], triangle_positions[2::3]
    normal = np.cross(b - a, c - a)
    normal /= np.maximum(np.linalg.norm(normal, axis=1, keepdims=True), 1e-12)
    return np.repeat(normal, 3, axis=0).astype(np.float32)
