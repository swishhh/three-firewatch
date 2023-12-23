import {BufferAttribute, Color} from 'three';
import {mergeBufferGeometries} from "../../../lib/addons/jsm/utils/BufferGeometryUtils.js";

const color = new Color();

const mergeMeshes = (meshes) => {
    return mergeBufferGeometries(meshes.map((child) => {
        let count = child.geometry.attributes.position.count;
        let geometry = child.geometry.clone();

        geometry.setAttribute( 'color', new BufferAttribute( new Float32Array( count * 3 ), 3 ) );

        const colorAttr = geometry.attributes.color;
        color.copy(child.material.color)

        for ( let i = 0; i < count; i ++ ) {
            colorAttr.setXYZ( i, color.r, color.g, color.b );
        }

        geometry.applyMatrix4(child.matrix)

        return geometry;
    }))
}

export {mergeMeshes}