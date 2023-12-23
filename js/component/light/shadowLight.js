import * as THREE from 'three';
import {getGui} from "../../registry/datGui.js";

const addShadowLight = (x, y, z, color, intensity) => {
    color = 0x758aff;
    x = 5.5;
    y = 10.5;
    const light = new THREE.DirectionalLight( color, intensity );
    light.position.set( x, y, z );

    light.castShadow = true;
    window.shadowLight = light;

    const d = 50;
    light.shadow.camera.left = - d;
    light.shadow.camera.right = d;
    light.shadow.camera.top = d;
    light.shadow.camera.bottom = - d;
    light.shadow.camera.near = .1;
    light.shadow.camera.far = 200;
    light.shadow.bias = 0;
    light.shadow.mapSize.width = 2048;
    light.shadow.mapSize.height = 2048;
    light.shadow.radius = 3;

    window.shadow = light.shadow;

    // if (true) {
    //     const folder = getGui().addFolder('Shadow light');
    //     folder.add(light, 'intensity', 0, 10);
    //     folder.add(light, 'castShadow');
    //     folder.add(light, 'visible');
    //     folder.add(light.position, 'x', -20, 30);
    //     folder.add(light.position, 'y', 0, 30);
    //     folder.add(light.position, 'z', -20, 30);
    //     folder.addColor({color: color}, 'color').onChange((value) => light.color.set(value));
    //
    //     const shadowFolder = folder.addFolder('Shadow');
    //     shadowFolder.add(light.shadow.camera, 'left', -40, 40)
    //     shadowFolder.add(light.shadow.camera, 'right', -40, 40)
    //     shadowFolder.add(light.shadow.camera, 'top', -40, 40)
    //     shadowFolder.add(light.shadow.camera, 'bottom', -40, 40)
    // }

    return light;
}

export {addShadowLight}