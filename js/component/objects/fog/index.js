import { Fog } from 'three';
import { getGui } from "../../../registry/datGui.js";

const FOG_COLOR = '#0f1329';
const FOG_NEAR = 1;
const FOG_FAR = 70;
const FOG_GUI = false;

const draw = (scene, camera, renderer) => {
    scene.fog = new Fog(FOG_COLOR, FOG_NEAR, FOG_FAR)
    if (FOG_GUI) {
        let datGui = getGui();
        let folder = datGui.addFolder('Fog');
        folder.add(scene.fog, 'near', 0, 10);
        folder.add(scene.fog, 'far', 0, 1000);
        folder.addColor({color: FOG_COLOR}, 'color').onChange((value) => scene.fog.color.set(value));
    }
}

export {draw}