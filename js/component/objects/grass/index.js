import {objectManager} from "../../../tools/object/manager.js";
import {registryGet} from "../../../registry/registry.js";
import {InstancedManager} from "../../scene/InstancedManager.js";

const MAP = [
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

const draw = (scene, camera, renderer) => {
    objectManager.get('grass', (model) => {
        let terrain = registryGet('terrain');

        const instance = new InstancedManager(scene, model.children, MAP);
        instance.setRelateCallback((dummy) => {
            terrain.relateY(dummy)
        });

        instance.draw();
    });
}

export {draw}