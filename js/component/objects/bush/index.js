import {interactableAdd} from '../../../registry/interactableObjects.js';
import {objectManager} from "../../../tools/object/manager.js";

const place = (x, y, z, scale, scene) => {
    objectManager.get('bush-tree-harvest', (model) => {
        model.position.x = x;
        model.position.y = y;
        model.position.z = z;

        interactableAdd(model.uuid, model)
        scene.add(model)
    });
}

const draw = (scene, camera, renderer) => {
    const map = [
        [11, 0, 4, .25],
        [6.5, 0, -2.6, 0.27],
        [1.7, 0, -8.7, 0.27],
        [-2.9, 0, -2.4, .27]
    ];

    map.forEach((config) => {
        place(...config, scene)
    })
}

export {draw}