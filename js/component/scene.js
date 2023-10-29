import { registryGet } from "../registry/registry.js";

const components = {
    'rocks': './objects/rocks/index.js',
    // 'lampPost': './objects/lampPost/index.js',
    'tent': './objects/tent/index.js',
    'clouds': './objects/clouds/index.js',
    'tree': './objects/tree/index.js',
    'terrain': './objects/terrain/index.js',
    // 'fireWatch': './objects/fireWatch/index.js',
    'snow': './objects/snow/index.js',
    // 'fireCamp': './objects/fireCamp/index.js',
    'fog': './objects/fog/index.js',
    'light': './light.js',
    'mapControls': './controls/map.js',
    'resize': './resize/index.js',
    'mouse': './controls/mouse.js',
    'mouseSelect': './controls/mouse/select.js',
    'outline': './action/object/outline.js'
}

async function draw() {
    const scene = registryGet('scene');
    const camera = registryGet('camera');
    const renderer = registryGet('renderer');
    for (const [name, path] of Object.entries(components)) {
        const component = await import(path);
        component.draw(scene, camera, renderer);
    }
}
export {draw}