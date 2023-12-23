import * as THREE from 'three';
import {addUpdateCallback} from "../../../registry/update.js";
import {getGui} from "../../../registry/datGui.js";

const createCanvasMaterial = (size, color) => {
    let canvas = document.createElement('canvas');
    let context = canvas.getContext('2d');
    let texture = new THREE.Texture(canvas);
    let center = size / 2;

    canvas.width = canvas.height = size;

    context.beginPath();
    context.arc(center, center, size/2, 0, 2 * Math.PI, false);
    context.closePath();
    context.fillStyle = color;
    context.fill();
    texture.needsUpdate = true;

    return texture;
}

const draw = (scene, camera, renderer) => {
    const geometry = new THREE.BufferGeometry();
    const material = new THREE.PointsMaterial({
        size: .05,
        color: 0xffffff,
        map: createCanvasMaterial(256, '#ffffff'),
        transparent: true,
        opacity: .3
    });

    const snow = new THREE.Points(geometry, material);
    snow.position.set(0, 0, 0)

    snow.randomVelocity = function () {
        return Math.random() * (this.snowConfig.speed / 100);
    }
    snow.generate = function (index = null) {
        if (index !== null) {
            let velocity = this.geometry.attributes.velocity;
            let positions = this.geometry.attributes.position;

            positions.array[index] = Math.random() * this.snowConfig.range.x;
            positions.array[index + 1] = Math.random() * this.snowConfig.range.y;
            positions.array[index + 2] = Math.random() * this.snowConfig.range.z;

            velocity.array[index] = this.randomVelocity() * (Math.random() > 0.5 ? -1 : 1);
            velocity.array[index + 1] = this.randomVelocity() * (this.snowConfig.speedY / this.snowConfig.speed);
            velocity.array[index + 2] = this.randomVelocity() * (Math.random() > 0.5 ? -1 : 1);

            return;
        }

        let positions = [];
        let velocities = [];
        for (let i = 0; i < this.snowConfig.count; i++) {
            positions.push(
                Math.floor(Math.random() * this.snowConfig.range.x),
                Math.floor(Math.random() * this.snowConfig.range.y),
                Math.floor(Math.random() * this.snowConfig.range.z),
            );
            velocities.push(
                this.randomVelocity(),
                this.randomVelocity() * (this.snowConfig.speedY / this.snowConfig.speed),
                this.randomVelocity(),
            )
        }

        geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
        geometry.setAttribute('velocity', new THREE.Float32BufferAttribute(velocities, 3));
    }

    snow.getSnowAttribute = function (name, index) {
        return [
            this.geometry.attributes[name].array[index],
            this.geometry.attributes[name].array[index + 1],
            this.geometry.attributes[name].array[index + 2]
        ]
    }
    snow.update = function () {
        for (let i = 0; i < this.snowConfig.count * 3; i += 3) {
            let velocity = this.geometry.attributes.velocity;
            let positions = this.geometry.attributes.position;

            positions.array[i] -= velocity.array[i];
            positions.array[i + 1] -= velocity.array[i + 1];
            positions.array[i + 2] -= velocity.array[i + 2];

            let xPos, yPos, zPos;
            [xPos, yPos, zPos] = this.getSnowAttribute('position', i);

            if (xPos < 0 || yPos < 0 || zPos < 0) {
                this.generate(i);
            } else if (xPos > this.snowConfig.range.x || zPos > this.snowConfig.range.x || yPos > this.snowConfig.range.y) {
                this.generate(i)
            }
        }
        snow.geometry.attributes.position.needsUpdate = true;
    }
    snow.initialize = function (configuration) {
        this.snowConfig = configuration;
        this.generate()
        this.position.set(
            this.position.x - (this.snowConfig.range.x / 2),
            this.position.x,
            this.position.z - (this.snowConfig.range.z / 2)
        )
        addUpdateCallback(this.update.bind(this))
    }

    let configuration = {
        count: 5000,
        range: {
            x: 50,
            y: 15,
            z: 50
        },
        speed: 0.9,
        speedY: 6
    }

    snow.initialize(configuration)


    scene.add(snow);

    if (true) {
        const folder = getGui().addFolder('Snow');
        folder.add(snow, 'visible');
        folder.add(configuration, 'count', 0, 90000).onChange(() => snow.generate());
        folder.add(configuration, 'speed', 0, 5).onChange(() => snow.generate());
        folder.add(configuration, 'speedY', 0, 20).onChange(() => snow.generate());
        folder.add(snow.material, 'size', 0, .2);
        folder.add(snow.material, 'transparent');
        folder.add(snow.material, 'opacity', 0, 1);

        folder.close();
    }
}

export {draw}