"""Compile a world for the game, and analyze it.

Compiling bakes everything static into saves/<name>/compiled/scene.bam:
  - terrain chunks, already simplified (gfx.terrain_lod) so the game skips building them,
  - foliage cells,
  - static objects (kind 'model', not interactable in the game) merged per 25 m cell and material
    settings into single vertex-colored meshes: one draw call per cell instead of one per mesh,
plus compiled.json with their colliders and a hash of the save. The game loads the bake when the
hash still matches (the environment is not part of it, so lighting can change freely), otherwise it
builds the world live like the editor does.

The analyzer report (compile_report.txt, also shown in the editor) lists triangle and draw call
counts and points at what costs the most: heavy models, tiny shadow casters, buried or duplicated
objects, expensive graphics settings.
"""
import hashlib
import json
from collections import defaultdict

import numpy as np
from panda3d.core import GeomNode, NodePath, Point3

from .. import library, objects, settings, shading
from ..geometry import make_geom
from ..objects import DISTANCE_RENDER_TAG
from ..paths import panda_filename
from .foliage import CELL

FOLDER = 'compiled'
FORMAT = 3  # bump when the bake's contents change
HEAVY_MODEL = 50_000  # triangles


def source_hash(document):
    data = {key: value for key, value in document.data.items() if key not in ('environment', 'next_id')}
    digest = hashlib.sha1(json.dumps(data, sort_keys=True).encode())
    for array in (document.terrain.heights, document.terrain.paint, document.terrain.water):
        digest.update(np.ascontiguousarray(array).tobytes())
    digest.update(str(settings.get('gfx.terrain_lod')).encode())
    digest.update(str(settings.get('gfx.smooth_terrain')).encode())
    digest.update(str(FORMAT).encode())
    return digest.hexdigest()


def is_static(record):
    return (record['kind'] == 'model' and not record['interactable'] and record['visible']
            and not record.get('breakable', {}).get('enabled') and library.exists(record['model'])
            and not objects.is_textured(record['model'], record.get('texture', '')))  # merging bakes colors only


def bakes_foliage(record):
    """Breakable foliage stays live so single instances can be chopped down in the game."""
    return not record.get('breakable', {}).get('enabled')


def _matrix(mat):
    return np.array([[mat.get_cell(row, column) for column in range(4)] for row in range(4)], np.float64)


def _flags_tag(node, flags):
    node.set_tag('flags', json.dumps(flags))


def apply_flags(node, flags):
    shading.set_cast_shadow(node, flags.get('cast_shadow', True))
    shading.set_receive_shadow(node, flags.get('receive_shadow', True))
    node.set_shader_input('unlit', 1.0 if flags.get('unlit') else 0.0)
    node.set_shader_input('shininess', float(flags.get('shininess', 0)))
    node.set_shader_input('roughness', float(flags.get('roughness', 0)))
    node.set_shader_input('sway_amount', float(flags.get('sway', 0)))
    if 'paint_base' in flags:
        node.set_shader_input('paint_base', tuple(flags['paint_base']))
    shading.set_in_depth_prepass(node, not flags.get('unlit'))


class CompiledWorld:
    def __init__(self, world, node, manifest):
        self.world = world
        self.node = node
        self.manifest = manifest
        self.baked_ids = set(manifest['baked_ids'])
        self.baked_foliage = set(manifest.get('baked_foliage', []))
        self.colliders = [tuple(shape) for shape in manifest['colliders']]
        self.terrain_triangles = manifest['stats']['terrain_triangles']
        self.triangles = manifest['stats']['baked_triangles']
        self.sways = manifest.get('sways', False)
        self.distance_nodes = []
        for child in node.find_all_matches('**/=flags'):
            apply_flags(child, json.loads(child.get_tag('flags')))
        for child in node.find_all_matches(f'**/={DISTANCE_RENDER_TAG}'):
            center = Point3(*(float(v) for v in child.get_tag('center').split()))
            self.distance_nodes.append((child, None, center))

        terrain = world.terrain
        terrain_node = node.find('terrain')
        if not terrain_node.is_empty():
            terrain_node.wrt_reparent_to(world.root)
            terrain.root = terrain_node
            terrain.chunk_nodes = {}
            for chunk in terrain_node.get_children():
                _, cx, cy = chunk.get_name().split('-')
                terrain.chunk_nodes[(int(cx), int(cy))] = chunk
            terrain.steps = np.array(manifest['terrain_steps'], np.int32)
            terrain.apply_material()

    def is_baked(self, identifier):
        return identifier in self.baked_ids

    def destroy(self):
        self.node.remove_node()


