"""Port of js/registry/interactableObjects.js: objects that can be picked with the mouse."""
from panda3d.core import BitMask32

PICK_MASK = BitMask32.bit(1)
TAG = 'interactable'

_objects = {}


def add(node_path):
    node_path.set_tag(TAG, '1')
    node_path.set_collide_mask(PICK_MASK)
    _objects[node_path.get_key()] = node_path


def get(key=None):
    return _objects if key is None else _objects.get(key)


def delete(key):
    _objects.pop(key, None)


def is_interactable(node_path):
    return node_path.get_key() in _objects


def find(node_path):
    """The interactable that owns `node_path` (e.g. the model root of a picked mesh), or None."""
    owner = node_path.find_net_tag(TAG)
    return None if owner.is_empty() else owner
