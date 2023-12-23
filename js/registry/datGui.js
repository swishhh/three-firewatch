import { GUI } from 'three/addons/libs/lil-gui.module.min.js';

const ENABLED = true;
let datGui = null;

const getGui = () => {
    if (!ENABLED) {
        return
    }
    
    let result = datGui === null ? datGui = new GUI() : datGui;

    result.close();

    return result;
}

const isVisible = () => {
    return ENABLED;
}

export {getGui, isVisible}
