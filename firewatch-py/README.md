# Firewatch scene — Python / Panda3D port

A native re-make of the three.js scene in the repository root, grown into a small game with a world
editor. It loads the same assets (`../obj`, `../sound`).

## Run

```bash
cd firewatch-py
python3 -m venv .venv            # Debian/Ubuntu: needs `sudo apt install python3-venv`
.venv/bin/pip install -r requirements.txt
#.venv/bin/python main.py         # the game (first person)
.venv/bin/python editor.py       # the world editor
```

Both take `--world NAME` (default: the world last opened), `--fps N` (0 = uncapped, -1 = display
refresh rate) and `--vsync / --no-vsync`. They share the graphics settings (`settings.json`) and
the world saves (`saves/<name>/`): whatever you build or change in the editor, the game shows.

No sound? The app uses OpenAL's ALSA backend by default (its PulseAudio backend fails on PipeWire);
set `ALSOFT_DRIVERS=pulse` (or `oss`) to try another. A warning is printed when no device opens.

On the first run the scene of the JS app becomes the `default` world, together with the environment
values from an older `settings.json`.

## Game controls

| Input | Action |
|---|---|
| Click | Capture the mouse (pointer lock) |
| Mouse | Look around |
| W A S D, Shift | Move, run |
| Space | Jump |
| Esc | Release the mouse |
| Click (while captured) | Select / unselect the object under the crosshair (objects marked "Selectable in game") |
| R | Rotate the selected object by 90° |
| E | Pick up the item you look at (placed in the editor as kind "Item") |
| 1-8, wheel | Select an inventory slot; the item shows in your hand |
| F | Switch a held flashlight on / off |
| Left click | Swing a held axe: chops what it hits (trees by default); its drops (wood) stack into the hotbar |
| G | Drop the held item in front of you |
| F2 | Cycle the frame cap |
| F1 | Settings: Graphics, Lighting, Sky, World, Player |

You walk on the terrain, collide with objects and tree trunks (per-object collision settings), step
onto low things and wade slower through water. Movement, collision and camera bob (bounce, sway, roll,
step rate, growth with speed, running, breathing, landing dip; or off) and footsteps (`sound/player/snow_step.mp3` loops while you walk and
stops within ~60 ms when you stop; volume, louder and faster when running) are in the Player tab. The
editor's Environment tool also has a Sound section (master, footsteps, campfire volume).
Items picked up are gone for this session only: playing never changes the save.

## Editor

Tool bar on top, tool options on the left, the selected object's properties on the right.
Every change is autosaved a moment later (the terrain once a brush stroke ends); Ctrl+S saves now.

| Tool | |
|---|---|
| File (8) | Save, save as, load, delete worlds; new flat world or a fresh copy of the JS scene |
| Select (1) | Click an object, a single tree / grass tuft of a foliage group, or a collider; drag to move along the ground (Shift: height, Ctrl: rotate, Alt: scale / resize). Del, Ctrl+D duplicate, R / Shift+R rotate 15°, End drop to ground. Foliage instances can be converted into regular objects. Player start position. |
| Place (2) | Every model in `obj/` (Refresh picks up new files without a restart). Kinds: model, campfire (light, smoke, sound, shadow), animated (bird), item (picked up by the player; models in `obj/tools/` default to it). Also standalone box and cylinder colliders. |
| Sculpt (3) | Raise / lower / smooth / flatten / roughen with a smooth falloff (no creases where hills meet the ground). Ctrl lowers, Shift smooths, Alt+click picks the flatten height. Reset to flat or the JS hills. |
| Paint (4) | Paint terrain colors over the base color (World settings); Ctrl erases, Alt+click picks a color. |
| Foliage (5) | Paint instance groups (grass, trees...) with density, spacing, scale range and random rotation; Ctrl erases. Per-group model, colors, wind sway, shadows, trunk collision. Converts objects placed one by one into a group. |
| Water (6) | Water bodies painted onto the terrain, optionally digging the ground below the level. Presets (lake, clear, murky, frozen); level, colors, opacity everywhere and opacity added by depth (1 = solid), reflections, sun glint, waves, shore foam, and "Frozen: walk on it". |
| Environment (7) | Lighting (time of day, sun, moon, world light, fog), Sky (gradient, stars, clouds), World (terrain material, campfire, ambience), Player physics, presets, cloud layout. |

Object properties: name, model, kind, position / rotation / scale, texture (the model's own, none,
or any image under `obj/`), every material color (tints the texture), shininess,
roughness, unlit, visibility, cast / receive shadows, draw-distance culling, "Selectable in game",
"Follow terrain", and collision (none, box, cylinder, or mesh footprint for concave models like rock
rings and houses; C shows all colliders). An object's box / cylinder collider can be detached into a
standalone collider, which is moved, rotated and resized on its own (invisible in the game).

Lights (Place → Lights): point lights (all around) and spot lights (a cone; rotate to aim), with
color, intensity, range, falloff, cone angle and edge softness, steady / flicker / strobe / pulse
mode (flicker: time between blinks, random delay, blink length, blinks per burst, darkness and a
constant shimmer; strobe and pulse: rate), shadows, and a bounce (a soft light that fills the room around it,
as if reflected: where a spot's beam lands, or near the middle of a point light's room; amount and
reach). The editor shows them as bulbs you can click and drag; the game only
shows their light. The 4 enabled lights nearest the player shine at a time. With "Casts shadows",
walls block a light: a lamp inside a house lights the outside only through its doors and window
holes. The 3 shadow-casting point lights nearest the player (campfire included) get shadow maps, and
one spot light (a flashlight in hand first). Shadow maps of lights that don't move only re-render
when something near them changes.

