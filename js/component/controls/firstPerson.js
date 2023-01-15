import * as THREE from 'three';
import { PointerLockControls } from 'three/addons/controls/PointerLockControls.js';
import { registryGet } from "../../registry/registry.js";
import { addUpdateCallback } from "../../registry/update.js";

let MOVEMENT_SPEED = 40;
let JUMP_HEIGHT = 1;

let moveForward = false;
let moveLeft = false;
let moveBackward = false;
let moveRight = false;
let canJump = false;

const velocity = new THREE.Vector3();
const direction = new THREE.Vector3();
const rayCaster = new THREE.Raycaster( new THREE.Vector3(), new THREE.Vector3( 0, -1, 0 ), 0, 1);

let prevTime = performance.now();

const moveAction = (key, move) => {
    switch (key) {
        case 'KeyW':
            moveForward = move;
            break;
        case 'KeyA':
            moveLeft = move;
            break;
        case 'KeyS':
            moveBackward = move;
            break;
        case 'KeyD':
            moveRight = move;
            break;
        case 'Space':
            if (!canJump) {
                return;
            }

            if ( canJump === move ) velocity.y += 5;
            canJump = false;
            break;
    }
}

const onKeyDown = (e) => moveAction(e.code, true)
const onKeyUp = (e) => moveAction(e.code, false)

const FirstPersonControls = () => {
    window.addEventListener( 'click', () => {controls.lock()}, false );


    const controls = new PointerLockControls(
        registryGet('camera'), registryGet('renderer').domElement
    );

    // console.log(registryGet('scene'))

    window.scene = registryGet('scene').children;
    window.rayCaster = rayCaster;

    rayCaster.ray.origin.copy( controls.getObject().position );

    let helper = new THREE.ArrowHelper(rayCaster.ray.direction, rayCaster.ray.origin, 1, 0xff0000);
    registryGet('scene').add(helper);
    window.helper = helper;

    const update = () => {
        const time = performance.now();
        if ( controls.isLocked === true ) {



            rayCaster.ray.origin.copy( controls.getObject().position );
            rayCaster.ray.origin.y += 0;

            const intersections = rayCaster.intersectObjects( registryGet('scene').children, false );

            const onObject = intersections.length > 0;

            const delta = (( time - prevTime ) / 10000) * MOVEMENT_SPEED;

            velocity.x -= velocity.x * 10.0 * delta;
            velocity.z -= velocity.z * 10.0 * delta;

            velocity.y -= 9.8 * 10.0 * ((delta / 10) / JUMP_HEIGHT); // 100.0 = mass

            direction.z = Number( moveForward ) - Number( moveBackward );
            direction.x = Number( moveRight ) - Number( moveLeft );
            direction.normalize(); // this ensures consistent movements in all directions

            if ( moveForward || moveBackward ) velocity.z -= direction.z * 10.0 * delta;
            if ( moveLeft || moveRight ) velocity.x -= direction.x * 10.0 * delta;

            if ( onObject === true ) {

                velocity.y = Math.max( 0, velocity.y );
                canJump = true;

            }

            controls.moveRight( - velocity.x * delta );
            controls.moveForward( - velocity.z * delta );

            controls.getObject().position.y += ( velocity.y * delta ); // new behavior

            if ( controls.getObject().position.y < 1.3 ) {

                velocity.y = 0;
                controls.getObject().position.y = 1.3;

                canJump = true;

            }

        }

        prevTime = time;
    }

    document.addEventListener('keydown',onKeyDown);
    document.addEventListener('keyup', onKeyUp);

    addUpdateCallback(update);
};

export {FirstPersonControls}