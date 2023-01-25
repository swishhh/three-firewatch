import * as THREE from 'three';

const draw = (scene, camera, renderer) => {
    const segmentsX = 100;
    const segmentsZ = 100;
    const sizeX = 1.1 * segmentsX;
    const sizeZ = 1.1 * segmentsZ;

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
    terrain.scale.set(0.3, 0.3, 0.3)

    const totalSegmentsX = segmentsX + 1;
    const totalSegmentsZ = segmentsZ + 1;

    for(let z = 0; z < totalSegmentsZ; z++) {
        for(let x = 0; x < totalSegmentsX; x++) {
            const index = 3 * (z * totalSegmentsX + x);
            let r = 20;
            let center = segmentsX / 2;

            geometry.attributes.position.array[index + 1] = (z - center) * (z - center) + (x - center) * (x - center) <= r * r
                ? (Math.random() / 1.5) * .3
                : Math.random() * 2;
        }
    }
}

export {draw};