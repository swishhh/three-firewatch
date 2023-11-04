import * as THREE from 'three';
import { isInteractable } from "../../../registry/interactableObjects.js";
import { outline, removeOutline } from "../../action/object/outline.js";
import { registryGet } from "../../../registry/registry.js";

let selected = null;

const select = (object, forceUnselect = false) => {
    if (object) {
        if (selected && selected.uuid === object.uuid) {
            removeOutline(selected);
            selected = null;
        } else {
            if (selected) {
                removeOutline(selected);
            }
            selected = object;
            outline(selected);
        }
    } else if (selected && forceUnselect) {
        removeOutline(selected);
        selected = null;
    }
}

const unselect = () => {

}

/**
 * Is object currently being selected.
 *
 * @param object
 * @returns {boolean|boolean}
 */
const isSelected = (object) => {
    return object && selected ? object.uuid === selected.uuid : false;
}

const getSelected = () => {
    return selected;
}

const draw = (scene, camera, renderer) => {
    const mouse = new THREE.Vector2();
    const rayCaster = new THREE.Raycaster();
    const dragControls = registryGet('dragControls');

    // todo: drag end causes click event
    window.addEventListener('click', function (e) {
        mouse.x = (e.clientX / window.innerWidth) * 2 - 1;
        mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
        rayCaster.setFromCamera(mouse, camera);

        let pointed = null;
        rayCaster.intersectObjects(scene.children).forEach(function (intersect) {
            let object = intersect.object;
            if (isInteractable(object)) {
                pointed = object;
            } else if (isInteractable(object.parent)) {
                pointed = object.parent;
            }
        });

        select(pointed);
        dragControls.enabled = !!getSelected();
    });
}

export {select, unselect, isSelected, getSelected, draw}