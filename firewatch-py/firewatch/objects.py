"""Port of js/tools/object/manager.js: model loading with caching and per-model material colors.

The JS callbacks recolored materials by name; that is declared here as `colors` for the models the
JS scene used. Other models from obj/ take their colors from their own .mtl / glTF materials. World
objects can override any material color (world/document.py).
"""
import dataclasses
from dataclasses import dataclass, field

from panda3d.core import (ColorAttrib, CullFaceAttrib, GeomNode, NodePath, PandaNode, RenderState, SamplerState,
                          TextureAttrib, TexturePool)

from . import library
from .colors import rgba
from .geometry import make_geom
from .paths import asset, panda_filename

DISTANCE_RENDER_TAG = 'distance_render'


@dataclass(frozen=True)
class ModelSpec:
    path: str
    colors: dict = field(default_factory=dict)  # material name -> color
    default_color: object = 0xffffff
    shininess: float = 0  # the JS callbacks zeroed MeshPhongMaterial's default of 30 on almost every model
    scale: float = 1.0
    distance_render: bool = False  # hidden when far from the camera, see renderer.py


ROCK_COLORS = {'Rock.001': 0x383838, 'Rock.002': 0x292929}

LIBRARY = {
    'bush-tree-harvest': ModelSpec(
        'obj/bush-tree-harvest.obj',
        colors={'Green': '#234517', 'Brown': '#291602', 'Berry': '#700b0b'},
        scale=.25,
        distance_render=True,
    ),
    'grass': ModelSpec('obj/grass.obj', colors={'Grass': '#1a1d0c'}, distance_render=True),
    'picnic-table': ModelSpec('obj/picnic-table.obj', colors={'table': '#1d0f02'}, distance_render=True),
    'rocks-array': ModelSpec('obj/rocksArray1.obj', colors=ROCK_COLORS, distance_render=True),
    'small-rocks-array': ModelSpec('obj/small-rocksArray.obj', colors=ROCK_COLORS, distance_render=True),
    'tiny-rock-vertical': ModelSpec(
        'obj/tiny-rock-vertical.obj', colors={'Rock.001': 0x383838}, shininess=30, distance_render=True,
    ),
    'welcome-sign': ModelSpec('obj/welcome-sign.obj', colors={'wood': 0x1d0f02, 'text': 0x5e3c1c}, distance_render=True),
    'animated-tree': ModelSpec(
        'obj/lowpoly-tree-bones.glb',
        colors={'Leaves': '#091204'},
        default_color='#140c03',
        distance_render=True,
    ),
    # The JS recolored every mesh named 'Icosphere*'; all eight meshes in rocks.obj are, and all use Rock.001.
    'rocks': ModelSpec('obj/rocks.obj', colors={'Rock.001': '#383838'}),
    'tent': ModelSpec('obj/tent.obj', colors={'brown': '#381801', 'green': '#d2d1d1'}),
    'cloud': ModelSpec('obj/cloud.obj'),
    'camp-fire': ModelSpec(
        'obj/campfire.obj',
        colors={'darkWood': '#1d0f02', 'lightWood': '#532d09', 'rock': '#505050', 'darkDirt': '#090301'},
    ),
}

_SPECS_BY_PATH = {}
for _spec in LIBRARY.values():
    _SPECS_BY_PATH.setdefault(_spec.path, _spec)


def _hex(value):
    return value if isinstance(value, str) else f'#{int(value):06x}'


