import {interactableAdd} from '../../../registry/interactableObjects.js';
import {objectManager} from "../../../tools/object/manager.js";

const draw = (scene, camera, renderer) => {
    objectManager.get('picnic-table', (model) => {
        let mesh = model.children[0];
        let scale = 0.25;

        model.rotateY(Math.PI / 1.2)
        model.position.x = 4.7;
        model.position.y = 0;
        model.position.z = -2;
        model.scale.set(scale,scale,scale);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        scene.add(model)
        interactableAdd(model.uuid, model)
    });
}

export {draw}