import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { addUpdateCallback } from "../../registry/update.js";

const draw = (scene, camera, renderer) => {
    let controls = new OrbitControls(camera, renderer.domElement);
    addUpdateCallback(controls.update);
}

export {draw}