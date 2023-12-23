import * as THREE from 'three';
import {registryGet} from '../../registry/registry.js';

const loader = registryGet('loader');
const gltfLoader = registryGet('gltfLoader');

const storage = {};
const list = {
    'bush-tree': {
        path: './obj/bush-tree.obj',
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
                    material.shininess = 0;
                    material.reflectivity = false;
                })
            });
            model.distanceRender = true;
        }
    },
    'bush-tree-harvest': {
        path: './obj/bush-tree-harvest.obj',
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
                    material.shininess = 0;
                    material.reflectivity = false;
                })
            });
            model.distanceRender = true;
        }
    },
    'grass': {
        path: './obj/grass.obj',
        callback: (model) => {
            model.children.forEach((child) => {
                switch (child.material.name) {
                    case 'Grass':
                        child.material.color = new THREE.Color('#062408');
                        break;
                }
                child.material.shininess = 0;
                child.material.reflectivity = false;
            });
            model.distanceRender = true;
        }
    },
    'picnic-table': {
        path: './obj/picnic-table.obj',
        callback: (model) => {
            model.children.forEach((child) => {
                switch (child.material.name) {
                    case 'table':
                        child.material.color = new THREE.Color('#1d0f02');
                        break;
                }
                child.material.shininess = 0;
                child.material.reflectivity = false;
            });
            model.distanceRender = true;
        }
    },
    'rocks-array': {
        path: './obj/rocksArray1.obj',
        callback: (model) => {
            model.children.forEach((child) => {
                child.material.forEach(function (material) {
                    switch (material.name) {
                        case 'Rock.001': // bright
                            material.color = new THREE.Color(0x383838);
                            break;
                        case 'Rock.002': // bright
                            material.color = new THREE.Color(0x292929);
                            break;
                    }
                    material.shininess = 0;
                    material.reflectivity = false;
                })
            });
            model.distanceRender = true;
        }
    },
    'small-rocks-array': {
        path: './obj/small-rocksArray.obj',
        callback: (model) => {
            model.children.forEach((child) => {
                child.material.forEach(function (material) {
                    switch (material.name) {
                        case 'Rock.001': // bright
                            material.color = new THREE.Color(0x383838);
                            break;
                        case 'Rock.002': // bright
                            material.color = new THREE.Color(0x292929);
                            break;
                    }
                    material.shininess = 0;
                    material.reflectivity = false;
                })
            });
            model.distanceRender = true;
        }
    },
    'tiny-rock-vertical': {
        path: './obj/tiny-rock-vertical.obj',
        callback: (model) => {
            model.children.forEach((child) => {
                switch (child.material.name) {
                    case 'Rock.001': // bright
                        child.material.color = new THREE.Color(0x383838);
                        break;
                }
            });
            model.distanceRender = true;
        }
    },
    'welcome-sign': {
        path: './obj/welcome-sign.obj',
        callback: (model) => {
            model.children.forEach((child) => {
                child.material.forEach(function (material) {
                    switch (material.name) {
                        case 'wood':
                            material.color = new THREE.Color(0x1d0f02);
                            break;
                        case 'text':
                            material.color = new THREE.Color(0x5e3c1c);
                            break;
                    }
                    material.shininess = 0;
                    material.reflectivity = false;
                })
            });
            model.distanceRender = true;
        }
    },
    'animated-tree': {
        path: './obj/lowpoly-tree-bones.glb',
        gltfLoader: true,
        callback: (gltf) => {
            const model = gltf.scene;
            model.children[0].children[1].children.forEach(function (child) {
                let color = child.material.name === 'Leaves' ? '#0a1f00' : '#241302';
                child.material = new THREE.MeshPhongMaterial({color: color, reflectivity: false, shininess: 0});
                child.receiveShadow = true;
                child.castShadow = true;
            });

            const getBones = (bone, bones = []) => {
                bone.rotationBase = {x: bone.rotation.x, y: bone.rotation.y, z: bone.rotation.z}
                bones.push(bone);
                if (bone.children.length > 0) {
                    bone.children.forEach(function (child) {
                        if (child.isBone) {
                            bones = getBones(child, bones);
                        }
                    })
                }

                return bones;
            }

            let bones = getBones(model.children[0].children[0]);
            model.skeleton = new THREE.Skeleton(bones);

            model.distanceRender = true;
        }
    },
    'animated-tree-level25': {
        path: './obj/lowpoly-tree-bones-level25.glb',
        gltfLoader: true,
        callback: (gltf) => {
            const model = gltf.scene;
            model.children[0].children[1].children.forEach(function (child) {
                let color = child.material.name === 'Leaves' ? '#0a1f00' : '#241302';
                child.material = new THREE.MeshPhongMaterial({color: color, reflectivity: false, shininess: 0});
                child.receiveShadow = true;
                child.castShadow = true;
            });

            const getBones = (bone, bones = []) => {
                bone.rotationBase = {x: bone.rotation.x, y: bone.rotation.y, z: bone.rotation.z}
                bones.push(bone);
                if (bone.children.length > 0) {
                    bone.children.forEach(function (child) {
                        if (child.isBone) {
                            bones = getBones(child, bones);
                        }
                    })
                }

                return bones;
            }

            let bones = getBones(model.children[0].children[0]);
            model.skeleton = new THREE.Skeleton(bones);

            model.distanceRender = true;
        }
    },
    'animated-bird': {
        path:  './obj/bird-animated.glb',
        gltfLoader: true,
        callback: (gltf) => {
            const model = gltf.scene;

            model.children[0].children[2].material = new THREE.MeshBasicMaterial({
                color: 0x000000,
                transparent: true
            });

            model.distanceRender = true;
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
            let loaderInstance = config.gltfLoader ? gltfLoader : loader;
            loaderInstance.load(config.path, (model) => {
                config.callback(model);
                callback(model);
            })
        }
    }
}

export {objectManager}