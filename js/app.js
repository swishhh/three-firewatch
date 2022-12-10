import * as THREE from 'three';
import { OBJLoader } from 'three/addons/loaders/OBJLoader.js';
import { registryAdd } from "./registry/registry.js";
import { Light } from "./component/light.js";
import { WorldFog} from "./component/fog.js";
import { addOrbitControls} from "./component/controls/orbit.js";
import { addUpdateCallback } from "./registry/update.js";
import { getUpdateCallbacks } from "./registry/update.js";

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera( 75, window.innerWidth / window.innerHeight, 0.1, 1000 );
const renderer = new THREE.WebGLRenderer({
    clearAlpha: 1,
    clearColor: 0xdddddd,
    antialias: true
});
renderer.physicallyCorrectLights = false;
renderer.setClearColor('#415475');

registryAdd('scene', scene);
registryAdd('camera', camera);
registryAdd('renderer', renderer);

const textureLoader = new THREE.TextureLoader();

document.body.appendChild(renderer.domElement);


renderer.setSize( window.innerWidth, window.innerHeight );
document.body.appendChild( renderer.domElement );

renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

camera.position.z = 10;
camera.position.y = 10;
camera.lookAt(scene);

const loader = new OBJLoader();


const treeManager = {
    object: null,
    load: function (x = 0, y = 0, z = 0, scale = 1) {
        loader.load('obj/lowpolytree.obj', (model) => {
            this.object = model.children[0];
            this.object.material.some((material) => {
                let color = material.name === 'Leaves' ? '#164200' : '#472706'
                material.color = new THREE.Color(color);
            })

            this.draw(x, y, z, scale)
        });
    },
    getNewInstance: function () {
        return new THREE.Mesh(this.object.geometry, this.object.material);
    },
    draw: function (x, y, z, scale = 1) {
        if (this.object === null) {
            this.load(x,y,z, scale);
        } else {
            let tree = this.getNewInstance();
            tree.position.x = x;
            tree.position.y = y + (1.9 * scale);
            tree.position.z = z;
            tree.scale.x = scale;
            tree.scale.y = scale;
            tree.scale.z = scale;
            tree.castShadow = true;
            tree.receiveShadow = true;
            scene.add(tree);
            window.tree = tree;
        }
    }
}

const addFireCampLight = (color, x, y, z, intensity, distance, blinking = false) => {
    let light = new THREE.PointLight(color, intensity, distance);
    light.castShadow = true;
    light.position.set(x, y, z);
    light.shadow.mapSize.width = 2048;
    light.shadow.mapSize.height = 2048;
    light.shadow.radius = 20;

    window.firecampLight = light;

    scene.add(light);
    blinking && setInterval(() => {
        let newIntensity = intensity - (Math.random() / 1.5);
        if (newIntensity <= 1.5) {
            newIntensity+= 0.4;
        }
        light.intensity = newIntensity;
        light.position.y = y + ((intensity - newIntensity) / 5);
    }, 100);
}

const generateTerrain = () => {
    const segmentsX = 100;
    const segmentsZ = 100;
    const sizeX = 1.1 * segmentsX;
    const sizeZ = 1.1 * segmentsZ;

    let geometry = new THREE.PlaneBufferGeometry(
        sizeX,
        sizeZ,
        segmentsX,
        segmentsZ
    );
    geometry.rotateX(Math.PI * -0.5);
    let material = new THREE.MeshPhongMaterial( { color: 0x888888 } )
    material.shininess = 0;
    window.material =material;
    const terrain = new THREE.Mesh(geometry, material);

    terrain.receiveShadow = true;
    scene.add(terrain)
    terrain.scale.set(0.3, 0.3, 0.3)

    const totalSegmentsX = segmentsX + 1;
    const totalSegmentsZ = segmentsZ + 1;

    for(let z = 0; z < totalSegmentsZ; z++) {
        for(let x = 0; x < totalSegmentsX; x++) {
            const index = 3 * (z * totalSegmentsX + x);
            let r = 20;
            let center = segmentsX / 2;

            geometry.attributes.position.array[index + 1] = (z - center) * (z - center) + (x - center) * (x - center) <= r * r
                ? (Math.random() / 1.5) * .3
                : Math.random() * 2;
        }
    }
}

