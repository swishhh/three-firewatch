import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';
import {interactableAdd} from '../../../registry/interactableObjects.js';

const position = [10.2, -.6, -2];
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
                    child.material.color = new THREE.Color('#383838');
                }
                child.receiveShadow = true;
                child.castShadow = true;
                interactableAdd(child.uuid, child)
            }
        })
    });
}

export {draw};