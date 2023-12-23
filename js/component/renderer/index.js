import {addUpdateCallback} from "../../registry/update.js";

const DISTANCE = 1400;

const initSceneRenderer = (scene, camera, renderer) => {
    addUpdateCallback(() => {
        scene.traverse( function(child) {
            let currentDistance = camera.position.distanceToSquared(child.position);
            if (child.distanceRender) {
                child.visible = currentDistance < DISTANCE
            }
        });
    })
}

export {initSceneRenderer}