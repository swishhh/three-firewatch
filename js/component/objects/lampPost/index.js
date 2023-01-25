import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';
import {addPointLight} from "../../light/pointLight.js";

const draw = (scene, camera, renderer) => {
    const loader = registryGet('loader');
    loader.load('../../../../obj/lamp-post.obj', (model) => {
        window.lamp = model;
        scene.add(model);
        model.position.set(-3, 0, -5);
        model.scale.set(.3, .3, .3);
        model.rotateY(Math.PI * -1.9)
        // model.rotateY(rotateY)
        model.traverse((child) => {
            if (child.isMesh) {
                let materialName = child.material.name;
                let material = child.material;
                if (materialName.indexOf('rock') !== -1) {
                    material.color = new THREE.Color('#505050');
                } else if (materialName.indexOf('wood') !== -1) {
                    material.color = new THREE.Color('#251106');
                } else if (materialName.indexOf('grass') !== -1) {
                    material.color = new THREE.Color('#06250a');
                } else if (materialName.indexOf('iron') !== -1) {
                    material.color = new THREE.Color('#0c0c0c');
                } else if (materialName.indexOf('glass') !== -1) {
                    material.color = new THREE.Color('#ffffff');
                    material.emissive.r = 255;
                    let position = child.getWorldPosition(new THREE.Vector3())
                    addPointLight('#ff4d00', position.x - 1, 1.75, position.z + .5, 1.5, 25)
                }

                child.castShadow = true;
                child.receiveShadow = true;
            }
        });
    });
}

export {draw};