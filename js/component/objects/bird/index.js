import * as THREE from 'three';
import {interactableAdd} from '../../../registry/interactableObjects.js';
import {objectManager} from "../../../tools/object/manager.js";
import {addUpdateCallback} from "../../../registry/update.js";

const draw = (scene, camera, renderer) => {
    const scale = .025;
    const clock = new THREE.Clock();

    objectManager.get('animated-bird', (gltf) => {
        const model = gltf.scene;
        scene.add(model)

        model.scale.set(scale,scale,scale)
        model.position.y = 7;

        model.mixer = new THREE.AnimationMixer(model);
        model.clip = THREE.AnimationClip.findByName(gltf.animations, 'ArmatureAction');
        model.fly = function (duration = 2.5, run = true) {
            model.clip.duration = 2.5;
            let action = this.mixer.clipAction(model.clip);
            run ? action.play() : action.stop();
        }
        model.updateCallback = function () {
            this.mixer.update(clock.getDelta())
        }

        model.fly();

        addUpdateCallback(model.updateCallback.bind(model))
    });
}

export {draw}