Items: inventory name and type. Flashlights have a shadow-casting spotlight with color, intensity,
range, falloff, beam angle, edge softness, steady / flicker / strobe mode and rate, battery life,
"casts shadows", "on when found",
the model axis it shines along, and a live preview in the editor.

Axes: damage per swing, reach, seconds per swing, and which model axes are the head and the blade
(guessed automatically). What breaks is set where it lives: every object and foliage group has a
Breakable section (can be broken, needs axe / any tool / bare hands, hits to break, and two drops:
item name and count). Trees default to 4 axe hits for 3 wood. Breaking lasts for the play session.
Campfire flames (World tab): animated low-poly flames with height, width, number of tongues, speed,
flicker, sway, core / middle / tip colors and brightness, plus rising embers (count, color,
brightness, rise speed and height, size).
Campfire smoke (World tab): a continuous column with amount, size, growth, rise speed and height,
sway, color, opacity and an X / Y / Z offset.
Optional sounds: `sound/player/axe_hit.mp3` and `sound/player/break.mp3` play when present.

Colors: click a swatch for the color picker (saturation / brightness square, hue bar, palette,
recent colors, hex); every slider also has a field to type an exact value.

Camera: hold the right button to look and fly with WASD (Q/E down/up, Shift faster, wheel changes
the speed while flying); wheel zooms to the cursor; middle button orbits, Shift+middle pans; F frames
the selection. Ctrl+Z / Ctrl+Y undo and redo.

The top right buttons:
- **Play** saves and starts the game on this world.
- **Compile** bakes the static parts (simplified terrain chunks, foliage cells, objects that aren't
  selectable in the game merged per 25 m cell) into `saves/<name>/compiled/` and writes an analyzer
  report. The game loads the bake while the save is unchanged; otherwise it builds the world live.
- **Analyze** shows triangle and draw call counts and what costs most (heavy models, tiny shadow
  casters, buried or duplicated objects, expensive graphics settings).
- **Benchmark** measures the frame time with each expensive graphics feature turned off in turn.

## Performance

The CPU, not the GPU, limits this renderer: the scene is light for any recent GPU, while every render
pass costs CPU time even when it draws little. What keeps that down:
- **Frame pacing.** The default frame cap follows the display's refresh rate ("Display"); the loop
  sleeps between frames. An unfocused or minimized window drops to 15 fps ("Unfocused frame cap").
  Uncapped (Off, no vsync) the loop renders as fast as it can and keeps a core at 100% — that was
  the old default.
- **Shadow maps render only when something moved** (light, camera, objects), or at "Animated
  shadow rate" while swaying plants or drifting clouds cast shadows. The campfire's 6-pass cube map
  usually renders once.
- **Fast bloom** (default): one pass whose GPU mipmaps replace the 11-pass blur chain.
- **Terrain** is split into 64 chunks that cameras cull, each simplified where it stays within
  `Terrain simplification` (~140k triangles instead of 1.8M for the default world).
- **Compiled worlds** merge static objects and foliage into a few meshes.

For the default world at 1080p on an RTX 3070: 1.35 ms per frame uncapped (2.12 before), about 36% of
one core at 165 fps (49% before) and 15–19% at 60 fps. The overlay (top left in the game) shows
whole-machine CPU and whole-GPU utilization (`components/stats.py`, `usage.py`).

## Layout

| Python | |
|---|---|
| `main.py`, `editor.py`, `firewatch/app.py` | entry points, window, frame pacing (`js/app.js`) |
| `firewatch/scene.py` | component lists for the game and the editor (`js/component/scene.js`) |
| `firewatch/settings.py` | settings schema, presets, persistence |
| `firewatch/world/` | saves (`document.py`), the JS scene as a save (`legacy.py`), terrain, foliage, water, objects (`entities.py`), collisions, compiler / analyzer |
| `firewatch/editor/` | editor controller, tools, camera, overlays, undo, benchmark |
| `firewatch/library.py`, `objects.py` | model library (`obj/` scan, .mtl colors, mesh cache in `.cache/`) and per-model colors (`js/tools/object/manager.js`) |
| `firewatch/components/*` | environment (sun, moon, sky, fog), campfire, smoke, bird, clouds, snow, fireflies, stats |
| `firewatch/controls/*` | first person, selection, outline (`js/component/controls/*`) |
| `firewatch/pipeline.py`, `sun.py`, `point_shadow.py`, `shadow_cache.py` | post-processing chain and shadow maps |
| `firewatch/ui/` | settings panel and shared widgets |

World saves use Panda3D coordinates (Z up, meters, headings in degrees); `legacy.py` keeps the JS
`MAP` arrays in three.js coordinates and converts them.

## Rendering notes

- Colors are used as raw hex values. The JS app runs three.js r146 in legacy color mode and renders
  through an EffectComposer whose final FXAA pass skips sRGB encoding, so hex values reached the
  screen without gamma conversion.
- Lights use three's `physicallyCorrectLights` math: `color * intensity`, Lambert's `1 / PI`, the
  physical point light falloff, GGX specular for the terrain and objects with a roughness, and
  Blinn-Phong for everything else.
- The sun and the moon are separate directional lights; one shadow map follows the brighter one
  that casts shadows.
- Snowflakes (Sky tab): color, opacity, shape (round, soft, six-armed crystal, star, square), edge
  softness, spin and a motion streak, besides amount, size and fall speed.
- Snowflakes settle: a top-down depth map of the solid world around the player (re-rendered after
  moving 4 m or when the world changes) tells each flake where it lands; it stays there, turns the
  "Settled flake color" and fades over "Settled flakes fade over" seconds (Sky tab), then falls again
  elsewhere. Snow catches on the
  ground, objects and tree crowns; it sinks out of sight in water.
- Water reads the depth prepass for its depth: clear in the shallows, deep color further out, foam
  and a soft edge at the shore.