def load(world, document):
    folder = document.folder / FOLDER
    try:
        manifest = json.loads((folder / 'compiled.json').read_text())
    except (OSError, ValueError):
        print(f'world "{document.name}" is not compiled; building it live (Compile in the editor to bake it)')
        return None
    if manifest.get('hash') != source_hash(document):
        print(f'world "{document.name}" changed since it was compiled; building it live (compile it again)')
        return None
    try:
        node = world.app.loader.load_model(panda_filename(folder / 'scene.bam'), noCache=True)
    except Exception as error:
        print(f'cannot load the compiled world: {error}')
        return None
    node.reparent_to(world.root)
    print(f'world "{document.name}": running the compiled bake')
    return CompiledWorld(world, node, manifest)


def _bake_static_objects(world, records):
    """Merged meshes: {(cell, flags json): [positions, normals, colors, indices]}."""
    groups = defaultdict(lambda: [[], [], [], [], 0])
    half = world.terrain.half
    for record in records:
        item = world.object_by_id(record['id'])
        if item is None:
            continue
        matrix = _matrix(item.root.get_mat(world.root))
        rotation = matrix[:3, :3]
        normal_matrix = np.linalg.inv(rotation).T
        position = item.root.get_pos(world.root)
        cell = (int((position.x + half) // CELL), int((position.y + half) // CELL))
        flags = {key: record[key] for key in ('cast_shadow', 'receive_shadow', 'unlit', 'shininess', 'roughness',
                                              'distance_render')}
        key = (cell, json.dumps(flags, sort_keys=True))
        group = groups[key]
        for part in objects.colored_parts(record['model'], record['colors']):
            count = len(part.positions)
            positions = part.positions.astype(np.float64) @ rotation + matrix[3, :3]
            normals = part.normals.astype(np.float64) @ normal_matrix
            normals /= np.maximum(np.linalg.norm(normals, axis=1, keepdims=True), 1e-9)
            group[0].append(positions.astype(np.float32))
            group[1].append(normals.astype(np.float32))
            group[2].append(np.broadcast_to(np.array(part.color, np.float32), (count, 4)))
            group[3].append(part.indices + group[4])
            group[4] += count
    return groups


def compile_world(world):
    """Bake the loaded world. Returns the analyzer report (str)."""
    world.flush()
    document = world.document
    folder = document.folder / FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    root = NodePath('compiled')

    # Terrain chunks as they are built now (simplified with the current gfx.terrain_lod).
    terrain = world.terrain
    terrain_root = root.attach_new_node('terrain')
    for (cx, cy), chunk in sorted(terrain.chunk_nodes.items()):
        node = GeomNode(f'terrain-{cx}-{cy}')
        node.add_geoms_from(chunk.node())
        terrain_root.attach_new_node(node)
    terrain_triangles = terrain.triangle_count()

    # Foliage cells.
    baked_triangles = 0
    sways = False
    baked_foliage = []
    for group in world.foliage:
        if not bakes_foliage(group.data):
            continue
        baked_foliage.append(group.data['id'])
        group_root = root.attach_new_node(f'foliage-{group.data["id"]}')
        flags = {'cast_shadow': group.data['cast_shadow'], 'receive_shadow': group.data['receive_shadow'],
                 'sway': group.data['sway']}
        sways = sways or (group.data['sway'] > 0 and group.data['cast_shadow'] and len(group.items) > 0)
        _flags_tag(group_root, flags)
        for cell, chunk in group.cells.items():
            node = group_root.attach_new_node(GeomNode(chunk.get_name()))
            node.node().add_geoms_from(chunk.node())
            if group.data['distance_render']:
                center = chunk.get_python_tag('center')
                node.set_tag(DISTANCE_RENDER_TAG, '1')
                node.set_tag('center', f'{center.x} {center.y} {center.z}')
        baked_triangles += group.triangle_count()

    # Static objects merged per cell and material flags.
    static = [record for record in world.data['objects'] if is_static(record)]
    statics_root = root.attach_new_node('static')
    half = terrain.half
    merged_geoms = 0
    for (cell, flags_json), (positions, normals, colors, indices, _count) in _bake_static_objects(world, static).items():
        if not positions:
            continue
        flags = json.loads(flags_json)
        node = statics_root.attach_new_node(GeomNode(f'static-{cell[0]}-{cell[1]}'))
        geom = make_geom(np.concatenate(positions), np.concatenate(normals),
                         np.concatenate(indices).astype(np.uint32), np.concatenate(colors))
        node.node().add_geom(geom)
        baked_triangles += sum(len(i) for i in indices) // 3
        merged_geoms += 1
        _flags_tag(node, flags)
        if flags['distance_render']:
            node.set_tag(DISTANCE_RENDER_TAG, '1')
            node.set_tag('center', f'{(cell[0] + .5) * CELL - half} {(cell[1] + .5) * CELL - half} 0')

    colliders = []
    for record in static:
        item = world.object_by_id(record['id'])
        if item is not None:
            colliders.extend(list(shape) for shape in item.collision_shapes())

    root.write_bam_file(panda_filename(folder / 'scene.bam'))
    stats = {'terrain_triangles': terrain_triangles, 'baked_triangles': baked_triangles,
             'static_objects': len(static), 'merged_meshes': merged_geoms}
    manifest = {'hash': source_hash(document), 'format': FORMAT, 'baked_ids': [record['id'] for record in static],
                'baked_foliage': baked_foliage,
                'colliders': colliders, 'stats': stats, 'sways': sways,
                'terrain_steps': terrain.steps.tolist()}
    (folder / 'compiled.json').write_text(json.dumps(manifest))
    report = analyze(world, stats)
    (folder.parent / 'compile_report.txt').write_text(report)
    return report


def _model_triangles(record):
    try:
        return library.stats(record['model'])['triangles']
    except Exception:
        return 0


def analyze(world, compiled_stats=None):
    """Plain-text performance report for the loaded world."""
    lines = []
    add = lines.append
    data = world.data
    terrain = world.terrain
    full_terrain = 2 * terrain.segments ** 2
    lod_terrain = terrain.triangle_count()
    counts = world.triangle_counts()

    add(f'WORLD "{world.name}"')
    add('')
    add('Geometry (triangles)')
    add(f'  terrain   {lod_terrain:>10,}   of {full_terrain:,} at full resolution '
        f'({100 * lod_terrain / max(full_terrain, 1):.1f}%, simplification {settings.get("gfx.terrain_lod")} m)')
    add(f'  objects   {counts["objects"]:>10,}   in {len(world.objects)} objects')
    add(f'  foliage   {counts["foliage"]:>10,}   in {sum(len(g.items) for g in world.foliage)} instances, '
        f'{sum(len(g.cells) for g in world.foliage)} cells')
    add(f'  water     {counts["water"]:>10,}   in {len(world.water)} bodies')
    lights = [record for record in data['objects'] if record['kind'] == 'light']
    if lights:
        enabled = sum(1 for record in lights if record['light']['enabled'])
        add(f'  lights    {len(lights)} placed ({enabled} enabled; the nearest 4 shine at a time)')

    geoms = len(terrain.chunk_nodes) + sum(len(g.cells) for g in world.foliage)
    object_geoms = 0
    for item in world.objects:
        if item.content is not None:
            for node in item.content.find_all_matches('**/+GeomNode'):
                object_geoms += node.node().get_num_geoms()
    water_geoms = sum(1 for body in world.water if body.node is not None)
    add('')
    add('Draw calls in the main pass (before culling)')
    add(f'  live: {geoms + object_geoms + water_geoms}  (terrain chunks {len(terrain.chunk_nodes)}, foliage cells '
        f'{sum(len(g.cells) for g in world.foliage)}, object meshes {object_geoms}, water {water_geoms})')
    if compiled_stats:
        static_ids = {record['id'] for record in data['objects'] if is_static(record)}
        dynamic_geoms = 0
        for item in world.objects:
            if item.id not in static_ids and item.content is not None:
                for node in item.content.find_all_matches('**/+GeomNode'):
                    dynamic_geoms += node.node().get_num_geoms()
        add(f'  compiled: {geoms + compiled_stats["merged_meshes"] + dynamic_geoms + water_geoms}  '
            f'({compiled_stats["static_objects"]} static objects merged into {compiled_stats["merged_meshes"]} meshes)')

    findings = []
    for record in data['objects']:
        label = record['name'] or record['id']
        if record['kind'] == 'light':
            continue
        if not library.exists(record['model']):
            findings.append(f'MISSING   {label}: model file {record["model"]} not found')
            continue
        triangles = _model_triangles(record)
        if triangles > HEAVY_MODEL:
            findings.append(f'HEAVY     {label}: {triangles:,} triangles ({record["model"]}); a lighter model, '
                            f'or turning off its shadows, saves the most')
        item = world.object_by_id(record['id'])
        if item is not None and item.local_bounds is not None:
            low, high = item.local_bounds
            size = max((high[i] - low[i]) * abs(record['scale'][i]) for i in range(3))
            if record['cast_shadow'] and size < .15:
                findings.append(f'TINY      {label}: {size:.2f} m casting shadows; its shadow is hardly visible')
            top = item.root.get_pos(world.root).z + high[2] * abs(record['scale'][2])
            x, y = record['pos'][0], record['pos'][1]
            if terrain.contains(x, y) and top < terrain.height_at(x, y) - .05:
                findings.append(f'BURIED    {label}: entirely below the ground')
        if not terrain.contains(record['pos'][0], record['pos'][1]):
            findings.append(f'OUTSIDE   {label}: outside the terrain')
    selectable = [record['name'] or record['id'] for record in data['objects']
                  if record['interactable'] and record['kind'] == 'model']
    if selectable:
        findings.append(f'DYNAMIC   {len(selectable)} objects are selectable in the game, so compiling keeps them '
                        f'separate: {", ".join(selectable)}. Turn off "Selectable in game" to merge them.')
    seen = {}
    for record in data['objects']:
        key = (record['model'], tuple(round(v, 2) for v in record['pos']))
        if key in seen:
            findings.append(f'DUPLICATE {record["name"] or record["id"]}: same model and place as {seen[key]}')
        else:
            seen[key] = record['name'] or record['id']
    for group in world.foliage:
        per_cell = max((np.count_nonzero(group._cell_keys()[:, 0] == c[0]) for c in group.cells), default=0)
        per_instance = sum(len(part.indices) // 3 for part in group.parts)
        if per_instance * per_cell > 200_000:
            findings.append(f'DENSE     foliage {group.data["name"]}: up to {per_instance * per_cell:,} triangles per '
                            f'cell; thin it out or enable draw-distance culling')
        if not group.data['distance_render'] and len(group.items) > 2000:
            findings.append(f'FOLIAGE   {group.data["name"]}: {len(group.items)} instances always drawn; enable '
                            f'"Hide beyond draw distance"')

    get = settings.get
    hints = []
    if get('gfx.fps_cap') == 0 and not get('gfx.vsync'):
        hints.append('Frame cap is Off and vsync is off: the game renders as many frames as it can, keeping a CPU '
                     'core busy. "Display" matches the monitor.')
    if get('gfx.render_scale') > 1:
        hints.append(f'Render scale {get("gfx.render_scale"):.0%} renders {get("gfx.render_scale") ** 2:.1f}x the '
                     f'pixels of the window.')
    if get('gfx.msaa') >= 8:
        hints.append('MSAA 8x on an HDR buffer is costly on the GPU; 4x looks nearly the same.')
    if get('gfx.shadows') and get('gfx.shadow_resolution') >= 8192:
        hints.append('8192 shadow maps take 256 MB/s of fill per update; 4096 is usually enough.')
    if get('gfx.shadows') and get('gfx.shadow_filter') == 'pcss' and get('gfx.shadow_samples') >= 64:
        hints.append('PCSS with 64 samples is the most expensive shadow filter setting.')
    if get('gfx.ao') and get('gfx.ao_resolution') == 'full' and get('gfx.ao_samples') >= 32:
        hints.append('Full resolution AO with 32 samples; half resolution halves its cost.')
    if get('gfx.bloom') and get('gfx.bloom_quality') == 'high':
        hints.append('High quality bloom adds 11 render passes; Fast uses one.')
    if get('gfx.shadow_update_rate') == 0:
        hints.append('Animated shadow rate "Every frame" re-renders shadow maps every frame while plants sway.')
    if get('env.snow') and get('env.snow_amount') > 16000:
        hints.append(f'{get("env.snow_amount")} snowflakes.')

    add('')
    add('Findings')
    lines.extend(f'  {finding}' for finding in findings) if findings else add('  none')
    add('')
    add('Graphics settings worth checking')
    lines.extend(f'  - {hint}' for hint in hints) if hints else add('  none')
    if compiled_stats:
        add('')
        add(f'Compiled: {compiled_stats["baked_triangles"]:,} triangles baked into the scene; the game loads it '
            f'while the save stays unchanged.')
    return '\n'.join(lines) + '\n'