const addFireCamp = (x, y, z) => {
    loader.load('obj/firecamp.obj', (model) => {
        scene.add(model);
        model.position.set(x, y, z)
        model.scale.set(.3, .3, .3);
        model.rotateY(45)
        model.traverse((child) => {
            if (child.isMesh) {
                if (child.name.indexOf('tree') !== -1) {
                    child.material.color = new THREE.Color('#bd8446');
                } else if (child.name.indexOf('rock') !== -1) {
                    child.material.color = new THREE.Color('#2f2f2d');
                } else if (child.name.indexOf('cauldron') !== -1) {
                    child.material.color = new THREE.Color('#131313');
                } else if (child.name.indexOf('fire') !== -1) {
                    child.material.color = new THREE.Color('#d21201');
                }
            }
        })
    });
}

const addRocks = (positions, rotateYDeg) => {
    loader.load('obj/rocks.obj', (model) => {
        window.rocks = model;
        scene.add(model);
        model.rotateY(rotateYDeg)
        model.position.set(...positions)
        model.traverse((child) => {
            if (child.isMesh) {
                if (child.name.indexOf('Icosphere') !== -1) {
                    child.material.color = new THREE.Color('#656563');
                }
                child.receiveShadow = true;
                child.castShadow = true;
            }
        })
    });
}

const addTent = () => {
    loader.load('obj/tent.obj', (model) => {
        window.tent = model;
        scene.add(model);
        model.position.set(2, 0, 6)
        model.rotateY(29)
        model.traverse((child) => {
            if (child.isMesh) {
                child.material.some((material) => {
                    if (material.name.indexOf('brown') !== -1) {
                        material.color = new THREE.Color('#381801');
                    }
                    if (material.name.indexOf('green') !== -1) {
                        material.color = new THREE.Color('#d2d1d1');
                    }
                })
                child.receiveShadow = true;
                child.castShadow = true;
            }
        })
    });
}


const addFallingSnow = (snowVelocity = 50) => {
    let geometry = new THREE.BufferGeometry();

    let numOfFlakes = 2500;
    let positions = []; let velocities = [];
    let minRange = 15; let maxRange = 22;
    let minHeight = 0;

    const addSnowFlakes = () => {
        for (let i = 0; i < numOfFlakes; i++) {
            positions.push(
                Math.floor(Math.random() * maxRange - minRange),
                Math.floor(Math.random() * minRange + minHeight),
                Math.floor(Math.random() * maxRange - minRange)
            );
            velocities.push(
                Math.floor(Math.random() * 6 - 3) * (snowVelocity / 10000),
                Math.floor(Math.random() * 5 + .12) * (snowVelocity / 10000),
                Math.floor(Math.random() * 6 - 3) * (snowVelocity / 10000),
            )
        }
    }

    addSnowFlakes();

    let flakeMaterial = new THREE.PointsMaterial({
        size: .05,
        map: textureLoader.load('textures/sprites/snowflake.png'),
        blending: THREE.AdditiveBlending,
        depthTest: false,
        transparent: false,
        opacity: 0.7
    });

    geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
    geometry.setAttribute('velocity', new THREE.Float32BufferAttribute(velocities, 3));

    let particles = new THREE.Points(geometry, flakeMaterial);
    window.particles = particles;
    particles.position.set(0, 0, -1)
    scene.add(particles);

    let updateSnow = () => {
        for (let i = 0; i < numOfFlakes * 3; i += 3) {
            particles.geometry.attributes.position.array[i] -= particles.geometry.attributes.velocity.array[i];
            particles.geometry.attributes.position.array[i + 1] -= particles.geometry.attributes.velocity.array[i + 1];
            particles.geometry.attributes.position.array[i + 2] -= particles.geometry.attributes.velocity.array[i + 2];

            if (particles.geometry.attributes.position.array[i+1] < 0) {
                particles.geometry.attributes.position.array[i] = Math.floor(Math.random() * maxRange - minRange);
                particles.geometry.attributes.position.array[i + 1] = Math.floor(Math.random() * minRange + minHeight) / 2;
                particles.geometry.attributes.position.array[i + 2] = Math.floor(Math.random() * maxRange - minRange) / 2;
            }
            particles.geometry.attributes.position.needsUpdate = true;
        }
    }

    addUpdateCallback(updateSnow)
}

