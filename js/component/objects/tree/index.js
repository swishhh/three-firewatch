import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';
import {objectManager} from "../../../tools/object/manager.js";
import {mergeMeshes} from "../../../tools/mesh";

const MAP = [
    [0, 0, 0, 1],
    [5,0, -9.5],
    [1.6, 0, -0.7, 0.6],
    [1.8, 0, 1.7, 0.4],
    [5.5, 0, .5, 0.6],
    [2.9, 0, -9.5, 0.7],
    [1.8, 0, -11, 1.1],
    [4, 0, -11.4, 1.3],
    [-1.8, 0, -4, 0.9],
    [-1.8, 0, -2.5, 0.5],
    [-.4, 0, -4.5, 0.65],
    [1, 0, -4.5, 0.9],
    [6, 0, -4, 0.81],
    [0, 0, -6.5, 1.2],
    [-2.5, 0, -6.6, 0.9],
    [-10.5, 0, 2.5, 1],
    [-4.5, 0, 0, .8],
    [-6, 0, -7, .4],
    [-6.9, 0, -6.4, .2],
    [-7.3, 0, -7.1, .4],
    [-13, 0, 2, .7],
    [-4.5, 0, -7.4, .74],
    [-4.5, 0, -9, .9],
    [-2.5, 0, -9.3, 1.1],
    [0, 0, -9, 1.3],
    [7.4, 0, -9, 1.2],
    [5.6, 0, -7, .95],
    [12, 0, -7.5, 1.2],
    [-8.3, 0, -3.8, 1],
    [-9, 0, -5.4, .5],
    [-5.5, 0, -12.5, 1.3],
    [-8.5, 0, -13, 1.6],
    [-14, 0, -.5, 1.1],
    [-10.1, 0, -2.2, .9],
    [-11, 0, 0, 1],
    [-5.5, 0, 1.5, .6],
    [-8, 0, 9.5, 1.3],
    [-9, 0, 7, .86],
    [-4.2, 0, 6.4, .77],
    [-6.2, 0, 6.9, 1.1],
    [-2.2, 0, 7.1, 1.3],
    [.3, 0, 7.5, .6],
    [-.5, 0, 9.1, .9],
    [11.6, 0, 2, 1.3],
    [13, 0, -5, 1.5],
    [-17, 0, -2.5, 1.55],
    [-18, 0, -5.5, 1.65],
    [-17.5, 0, -8.5, 1.45],
    [-17.5, 0, -12.5, 1.58],
    [-20.5, 0, -8.5, 1.39],
    [-14, 0, -13.5, 1.68],
    [-11.5, 0, -15, 1.7],
];

const draw = (scene, camera, renderer) => {
    // for (let i = 0; i < MAP.length; i++) {
    //     drawAnimated(...MAP[i])
    // }

    drawInstanced(scene, camera, renderer);
}

const drawInstanced = (scene, camera, renderer) => {
    let terrain = registryGet('terrain');

    objectManager.get('animated-tree', (gltf) => {
        const model = gltf.scene;
        const group = model.getObjectByName('Cylinder');
        const geometry = mergeMeshes(group.children)
        const material = new THREE.MeshPhongMaterial({
            reflectivity: false,
            shininess: 0,
            vertexColors: true
        });

        const instancedMesh = new THREE.InstancedMesh(geometry, material, MAP.length);

        instancedMesh.castShadow = true;
        instancedMesh.receiveShadow = true;

        // todo: run draw animate, inherit matrix from animated objects, update instanced mesh with matrix
        const dummy = new THREE.Object3D();
        for (let i = 0; i < MAP.length; i++) {
            let x,y,z,scale;
            [x,y,z,scale] = [...MAP[i]]

            if (y !== 0) {
                console.log(MAP[i])
            }
            dummy.position.x = x;
            dummy.position.y = y;
            dummy.position.z = z;
            dummy.scale.set(scale, scale, scale)

            terrain.relateY(dummy)

            dummy.updateMatrix();

            instancedMesh.setMatrixAt(i, dummy.matrix);
        }

        scene.add(instancedMesh)
    })
}

export {draw}