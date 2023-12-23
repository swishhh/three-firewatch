import * as THREE from 'three';
import {interactableAdd} from '../../../registry/interactableObjects.js';
import {getGui, isVisible} from "../../../registry/datGui.js";
import {addUpdateCallback} from '../../../registry/update.js';
import {createSmoke} from "../smoke/index.js";
import {objectManager} from "../../../tools/object/manager.js";


const draw = (scene, camera, renderer) => {
    objectManager.load('camp-fire', (model) => {
        model.scale.set(.7, .7, .7);

        interactableAdd(model.uuid, model)

        model.position.x = 2.7;
        model.position.z = -2.5

        const campLightColor = 0xca4316;
        const campLight = new THREE.PointLight(campLightColor, 2, 10);
        campLight.position.y = .8;
        campLight.decay = .9;
        campLight.castShadow = true;
        campLight.blinkMax = campLight.intensity;
        campLight.blinkMin = campLight.intensity - .1;
        campLight.blinkStep = 0.01;
        campLight.blinkStepMax = 0.02;
        campLight.blinkStepMin = 0.01;
        campLight.blinkObject = {
            mod: 1
        };
        campLight.dispose();

        const campGlowLightColor = 0x992600;
        const campGlowLight = new THREE.PointLight(campGlowLightColor, 3, .5);
        campGlowLight.position.y = .75;
        campGlowLight.decay = 5.2;

        campLight.glowLight = campGlowLight;
        campGlowLight.dispose();

        campLight.blink = function () {
            let randStep = Math.random();
            if (randStep >= this.blinkStepMin && randStep <= this.blinkStepMax) {
                this.blinkStep = randStep;
            }

            let increment = (this.blinkStep * this.blinkObject.mod)
                + (Math.random() < .005 ? .3 : 0) + (Math.random() < .02 ? this.blinkStep * 4 : 0);

            this.intensity += increment;
            this.glowLight.intensity += increment * 10;
            if (this.intensity > this.blinkMax) {
                this.blinkObject.mod = -1;
            } else if (this.intensity < this.blinkMin) {
                this.blinkObject.mod = 1;
            }
        }

        model.add(campLight);
        model.add(campGlowLight);

        // if (isVisible) {
        //     const fireCampFolder = getGui().addFolder('Fire Camp');
        //     const fireCampLightFolder = fireCampFolder.addFolder('Light')
        //     fireCampLightFolder.add(campLight, 'decay', -1, 20);
        //     fireCampLightFolder.add(campLight, 'intensity', 0, 20);
        //     fireCampLightFolder.add(campLight, 'distance', 0, 50);
        //     fireCampLightFolder.addColor(
        //         {color: campLightColor}, 'color').onChange((value) => campLight.color.set(value)
        //     );
        //     const fireCampGlowLightFolder = fireCampFolder.addFolder('Glow Light')
        //     fireCampGlowLightFolder.add(campGlowLight, 'decay', -1, 20);
        //     fireCampGlowLightFolder.add(campGlowLight, 'intensity', 0, 20);
        //     fireCampGlowLightFolder.add(campGlowLight, 'distance', 0, 50);
        //     fireCampGlowLightFolder.addColor(
        //         {color: campGlowLightColor}, 'color').onChange((value) => campGlowLight.color.set(value)
        //     );
        // }

        addUpdateCallback(campLight.blink.bind(campLight))


        // smoke simulation

        let group = createSmoke(model.position.x, model.scale.y + .5, model.position.z);

        scene.add(model);
        scene.add(group)
    });
}

export {draw}