const makeCloudMovable = (
    cloud,
    moveByAxis,
    maxAxisValue,
    minAxisValue,
    step,
    opacityThreshold
) => {
    cloud.material.transparent = true;
    step = step / cloud.scale.z;
    let callback = () => {
        let vector = new THREE.Vector3(
            cloud.position.x,
            cloud.position.y,
            cloud.position.z
        );
        vector[moveByAxis] += step;
        if (vector[moveByAxis] > maxAxisValue) {
            vector[moveByAxis] = minAxisValue
        }
        cloud.position.lerp(vector, 1);
        let pos = vector[moveByAxis];
        pos = (Math.abs(pos > opacityThreshold ? maxAxisValue : minAxisValue) - Math.abs(pos))
        cloud.material.opacity = (pos / step) * (1 / (opacityThreshold / step));
    }

    addUpdateCallback(callback.bind(cloud, moveByAxis, step, maxAxisValue, minAxisValue, opacityThreshold));
}

const addCloud = () => {
    loader.load('obj/cloud.obj', (model) => {
        let object = model.children.pop();
        let map = [
            [
                [-1, 12, 1], [.7, .7, .7]
            ],
            [
                [-10, 9, -3], [.6, .5, .6]
            ],
            [
                [5, 10, 4], [.4, .4, .4]
            ],
            [
                [9, 11, -4], [.8, .8, .8]
            ],
            [
                [-2, 8.5, -10], [.3, .3, .3]
            ],
            [
                [-5, 10, 8], [.9, .9, .9]
            ],
            [
                [8, 9, 10], [.25, .25, .25]
            ],
        ];

        for (let i = 0; i < map.length; i++) {
            let cloud = new THREE.Mesh(object.geometry.clone(), object.material.clone());
            cloud.position.set(...map[i][0])
            cloud.scale.set(...map[i][1])
            cloud.receiveShadow = true;
            cloud.castShadow = true;
            scene.add(cloud);
            makeCloudMovable(
                cloud,
                'z',
                18,
                -18,
                0.007,
                3
            )
        }
    });
}

const addPointLight = (color, x, y, z, intensity, distance, blinking = false, castShadow = true) => {
    let light = new THREE.PointLight(color, blinking ? 0 : intensity, distance);
    light.position.set(x, y, z);
    scene.add(light);
    light.castShadow = castShadow;
    blinking && setInterval(() => {
        light.intensity = intensity;
        setTimeout(() => {
            light.intensity = 0;
        }, 500);
    }, 2000);
}

