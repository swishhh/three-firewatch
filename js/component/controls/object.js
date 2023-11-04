import * as THREE from 'three';
import {getSelected} from "./mouse/select.js";

const rotate = (object) => {
    if (!object.isMesh && object.isGroup) {
        object.children.some((child) => {
            child.rotation.y += (Math.PI / 2)
        });
    } else {
        object.rotation.y += (Math.PI / 2)
    }
}

const draw = (scene, camera, renderer) => {
    window.addEventListener('keyup', function (e) {
        let selected = getSelected();
        if (selected) {
            switch(e.code) {
                case 'KeyR':
                    rotate(selected);
                    break;
            }
        }
    });
}

export {draw}