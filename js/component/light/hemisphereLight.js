import * as THREE from 'three';
import {getGui} from "../../registry/datGui.js";

const HemisphereLight = (color, intensity, addGui = false) => {
    // color = 0x0f1329;
    // let groundColor =  0x0f1329;
    // intensity = 3.9;

    color = 0xffffff;
    let groundColor =  0xffffff;
    intensity = .8;



    // intensity = 20;
    // color = 0x757b99;
    // groundColor = 0x757b99;






    const light = new THREE.HemisphereLight( color, groundColor, intensity );
    light.castShadow = false;
    window.hemiLight = light;

    if (true) {
        const folder = getGui().addFolder('World light');
        folder.add(light, 'intensity', 0, 10);
        folder.add(light, 'castShadow');
        folder.add(light, 'visible');
        folder.addColor({color: color}, 'color').onChange((value) => light.color.set(value));
        folder.addColor({groundColor: groundColor}, 'groundColor').onChange((value) => light.groundColor.set(value));
        folder.close();
    }

    return light;
}

export {HemisphereLight};