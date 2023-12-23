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

const addRelativeObject = function (object) {
    this.relativeObjects[object.uuid] = object;
    object.fixRelativity = fixRelativeObject.bind(this, object.uuid)
    object.fixRelativity();
}

const fixRelativeObject = function (uuid = null) {
    if (!this.relativeObjects) return;

    let object = this.relativeObjects[uuid];

    if (!object) return;

    let geometry = this.geometry;
    let radius = (object.scale.x + object.scale.z) / 2;
    for (let i = 0; i < geometry.vertices.length; i += 3) {
        let x = geometry.attributes.position.array[i];
        let z = geometry.attributes.position.array[i + 2];

        let val = Math.pow(x - object.position.x, 2) + Math.pow(z - object.position.z, 2);
        if (val < Math.pow(radius, 2)) {
            let height = geometry.attributes.position.array[i + 1];
            let value = this.relativity[object.uuid];

            object.position.y = value !== undefined
                ? value
                : this.relativity[object.uuid] = object.position.y + height;
        }
    }
}

const relateY = function (object) {
    let geometry = this.geometry;
    let radius = (object.scale.x + object.scale.z) / 2;
    let heightsArray = [];
    for (let i = 0; i < geometry.vertices.length; i += 3) {
        let x = geometry.attributes.position.array[i];
        let z = geometry.attributes.position.array[i + 2];

        let val = Math.pow(x - object.position.x, 2) + Math.pow(z - object.position.z, 2);
        if (val < Math.pow(radius, 2)) {
            heightsArray.push(geometry.attributes.position.array[i + 1])
        }
    }
    if (heightsArray.length > 0) {
        let min = Math.min(...heightsArray)
        object.position.y += min;
    }
}

const draw = (scene, camera, renderer) => {
    const size = 50;
    const segments = 120;

    const geometry = new THREE.PlaneGeometry(size, size, segments, segments);
    const material = new THREE.MeshStandardMaterial( { color: 0x888888 } )
    // const material = new THREE.MeshStandardMaterial( { color: 0x1d3825 } )
    const terrain = new THREE.Mesh(geometry, material);

    geometry.rotateX(Math.PI * -0.5);
    terrain.receiveShadow = true;
    terrain.castShadow = true;
    terrain.showGrid = showGrid;

    terrain.relativity = {};
    terrain.addRelativeObject = addRelativeObject;
    terrain.fixRelativeObject = fixRelativeObject;
    terrain.relativeObjects = {};

    terrain.relateY = relateY

    scene.add(terrain) // interactable terrain
    registryAdd('terrain', terrain)// interactable terrain

    mergeVertices(geometry);
    geometry.vertices = geometry.attributes.position.array;

    // addWater(
    //     terrain,
    //     [
    //         {x: [0, 3], z: [1, 3]},
    //         {x: [0, 3], z: [3, 6]},
    //         {x: [3, 6], z: [1, 4]},
    //         {x: [3, 6], z: [4, 7]},
    //         {x: [3, 6], z: [7, 10]},
    //         {x: [3, 6], z: [10, 13]},
    //         {x: [3, 6], z: [13, 16]},
    //         {x: [3, 6], z: [16, 19]},
    //
    //         {x: [6, 9], z: [1, 4]},
    //         {x: [6, 9], z: [4, 7]},
    //         {x: [6, 9], z: [7, 10]},
    //         {x: [6, 9], z: [10, 13]},
    //         {x: [6, 9], z: [13, 16]},
    //         {x: [6, 9], z: [16, 19]},
    //
    //         {x: [0, 3], z: [16, 19]},
    //         {x: [-3, 0], z: [16, 19]}
    //     ]
    // );

    // addCircle(terrain, -5, 15, 3, 2);
    // addCircle(terrain, -6, 16, 3, 2.5);
    // addCircle(terrain, -7, 17, 3, 2);

    // ground
    addCircle(terrain, -1, 10, 2, .3);
    addCircle(terrain, -.5, 9, 2, .3);
    addCircle(terrain, 0, 8, 2, .2);
    addCircle(terrain, 1.5, 8, 2, .2);

    addCircle(terrain, -5, 1, 2, .2);
    addCircle(terrain, -11, 1, 2, .3);
    addCircle(terrain, -11, 1.5, 2, .25);
    addCircle(terrain, -11, 2, 2, .25);
    addCircle(terrain, -9, 2, 2, .15);
    addCircle(terrain, -13, 2, 2, .2);
    addCircle(terrain, -14, 1, 2, .3);

    addCircle(terrain, -5, 8, 2, .3);
    addCircle(terrain, -6, 8.5, 2, .25);
    addCircle(terrain, -7, 8, 2, .25);
    addCircle(terrain, -8, 8, 2, .2);
    addCircle(terrain, -7, 9, 2, .25);
    addCircle(terrain, -8, 8, 2, .3);


    addCircle(terrain, 1, 0, 2, .35);
    addCircle(terrain, 1, 0.5, 2, .15);
    addCircle(terrain, .5, 1.5, 2, .15);
    addCircle(terrain, .5, 1.8, 2, .1);
    addCircle(terrain, 7, 1.5, 2, .1);
    addCircle(terrain, 8, 2, 2, .25);
    addCircle(terrain, 8, 3, 2, .3);
    addCircle(terrain, 9, 4, 2, .2);

    // water
    // addCircle(terrain, -3, 2, 1.7, .8, -1);
    // addCircle(terrain, -1.5, 3.5, 1.7, .6, -1);
    // addCircle(terrain, .5, 4, 1.7, .6, -1);


    // addCircle(terrain, 4.5, 4, 3, .6, -1);
    // addCircle(terrain, 5, 5, 3, .7, -1);
    // addCircle(terrain, 5, 6, 2, .7, -1);
    // addCircle(terrain, 6, 6, 2, .7, -1);
    // addCircle(terrain, 6, 5.5, 2, .7, -1);
    // addCircle(terrain, 7, 5.5, 2, .7, -1);
    // addCircle(terrain, 8, 6, 2, .7, -1);
    // addCircle(terrain, 9, 6, 2, .7, -1);
    // addCircle(terrain, 10, 7, 2, .7, -1);
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

const addCircle = (
    terrain,
    centerX,
    centerZ,
    radius,
    strength,
    mod = 1
) => {
    const geometry = terrain.geometry;
    for (let i = 0; i < geometry.vertices.length; i += 3) {
        let x = geometry.attributes.position.array[i];
        let z = geometry.attributes.position.array[i + 2];

        let val = Math.pow(x - centerX, 2) + Math.pow(z - centerZ, 2);
        if (val < Math.pow(radius, 2)) {
            let distance = Math.sqrt(val);

            let newValue =  Math.sqrt(Math.pow(strength, 2) * Math.sqrt(Math.pow(radius, 2) - Math.pow(distance, 2)));
            let currValue = geometry.attributes.position.array[i + 1];
            geometry.attributes.position.array[i + 1] =
                Math.abs(newValue) > Math.abs(currValue) * mod ? newValue * mod : currValue;
        }
    }

    window.terrain = terrain;
    terrain.geometry.attributes.position.needsUpdate = true;
    // terrain.geometry.computeVertexNormals();
}

export {draw};