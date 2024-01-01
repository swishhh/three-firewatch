import * as THREE from 'three';
import {mergeMeshes} from "../../tools/mesh/index.js";

class InstancedManager {
    mapping = []
    relate
    instance
    constructor(scene, meshes, mapping) {
        this.scene = scene;
        this.meshes = meshes;
        this.mapping = mapping;
    }
    setRelateCallback(callback = () => {}) {
        this.relate = callback;
    }
    setCallback(callback = () => {}) {

    }
    addItem(x, y, z, scale) {
        this.mapping.push([x, y, z, scale]);
    }
    draw() {
        let instance = this._create();
        this.scene.add(instance);

        if (this.instance) {
            this.scene.remove(this.instance);
        }

        this.instance = instance;
        this.instance.geometry.dispose()
    }
    _create() {
        const geometry = mergeMeshes(this.meshes);
        const material = new THREE.MeshPhongMaterial({
            reflectivity: false,
            shininess: 0,
            vertexColors: true
        });

        const instancedMesh = new THREE.InstancedMesh(geometry, material, this.mapping.length);
        instancedMesh.castShadow = true;
        instancedMesh.receiveShadow = true;

        const dummy = new THREE.Object3D();
        for (let i = 0; i < this.mapping.length; i++) {
            let x,y,z,scale;
            [x,y,z,scale] = [...this.mapping[i]]

            dummy.position.x = x;
            dummy.position.y = y;
            dummy.position.z = z;
            dummy.scale.set(scale, scale, scale)

            this.relate && this.relate(dummy);

            dummy.updateMatrix();
            instancedMesh.setMatrixAt(i, dummy.matrix);
        }

        return instancedMesh;
    }
}

export {InstancedManager}