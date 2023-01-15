import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { registryGet } from "../../registry/registry.js";
import { addUpdateCallback } from "../../registry/update.js";

const addOrbitControls = () => {
    let controls = new OrbitControls(registryGet('camera'), registryGet('renderer').domElement);
    addUpdateCallback(controls.update);
    controls.enabled = false;
}

export {addOrbitControls}