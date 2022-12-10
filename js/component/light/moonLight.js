import * as THREE from "three";

const SpotLight = (position, color, intensity) => {
    let light = new THREE.SpotLight(color, intensity);
    light.castShadow = true;
    light.position.x = x;
    light.position.y = y;
    light.position.z = z;
    light.position = {...light.position, ...position};

    light.shadow.mapSize.width = 252;
    light.shadow.mapSize.height = 252;
    light.shadow.camera.near = 0.5;
    light.shadow.camera.far = 1500;
    light.shadow.focus = 10;

    window.moon = light;
}