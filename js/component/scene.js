import { registryGet } from "../registry/registry.js";
import {initSceneRenderer} from "./renderer/index.js";

const components = {
    'terrain': './objects/terrain/index.js',
    'rocks': './objects/rocks/index.js',
    // 'lampPost': './objects/lampPost/index.js',
    'tent': './objects/tent/index.js',
    'clouds': './objects/clouds/index.js',
    'tree': './objects/tree/index.js',
    'bush': './objects/bush/index.js',
    'grass': './objects/grass/index.js',
    // 'water': './objects/water/index.js',
    'campFire': './objects/campFire/index.js',
    'picnicTable': './objects/picnicTable/index.js',
    'welcomeSign': './objects/welcomeSign/index.js',
    'bird': './objects/bird/index.js',
    // 'house': './objects/house/index.js',
    // 'fireWatch': './objects/fireWatch/index.js',
    'snow': './objects/snow/index.js',
    // 'fireCamp': './objects/fireCamp/index.js',
    'fog': './objects/fog/index.js',
    'light': './light.js',
    'mapControls': './controls/map.js',
    'resize': './resize/index.js',
    'mouse': './controls/mouse.js',
    'toolbar': './controls/toolbar.js',
    'object': './controls/object.js',
    // 'mouseSelect': './controls/mouse/select.js',
    'outline': './action/object/outline.js',
    'stats': './stats.js',
}

async function draw() {
    const scene = registryGet('scene');
    const camera = registryGet('camera');
    const renderer = registryGet('renderer');
    for (const [name, path] of Object.entries(components)) {
        const component = await import(path);
        component.draw(scene, camera, renderer);
    }

    initSceneRenderer(scene, camera, renderer);
}

export {draw}