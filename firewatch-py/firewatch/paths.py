from pathlib import Path

from panda3d.core import Filename

PACKAGE_DIR = Path(__file__).resolve().parent

# obj/, sound/ and textures/ are shared with the three.js app in the repository root.
ASSETS_DIR = PACKAGE_DIR.parent.parent


def asset(relative):
    return ASSETS_DIR / relative


def shader(name):
    return Filename.from_os_specific(str(PACKAGE_DIR / 'shaders' / name))


def panda_filename(path):
    return Filename.from_os_specific(str(path))
