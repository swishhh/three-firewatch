import { FogExp2 } from 'three';
import { getGui } from "../../../registry/datGui.js";
import {localStorageGet, localStorageSet} from "../../../tools/local/storage.js";

const FOG_GUI = true;
const DEFAULT_DENSITY = 0.028;
const DEFAULT_COLOR = 0x173e4f;

const WARM_COLOR_ORANGE = 0xcc5200;

const draw = (scene, camera, renderer) => {
    let storageDensity = localStorageGet('fogDensity');
    let storageColor = localStorageGet('fogColor');

    scene.fog = new FogExp2(
        storageColor ? storageColor : WARM_COLOR_ORANGE,
        storageDensity ? parseFloat(storageDensity) : DEFAULT_DENSITY
    );

    FOG_GUI && addGui(scene);
}

const addGui = (scene) => {
    let folder = getGui().addFolder('Fog');

    folder.add(scene.fog, 'density', 0, .15).onChange(function (value) {
        localStorageSet('fogDensity', value)
    });
    folder.addColor({color: '#' + scene.fog.color.getHexString()}, 'color').onChange(function (value) {
        scene.fog.color.set(value)
        localStorageSet('fogColor', value)
    });
    folder.close();

}

export {draw}