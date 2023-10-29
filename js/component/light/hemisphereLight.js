import * as THREE from 'three';
import {getGui} from "../../registry/datGui.js";

const HemisphereLight = (color, intensity, addGui = false) => {
    const light = new THREE.HemisphereLight( 0xffddad, 0xffddad, 1 );
    light.castShadow = false;

    return light;
}

export {HemisphereLight};