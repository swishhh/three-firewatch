import * as THREE from 'three';
import { HemisphereLight } from "./light/hemisphereLight.js";
import { addShadowLight} from "./light/shadowLight.js";

const MOON_LIGHT_COLOR = '#8fbaff';
const MOON_LIGHT_INTENSITY = 2;
const MOON_LIGHT_POSITION_X = -50;
const MOON_LIGHT_POSITION_Y = 100;
const MOON_LIGHT_POSITION_Z = 100;

const draw = (scene, camera, renderer) => {
    renderer.physicallyCorrectLights = true;
    // winter color 2c241c
    renderer.setClearColor('#4b6fc4');

    const hemisphereLight = HemisphereLight(
        MOON_LIGHT_COLOR,
        MOON_LIGHT_INTENSITY,
        {x: MOON_LIGHT_POSITION_X, y: MOON_LIGHT_POSITION_Y, z: MOON_LIGHT_POSITION_Z},
        false
    )

    window.worldLight = hemisphereLight;

    // let winter color 0xffe2c2
    const shadowLight = addShadowLight(-3, 5, 5, 0xffffff, 4)

    scene.add(hemisphereLight);
    scene.add(shadowLight);
}

export { draw }