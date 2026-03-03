import * as THREE from 'three';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { registryGet, registryAdd } from "../../registry/registry.js";
import { addUpdateCallback } from "../../registry/update.js";

const SPEED = 5;
const GRAVITY = 20;
const JUMP_VELOCITY = 8;
const EYE_HEIGHT = 1.6;
let moveForward = false;
let moveBackward = false;
let moveLeft = false;
let moveRight = false;
let velocityY = 0;
let onGround = false;

const onKeyDown = (e) => {
    switch (e.code) {
        case 'KeyW': moveForward  = true;  break;
        case 'KeyS': moveBackward = true;  break;
        case 'KeyA': moveLeft     = true;  break;
        case 'KeyD': moveRight    = true;  break;
        case 'Space':
            if (onGround) { velocityY = JUMP_VELOCITY; onGround = false; }
            break;
    }
};

const onKeyUp = (e) => {
    switch (e.code) {
        case 'KeyW': moveForward  = false; break;
        case 'KeyS': moveBackward = false; break;
        case 'KeyA': moveLeft     = false; break;
        case 'KeyD': moveRight    = false; break;
    }
};

const draw = (scene, camera, renderer) => {
    camera.rotation.set(0, Math.PI, 0);

    const controls = new PointerLockControls(camera, renderer.domElement);
    registryAdd('firstPersonControls', controls);

    controls.getObject().position.set(2, EYE_HEIGHT, 2);

    renderer.domElement.addEventListener('click', () => controls.lock());
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('keyup', onKeyUp);

    addUpdateCallback((delta) => {
        if (!controls.isLocked) return;

        const pos     = controls.getObject().position;
        const floorY   = EYE_HEIGHT;
        //
        velocityY -= GRAVITY * delta;
        pos.y     += velocityY * delta;

        if (pos.y < floorY) {
            pos.y     = floorY;
            velocityY = 0;
            onGround  = true;
        }

        // --- horizontal movement ---
        if (moveForward || moveBackward) controls.moveForward((moveForward ? 1 : -1) * SPEED * delta);
        if (moveLeft || moveRight)       controls.moveRight((moveRight ? 1 : -1) * SPEED * delta);
    });
};

export { draw };
