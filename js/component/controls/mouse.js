import { DragControls } from '../../../lib/addons/controls/DragControls.js';
import { registryGet } from "../../registry/registry.js";
import { interactableGet } from "../../registry/interactableObjects.js";
import { highlight } from "../action/object/highlight.js";
import { isSelected, select } from "./mouse/select.js";

const draw = (scene, camera, renderer) => {
    const mapControls = registryGet('mapControls');
    const controls = new DragControls(Object.values(interactableGet()), camera, renderer.domElement);
    controls.addEventListener('hoveron', function (e) {
        highlight(e.object)
    });

    controls.addEventListener('hoveroff', function (e) {
        highlight(e.object, false);
    })

    let posY;
    let posZ;
    let posX;
    controls.addEventListener( 'dragstart', function ( e ) {
        mapControls.enabled = false;
        posY = e.object.position.y;
        posX = e.object.position.x;
        posZ = e.object.position.z;

        highlight(e.object)
    });

    controls.addEventListener( 'dragend', function ( e ) {
        mapControls.enabled = true;
        if (!isSelected(e.object)) {
            highlight(e.object, false);
        }
    });

    controls.addEventListener( 'drag', function ( e ) {
        e.object.position.y = posY;
        e.object.position.x = Math.round(e.object.position.x);
        e.object.position.z = Math.round(e.object.position.z);
    });

    window.drag = controls;
}

export {draw}