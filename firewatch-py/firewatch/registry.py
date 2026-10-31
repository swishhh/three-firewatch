"""Port of js/registry/registry.js: share objects between components without import coupling."""

_storage = {}


def add(key, value):
    _storage[key] = value


def get(key):
    return _storage.get(key)


def delete(key):
    _storage.pop(key, None)
