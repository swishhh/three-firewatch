import {MathUtils} from 'three';
import {addUpdateCallback} from '../../../../registry/update.js';

const buildConfig = (
    speed,
    intensity,
    blendStrength,
    start = 0,
    axis = 'x',
    mod = 1,
    degMode = -1
) => {
    return {
        speed: speed,
        intensity: intensity,
        blendStrength: blendStrength,
        beg: start,
        axis: axis,
        mod: mod,
        degMode: degMode
    }
}

const addSwing = (model, speed, intensity, strength, start = 0, axis = 'z', mod = 1, degMode = -1) => {
    if (!model.skeleton) return;

    model.skeleton.rotate = function (deg, strength = 0.5, axis = 'x') {
        let iter = 0;
        this.bones.forEach(function (bone) {
            iter++;
            if (axis === 'xz') {
                let rad = MathUtils.degToRad( deg * Math.sqrt((iter / 100 * strength)));
                bone.rotation['x'] = bone.rotation['z'] = rad
            } else {
                bone.rotation[axis] = MathUtils.degToRad( deg * Math.sqrt((iter / 100 * strength)))
            }
        })
    }

    model.swingConfig = buildConfig(
        speed,
        intensity,
        strength,
        start,
        axis,
        mod,
        degMode
    );
    model.swing = function () {
        if (!this.swingConfig) return;

        this.swingConfig.beg += (this.swingConfig.speed / 1000) * this.swingConfig.mod;

        if (this.swingConfig.beg >= 1) {
            this.swingConfig.mod = -1;
        } else if (this.swingConfig.beg <= 0) {
            this.swingConfig.mod = 1;
            this.swingConfig.degMode *= -1
        }

        let deg = 1 - Math.pow(1 - this.swingConfig.beg, 2);
        deg *= this.swingConfig.intensity;
        this.skeleton.rotate(deg * this.swingConfig.degMode, this.swingConfig.blendStrength, this.swingConfig.axis)
    }

    addUpdateCallback(model.swing.bind(model))
}

export {addSwing}