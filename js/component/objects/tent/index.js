import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';
import {interactableAdd} from '../../../registry/interactableObjects.js';

const draw = (scene, camera, renderer) => {
    const loader = registryGet('loader');
    loader.load('../../../../obj/tent.obj', (model) => {
        scene.add(model);
        model.position.set(3.5, 0, -6)
        // model.rotateY(29)
        model.traverse((child) => {
            if (child.isMesh) {
                child.material.some((material) => {
                    if (material.name.indexOf('brown') !== -1) {
                        material.color = new THREE.Color('#381801');
                    }
                    if (material.name.indexOf('green') !== -1) {
                        material.color = new THREE.Color('#d2d1d1');
                    }
                })
                child.receiveShadow = true;
                child.castShadow = true;
            }
        })
        interactableAdd(model.uuid, model)
    });
}

export {draw}