"""Port of js/tools/object/manager.js: model loading with caching and per-model material colors.

The JS callbacks recolored materials by name; here that is declared as `colors`. Any material
without an override stays white, as the default MeshPhongMaterial did in the JS app.
"""
import dataclasses
from dataclasses import dataclass, field

from panda3d.core import ColorAttrib, GeomNode, NodePath, PandaNode, RenderState

from . import shading
from .colors import rgba
from .geometry import make_geom
from .loaders.glb import load_glb
from .loaders.obj import load_obj
from .paths import asset

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
    'grass': ModelSpec('obj/grass.obj', colors={'Grass': '#062408'}, distance_render=True),
    'picnic-table': ModelSpec('obj/picnic-table.obj', colors={'table': '#1d0f02'}, distance_render=True),
    'rocks-array': ModelSpec('obj/rocksArray1.obj', colors=ROCK_COLORS, distance_render=True),
    'small-rocks-array': ModelSpec('obj/small-rocksArray.obj', colors=ROCK_COLORS, distance_render=True),
    'tiny-rock-vertical': ModelSpec(
        'obj/tiny-rock-vertical.obj', colors={'Rock.001': 0x383838}, shininess=30, distance_render=True,
    ),
    'welcome-sign': ModelSpec('obj/welcome-sign.obj', colors={'wood': 0x1d0f02, 'text': 0x5e3c1c}, distance_render=True),
    'animated-tree': ModelSpec(
        'obj/lowpoly-tree-bones.glb',
        colors={'Leaves': '#0a1f00'},
        default_color='#241302',
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

_parts = {}
_prototypes = {}


def parts(name):
    """The model's mesh parts with their material colors applied (used for instancing)."""
    if name not in _parts:
        spec = LIBRARY[name]
        path = asset(spec.path)
        loaded = load_glb(path) if path.suffix == '.glb' else load_obj(path)
        _parts[name] = [
            dataclasses.replace(part, color=rgba(spec.colors.get(part.material, spec.default_color)))
            for part in loaded
        ]
    return _parts[name]


def get(name):
    """A new copy of the model (geometry is shared between copies)."""
    if name not in _prototypes:
        _prototypes[name] = _build(name)
    return NodePath(_prototypes[name].node().copy_subgraph())


def _build(name):
    spec = LIBRARY[name]
    model = NodePath(PandaNode(name))
    meshes = {}
    for part in parts(name):
        if part.name not in meshes:
            meshes[part.name] = GeomNode(part.name)
            model.attach_new_node(meshes[part.name])
        state = RenderState.make(ColorAttrib.make_flat(part.color))
        meshes[part.name].add_geom(make_geom(part.positions, part.normals, part.indices), state)

    model.set_scale(spec.scale)
    if spec.shininess:
        shading.set_shininess(model, spec.shininess)
    if spec.distance_render:
        model.set_tag(DISTANCE_RENDER_TAG, '1')
    return model
