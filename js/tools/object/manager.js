import * as THREE from 'three';
import {registryGet} from '../../registry/registry.js';

const loader = registryGet('loader');
const gltfLoader = registryGet('gltfLoader');
const scene = registryGet('scene');

const storage = {};
const list = {
    'bush-tree': {
        path: '../../../obj/bush-tree.obj',
        callback: (model) => {
            model.scale.set(.25, .25, .25);
            model.children.forEach((child) => {
                child.recieveShadow = true;
                child.castShadow = true;
            });
            model.recieveShadow = true;
            model.castShadow = true;

            model.children.forEach((child) => {
                child.material.forEach((material) => {
                    switch (material.name) {
                        case 'Green':
                            material.color = new THREE.Color('#205704');
                            break;
                        case 'Brown':
                            material.color = new THREE.Color('#291602');
                            break;
                    }
                })
            });
        }
    },
    'bush-tree-harvest': {
        path: '../../../obj/bush-tree-harvest.obj',
        callback: (model) => {
            model.scale.set(.25, .25, .25);
            model.children.forEach((child) => {
                child.recieveShadow = true;
                child.castShadow = true;
            });
            model.recieveShadow = true;
            model.castShadow = true;

            model.children.forEach((child) => {
                child.material.forEach((material) => {
                    switch (material.name) {
                        case 'Green':
                            material.color = new THREE.Color('#234517');
                            break;
                        case 'Brown':
                            material.color = new THREE.Color('#291602');
                            break;
                        case 'Berry':
                            // #ff0000
                            //#3c054a
                            material.color = new THREE.Color('#700b0b');
                            break;
                    }
                })
            });
        }
    },
    'grass': {
        path: '../../../obj/grass.obj',
        callback: (model) => {
            model.children.forEach((child) => {
                switch (child.material.name) {
                    case 'Grass':
                        child.material.color = new THREE.Color('#062408');
                        break;
                }
            });
        }
    }
}

const objectManager = {
    /**
     * Get object's mesh.
     *
     * @param name
     * @param callback
     */
    get: function (name, callback) {
        if (storage.hasOwnProperty(name)) {
            let object = storage[name];
            callback(new THREE.Mesh(object.geometry, object.material));
        } else {
            this.load(name, callback);
        }
    },

    /**
     * Load object
     *
     * @param name
     * @param callback
     */
    load: function (name, callback) {
        if (list.hasOwnProperty(name)) {
            let config = list[name];
            loader.load(config.path, (model) => {
                config.callback(model);
                callback(model);
            })
        }
    }
}

export {objectManager}