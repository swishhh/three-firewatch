import {Vector2, Raycaster} from 'three';
import {registryGet} from "../../../registry/registry.js";
import {roundPositionValue} from "../../../tools/position/roundXZAxis.js";
import { outline, removeOutline } from "../../action/object/outline.js";

const camera = registryGet('camera');
const scene = registryGet('scene');
const terrain = registryGet('terrain');

const cursor = new Vector2();
const ray = new Raycaster();

let config;
let events = false;

const runPlacement = (object) => {
    if (!events) declareEvents();

    config = {
        object: object,
        scene: false
    }

    outline(config.object)
    terrain.showGrid(true);
}

const disable = () => {
    config = null;
    terrain.showGrid(false);
}

const rightClick = () => {
    if (config && config.scene) {
        config.object.parent.remove(config.object);
        removeOutline(config.object);
        disable();
    }
}

const mouseUp = () => {
    if (config && config.object) {
        removeOutline(config.object);
        disable();
    }
}

const pointerMove = (e) => {
    if (!config) return;

    cursor.x = (e.clientX / window.innerWidth) * 2 - 1;
    cursor.y = -(e.clientY / window.innerHeight) * 2 + 1;
    ray.setFromCamera(cursor, camera);

    ray.intersectObjects([terrain]).forEach((intersection) => {
        if (intersection.point.y === terrain.position.y) {
            config.object.position.x = roundPositionValue(intersection.point.x);
            config.object.position.z = roundPositionValue(intersection.point.z);
            config.object.position.y = intersection.point.y;
            if (!config.scene) {
                scene.add(config.object)
                config.scene = true;
            }
        }
    });
}

const declareEvents = () => {
    window.addEventListener('pointermove', pointerMove);
    window.addEventListener('mouseup', mouseUp);
    window.addEventListener('contextmenu', rightClick);

    events = true;
}

export {runPlacement};