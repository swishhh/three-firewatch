import {interactableAdd} from '../../../registry/interactableObjects.js';
import {objectManager} from "../../../tools/object/manager.js";
import {registryGet} from "../../../registry/registry.js";

const place = (x, y, z, scale, scene) => {
    objectManager.get('grass', (model) => {
        let mesh = model.children[0];

        model.position.x = x;
        model.position.y = y;
        model.position.z = z;
        model.scale.set(scale, scale, scale);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        let terrain = registryGet('terrain');
        terrain.addRelativeObject(model);

        scene.add(model)
        interactableAdd(model.uuid, model)
    });
}

const draw = (scene, camera, renderer) => {
    const mapping = [
        [1.2, 0, -7.4, .5],
        [0, 0, -7.4, .5],
        [1.2, 0, -3.8, .5],
        [5.6, 0, -4.5, .5],
        [6.3, 0, -3, .5],
        [5.9, 0, -.8, .5],
        [9.6, 0, -0.5, .5],
        [10.6, 0, 1.9, .5],
        [10.6, 0, 3.5, .5],
        [-2.9, 0, -2, .6],
        [-4, 0, -.7, .6],
        [-.5, 0, -3.5, .6],
        [0, 0, 0, .6],
        [1.5, 0, -.7, .6],
        [2, -.1, .8, .6],
        [0, -.05, 1.5, .6],
    ];
    mapping.forEach((config) => {
        place(...config, scene);
    })
}

export {draw}