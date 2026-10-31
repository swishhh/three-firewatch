"""Static mesh reader for binary glTF: POSITION, NORMAL and indices of every mesh, placed by the
node hierarchy (matrix or translation / rotation / scale).

Skinned models are the exception: the JS tree instancing merged the raw primitive geometry of the
skinned tree (bind matrices and the armature transform never applied), so those are read as stored.
Animated models (the bird) go through panda3d-gltf instead.
"""
import json
import struct
import zlib

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
    meshes = gltf['meshes']
    if gltf.get('skins'):
        # Skinned models (the JS tree): its instancing used the raw primitives, without node transforms.
        placements = [(index, None) for index in range(len(meshes))]
    else:
        placements = _mesh_placements(gltf)

    parts = []
    for mesh_index, matrix in placements:
        mesh = meshes[mesh_index]
        for primitive in mesh['primitives']:
            attributes = primitive['attributes']
            if 'POSITION' not in attributes:
                continue
            positions = _accessor(gltf, binary, attributes['POSITION']).astype(np.float64)
            if 'NORMAL' in attributes:
                normals = _accessor(gltf, binary, attributes['NORMAL']).astype(np.float64)
            else:
                normals = np.zeros_like(positions)
                normals[:, 1] = 1
            if 'indices' in primitive:
                indices = _accessor(gltf, binary, primitive['indices']).ravel()
            else:
                indices = np.arange(len(positions))
            if primitive.get('mode', 4) != 4:
                continue  # points / lines: nothing to draw as a surface
            if matrix is not None:
                positions = positions @ matrix[:3, :3].T + matrix[:3, 3]
                normals = normals @ np.linalg.inv(matrix[:3, :3])
                normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-12)
                if np.linalg.det(matrix[:3, :3]) < 0:  # mirrored: keep triangles facing out
                    indices = indices.reshape(-1, 3)[:, ::-1].ravel()

            material = primitive.get('material')
            info = materials[material] if material is not None else {}
            uvs = None
            if 'TEXCOORD_0' in attributes:
                uvs = _accessor(gltf, binary, attributes['TEXCOORD_0']).astype(np.float64)
                if accessor_normalized(gltf, attributes['TEXCOORD_0']):
                    uvs = _normalized(gltf, attributes['TEXCOORD_0'], uvs)
                uvs = np.column_stack((uvs[:, 0], 1 - uvs[:, 1])).astype(np.float32)  # glTF v runs down
            parts.append(MeshPart(
                name=mesh.get('name', ''),
                material=info.get('name', ''),
                positions=three_array_to_panda(positions.astype(np.float32)),
                normals=three_array_to_panda(normals.astype(np.float32)),
                indices=indices.astype(np.uint32),
                uvs=uvs,
                texture=_material_texture(gltf, binary, info, path) if uvs is not None else '',
                double_sided=bool(info.get('doubleSided', False)),
            ))
    return parts


def accessor_normalized(gltf, index):
    accessor = gltf['accessors'][index]
    return accessor.get('normalized', False) and accessor['componentType'] != 5126


def _normalized(gltf, index, values):
    accessor = gltf['accessors'][index]
    limits = {5121: 255.0, 5123: 65535.0, 5120: 127.0, 5122: 32767.0}
    return values / limits.get(accessor['componentType'], 1.0)


def _material_texture(gltf, binary, material, path):
    """Image file of a material's baseColorTexture: an external file next to the model, or an embedded
    image extracted once into the model cache."""
    reference = material.get('pbrMetallicRoughness', {}).get('baseColorTexture')
    if reference is None:
        return ''
    try:
        image = gltf['images'][gltf['textures'][reference['index']]['source']]
    except (KeyError, IndexError):
        return ''
    if 'uri' in image and not image['uri'].startswith('data:'):
        external = path.parent / image['uri']
        return str(external) if external.is_file() else ''
    if 'bufferView' not in image:
        return ''
    view = gltf['bufferViews'][image['bufferView']]
    data = binary[view.get('byteOffset', 0):view.get('byteOffset', 0) + view['byteLength']]
    extension = '.jpg' if 'jpeg' in image.get('mimeType', '') else '.png'
    from ..library import CACHE_DIR  # (late: library imports this module)
    target = CACHE_DIR.parent / 'textures' / f'{path.stem}-{zlib.crc32(data):08x}{extension}'
    if not target.is_file():
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        except OSError:
            return ''
    return str(target)


def _local_matrix(node):
    if 'matrix' in node:
        return np.array(node['matrix'], np.float64).reshape(4, 4).T  # glTF stores column-major
    matrix = np.eye(4)
    x, y, z, w = node.get('rotation', (0, 0, 0, 1))
    rotation = np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])
    matrix[:3, :3] = rotation * np.array(node.get('scale', (1, 1, 1)))[np.newaxis, :]
    matrix[:3, 3] = node.get('translation', (0, 0, 0))
    return matrix


def _mesh_placements(gltf):
    """(mesh index, world matrix) for every mesh instance in the default scene's node tree."""
    nodes = gltf.get('nodes', [])
    scenes = gltf.get('scenes')
    if scenes:
        roots = scenes[gltf.get('scene', 0)].get('nodes', [])
    else:
        children = {child for node in nodes for child in node.get('children', [])}
        roots = [index for index in range(len(nodes)) if index not in children]
    placements = []
    stack = [(index, np.eye(4)) for index in roots]
    while stack:
        index, parent = stack.pop()
        node = nodes[index]
        matrix = parent @ _local_matrix(node)
        if 'mesh' in node:
            placements.append((node['mesh'], matrix))
        stack.extend((child, matrix) for child in node.get('children', []))
    if not placements:  # no scene graph: meshes as stored
        placements = [(index, None) for index in range(len(gltf['meshes']))]
    return placements


def _accessor(gltf, binary, index):
    accessor = gltf['accessors'][index]
    view = gltf['bufferViews'][accessor['bufferView']]
    dtype = np.dtype(_COMPONENT_TYPES[accessor['componentType']])
    size = _TYPE_SIZES[accessor['type']]
    offset = view.get('byteOffset', 0) + accessor.get('byteOffset', 0)
    stride = view.get('byteStride', dtype.itemsize * size)
    return np.ndarray((accessor['count'], size), dtype, binary, offset, (stride, dtype.itemsize)).copy()
