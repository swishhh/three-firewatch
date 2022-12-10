import * as THREE from 'three';
import { GUI } from 'three/addons/libs/lil-gui.module.min.js';

const AmbientLight = (color, intensity, scene, addGui = false) => {
    const light = new THREE.AmbientLight(color, intensity);
    scene.add(light);

    if (addGui) {
        const datGui = new GUI();
        const folder = datGui.addFolder('World light');
        folder.add(light, 'intensity', 0, 10);
        folder.addColor({color: color}, 'color').onChange((value) => light.color.set(value));
    }
}

export {AmbientLight};