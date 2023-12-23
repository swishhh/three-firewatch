import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';
import {interactableAdd} from '../../../registry/interactableObjects.js';
import {objectManager} from "../../../tools/object/manager.js";
import {addSwing} from "./animation/swing.js";

const loader = registryGet('loader');
const scene = registryGet('scene');

const TREE_SCALE_MULTIPLIER = 1.2;

const treeManager = {
    object: null,

    /**
     * Load object's model.
     *
     * @param x
     * @param y
     * @param z
     * @param scale
     */
    load: function (x = 0, y = 0, z = 0, scale = 1) {
        loader.load('../../../../obj/lowpolytree.obj', (model) => {
            this.object = model.children[0];
            this.object.material.some((material) => {
                let color = material.name === 'Leaves' ? '#0a1f00' : '#241302'
                material.color = new THREE.Color(color);
                material.shininess = 0;
                material.reflectivity = false;
            })

            this.draw(x, y, z, scale)
        });
    },

    /**
     * Retrieve new instance.
     *
     * @returns {*}
     */
    getNewInstance: function () {
        return new THREE.Mesh(this.object.geometry, this.object.material);
    },

    /**
     * Draw object.
     *
     * @param x
     * @param y
     * @param z
     * @param scale
     */
    draw: function (x, y, z, scale = 1) {
        scale /= 1.1;
        scale *= TREE_SCALE_MULTIPLIER;
        if (this.object === null) {
            this.load(x,y,z, scale);
        } else {
            let tree = this.getNewInstance();
            tree.position.x = x;
            tree.position.y = y + (1.9 * scale);
            tree.position.z = z;
            tree.scale.x = scale
            tree.scale.y = scale
            tree.scale.z = scale
            tree.castShadow = true;
            tree.receiveShadow = true;
            tree.name = 'tree';

            let terrain = registryGet('terrain');
            terrain.addRelativeObject(tree);

            scene.add(tree);

            interactableAdd(tree.uuid, tree);
        }
    }
}

const drawAnimated = (x = 0, y = 0, z = 0, scale) => {
    scale /= 1.1;
    scale *= TREE_SCALE_MULTIPLIER;
    objectManager.get('animated-tree', (gltf) => {
        const model = gltf.scene;

        model.position.x = x;
        model.position.y = y;
        model.position.z = z;
        model.scale.x = scale
        model.scale.y = scale
        model.scale.z = scale

        let terrain = registryGet('terrain');
        terrain.addRelativeObject(model);

        let random = Math.random();
        let axis = 'x';
        if (random < 0.3) {
            axis = 'x';
        } else if (random < 0.6) {
            axis = 'z'
        } else if (random < 1) {
            axis = 'xz'
        }
        const randomSpeed = (speed) => {
            return speed + Math.sqrt(speed * Math.random()) * 2;
        }
        let intensity = .3;
        addSwing(
            model,
            randomSpeed(7),
            intensity - (model.scale.x / 2),
            20,
            random,
            axis,
            Math.random() > 0.5 ? 1 : -1,
            Math.random() > 0.5 ? 1 : -1
        );
        interactableAdd(model.uuid, model); // todo: meshes unmerged, won't work

        scene.add(model);
    })
}

export {treeManager, drawAnimated};