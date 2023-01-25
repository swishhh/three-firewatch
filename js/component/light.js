import { WorldLight } from "./light/worldLight.js";
import { MoonLight } from "./light/moonLight.js";

const AMBIENT_LIGHT_COLOR = '#32385d';
const AMBIENT_LIGHT_INTENSITY = .9;

const MOON_LIGHT_COLOR = '#8fbaff';
const MOON_LIGHT_INTENSITY = .8;
const MOON_LIGHT_POSITION_X = -50;
const MOON_LIGHT_POSITION_Y = 100;
const MOON_LIGHT_POSITION_Z = 100;

const draw = (scene, camera, renderer) => {
    renderer.physicallyCorrectLights = false;
    renderer.setClearColor('#415475');
    const worldLight = WorldLight(
        AMBIENT_LIGHT_COLOR,
        AMBIENT_LIGHT_INTENSITY,
        false
    );
    const moonLight = MoonLight(
        MOON_LIGHT_COLOR,
        MOON_LIGHT_INTENSITY,
        {x: MOON_LIGHT_POSITION_X, y: MOON_LIGHT_POSITION_Y, z: MOON_LIGHT_POSITION_Z},
        false
    );

    scene.add(worldLight)
    scene.add(moonLight)
}

export { draw }