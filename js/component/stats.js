import Stats from "../../lib/stats.module.js";
import {addUpdateCallback} from "../registry/update.js";

const draw = (scene, camera, renderer) => {
    let fpsStats = new Stats();
    fpsStats.dom.style.width = '120px';
    fpsStats.dom.style.height = '120px';
    fpsStats.showPanel(0)
    document.body.appendChild(fpsStats.dom);

    addUpdateCallback(fpsStats.update.bind(fpsStats));
}

export {draw}