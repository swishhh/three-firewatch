import { HemisphereLight } from "./light/hemisphereLight.js";
import { addShadowLight} from "./light/shadowLight.js";
import {getGui, isVisible} from "../registry/datGui.js";

const MOON_LIGHT_COLOR = '#8fbaff';
const MOON_LIGHT_INTENSITY = 2;
const MOON_LIGHT_POSITION_X = -50;
const MOON_LIGHT_POSITION_Y = 100;
const MOON_LIGHT_POSITION_Z = 100;

const COLOR_WINTER = 0x173e4f;
const COLOR_WARM_BLUE = 0x42a7f5;
const COLOR_WARM_SUMMER_EVENING = 0xb79071;

const draw = (scene, camera, renderer) => {
    renderer.physicallyCorrectLights = true;
    renderer.setClearColor(0x173e4f);

    // warm blue
    renderer.setClearColor(COLOR_WARM_SUMMER_EVENING);
    window.renderer = renderer;

    const hemisphereLight = HemisphereLight(
        MOON_LIGHT_COLOR,
        MOON_LIGHT_INTENSITY,
        {x: MOON_LIGHT_POSITION_X, y: MOON_LIGHT_POSITION_Y, z: MOON_LIGHT_POSITION_Z},
        false
    )

    // dark 1.1.
    const shadowLight = addShadowLight(-3, 5, 5, 0x009dff, 3.9)

    scene.add(hemisphereLight);
    scene.add(shadowLight);

    const worldGui = getGui().addFolder('World');
    worldGui.addColor({color: COLOR_WARM_SUMMER_EVENING}, 'color').onChange((value) => renderer.setClearColor(value));
}

export { draw }