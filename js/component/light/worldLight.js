import * as THREE from 'three';
import {getGui} from "../../registry/datGui.js";

const WorldLight = (color, intensity, addGui = false) => {
    const light = new THREE.AmbientLight(color, intensity);

    if (addGui) {
        const folder = getGui().addFolder('World light');
        folder.add(light, 'intensity', 0, 10);
        folder.add(light, 'visible', 0, 10);
        folder.addColor({color: color}, 'color').onChange((value) => light.color.set(value));
    }

    return light;
}

export {WorldLight};