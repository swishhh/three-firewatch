import * as THREE from 'three';
import {getGui} from "../../registry/datGui.js";

const addShadowLight = (x, y, z, color, intensity) => {
    const light = new THREE.DirectionalLight( color, intensity );
    light.position.set( x, y, z );

    light.castShadow = true;

    const d = 20;
    light.shadow.camera.left = - d;
    light.shadow.camera.right = d;
    light.shadow.camera.top = d;
    light.shadow.camera.bottom = - d;
    light.shadow.camera.near = .1;
    light.shadow.camera.far = 20;
    light.shadow.bias = 0;


    if (true) {
        const folder = getGui().addFolder('Shadow light');
        folder.add(light, 'intensity', 0, 4);
        folder.add(light, 'castShadow');
        folder.add(light, 'visible');
        folder.add(light.position, 'x', -10, 10);
        folder.add(light.position, 'y', 0, 10);
        folder.add(light.position, 'z', -10, 10);
        folder.addColor({color: color}, 'color').onChange((value) => light.color.set(value));
        folder.add(light.shadow, 'bias', -1, 1);
    }

    return light;
}

export {addShadowLight}