const addFireWatch = (position, scale, rotateY) => {
    loader.load('obj/firewatch.obj', (model) => {
        scene.add(model);
        model.position.set(...position);
        model.scale.set(...scale);
        model.rotateY(rotateY)

        let glassMaterial = new THREE.MeshPhysicalMaterial({
            reflectivity: 1.0,
            transmission: 1.0,
            roughness: 0,
            metalness: 0,
            color: new THREE.Color('#9f9fbd'),
            ior: 5,
            thickness: .5
        });
        model.traverse((child) => {
            if (child.isMesh) {
                let materialName = child.material.name;
                let material = child.material;
                if (materialName.indexOf('roof') !== -1) {
                    material.color = new THREE.Color('#850707');
                } else if (materialName.indexOf('wood') !== -1) {
                    material.color = new THREE.Color('#251106');
                } else if (materialName.indexOf('Door') !== -1) {
                    material.color = new THREE.Color('#251106');
                } else if (materialName.indexOf('glass') !== -1) {
                    child.material = glassMaterial;
                    window.glass = child.material;
                } else if (materialName.indexOf('rock') !== -1) {
                    material.color = new THREE.Color('#7c7c7c');
                } else if (materialName.indexOf('iron') !== -1) {
                    material.color = new THREE.Color('#0c0c0c');
                } else if (materialName.indexOf('stairs') !== -1) {
                    material.color = new THREE.Color('#0c0c0c');
                } else if (materialName.indexOf('foundation') !== -1) {
                    material.color = new THREE.Color('#0c0c0c');
                } else if (materialName.indexOf('whiteMetal') !== -1) {
                    material.color = new THREE.Color('#282828');
                } else if (materialName.indexOf('wall') !== -1) {
                    material.color = new THREE.Color('#572c16');
                } else if (materialName.indexOf('anten') !== -1) {
                    let position = child.getWorldPosition(new THREE.Vector3())
                    addPointLight('#ff0000', position.x, 7.7, position.z, 4, .65, true)
                    material.color = new THREE.Color('#ff0000');
                } else if (materialName.indexOf('Door') !== -1) {
                    material.color = new THREE.Color('#251106');
                }

                child.castShadow = true;
                child.receiveShadow = true;
            }
        });
    });
}

const addLampPost = () => {
    loader.load('obj/lamp-post.obj', (model) => {
        window.lamp = model;
        scene.add(model);
        model.position.set(-3, 0, -5);
        model.scale.set(.3, .3, .3);
        model.rotateY(Math.PI * -1.9)
        // model.rotateY(rotateY)
        model.traverse((child) => {
            if (child.isMesh) {
                let materialName = child.material.name;
                let material = child.material;
                if (materialName.indexOf('rock') !== -1) {
                    material.color = new THREE.Color('#505050');
                } else if (materialName.indexOf('wood') !== -1) {
                    material.color = new THREE.Color('#251106');
                } else if (materialName.indexOf('grass') !== -1) {
                    material.color = new THREE.Color('#06250a');
                } else if (materialName.indexOf('iron') !== -1) {
                    material.color = new THREE.Color('#0c0c0c');
                } else if (materialName.indexOf('glass') !== -1) {
                    material.color = new THREE.Color('#ffffff');
                    material.emissive.r = 255;
                    let position = child.getWorldPosition(new THREE.Vector3())
                    addPointLight('#ff4d00', position.x - 1, 1.75, position.z + .5, 5, 25)
                }

                child.castShadow = true;
                child.receiveShadow = true;
            }
        });
    });
}

let treesButch = [
    [0,0, -1.5],
    [1.6, 0, -0.7, 0.6],
    [-1.9, 0, -0.9, 0.7],
    [-1.8, 0, -4, 0.9],
    [-1.8, 0, -2.5, 0.5],
    [-.1, 0, -3.5, 0.65],
    [1, 0, -4.5, 0.9],
    [3, 0, -5.5, 0.81],
    [0, 0, -6.5, 1.2],
    [-2.5, 0, -6.6, 0.9],
    [-6, 0, -3.2, 1],
    [-5.8, 0, -1.2, .8],
    [-5.8, .3, -7.9, .4],
    [-6.9, 0, -6.4, .2],
    [-7.3, 0, -7.1, .4],
    [-6.5, 0, -8.9, .7],
    [-4.5, 0, -7.4, .74],
    [-4.5, 0, -9, .9],
    [-2.5, 0, -9.3, 1.1],
    [0, 0, -9, 1.3],
    [2.4, 0, -7.4, .9],
    [4.6, 0, -7.3, .85],
    [6.1, 0, -5.4, 1.2],
    [-8.3, 0, -3.8, 1],
    [-9, 0, -5.4, .5],
    [-8.8, 0, -9.2, .9],
    [-10.5, 0, -7.6, 1.3],
    [-10.6, 0, -4.8, 1.1],
    [-10.1, 0, -2.2, .9],
    [-8.1, 0, -1.6, 1],
    [-6.5, 0, .7, 1],
    [-6.7, 0, 3, .86],
    [-6, 0, 4.8, .86],
    [-4.2, 0, 6.4, .77],
    [-6.2, 0, 6.9, 1.1],
    [-2.2, 0, 7.1, 1.3],
    [.3, 0, 7.5, .6],
    [-.5, 0, 9.1, .9]
];

