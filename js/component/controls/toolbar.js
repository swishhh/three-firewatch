import {loadCss} from "../../tools/files/cssLoader.js";
import {objectManager} from "../../tools/object/manager.js";
import {runPlacement} from "./toolbar/place.js";

const draw = (scene, camera, renderer) => {
    loadCss('./css/toolbar.css', () => {
        let div = document.createElement('div');
        div.className = 'toolbar__container';
        document.body.appendChild(div);

        let treeButton = document.createElement('div');
        treeButton.className = 'toolbar__button';
        treeButton.innerHTML = 'tree';

        div.appendChild(treeButton);

        treeButton.addEventListener('click', function (e) {
            objectManager.get('bush-tree-harvest', (model) => {
                runPlacement(model);
            });
        });

        let grassButton = document.createElement('div');
        grassButton.className = 'toolbar__button';
        grassButton.innerHTML = 'grass';

        div.appendChild(grassButton);

        grassButton.addEventListener('click', function (e) {
            objectManager.get('grass', (model) => {
                runPlacement(model);
            });
        });
    })
}

export {draw}