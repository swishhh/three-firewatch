import {interactableAdd} from '../../../registry/interactableObjects.js';
import {objectManager} from "../../../tools/object/manager.js";
import {registryGet} from '../../../registry/registry.js';

const draw = (scene, camera, renderer) => {
    objectManager.get('welcome-sign', (model) => {
        let mesh = model.children[0];
        let scale = 0.4;

        // model.rotateY(74.5)
        model.rotateY(20)

        model.position.x = -4.2;
        model.position.y = 0;
        model.position.z = 1.7;
        model.scale.set(scale,scale,scale);
        mesh.castShadow = true;
        mesh.receiveShadow = true;

        let terrain = registryGet('terrain');
        terrain.addRelativeObject(model);

        scene.add(model)
        interactableAdd(model.uuid, model)
    });
}

export {draw}