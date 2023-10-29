import {isSelected} from "../../controls/mouse/select.js";

const highlight = (object, visible = true) => {
    if (isSelected(object)) {
        return;
    }

    const changeMaterial = (material) => {
        material.emissive.set(visible ? 0xaaaaaa : 0x000000);
        material.emissiveIntensity = visible ? .2 : 1;
    }

    if (Array.isArray(object.material)) {
        object.material.forEach(changeMaterial)
    } else if (object.material){
        changeMaterial(object.material)
    }
}

export {highlight}