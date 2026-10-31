"""Runtime side of world objects: a node per record in world.json's 'objects', rebuilt or updated
when the editor changes the record.

Node layout: root (transform, 'world_object' tag, visibility) -> content (the model; hidden by the
draw-distance culling in renderer.py).
"""
import json
import math

import numpy as np
from panda3d.core import BitMask32, Point3

from .. import interactables, library, objects, shading
from ..components.bird import Bird
from ..components.campfire import CampfireRig
from ..objects import DISTANCE_RENDER_TAG
from .items import PlacedItem
from .lights import PlacedLight

TAG = 'world_object'
MESH_CELL = .3  # meters per collision cell of 'mesh' colliders
MESH_GAP = 1.9  # vertical room (meters) that splits a cell's collider so the player fits in between


def _sample_triangles(triangles, spacing):
    """Points covering each triangle at about `spacing` apart (vertices included)."""
    a, b, c = triangles[:, 0], triangles[:, 1], triangles[:, 2]
    size = np.maximum(np.linalg.norm(b - a, axis=1), np.maximum(np.linalg.norm(c - a, axis=1),
                                                                 np.linalg.norm(c - b, axis=1)))
    steps = np.clip(np.ceil(size / spacing), 1, 64).astype(np.int64)
    points = [a, b, c]
    for count in np.unique(steps):
        if count < 2:
            continue
        chosen = steps == count
        u, v = np.meshgrid(np.arange(count + 1), np.arange(count + 1))
        keep = u + v <= count
        u, v = u[keep] / count, v[keep] / count
        ta, tb, tc = a[chosen], b[chosen], c[chosen]
        samples = ta[:, None, :] + (tb - ta)[:, None, :] * u[None, :, None] + (tc - ta)[:, None, :] * v[None, :, None]
        points.append(samples.reshape(-1, 3))
    return np.concatenate(points)
EDITOR_PICK_MASK = BitMask32.bit(3)
SURFACE_MASK = BitMask32.bit(6)  # visible geometry rays may hit (light bounces); not used for picking


