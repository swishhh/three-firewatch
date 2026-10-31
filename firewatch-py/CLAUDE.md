# CLAUDE.md — firewatch-py

Python/Panda3D remake of the three.js scene in the parent dir. Work only inside `firewatch-py/`; the parent JS app is reference only (assets `../obj`, `../sound` are shared, read-only). README.md has user-facing detail; don't read it unless needed.

## Run / test
- Run: `.venv/bin/python main.py [--fps N] [--vsync|--no-vsync]`. Deps pinned in requirements.txt (panda3d, panda3d-gltf, numpy).
- System python lacks ensurepip; venv was made with `--without-pip` + pip.pyz. Use `.venv/bin/python -m pip`.
- No test suite. Lint: `.venv/bin/python -m pyflakes main.py firewatch`.
- Verify visually offscreen (never pop windows on the user's desktop): before importing the app, `load_prc_file_data('', 'window-type offscreen\naudio-library-name null')` and set `firewatch.settings.FILE` to a scratch path (else tests overwrite the user's settings.json). Step with `app.task_mgr.step()`, save with `app.win.save_screenshot(Filename.from_os_specific(path))`, then view the PNG.

## Architecture (`firewatch/`)
- `app.py` ShowBase: loads settings → PRC → `shading.init` → `scene.draw` (component list in `scene.py`, each module has `draw(app)`) → `pipeline.init_pipeline`. Per-frame callbacks via `update.add_update_callback(fn(dt))`; shared objects via `registry.add/get`.
- `settings.py`: schema (Tabs/Sections/Setting with default + `js` value), presets, `TIME_KEYFRAMES`, JSON store (`settings.json`, debounced save). API: `settings.get/set/update/subscribe(cb, prefix)`. New setting = add to schema; UI (`ui/settings_panel.py`, F1) is generated from it.
- `pipeline.py`: FilterManager chain: depth prepass → `ao.frag` lighting mask (AO R, contact shadows G, sun shadow-map lookup B) → 4x4 blur → HDR MSAA scene → bloom down/up → dof → `post.frag` (tonemap/grade) → `final.frag` (FXAA/sharpen/vignette/dither). `apply_settings` toggles buffers by index (prepass, ao, blur, scene, 11 bloom, dof, post) — keep in sync if passes change. MSAA/render scale/AO res trigger `rebuild()`.
- `sun.py`: own shadow camera/buffer (not a Panda light); same depth texture bound twice (compare + raw) for PCF/PCSS; `sun.bind(ao_quad)` gives the mask pass its inputs. The scene shader only reads the blurred mask. `components/environment.py`: sky dome, sun dir/color, hemisphere, fog, wind, snow cover, time of day; applies only when dirty.
- `point_shadow.py`: campfire cube shadow (`make_cube_map`, distance shader, near 0.5 like three); sampled in scene.frag for the point lights (`gfx.fire_shadow*`).
- `shading.py`: camera masks MAIN/SHADOW/PREPASS (`set_cast_shadow`, `set_in_depth_prepass`), per-node shader inputs (`set_unlit`, `set_receive_shadow`, `set_standard_material`, `sway_amount`), `depth_state()`.
- Terrain (`components/terrain.py`): numpy heightfield; default smooth bell hills with a smooth union (`env.terrain_shape` = 'js' restores the JS bumps); grid density `gfx.terrain_detail`. Both are restart-only because trees/props are placed on the heights at startup.
- Geometry: `loaders/obj.py`, `loaders/glb.py` (static), `objects.py` (model library + per-material colors), `instancing.py` (bakes instances into one mesh + `sway` column), `particles.py` (GPU quads: snow, fireflies). Bird uses panda3d-gltf `Actor`.
- Shaders in `shaders/`, loaded via `shading.load_shader(vert, frag)`; `#pragma include` works (`common.glsl` wind sway, `depth_utils.glsl`).

## Conventions
- Component MAP data stays in three.js coords (Y-up); convert with `coords.three_to_panda`, `rotation_y_to_heading` (JS rotateY values are radians).
- Colors are raw hex (JS r146 legacy color mode, no sRGB). Light colors = color*intensity; shader applies 1/PI.
- Comment ports with the JS file they mirror; keep code style of surrounding modules (snake_case Panda API).

## Gotchas (learned the hard way)
- `make_cube_map` faces each have a display region with Panda's grey (0.41) clear: set the clear per region, not on the buffer.
- Panda caches `p3d_Fog`: use plain uniforms (`fog_color`, `fog_density`) for anything changed at runtime.
- `gl_PointSize` is ignored (GL_PROGRAM_POINT_SIZE never enabled) → particles are vertex-shader quads.
- Depth-pass override uses `ShaderAttrib.make(shader, 100)` (priority), not an attrib override, so node inputs survive.
- Mask-pass sample rotations use a 4x4 Bayer tile and `ao_blur.frag` is a 4x4 box: keep them aligned or noise patterns return. Receiver-plane bias comes from the reconstructed face normal, not dFdx. Mask texels are snapped to one prepass pixel, the scene picks the depth-matching mask texel (3x3), and sun-facing-away surfaces store shadow/contact = 0 — otherwise lit values bleed across contact lines as a white fringe.
- The depth prepass also writes view-space normals (depth.frag); AO must use them — normals rebuilt from depth are per triangle and draw the terrain mesh onto smooth hills.
- Prepass depth texture must stay linear-filtered, or AO/contact shadows band on sloped faces.
- `direct` classes (OnscreenText, DirectGUI) are camelCase only (`setText`); DirectGUI rejects numpy floats in colors; DirectSlider echoes values as float32 (ignore tiny diffs).
- OpenAL spatializes mono only → campfire mp3 is downmixed at load (`load_mono`).
- Panda's `M_limited` clock busy-waits; the frame cap sleeps in `app._limit_frame_rate`.
- Mouse look on X11: don't warp every frame (stale pre-warp events cause shake); warp near edges, drop large deltas.
