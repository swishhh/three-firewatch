import * as THREE from 'three';
import {addUpdateCallback} from "../../../registry/update.js";
import {registryGet} from "../../../registry/registry.js";

const snowVelocity = 50;

const draw = (scene, camera, renderer) => {
    const textureLoader = registryGet('textureLoader');
    let geometry = new THREE.BufferGeometry();

    let numOfFlakes = 2500;
    let positions = []; let velocities = [];
    let minRange = 15; let maxRange = 22;
    let minHeight = 0;

    const addSnowFlakes = () => {
        for (let i = 0; i < numOfFlakes; i++) {
            positions.push(
                Math.floor(Math.random() * maxRange - minRange),
                Math.floor(Math.random() * minRange + minHeight),
                Math.floor(Math.random() * maxRange - minRange)
            );
            velocities.push(
                Math.floor(Math.random() * 6 - 3) * (snowVelocity / 10000),
                Math.floor(Math.random() * 5 + .12) * (snowVelocity / 10000),
                Math.floor(Math.random() * 6 - 3) * (snowVelocity / 10000),
            )
        }
    }

    addSnowFlakes();

    let flakeMaterial = new THREE.PointsMaterial({
        size: .05,
        map: textureLoader.load('../../../../textures/sprites/snowflake.png'),
        blending: THREE.AdditiveBlending,
        depthTest: false,
        transparent: true,
        opacity: 0.7
    });

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('velocity', new THREE.Float32BufferAttribute(velocities, 3));

    let particles = new THREE.Points(geometry, flakeMaterial);
    window.particles = particles;
    particles.position.set(0, 0, -1)
    scene.add(particles);

    let updateSnow = () => {
        for (let i = 0; i < numOfFlakes * 3; i += 3) {
            particles.geometry.attributes.position.array[i] -= particles.geometry.attributes.velocity.array[i];
            particles.geometry.attributes.position.array[i + 1] -= particles.geometry.attributes.velocity.array[i + 1];
            particles.geometry.attributes.position.array[i + 2] -= particles.geometry.attributes.velocity.array[i + 2];

            if (particles.geometry.attributes.position.array[i+1] < 0) {
                particles.geometry.attributes.position.array[i] = Math.floor(Math.random() * maxRange - minRange);
                particles.geometry.attributes.position.array[i + 1] = Math.floor(Math.random() * minRange + minHeight) / 2;
                particles.geometry.attributes.position.array[i + 2] = Math.floor(Math.random() * maxRange - minRange) / 2;
            }
            particles.geometry.attributes.position.needsUpdate = true;
        }
    }

    addUpdateCallback(updateSnow)
}

export {draw}