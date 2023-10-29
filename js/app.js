import * as THREE from 'three';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { registryAdd } from "./registry/registry.js";
import { getUpdateCallbacks } from "./registry/update.js";
import { draw } from "./component/scene.js";

const loader = new OBJLoader();
const textureLoader = new THREE.TextureLoader();

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera( 75, window.innerWidth / window.innerHeight, 0.1, 1000 );
const renderer = new THREE.WebGLRenderer({
    clearAlpha: 1,
    clearColor: 0xdddddd,
    antialias: true
});

registryAdd('scene', scene);
registryAdd('camera', camera);
registryAdd('renderer', renderer);
registryAdd('loader', loader);
registryAdd('textureLoader', textureLoader);

renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.setPixelRatio(window.devicePixelRatio);
renderer.outputEncoding = THREE.sRGBEncoding;
document.body.appendChild(renderer.domElement);
document.body.appendChild( renderer.domElement );

camera.position.z = 10;
camera.position.y = 10;
camera.lookAt(scene);
camera.fov = 60;
window.camera = camera;

await draw();

const clock = new THREE.Clock();

function animate() {
    requestAnimationFrame(animate);
    renderer.render( scene, camera );
    let callbacks = getUpdateCallbacks();
    for (let i = 0; i < callbacks.length; i++) {
        callbacks[i](clock.getDelta());
    }
}

animate();