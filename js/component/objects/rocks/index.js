import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';

const position = [5.8, -.6, 1.3];
const rotateYDeg = 90;

const draw = (scene, camera, renderer) => {
    const loader = registryGet('loader');
    loader.load('../../../../obj/rocks.obj', (model) => {
        window.rocks = model;
        scene.add(model);
        model.rotateY(rotateYDeg)
        model.position.set(...position)
        model.traverse((child) => {
            if (child.isMesh) {
                if (child.name.indexOf('Icosphere') !== -1) {
                    child.material.color = new THREE.Color('#656563');
                }
                child.receiveShadow = true;
                child.castShadow = true;
            }
        })
    });
}

export {draw};