class WorldObject:
    def __init__(self, world, data):
        self.world = world
        self.data = data
        self.root = world.root.attach_new_node(f'object-{data["id"]}')
        self.root.set_tag(TAG, data['id'])
        self.content = None
        self.prefab = None
        self.local_bounds = None  # (min, max) of the content in root space
        self.error = None
        self.build()

    @property
    def id(self):
        return self.data['id']

    @property
    def app(self):
        return self.world.app

    def build(self):
        """(Re)create the model, e.g. after the model or a material color changed."""
        self._destroy_content()
        data = self.data
        self.error = None
        try:
            if data['kind'] == 'light':
                self.content = self.root.attach_new_node('light')  # the light and its editor marker: PlacedLight
            elif data['kind'] == 'bird':
                self.prefab = Bird(self.root, data['model'])
                self.content = self.prefab.actor
            else:
                self.content = objects.instance(data['model'], data['colors'], data.get('texture', ''))
                self.content.reparent_to(self.root)
        except Exception as error:  # a missing or broken model file must not stop the world
            self.error = str(error)
            print(f'object {data.get("name") or data["id"]}: cannot load {data["model"]}: {error}')
            self.content = self.root.attach_new_node('missing')
        bounds = self.content.get_tight_bounds(self.root)
        self.local_bounds = bounds if bounds else None
        self.apply_transform()
        self.apply_flags()
        if data['kind'] == 'campfire' and self.error is None:
            self.prefab = CampfireRig(self.app, self.root)
        elif data['kind'] == 'item' and self.error is None:
            self.prefab = PlacedItem(self.world, self.root, data)
        elif data['kind'] == 'light':
            self.prefab = PlacedLight(self.world, self.root, data)
            self.apply_flags()  # again: the bulb marker must get the editor's pick mask

    def apply_transform(self):
        data = self.data
        self.root.set_pos(*data['pos'])
        self.root.set_hpr(*data['hpr'])
        self.root.set_scale(*(max(abs(s), 1e-4) for s in data['scale']))
        if hasattr(self.prefab, 'moved'):  # campfire smoke, a spot light's bounce
            self.prefab.moved()

    def apply_flags(self):
        data = self.data
        root = self.root
        if data['visible']:
            root.show()
        else:
            root.hide()
        shading.set_cast_shadow(root, data['cast_shadow'])
        shading.set_receive_shadow(root, data['receive_shadow'])
        root.set_shader_input('unlit', 1.0 if data['unlit'] else 0.0)
        root.set_shader_input('shininess', float(data['shininess']))
        root.set_shader_input('roughness', float(data['roughness']))
        if data['unlit'] or data['kind'] == 'bird':
            shading.set_in_depth_prepass(root, False)
        else:
            shading.set_in_depth_prepass(root, True)
        if data['distance_render']:
            root.set_tag(DISTANCE_RENDER_TAG, '1')
        else:
            root.clear_tag(DISTANCE_RENDER_TAG)
            self.content.show()

        if self.world.mode == 'editor':
            root.set_collide_mask(EDITOR_PICK_MASK | SURFACE_MASK)
        elif data['interactable']:
            interactables.add(root)
            root.set_collide_mask(interactables.PICK_MASK | SURFACE_MASK)
        else:
            interactables.delete(root.get_key())
            root.clear_tag(interactables.TAG)
            root.set_collide_mask(SURFACE_MASK)
        self.world.distance_changed()

    def center(self):
        return self.root.get_pos(self.world.app.render)

    def collision_shapes(self):
        """2.5D colliders in world space: ('box', cx, cy, hx, hy, heading, z0, z1) and
        ('cylinder', cx, cy, radius, z0, z1) tuples (empty without collision)."""
        collision = self.data['collision']
        if collision['shape'] == 'none' or self.local_bounds is None or not self.data['visible']:
            return []
        if collision['shape'] == 'mesh':
            return self._mesh_shapes()
        low, high = self.local_bounds
        scale = [max(abs(s), 1e-4) for s in self.data['scale']]
        factor = collision['scale']
        offset = collision['offset']
        half = [(high[i] - low[i]) / 2 * scale[i] * factor[i] for i in range(3)]
        local_center = Point3(*((low[i] + high[i]) / 2 for i in range(3)))
        center = self.world.root.get_relative_point(self.root, local_center)
        center = Point3(center.x + offset[0], center.y + offset[1], center.z + offset[2])
        z0, z1 = center.z - half[2], center.z + half[2]
        if collision['shape'] == 'cylinder':
            return [('cylinder', center.x, center.y, max(half[0], half[1]), z0, z1)]
        return [('box', center.x, center.y, half[0], half[1], math.radians(self.data['hpr'][0]), z0, z1)]

    def _mesh_shapes(self):
        """Footprint of the actual triangles: a grid of small boxes, each spanning the heights of the
        surfaces above it (split where there is room to walk in between)."""
        key = (tuple(self.data['pos']), tuple(self.data['hpr']), tuple(self.data['scale']), self.data['model'],
               json.dumps(self.data['collision'], sort_keys=True))
        if getattr(self, '_mesh_key', None) == key:
            return self._mesh_cache
        matrix = self.root.get_mat(self.world.root)
        rotation = np.array([[matrix.get_cell(r, c) for c in range(3)] for r in range(3)])
        translation = np.array([matrix.get_cell(3, c) for c in range(3)])
        offset = np.array(self.data['collision']['offset'])
        points = []
        try:
            parts = library.load_parts(self.data['model'])
        except OSError:
            parts = []
        for part in parts:
            triangles = part.positions[part.indices].reshape(-1, 3, 3).astype(np.float64) @ rotation + translation
            points.append(_sample_triangles(triangles, MESH_CELL / 2))
        shapes = []
        if points:
            points = np.concatenate(points) + offset
            cells = np.floor(points[:, :2] / MESH_CELL).astype(np.int64)
            order = np.lexsort((points[:, 2], cells[:, 1], cells[:, 0]))
            cells, heights = cells[order], points[order, 2]
            boundaries = np.nonzero(np.any(np.diff(cells, axis=0) != 0, axis=1))[0] + 1
            half = MESH_CELL / 2
            for cell, z in zip(np.split(cells, boundaries), np.split(heights, boundaries)):
                cx, cy = (cell[0, 0] + .5) * MESH_CELL, (cell[0, 1] + .5) * MESH_CELL
                gaps = np.nonzero(np.diff(z) > MESH_GAP)[0]
                start = 0
                for gap in list(gaps) + [len(z) - 1]:
                    z0, z1 = z[start], z[gap]
                    shapes.append(('box', float(cx), float(cy), half, half, 0.0, float(z0) - .05, float(z1)))
                    start = gap + 1
        self._mesh_key, self._mesh_cache = key, shapes
        return shapes

    def triangle_count(self):
        if self.content is None:
            return 0
        total = 0
        for geom_node in self.content.find_all_matches('**/+GeomNode'):
            for index in range(geom_node.node().get_num_geoms()):
                geom = geom_node.node().get_geom(index)
                for primitive in range(geom.get_num_primitives()):
                    total += geom.get_primitive(primitive).get_num_faces()
        return total

    def _destroy_content(self):
        if self.prefab is not None:
            self.prefab.destroy()
            self.prefab = None
        if self.content is not None and not self.content.is_empty():
            self.content.remove_node()
        self.content = None

    def destroy(self):
        self._destroy_content()
        interactables.delete(self.root.get_key())
        self.root.remove_node()
