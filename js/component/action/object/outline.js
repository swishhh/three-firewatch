import * as THREE from 'three';
import {EffectComposer} from "../../../../lib/addons/postprocessing/EffectComposer.js";
import {RenderPass} from "../../../../lib/addons/postprocessing/RenderPass.js";
import {OutlinePass} from "../../../../lib/addons/postprocessing/OutlinePass.js";
import {ShaderPass} from "../../../../lib/addons/postprocessing/ShaderPass.js";
import {FXAAShader} from "../../../../lib/addons/shaders/FXAAShader.js";
import {addUpdateCallback} from "../../../registry/update.js";
import {addResizeCallback} from "../../../registry/resize.js";

let outlinePass;
let outlineObjects = {};

const outline = (object) => {
    outlineObjects[object.uuid] = object;
    outlinePass.selectedObjects = Object.values(outlineObjects)
}

const removeOutline = (object = null) => {
    if (!object || !object.uuid) {
        outlineObjects = {};
    } else if (object.uuid) {
        delete outlineObjects[object.uuid];
    }

    outlinePass.selectedObjects = Object.values(outlineObjects)
}

const draw = (scene, camera, renderer) => {
    outlinePass = new OutlinePass( new THREE.Vector2( window.innerWidth, window.innerHeight ), scene, camera );

    const composer = new EffectComposer( renderer );
    const renderPass = new RenderPass( scene, camera );
    const effectFXAA = new ShaderPass( FXAAShader );

    effectFXAA.uniforms[ 'resolution' ].value.set( 1 / window.innerWidth, 1 / window.innerHeight );

    composer.addPass( renderPass );
    composer.addPass( outlinePass );
    composer.addPass( effectFXAA );

    outlinePass.visibleEdgeColor.set('#ffffff');
    outlinePass.hiddenEdgeColor.set('#ffffff');

    outlinePass.edgeThickness = .1;
    outlinePass.edgeStrength = 2;
    outlinePass.pulsePeriod = 0;

    addUpdateCallback(composer.render.bind(composer));

    const resizeCallback = () => {
        const width = window.innerWidth;
        const height = window.innerHeight;

        composer.setSize( width, height );
        effectFXAA.uniforms[ 'resolution' ].value.set( 1 / window.innerWidth, 1 / window.innerHeight );
    }
    addResizeCallback(resizeCallback)
}

export {draw, outline, removeOutline};