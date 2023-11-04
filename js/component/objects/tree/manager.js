import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';
import {interactableAdd} from '../../../registry/interactableObjects.js';
import {GLTFLoader} from '../../../../lib/addons/loaders/GLTFLoader.js';
import {addUpdateCallback} from '../../../registry/update.js';

const loader = registryGet('loader');
const scene = registryGet('scene');

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
        if (this.object === null) {
            this.load(x,y,z, scale);
        } else {
            let tree = this.getNewInstance();
            tree.position.x = x;
            tree.position.y = y + (1.9 * scale);
            tree.position.z = z;
            tree.scale.x = scale;
            tree.scale.y = scale;
            tree.scale.z = scale;
            tree.castShadow = true;
            tree.receiveShadow = true;
            scene.add(tree);
            tree.name = 'tree';

            window.tree = tree;
            interactableAdd(tree.uuid, tree);
        }

        // const assetLoader = new GLTFLoader();
        // assetLoader.load('../../../../obj/lowpoly-tree-animation.glb', function (gltf) {
        //     const model = gltf.scene;
        //     model.children[0].children[1].children.forEach(function (child) {
        //         let color = child.material.name === 'Leaves' ? '#164200' : '#472706'
        //         child.material.color = new THREE.Color(color);
        //     });
        //     console.log(gltf);
        //     model.position.y = 2;
        //     scene.add(model);
        //     mixer = new THREE.AnimationMixer(model);
        //     const clips = gltf.animations;
        //     console.log(clips)
        //     const clip = THREE.AnimationClip.findByName(clips, "ArmatureAction");
        //     const action = mixer.clipAction(clip);
        //     action.play();
        //
        //     addUpdateCallback(mixer.update.bind(mixer));
        //
        //     let tree = model.children[0].children[1];
        //     interactableAdd(tree.uuid, tree);
        //     //armatureAction
        // });
    }
}

export {treeManager};