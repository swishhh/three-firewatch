import * as THREE from 'three';
import { HemisphereLight } from "./light/hemisphereLight.js";
import { addShadowLight} from "./light/shadowLight.js";

const MOON_LIGHT_COLOR = '#8fbaff';
const MOON_LIGHT_INTENSITY = .8;
const MOON_LIGHT_POSITION_X = -50;
const MOON_LIGHT_POSITION_Y = 100;
const MOON_LIGHT_POSITION_Z = 100;

const draw = (scene, camera, renderer) => {
    renderer.physicallyCorrectLights = true;
    // renderer.setClearColor('#415475');
    // 121212
    renderer.setClearColor('#2c241c');

    const hemisphereLight = HemisphereLight(
        MOON_LIGHT_COLOR,
        MOON_LIGHT_INTENSITY,
        {x: MOON_LIGHT_POSITION_X, y: MOON_LIGHT_POSITION_Y, z: MOON_LIGHT_POSITION_Z},
        false
    )

    const shadowLight = addShadowLight(-3, 5, 5, 0xffe2c2, 1.2)

    scene.add(hemisphereLight);
    scene.add(shadowLight);
}

export { draw }