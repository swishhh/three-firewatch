import {registryGet} from '../../../registry/registry.js';
import {interactableAdd} from '../../../registry/interactableObjects.js';
import {objectManager} from "../../../tools/object/manager.js";

const position = [10.2, -.6, -2];
const rotateYDeg = 90;

const draw = (scene, camera, renderer) => {
    objectManager.get('rocks', (model) => {
        scene.add(model);
        model.rotateY(rotateYDeg)
        model.position.set(...position)
    });

    objectManager.get('rocks-array', (model) => {
        let mesh = model.children[0];
        let scale = 1.4;

        model.position.x = -10;
        model.position.y = 0;
        model.position.z = -5;
        model.scale.set(scale,scale,scale);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        scene.add(model)
        interactableAdd(model.uuid, model)
    });

    objectManager.get('small-rocks-array', (model) => {
        let mesh = model.children[0];
        let scale = .5;

        model.position.x = -3;
        model.position.y = 0;
        model.position.z = 5;
        model.scale.set(scale,scale,scale);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        let terrain = registryGet('terrain');
        terrain.addRelativeObject(model);

        scene.add(model)
        interactableAdd(model.uuid, model)
    });

    objectManager.get('tiny-rock-vertical', (model) => {
        let mesh = model.children[0];
        let scale = .5;

        model.position.x = 1;
        model.position.y = 0;
        model.position.z = 2;
        model.scale.set(scale,scale,scale);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        let terrain = registryGet('terrain');
        terrain.addRelativeObject(model);

        scene.add(model)
        interactableAdd(model.uuid, model)
    });
}

export {draw};