import * as THREE from 'three';
import {getGui} from "../../registry/datGui.js";

const HemisphereLight = (color, intensity, addGui = false) => {
    const light = new THREE.HemisphereLight( 0xffddad, 0xffddad, intensity );
    light.castShadow = false;
    window.hemiLight = light;

    return light;
}

export {HemisphereLight};