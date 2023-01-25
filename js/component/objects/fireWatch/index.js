import * as THREE from 'three';
import {registryGet} from "../../../registry/registry.js";
import {addPointLight} from "../../light/pointLight.js";

const position = [-7, 0 , -7];
const scale = [.040, .050, .040];
const rotateY = Math.PI * -1.7;

const draw = (scene, camera, renderer) => {
    const loader = registryGet('loader');
    loader.load('obj/firewatch.obj', (model) => {
        scene.add(model);
        model.position.set(...position);
        model.scale.set(...scale);
        model.rotateY(rotateY)

        let glassMaterial = new THREE.MeshPhysicalMaterial({
            reflectivity: 1.0,
            transmission: 1.0,
            roughness: 0,
            metalness: 0,
            color: new THREE.Color('#9f9fbd'),
            ior: 5,
            thickness: .5
        });
        model.traverse((child) => {
            if (child.isMesh) {
                let materialName = child.material.name;
                let material = child.material;
                if (materialName.indexOf('roof') !== -1) {
                    material.color = new THREE.Color('#850707');
                } else if (materialName.indexOf('wood') !== -1) {
                    material.color = new THREE.Color('#251106');
                } else if (materialName.indexOf('Door') !== -1) {
                    material.color = new THREE.Color('#251106');
                } else if (materialName.indexOf('glass') !== -1) {
                    child.material = glassMaterial;
                    window.glass = child.material;
                } else if (materialName.indexOf('rock') !== -1) {
                    material.color = new THREE.Color('#7c7c7c');
                } else if (materialName.indexOf('iron') !== -1) {
                    material.color = new THREE.Color('#0c0c0c');
                } else if (materialName.indexOf('stairs') !== -1) {
                    material.color = new THREE.Color('#0c0c0c');
                } else if (materialName.indexOf('foundation') !== -1) {
                    material.color = new THREE.Color('#0c0c0c');
                } else if (materialName.indexOf('whiteMetal') !== -1) {
                    material.color = new THREE.Color('#282828');
                } else if (materialName.indexOf('wall') !== -1) {
                    material.color = new THREE.Color('#572c16');
                } else if (materialName.indexOf('anten') !== -1) {
                    let position = child.getWorldPosition(new THREE.Vector3())
                    addPointLight('#ff0000', position.x, 7.7, position.z, 4, .65, true)
                    material.color = new THREE.Color('#ff0000');
                } else if (materialName.indexOf('Door') !== -1) {
                    material.color = new THREE.Color('#251106');
                }

                child.castShadow = true;
                child.receiveShadow = true;
            }
        });
    });
}

export {draw}