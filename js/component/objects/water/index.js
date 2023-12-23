import * as THREE from 'three';
import {addUpdateCallback} from '../../../registry/update.js';
import {mergeVertices} from '../../../../lib/addons/jsm/utils/BufferGeometryUtils.js';
import {getGui} from "../../../registry/datGui.js";

const random = (min, max) => {
    return Math.floor(Math.random() * (max - min + 1) + min)
};

const draw = (scene, camera, renderer) => {
    const segX = 50;
    const segZ = 50;
    const size = 50;
    const waterColor = 0x5d83c2;

    const waterGeometry = new THREE.PlaneGeometry(size, size, segX, segZ);
    const waterMaterial = new THREE.MeshPhysicalMaterial({
        color: waterColor,
        metalness: .6,
        roughness: 1,
        envMapIntensity: 0.9,
        transparent: true,
        opacity: .95,
        reflectivity: 1,
        ior: 0.9,
        side: THREE.FrontSide,
        flatShading: true,
    });

    const water = new THREE.Mesh(waterGeometry, waterMaterial);

    waterGeometry.rotateX(Math.PI * -0.5);

    water.receiveShadow = true;
    water.castShadow = true;
    water.position.y = -.4;

    scene.add(water);

    // addGUI(water);

    const waterFactor = 0.002;
    const maxY = .15;
    const minY = 0;

    mergeVertices(waterGeometry);
    waterGeometry.vertices = waterGeometry.attributes.position.array;
    let waves = [];
    for (let i = 0; i < waterGeometry.vertices.length; i += 3) {
        let y = i + 1;
        waterGeometry.attributes.position.array[y] = (random(1, 1000) / 1000) * maxY;
        waves.push({
            index: y,
            value: waterGeometry.attributes.position.array[y],
            factor:  (waterGeometry.attributes.position.array[y] >= 0.5 ? (waterFactor) * -1 : waterFactor)
        })
    }

    water.animate = function () {
        let geometry = this.geometry;
        waves.forEach((wave) => {
            wave.value = wave.value + wave.factor;
            geometry.attributes.position.array[wave.index] = wave.value;
            if (wave.value >= maxY) {
                wave.factor *= -1;
            } else if (wave.value <= minY) {
                wave.factor = Math.abs(wave.factor);
            }

            if (Math.random() > 0.99) {
                wave.factor *= -1;
            }
        });

        this.geometry.attributes.position.needsUpdate = true;
    }

    addUpdateCallback(water.animate.bind(water));

    const underWaterGeometry = new THREE.PlaneGeometry(size, size, segX, segZ);
    const underWaterMaterial = new THREE.MeshPhongMaterial({color: '#7d7c7c', side: THREE.FrontSide});

    const underWater = new THREE.Mesh(underWaterGeometry, underWaterMaterial);

    underWaterGeometry.rotateX(Math.PI * -0.5);
    underWater.position.y = water.position.y - 3;

    scene.add(underWater)
    window.underWater = underWater;
    window.water = water;
}

const addGUI = (water) => {
    return;
    const folder = getGui().addFolder('Water');
    folder.addColor({color: water.material.color}, 'color').onChange((value) => water.material.color.set(value));
}

export {draw}