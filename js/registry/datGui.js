import { GUI } from 'three/addons/libs/lil-gui.module.min.js';

const ENABLED = false;
let datGui = null;

const getGui = () => {
    if (!ENABLED) {
        return
    }
    
    return datGui === null ? datGui = new GUI() : datGui;
}

const isVisible = () => {
    return ENABLED;
}

export {getGui, isVisible}
