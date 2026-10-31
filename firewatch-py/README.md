# Firewatch scene — Python / Panda3D port

A native re-make of the three.js scene in the repository root. It loads the same assets
(`../obj`, `../sound`) and mirrors the JS layout, so each module maps onto the JS file it ports.

## Run

```bash
cd firewatch-py
python3 -m venv .venv            # Debian/Ubuntu: needs `sudo apt install python3-venv`
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

## Controls

| Input | Action |
|---|---|
| Click | Capture the mouse (pointer lock) |
| Mouse | Look around |
| W A S D | Move |
| Space | Jump |
| Esc | Release the mouse |
| Click (while captured) | Select / unselect the interactable under the crosshair |
| R | Rotate the selected object by 90° |

## Performance overlay

The frame rate is uncapped by default. `F` cycles a frame cap (off, 240, 144, 60), and
`main.py --fps 144` or `--vsync` sets one at startup. Uncapped, the loop starts the next frame as
soon as the last one is submitted, so it keeps a CPU core (and the desktop compositor) busy while
the GPU, which needs well under a millisecond per frame for this scene, mostly waits. Capped, the
loop sleeps between frames (about 5% of a core at 60 fps).

The top left shows whole-machine CPU and whole-GPU utilization graphs (`components/stats.py`,
sampled in `usage.py` via `/proc/stat` and NVIDIA's NVML or amdgpu's sysfs counter).

## Layout

| Python | JS |
|---|---|
| `main.py`, `firewatch/app.py` | `js/app.js` |
| `firewatch/scene.py` | `js/component/scene.js` — the component list; comment a line out to disable it |
| `firewatch/registry.py`, `update.py`, `interactables.py` | `js/registry/*` |
| `firewatch/objects.py` | `js/tools/object/manager.js` — model paths and per-material colors |
| `firewatch/instancing.py` | `js/component/scene/InstancedManager.js` |
| `firewatch/renderer.py` | `js/component/renderer/index.js` — hides far `distance_render` models |
| `firewatch/components/*` | `js/component/objects/*`, `light.js`, `stats.js` |
| `firewatch/controls/*` | `js/component/controls/*`, `action/object/outline.js` |
| `firewatch/shaders/scene.*` | the parts of three.js r146's Phong/Standard shading the scene used |

Coordinates in the component `MAP` arrays are three.js coordinates (Y-up), copied unchanged from the
JS files and converted to Panda3D's Z-up in `coords.py`, so values can move between the two apps.

## Rendering notes

- Colors are used as raw hex values. The JS app runs three.js r146 in legacy color mode and renders
  through an EffectComposer whose final FXAA pass skips sRGB encoding, so hex values reached the
  screen without gamma conversion.
- Lights use three's `physicallyCorrectLights` math: `color * intensity`, Lambert's `1 / PI`, the
  physical point light falloff, GGX specular for the terrain (`MeshStandardMaterial`) and
  Blinn-Phong for everything else.
- Trees and grass are baked into one vertex-colored mesh each (one draw call, like `InstancedMesh`).

## Differences from the JS version

Not ported:
- lil-gui debug panels (fog, light and terrain color tweaks with localStorage persistence)
- The placement toolbar (disabled by default in the JS too), drag-to-move (`DragControls`) and the
  selection panel's drag scrubbers — the panel here is read-only
- Components already disabled in `scene.js`: map/orbit controls, lamp post, water, house, fire
  watch tower, snow, fire camp; the unused tree swing animation

Deliberate changes:
- Picking selects the nearest interactable along the ray (the JS loop ended on the farthest), and
  while the mouse is captured it picks at the crosshair.
- Per-frame motion (clouds, smoke, fire flicker) is normalized to 60 fps instead of running faster
  on high refresh rate displays.
- The campfire point light does not cast shadows.
- Higher quality than the JS: 8x MSAA instead of FXAA, a 4096 shadow map (2048 in JS) filtered
  with 25 taps and a normal offset for soft, acne-free edges, and dithered output so the dark fog
  gradients don't band into stripes.
- The stereo campfire sound is downmixed to mono at load, since OpenAL only spatializes mono
  sources (Web Audio's panner downmixed it implicitly).

Kept on purpose so the scene matches: `rotateY(90)` and `rotateY(20)` are radians, the tree `MAP`
entry without a scale is skipped (it rendered as NaN in JS), bushes and the campfire don't receive
shadows (`recieveShadow` typo), and the terrain normals stay pointing up.