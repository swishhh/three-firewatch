import * as THREE from 'three';
import { registryAdd } from "../../../registry/registry.js";
import {mergeVertices} from '../../../../lib/addons/jsm/utils/BufferGeometryUtils.js';
import {registryGet} from '../../../registry/registry.js';

let scene = registryGet('scene');

const showGrid = function (visible) {
    if (visible) {
        let parameters = this.geometry.parameters;
        let size = parameters.width > parameters.height ? parameters.width : parameters.height;
        this.gridHelper = new THREE.GridHelper(size, size * 2);
        this.gridHelper.dispose();
        this.gridHelper.position.copy(this.position);
        scene.add(this.gridHelper);
    } else if (this.gridHelper) {
        this.gridHelper.parent.remove(this.gridHelper)
    }
}

const draw = (scene, camera, renderer) => {
    const size = 50;
    const segments = 30;

    const geometry = new THREE.PlaneGeometry(size, size, segments, segments);
    // const material = new THREE.MeshPhongMaterial( { color: 0x888888 } ) // winter
    const material = new THREE.MeshPhongMaterial( { color: 0x124a1b } )
    const terrain = new THREE.Mesh(geometry, material);

    geometry.rotateX(Math.PI * -0.5);
    terrain.receiveShadow = true;
    terrain.showGrid = showGrid;

    scene.add(terrain) // interactable terrain
    registryAdd('terrain', terrain)// interactable terrain


    mergeVertices(geometry);
    geometry.vertices = geometry.attributes.position.array;

    addWater(
        terrain,
        [
            {x: [0, 3], z: [1, 3]},
            {x: [0, 3], z: [3, 6]},
            {x: [3, 6], z: [1, 4]},
            {x: [3, 6], z: [4, 7]},
            {x: [3, 6], z: [7, 10]},
            {x: [3, 6], z: [10, 13]},
            {x: [3, 6], z: [13, 16]},
            {x: [3, 6], z: [16, 19]},

            {x: [6, 9], z: [1, 4]},
            {x: [6, 9], z: [4, 7]},
            {x: [6, 9], z: [7, 10]},
            {x: [6, 9], z: [10, 13]},
            {x: [6, 9], z: [13, 16]},
            {x: [6, 9], z: [16, 19]},

            {x: [0, 3], z: [16, 19]},
            {x: [-3, 0], z: [16, 19]}
        ]
    );
}

const isInCoordinatesRange = (x, z, coordinates) => {
    let result = false;
    coordinates.forEach((item) => {
        let [x1, x2] = item.x;
        let [z1, z2] = item.z;

        if ((x >= x1 && x <= x2) && (z >= z1 && z <= z2)) {
            result = true;
        }
    });

    return result;
}

const addWater = (terrain, coordinates) => {
    const geometry = terrain.geometry;

    for (let i = 0; i < geometry.vertices.length; i += 3) {
        let x = geometry.attributes.position.array[i];
        let z = geometry.attributes.position.array[i +2];

        if (isInCoordinatesRange(x, z, coordinates)) {
            geometry.attributes.position.array[i + 1] = (Math.random() + 4) * -1;
        }
    }

    terrain.geometry.attributes.position.needsUpdate = true;
}

export {draw};