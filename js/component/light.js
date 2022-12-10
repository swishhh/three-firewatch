import { registryGet } from "../registry/registry.js";
import { WorldLight } from "./light/worldLight.js";
import { MoonLight } from "./light/moonLight.js";

const AMBIENT_LIGHT_COLOR = '#32385d';
const AMBIENT_LIGHT_INTENSITY = .9;

const MOON_LIGHT_COLOR = '#8fbaff';
const MOON_LIGHT_INTENSITY = .8;
const MOON_LIGHT_POSITION_X = -50;
const MOON_LIGHT_POSITION_Y = 100;
const MOON_LIGHT_POSITION_Z = 100;

const Light = () => {
    const worldLight = WorldLight(
        AMBIENT_LIGHT_COLOR,
        AMBIENT_LIGHT_INTENSITY,
        true
    );
    const moonLight = MoonLight(
        MOON_LIGHT_COLOR,
        MOON_LIGHT_INTENSITY,
        {x: MOON_LIGHT_POSITION_X, y: MOON_LIGHT_POSITION_Y, z: MOON_LIGHT_POSITION_Z},
        true
    );

    let scene = registryGet('scene');

    scene.add(worldLight)
    scene.add(moonLight)
}

export { Light }