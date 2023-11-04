import { MapControls } from '../../../lib/addons/controls/MapControls.js';
import { addUpdateCallback } from "../../registry/update.js";
import { registryAdd } from "../../registry/registry.js";

const smoothCamera = false;
const minDistance = 3;
const maxDistance = 25;
const maxPolarAngle = (Math.PI / 2) - .15;

const draw = (scene, camera, renderer) => {
    let controls = new MapControls(camera, renderer.domElement);

    if (smoothCamera) {
        controls.enableDamping = true;
        controls.dampingFactor = .3;
    }

    controls.minDistance = minDistance;
    controls.maxDistance = maxDistance;
    controls.maxPolarAngle = maxPolarAngle;

    addUpdateCallback(controls.update);
    registryAdd('mapControls', controls);
}

export {draw}