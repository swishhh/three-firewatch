"""Static mesh reader for binary glTF.

The JS tree instancing merged the raw primitive geometry of the skinned tree (bind matrices and the
armature transform never applied), so this reads exactly that: POSITION, NORMAL and indices.
Animated models (the bird) go through panda3d-gltf instead.
"""
import json
import struct

import numpy as np

from ..coords import three_array_to_panda
from ..geometry import MeshPart

_COMPONENT_TYPES = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_TYPE_SIZES = {'SCALAR': 1, 'VEC2': 2, 'VEC3': 3, 'VEC4': 4, 'MAT4': 16}


def load_glb(path):
    data = path.read_bytes()
    magic, _version, _length = struct.unpack_from('<4sII', data, 0)
    if magic != b'glTF':
        raise ValueError(f'{path} is not a binary glTF file')

    json_length, _ = struct.unpack_from('<II', data, 12)
    gltf = json.loads(data[20:20 + json_length])
    binary_length, _ = struct.unpack_from('<II', data, 20 + json_length)
    binary = data[28 + json_length:28 + json_length + binary_length]

    materials = gltf.get('materials', [])
    parts = []
    for mesh in gltf['meshes']:
        for primitive in mesh['primitives']:
            attributes = primitive['attributes']
            positions = _accessor(gltf, binary, attributes['POSITION'])
            normals = _accessor(gltf, binary, attributes['NORMAL'])
            if 'indices' in primitive:
                indices = _accessor(gltf, binary, primitive['indices']).ravel()
            else:
                indices = np.arange(len(positions))

            material = primitive.get('material')
            parts.append(MeshPart(
                name=mesh.get('name', ''),
                material=materials[material].get('name', '') if material is not None else '',
                positions=three_array_to_panda(positions),
                normals=three_array_to_panda(normals),
                indices=indices.astype(np.uint32),
            ))
    return parts


def _accessor(gltf, binary, index):
    accessor = gltf['accessors'][index]
    view = gltf['bufferViews'][accessor['bufferView']]
    dtype = np.dtype(_COMPONENT_TYPES[accessor['componentType']])
    size = _TYPE_SIZES[accessor['type']]
    offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    stride = view.get('byteStride', dtype.itemsize * size)
    return np.ndarray((accessor['count'], size), dtype, binary, offset, (stride, dtype.itemsize)).copy()
