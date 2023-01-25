import * as THREE from 'three';
import {registryGet} from '../../../registry/registry.js';

const loader = registryGet('loader');
const scene = registryGet('scene');

const treeManager = {
    object: null,
    load: function (x = 0, y = 0, z = 0, scale = 1) {
        loader.load('../../../../obj/lowpolytree.obj', (model) => {
            this.object = model.children[0];
            this.object.material.some((material) => {
                let color = material.name === 'Leaves' ? '#164200' : '#472706'
                material.color = new THREE.Color(color);
            })

            this.draw(x, y, z, scale)
        });
    },
    getNewInstance: function () {
        return new THREE.Mesh(this.object.geometry, this.object.material);
    },
    draw: function (x, y, z, scale = 1) {
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
        }
    }
}

export {treeManager};