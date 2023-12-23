import { GUI } from 'three/addons/libs/lil-gui.module.min.js';

const ENABLED = true;
let datGui = null;

const getGui = () => {
    return datGui === null ? datGui = new GUI() : datGui;
}

const isVisible = () => {
    return ENABLED;
}

export {getGui, isVisible}
