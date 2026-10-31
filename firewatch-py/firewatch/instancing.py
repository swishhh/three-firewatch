"""Port of js/component/scene/InstancedManager.js.

Every [x, y, z, scale] entry of the mapping is baked into a single vertex-colored GeomNode: one draw
call, which is what THREE.InstancedMesh bought the JS version. Entries use three.js coordinates.
Each vertex also gets a wind sway weight (0 at the base, growing towards the top) and a per-instance
phase, read by shaders/common.glsl.
"""
import math

import numpy as np
from panda3d.core import GeomNode

from .coords import three_to_panda
from .geometry import make_geom


class InstancedManager:
    def __init__(self, scene, parts, mapping):
        self.scene = scene
        self.parts = parts
        self.mapping = list(mapping)
        self.relate = None
        self.instance = None

    def set_relate_callback(self, callback):
        """`callback(x, y, z, scale)` returns the adjusted y, e.g. Terrain.relate_y."""
        self.relate = callback

    def add_item(self, x, y, z, scale):
        self.mapping.append([x, y, z, scale])

    def draw(self):
        node = self._create()
        if self.instance is not None:
            self.instance.remove_node()
        self.instance = self.scene.attach_new_node(node)
        return self.instance

    def _create(self):
        positions, normals, colors, sway, indices = [], [], [], [], []
        offset = 0
        bottom = min(part.positions[:, 2].min() for part in self.parts)
        height = max(max(part.positions[:, 2].max() for part in self.parts) - bottom, 1e-6)
        for entry in self.mapping:
            if len(entry) < 4:
                # The JS build turned a missing scale into NaN, so that instance never rendered.
                continue
            x, y, z, scale = entry
            if self.relate:
                y = self.relate(x, y, z, scale)
            translation = np.array(three_to_panda(x, y, z), dtype=np.float32)
            phase = (math.sin(x * 12.9898 + z * 78.233) * 43758.5453) % 1 * 2 * math.pi

            for part in self.parts:
                count = len(part.positions)
                positions.append(part.positions * scale + translation)
                normals.append(part.normals)
                colors.append(np.broadcast_to(np.array(part.color, dtype=np.float32), (count, 4)))
                weight = ((part.positions[:, 2] - bottom) / height) ** 2 * scale
                sway.append(np.stack((weight, np.full(count, phase)), axis=1))
                indices.append(part.indices + offset)
                offset += count

        node = GeomNode('instanced')
        if positions:
            node.add_geom(make_geom(
                np.concatenate(positions), np.concatenate(normals), np.concatenate(indices), np.concatenate(colors),
                np.concatenate(sway),
            ))
        return node
