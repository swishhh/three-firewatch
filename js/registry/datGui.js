import { GUI } from 'three/addons/libs/lil-gui.module.min.js';

let datGui = null;

const getGui = () => {
    return datGui === null ? datGui = new GUI() : datGui;
}

export {getGui}
