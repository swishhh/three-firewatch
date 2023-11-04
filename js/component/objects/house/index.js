import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';

const draw = (scene, camera, renderer) => {
    const loader = registryGet('loader');
    loader.load('../../../../obj/winter-house.obj', (model) => {
        scene.add(model);
        model.position.set(2, 0, 6)
        window.house = model;
        model.scale.set(0.7, 0.7, 0.7)
        model.rotateY(10);
        model.recieveShadow = true;
        model.castShadow = true;
        model.children.forEach(function (child) {
            let name = child.material.name;
            child.recieveShadow = true;
            child.castShadow = true;
            let color = '#d2d1d1';
            if (name) {
                if (name.indexOf('Snow') !== -1) {
                    color = '#aaaaaa';
                } else if (name === 'concret') {
                    color = '#BCB8B0';
                } else if (name === 'brown') {
                    color = '#7A533C';
                } else if (name === 'black') {
                    color = '#494949';
                } else if (name === 'brown2') {
                    color = '#B2946C';
                } else if (name === 'dark') {
                    color = '#000000';
                } else if (name === 'metal') {
                    color = '#EBEAEC';
                } else if (name === 'wall2') {
                    color = '#3D0500';
                } else if (name === 'snow') {
                    color = '#F4F4F4';
                } else if (name === 'white') {
                    color = '#FBFBFB';
                } else if (name === 'roof1') {
                    color = '#8E4F1C';
                }

                child.material.color = new THREE.Color(color);
            }
        });
        // model.traverse((child) => {
        //     if (child.isMesh) {
        //         child.material.some((material) => {
        //             if (material.name.indexOf('brown') !== -1) {
        //                 material.color = new THREE.Color('#381801');
        //             }
        //             if (material.name.indexOf('green') !== -1) {
        //                 material.color = new THREE.Color('#d2d1d1');
        //             }
        //         })
        //         child.receiveShadow = true;
        //         child.castShadow = true;
        //     }
        // })
    });
}

export {draw}