import {SpotLight} from "three";
import {getGui} from "../../registry/datGui.js";

const MoonLight = (color, intensity, position, addGui = false) => {
    let light = new SpotLight(color, intensity);
    light.position.set(position.x, position.y, position.z);

    light.castShadow = true;

    light.shadow.mapSize.width = 252;
    light.shadow.mapSize.height = 252;
    light.shadow.camera.near = 0.5;
    light.shadow.camera.far = 1500;
    light.shadow.focus = 10;

    if (addGui) {
        const folder = getGui().addFolder('Moon light');
        folder.add(light, 'intensity', 0, 4);
        folder.add(light, 'distance', 0, 700);
        folder.add(light, 'castShadow');
        folder.add(light, 'visible');
        folder.add(light.position, 'x', -150, 150);
        folder.add(light.position, 'y', -150, 150);
        folder.add(light.position, 'z', -150, 150);
        folder.addColor({color: color}, 'color').onChange((value) => light.color.set(value));
    }

    light.castShadow = true;

    return light;
}

export {MoonLight};