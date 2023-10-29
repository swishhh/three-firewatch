import * as THREE from 'three';
import { registryAdd } from "../../../registry/registry.js";

const draw = (scene, camera, renderer) => {
    const segmentsX = 50;
    const segmentsZ = 50;
    const sizeX = segmentsX * 1.1;
    const sizeZ = segmentsZ * 1.1;

    let geometry = new THREE.PlaneBufferGeometry(
        sizeX,
        sizeZ,
        segmentsX,
        segmentsZ
    );
    geometry.rotateX(Math.PI * -0.5);
    let material = new THREE.MeshPhongMaterial( { color: 0x888888 } )
    material.shininess = 0;
    const terrain = new THREE.Mesh(geometry, material);

    terrain.receiveShadow = true;
    scene.add(terrain)
    terrain.scale.set(1, 1, 1)

    const totalSegmentsX = segmentsX + 1;
    const totalSegmentsZ = segmentsZ + 1;

    for(let z = 0; z < totalSegmentsZ; z++) {
        for(let x = 0; x < totalSegmentsX; x++) {
            const index = 3 * (z * totalSegmentsX + x);
            let r = 15;
            let center = segmentsX / 2;

            geometry.attributes.position.array[index + 1] = (z - center) * (z - center) + (x - center) * (x - center) <= r * r
                ? (Math.random() / 1.5) * .2
                : Math.random() * 1.2;
        }
    }

    // const grid = new THREE.GridHelper(segmentsX, segmentsZ);
    // scene.add(grid);
    // grid.position.x += .5;
    // grid.position.z += .5;
    terrain.position.x += .5;
    terrain.position.z += .5;

    window.plane = terrain;
}

export {draw};