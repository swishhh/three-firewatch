import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';
import {addUpdateCallback} from "../../../registry/update.js";

const map = [
    [
        [-1, 16, 1], [.7, .7, .7]
    ],
    [
        [-10, 13, -3], [.6, .5, .6]
    ],
    [
        [5, 14, 4], [.4, .4, .4]
    ],
    [
        [9, 15, -4], [.8, .8, .8]
    ],
    [
        [-2, 12.5, -10], [.3, .3, .3]
    ],
    [
        [-5, 14, 8], [.9, .9, .9]
    ],
    [
        [8, 13, 10], [.25, .25, .25]
    ],
];

const makeCloudMovable = (
    cloud,
    moveByAxis,
    maxAxisValue,
    minAxisValue,
    step,
    opacityThreshold
) => {
    cloud.material.transparent = true;
    step = step / cloud.scale.z;
    let callback = () => {
        let vector = new THREE.Vector3(
            cloud.position.x,
            cloud.position.y,
            cloud.position.z
        );
        vector[moveByAxis] += step;
        if (vector[moveByAxis] > maxAxisValue) {
            vector[moveByAxis] = minAxisValue
        }
        cloud.position.lerp(vector, 1);
        let pos = vector[moveByAxis];
        pos = (Math.abs(pos > opacityThreshold ? maxAxisValue : minAxisValue) - Math.abs(pos))
        cloud.material.opacity = (pos / step) * (1 / (opacityThreshold / step));
    }

    addUpdateCallback(callback.bind(cloud, moveByAxis, step, maxAxisValue, minAxisValue, opacityThreshold));
}

const draw = (scene, camera, renderer) => {
    const loader = registryGet('loader');
    loader.load('../../../../obj/cloud.obj', (model) => {
        let object = model.children.pop();
        object.material = new THREE.MeshBasicMaterial({
            color: 0xffffff,
            transparent: true
        });
        for (let i = 0; i < map.length; i++) {
            let cloud = new THREE.Mesh(object.geometry.clone(), object.material.clone());
            cloud.position.set(...map[i][0])
            cloud.scale.set(...map[i][1])
            cloud.receiveShadow = true;
            cloud.castShadow = true;
            cloud.material.shininess = 0;
            cloud.material.reflectivity = false;
            scene.add(cloud);
            makeCloudMovable(
                cloud,
                'z',
                18,
                -18,
                0.007,
                3
            )
        }
    });
}

export {draw}