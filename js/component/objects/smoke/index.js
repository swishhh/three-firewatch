import * as THREE from 'three';
import {registryGet} from "../../../registry/registry.js";
import {interactableAdd} from '../../../registry/interactableObjects.js';
import {getGui, isVisible} from "../../../registry/datGui.js";
import {addUpdateCallback} from '../../../registry/update.js';

const SHARPNESS = 15;
const MAX_SIZE = .1;
const MIN_SIZE = .05;
const SPEED = 3;
const DISTANCE = 9;
const AMPLITUDE = .1;
const FREQUENCY = .6;
const COUNT = 20;
const SALT = .4;
const FADE_AWAY = true;
const OPACITY = .5;
const MIN_OPACITY = .05;
const RANDOMIZE_OPACITY = true;
const COLOR = 0x474747;

// todo randomize initial opacity

const makeSmokeParticle = (sphereMesh, salt = 1) => {
    sphereMesh.smokeConfig = {
        step: SPEED / 100 + (Math.random() / 1000),
        amplitude: (AMPLITUDE * 10) / 2,
        initialOpacity: sphereMesh.material.opacity,
        offsetX: sphereMesh.position.x,
        offsetY: sphereMesh.position.y,
        offsetZ: sphereMesh.position.z,
        min: sphereMesh.position.y,
        max: sphereMesh.position.y + DISTANCE,
        createGraph: function () {
            let offset = this.offsetY;
            let amplitude = this.amplitude;

            return {
                xMod: Math.random() > 0.5 ? -1 : 1,
                zMod: Math.random() > 0.5 ? -1 : 1,
                function: function (y) {
                    y += offset * -1;

                    return Math.sin( (y * amplitude * salt) * (y / (10 / amplitude)) )
                },
                x: function (vector) {
                    return this.function(vector['y']) * this.xMod;
                },
                z: function (vector) {
                    return this.function(vector['y']) * this.zMod;
                }
            }
        },
        graph: null
    }
    sphereMesh.smoke = function () {
        if (!this.smokeConfig) return;

        let vector = new THREE.Vector3(this.position.x, this.position.y, this.position.z);
        vector['y'] += this.smokeConfig.step;

        if (!this.smokeConfig.graph) {
            this.smokeConfig.graph = this.smokeConfig.createGraph();
        }

        if (vector['y'] >= this.smokeConfig.max) {
            vector['y'] = this.smokeConfig.min;
            this.smokeConfig.graph = this.smokeConfig.createGraph();
        }

        vector['x'] = this.smokeConfig.graph.x(vector) + this.smokeConfig.offsetX;
        vector['z'] = this.smokeConfig.graph.z(vector) + this.smokeConfig.offsetZ;

        if (FADE_AWAY) {
            let position = vector['y'];
            let value = this.smokeConfig.max - position;
            this.material.opacity = value > this.material.opacity ? this.smokeConfig.initialOpacity : value;
        }

        this.position.lerp(vector, 1);
    };

    addUpdateCallback(sphereMesh.smoke.bind(sphereMesh))
}

const random = (min, max) => {
    let rand = Math.random();
    if (rand >= min && rand <= max) {
        return rand;
    }

    return random(min, max);
}

const createSmoke = (x, y, z) => {
    let group = new THREE.Group();
    window.smokeGroup = group;

    for (let i = 0; i < COUNT; i++) {
        let sphereMaterial = new THREE.MeshBasicMaterial({
            color: COLOR,
            transparent: true,
            opacity: RANDOMIZE_OPACITY ? random(MIN_OPACITY, OPACITY) : OPACITY
        });
        let sphereGeometry = new THREE.SphereGeometry(
            random(MIN_SIZE, MAX_SIZE),
            SHARPNESS,
            SHARPNESS
        );

        let sphereMesh = new THREE.Mesh(sphereGeometry, sphereMaterial);

        window.sphere = sphereMesh;

        sphereMesh.position.y = y + (Math.random() / 10);
        sphereMesh.position.z = z;
        sphereMesh.position.x = x;

        sphereMesh.visible = false;

        group.add(sphereMesh);
    }

    let iter = 0;
    let interval = setInterval(function () {
        let children = group.children;
        if (iter >= children.length) {
            clearInterval(interval)

            return;
        }

        let particle = children[iter++];
        makeSmokeParticle(particle, SALT * Math.random())
        particle.visible = true;
    }, 1000 - (FREQUENCY * 1000));


    if (false) {
        const fireCampFolder = getGui().addFolder('Fire Camp Smoke');
        fireCampFolder.addColor({color: COLOR}, 'color').onChange(function (value) {
            group.children.forEach(function (child) {
                child.material.color.set(value)
            })
        });
    }

    return group;
}

export {createSmoke}