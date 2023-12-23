import {interactableAdd} from '../../../registry/interactableObjects.js';
import {objectManager} from "../../../tools/object/manager.js";

const draw = (scene, camera, renderer) => {
    objectManager.load('tent', (model) => {
        model.position.set(3.5, 0, -6)

        interactableAdd(model.uuid, model)

        scene.add(model);
    })
}

export {draw}