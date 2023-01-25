import * as THREE from 'three';
import {registryGet} from '../../registry/registry.js';

const addPointLight = (color, x, y, z, intensity, distance, blinking = false, castShadow = true) => {
    const scene = registryGet('scene');
    const light = new THREE.PointLight(color, blinking ? 0 : intensity, distance);
    light.position.set(x, y, z);
    scene.add(light);
    light.castShadow = castShadow;
    blinking && setInterval(() => {
        light.intensity = intensity;
        setTimeout(() => {
            light.intensity = 0;
        }, 500);
    }, 2000);
}

export {addPointLight}