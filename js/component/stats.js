import Stats from "../../lib/stats.module.js";
import {addUpdateCallback} from "../registry/update.js";

const draw = (scene, camera, renderer) => {
    let fpsStats = new Stats();
    fpsStats.dom.style.width = '120px';
    fpsStats.dom.style.height = '120px';
    fpsStats.showPanel(0)
    document.body.appendChild(fpsStats.dom);

    addUpdateCallback(fpsStats.update.bind(fpsStats));

    let memoryStats = new Stats();
    memoryStats.dom.style.width = '120px';
    memoryStats.dom.style.height = '120px';
    memoryStats.showPanel(2)
    document.body.appendChild(memoryStats.dom);

    addUpdateCallback(memoryStats.update.bind(memoryStats));
}

export {draw}