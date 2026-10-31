"""The model library: every .obj / .glb under the shared obj/ folder, rescanned on demand (the editor's
Refresh button), with parsed meshes cached on disk so big models load quickly the second time.

Model ids are paths relative to the assets folder ('obj/tent.obj'), as stored in world saves.
"""
import json
import zlib
from pathlib import Path

import numpy as np

from .geometry import MeshPart
from .loaders.glb import load_glb
from .loaders.obj import load_obj
from .paths import ASSETS_DIR, PACKAGE_DIR

MODEL_DIR = ASSETS_DIR / 'obj'
EXTENSIONS = ('.obj', '.glb')
CACHE_DIR = PACKAGE_DIR.parent / '.cache' / 'models'
CACHE_VERSION = 3  # bump when the loaders change what they produce

_parts = {}  # model id -> (stamp, parts)


def scan():
    """Model ids of every supported file under obj/, sorted by name."""
    if not MODEL_DIR.is_dir():
        return []
    paths = [path for path in MODEL_DIR.rglob('*') if path.suffix.lower() in EXTENSIONS and path.is_file()]
    return sorted((path.relative_to(ASSETS_DIR).as_posix() for path in paths), key=str.lower)


IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.tga', '.bmp')


def scan_textures():
    """Image files under obj/ that can be put on objects ('obj/.../texture.png'), sorted."""
    if not MODEL_DIR.is_dir():
        return []
    paths = [path for path in MODEL_DIR.rglob('*') if path.suffix.lower() in IMAGE_EXTENSIONS and path.is_file()]
    return sorted((path.relative_to(ASSETS_DIR).as_posix() for path in paths), key=str.lower)


def display_name(model):
    return model.rsplit('/', 1)[-1].rsplit('.', 1)[0]


def exists(model):
    return (ASSETS_DIR / model).is_file()


def _stamp(path):
    stat = path.stat()
    return f'{stat.st_size}-{stat.st_mtime_ns}-{CACHE_VERSION}'


def _cache_file(model):
    return CACHE_DIR / f'{zlib.crc32(model.encode()):08x}-{display_name(model)}.npz'


def _read_cache(model, stamp):
    try:
        with np.load(_cache_file(model), allow_pickle=False) as data:
            meta = json.loads(str(data['meta']))
            if meta['stamp'] != stamp:
                return None
            parts = [MeshPart(name=part['name'], material=part['material'], positions=data[f'p{index}'],
                              normals=data[f'n{index}'], indices=data[f'i{index}'],
                              uvs=data[f'u{index}'] if f'u{index}' in data else None,
                              texture=part.get('texture', ''), double_sided=part.get('double_sided', False))
                     for index, part in enumerate(meta['parts'])]
            if any(part.texture and not Path(part.texture).is_file() for part in parts):
                return None  # an extracted texture was deleted: parse again
            return parts
    except (OSError, KeyError, ValueError):
        return None


def _write_cache(model, stamp, parts):
    arrays = {}
    for index, part in enumerate(parts):
        arrays[f'p{index}'], arrays[f'n{index}'], arrays[f'i{index}'] = part.positions, part.normals, part.indices
        if part.uvs is not None:
            arrays[f'u{index}'] = part.uvs
    meta = {'stamp': stamp, 'parts': [{'name': part.name, 'material': part.material, 'texture': part.texture,
                                       'double_sided': part.double_sided} for part in parts]}
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        np.savez(_cache_file(model), meta=json.dumps(meta), **arrays)
    except OSError:
        pass


def load_parts(model):
    """Uncolored mesh parts of a model, in Panda3D coordinates. Reloads when the file changes."""
    path = ASSETS_DIR / model
    stamp = _stamp(path)
    cached = _parts.get(model)
    if cached is not None and cached[0] == stamp:
        return cached[1]
    parts = _read_cache(model, stamp)
    if parts is None:
        parts = load_glb(path) if path.suffix.lower() == '.glb' else load_obj(path)
        _write_cache(model, stamp, parts)
    _parts[model] = (stamp, parts)
    return parts


def version(model):
    """Changes whenever the model file changes (after load_parts picks it up)."""
    load_parts(model)
    return _parts[model][0]


def material_colors(model):
    """Diffuse colors from the model's own materials (.mtl Kd, glTF baseColorFactor) as '#rrggbb'."""
    path = ASSETS_DIR / model
    colors = {}
    try:
        if path.suffix.lower() == '.obj':
            library = None
            with open(path) as file:
                for line in file:
                    if line.startswith('mtllib '):
                        library = path.parent / line[7:].strip()
                        break
            if library is not None and library.is_file():
                name = None
                for line in library.read_text(errors='replace').splitlines():
                    if line.startswith('newmtl '):
                        name = line[7:].strip()
                    elif line.strip().startswith('Kd ') and name is not None:
                        rgb = [min(max(float(value), 0), 1) for value in line.split()[1:4]]
                        colors[name] = '#' + ''.join(f'{round(value * 255):02x}' for value in rgb)
        elif path.suffix.lower() == '.glb':
            data = path.read_bytes()
            length = int.from_bytes(data[12:16], 'little')
            gltf = json.loads(data[20:20 + length])
            for material in gltf.get('materials', []):
                factor = material.get('pbrMetallicRoughness', {}).get('baseColorFactor')
                if factor:
                    colors[material.get('name', '')] = '#' + ''.join(
                        f'{round(min(max(value, 0), 1) * 255):02x}' for value in factor[:3])
    except (OSError, ValueError, IndexError):
        pass
    return colors


def materials(model):
    """Material names used by the model's meshes, in first-use order."""
    seen = []
    for part in load_parts(model):
        if part.material not in seen:
            seen.append(part.material)
    return seen


def stats(model):
    parts = load_parts(model)
    triangles = sum(len(part.indices) // 3 for part in parts)
    if parts:
        positions = np.concatenate([part.positions for part in parts])
        low, high = positions.min(axis=0), positions.max(axis=0)
    else:
        low = high = np.zeros(3, dtype=np.float32)
    return {'triangles': triangles, 'parts': len(parts), 'min': low, 'max': high}
