# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Three.js 3D scene inspired by the Firewatch game aesthetic. It renders an outdoor environment with terrain, trees, rocks, fog, snow, campfire, and other objects using vanilla ES modules (no bundler).

## Running the Project

Serve with any static HTTP server from the project root (e.g., `npx serve .` or `python3 -m http.server`). The app loads via `index.html` using an import map that aliases `three` and `three/addons/` to local copies in `lib/`.

There is no build step, no bundler, no test suite, and no linter.

## Architecture

### Entry Point & Render Loop
- `js/app.js` — Creates scene, camera, renderer, registers them in the global registry, then calls `draw()` and starts the `animate()` loop. The animate loop calls all registered update callbacks each frame with `clock.getDelta()`.

### Registry (Global State)
- `js/registry/registry.js` — Simple key-value store (`registryAdd`/`registryGet`) used to share scene, camera, renderer, loaders, and other objects across modules without import coupling.
- `js/registry/update.js` — Stores per-frame update callbacks. Components register via `addUpdateCallback(fn)`.
- `js/registry/interactableObjects.js` — Tracks which scene objects are interactable (for raycasting/selection).

### Component System
- `js/component/scene.js` — Declares all components in a `components` map (name → relative path). The `draw()` function dynamically imports each component and calls its `draw(scene, camera, renderer)` function. Components are commented out to disable them.
- Every component in `js/component/objects/*/index.js` exports a `draw(scene, camera, renderer)` function. This is the standard component interface.

### Key Subsystems
- **Instanced rendering**: `js/component/scene/InstancedManager.js` — Manages `THREE.InstancedMesh` for placing many copies of an object (trees, grass, rocks) from a coordinate map.
- **Object loading**: `js/tools/object/manager.js` — Centralized GLTF/OBJ model loading with caching.
- **Controls**: `js/component/controls/` — Map controls (OrbitControls), mouse interaction, object manipulation, toolbar UI.
- **Toolbar**: `js/component/controls/toolbar/Toolbar.js` — Custom HTML toolbar for placing objects, with folder/item hierarchy and icon management.
- **Lighting**: `js/component/light.js` aggregates individual lights from `js/component/light/`.
- **Post-processing**: Configured in `js/component/renderer/index.js` using EffectComposer.

### Conventions
- Object positions are defined as coordinate arrays (MAP arrays) inside each component, e.g., `[x, y, z, scale]`.
- Three.js and addons are vendored in `lib/` (not installed from npm at runtime). The `package.json` exists but the app uses import maps, not node_modules.
- 3D models live in `obj/` (GLTF/OBJ), textures in `textures/`.
- GUI controls use lil-gui (`lib/addons/libs/lil-gui.module.min.js`) via `js/registry/datGui.js`.
