import { FogExp2 } from 'three';
import { getGui } from "../../../registry/datGui.js";

const FOG_GUI = true;

const draw = (scene, camera, renderer) => {
    // let density = 0.08;
    // let color = 0x0f1329;

    let density = 0.06;
    let color = 0x173e4f;

    // let density = 0;
    scene.fog = new FogExp2(color, density);
    window.fog = scene.fog;
    if (FOG_GUI) {
        let datGui = getGui();
        let folder = datGui.addFolder('Fog');
        folder.add(scene.fog, 'density', 0, .15);
        folder.addColor({color: color}, 'color').onChange((value) => scene.fog.color.set(value));
        folder.close()
    }
}

export {draw}