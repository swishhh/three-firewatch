import {getResieCallbacks} from "../../registry/resize.js";

const draw = (scene, camera, renderer) => {
    window.addEventListener( 'resize', () => {
        renderer.setSize(window.innerWidth, window.innerHeight)
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();

        let callbacks = getResieCallbacks();
        for (let i = 0; i < callbacks.length; i++) {
            callbacks[i]();
        }
    }, false);
}

export {draw}