for (let i = 0; i < treesButch.length; i++) {
    treeManager.draw(...treesButch[i]);
}

treeManager.draw(4.5, 0, 4.8, 0.65);
treeManager.draw(9.2, 0, -2.2, 1.2);
treeManager.draw(7.8, 0, -3.2, 1);

Light();
WorldFog();
addOrbitControls();

addFireCampLight('#ff4d00', 0, 1, 2, 2, 10, true);
addFireCamp(.3, 0, 1.9);
generateTerrain();
addRocks([5.8, -.6, 1.3], 90);
addFallingSnow();
addTent();
//addCloud();
//addFireWatch([-7, 0 , -7], [.040, .050, .040], Math.PI * -1.7);
//addLampPost();

const Interaction = {
    selectedObject: null,
    hoverObject: null,
    pointer: null,
    caster: null,
    init: function () {
        let caster = new THREE.Raycaster();
        let pointer = new THREE.Vector2();
        this.caster = caster;
        this.pointer = pointer;

        addUpdateCallback(this.update.bind(this))
        window.addEventListener('pointermove', this.onMouseMove.bind(this))
        window.addEventListener('click', this.onClick.bind(this))
        window.addEventListener('keydown', this.onKey.bind(this), false)
    },

    highlight: function (object, r, g, b) {
        if (object !== null) {
            let material = object.material;
            if (material.length) {
                if (material.length > 1) {
                    material.some((mat) => {
                        mat.emissive.set(r, g, b);
                    })
                } else {
                    material.emissive.set(r, g, b);
                }
            } else {
                material.emissive.set(r, g, b);
            }
        }
    },

    onMouseMove: function (event) {
        this.pointer.x =  (event.clientX / window.innerWidth) * 2 - 1;
        this.pointer.y = - (event.clientY / window.innerHeight) * 2 + 1;
    },

    onKey: function (event) {
        if (this.selectedObject === null) {
            return;
        }

        let code = event.keyCode;
        switch (code) {
            case 38:
                this.selectedObject.position.z -= 1;
                break;
            case 40:
                this.selectedObject.position.z += 1;
                break;
            case 37:
                this.selectedObject.position.x -= 1;
                break;
            case 39:
                this.selectedObject.position.x += 1;
                break;
        }
    },

    onClick: function (event) {
        if (!event.ctrlKey) {
            return;
        }

        if (this.selectedObject !== null) {
            this.highlight(this.selectedObject, 0, 0, 0);
        }

        if (this.hoverObject !== null) {
            this.selectedObject = this.hoverObject;
            this.highlight(this.selectedObject, 255, 0, 0);
        }
    },

    unHover: function () {
        if (this.hoverObject !== null) {
            //this.highlight(this.hoverObject, 0, 0, 0);
            this.hoverObject = null;
        }
    },

    onHover: function (object) {
        this.unHover();
        this.hoverObject = object;
        //this.highlight(this.hoverObject, 255, 0, 0)
    },

    update: function () {
        this.caster.setFromCamera(this.pointer, camera);
        let intersects = this.caster.intersectObject(scene);
        if (intersects.length) {
            this.onHover(intersects.shift().object);
        }
    }
}

Interaction.init();

//
// window.addEventListener('pointermove', onMouseMove);

window.addEventListener( 'resize', () => {
    renderer.setSize(window.innerWidth, window.innerHeight)
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
}, false);

function animate() {
    requestAnimationFrame(animate);
    let callbacks = getUpdateCallbacks();
    for (let i = 0; i < callbacks.length; i++) {
        callbacks[i]();
    }
    renderer.render( scene, camera );
}

animate();