def model_defaults(model):
    """Defaults for a model id: {'colors', 'default_color', 'shininess', 'scale', 'distance_render',
    'collision'}. Grass-like models and anything smaller than knee height get no collider."""
    from .world.document import no_collision_by_default
    spec = _SPECS_BY_PATH.get(model)
    if spec is not None:
        defaults = {'colors': {name: _hex(color) for name, color in spec.colors.items()},
                    'default_color': _hex(spec.default_color), 'shininess': spec.shininess, 'scale': spec.scale,
                    'distance_render': spec.distance_render}
    else:
        defaults = {'colors': library.material_colors(model), 'default_color': '#ffffff', 'shininess': 0,
                    'scale': 1.0, 'distance_render': True}
    collision = 'box'
    if no_collision_by_default(model):
        collision = 'none'
    else:
        try:
            info = library.stats(model)
            if max(info['max'] - info['min']) * defaults['scale'] < .3:
                collision = 'none'
        except (OSError, ValueError):
            pass
    defaults['collision'] = collision
    return defaults


def resolved_colors(model, overrides=None):
    """material -> '#rrggbb' for every material of the model (defaults, then overrides)."""
    defaults = model_defaults(model)
    colors = {}
    for material in library.materials(model):
        colors[material] = (overrides or {}).get(material, defaults['colors'].get(material, defaults['default_color']))
    return colors


def colored_parts(model, overrides=None, texture=''):
    """The model's mesh parts with material colors applied (used for instancing and baking).
    `texture`: '' keeps the model's own textures, 'none' drops them, a path ('obj/...png') replaces
    them on every part that has texture coordinates."""
    colors = resolved_colors(model, overrides)
    parts = []
    for part in library.load_parts(model):
        image = part.texture
        if texture == 'none' or part.uvs is None:
            image = ''
        elif texture:
            image = str(asset(texture))
        parts.append(dataclasses.replace(part, color=rgba(colors[part.material]), texture=image))
    return parts


def is_textured(model, texture=''):
    try:
        return any(part.texture for part in colored_parts(model, None, texture))
    except (OSError, KeyError):
        return False


_prototypes = {}
_textures = {}


def load_texture(path):
    """An image file as a mipmapped, anisotropically filtered texture (cached)."""
    if path not in _textures:
        texture = TexturePool.load_texture(panda_filename(path))
        if texture is not None:
            texture.set_minfilter(SamplerState.FT_linear_mipmap_linear)
            texture.set_magfilter(SamplerState.FT_linear)
            texture.set_anisotropic_degree(4)
        _textures[path] = texture
    return _textures[path]


def instance(model, overrides=None, texture=''):
    """A new copy of a model (geometry is shared between copies with the same colors and texture)."""
    key = (model, tuple(sorted((overrides or {}).items())), texture, library.version(model))
    if key not in _prototypes:
        if len(_prototypes) > 300:  # color picking creates many variants; keep the cache bounded
            _prototypes.clear()
        _prototypes[key] = _build(model, overrides, texture)
    return NodePath(_prototypes[key].node().copy_subgraph())


def _build(model, overrides, texture=''):
    root = NodePath(PandaNode(library.display_name(model)))
    meshes = {}
    for part in colored_parts(model, overrides, texture):
        if part.name not in meshes:
            meshes[part.name] = GeomNode(part.name or 'mesh')
            root.attach_new_node(meshes[part.name])
        state = RenderState.make(ColorAttrib.make_flat(part.color))
        image = load_texture(part.texture) if part.texture else None
        if image is not None:
            state = state.add_attrib(TextureAttrib.make(image))
        if part.double_sided:
            state = state.add_attrib(CullFaceAttrib.make(CullFaceAttrib.M_cull_none))
        uvs = part.uvs if image is not None else None
        meshes[part.name].add_geom(make_geom(part.positions, part.normals, part.indices, uvs=uvs), state)
    return root


def parts(name):
    """Colored parts of a LIBRARY model by its JS name."""
    return colored_parts(LIBRARY[name].path)


def get(name):
    """A copy of a LIBRARY model by its JS name, with the JS scale and flags applied."""
    spec = LIBRARY[name]
    model = instance(spec.path)
    model.set_scale(spec.scale)
    if spec.shininess:
        model.set_shader_input('shininess', float(spec.shininess))
    if spec.distance_render:
        model.set_tag(DISTANCE_RENDER_TAG, '1')
    return model
