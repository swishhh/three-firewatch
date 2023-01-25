import * as THREE from 'three';
import {registryGet} from "../../../registry/registry.js";

const x = .3;
const y = 0;
const z = 1.9;

const addFireCampLight = (scene, color, x, y, z, intensity, distance, blinking = false) => {
    let light = new THREE.PointLight(color, intensity, distance);
    light.castShadow = true;
    light.position.set(x, y, z);
    light.shadow.mapSize.width = 2048;
    light.shadow.mapSize.height = 2048;
    light.shadow.radius = 20;

    window.firecampLight = light;

    scene.add(light);
    blinking && setInterval(() => {
        let newIntensity = intensity - (Math.random() / 1.5);
        if (newIntensity <= 1.5) {
            newIntensity+= 0.4;
        }
        light.intensity = newIntensity;
        light.position.y = y + ((intensity - newIntensity) / 5);
    }, 100);
}

const draw = (scene, camera, renderer) => {
    const loader = registryGet('loader');
    loader.load('../../../../obj/firecamp.obj', (model) => {
        scene.add(model);
        model.position.set(x, y, z)
        model.scale.set(.3, .3, .3);
        model.rotateY(45)
        model.traverse((child) => {
            if (child.isMesh) {
                if (child.name.indexOf('tree') !== -1) {
                    child.material.color = new THREE.Color('#bd8446');
                } else if (child.name.indexOf('rock') !== -1) {
                    child.material.color = new THREE.Color('#2f2f2d');
                } else if (child.name.indexOf('cauldron') !== -1) {
                    child.material.color = new THREE.Color('#131313');
                } else if (child.name.indexOf('fire') !== -1) {
                    child.material.color = new THREE.Color('#d21201');
                }
            }
        })
    });
    addFireCampLight(scene, '#ff4d00', 0, 1, 2, 2, 10, true);
}

export {draw}