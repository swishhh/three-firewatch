import {getGui} from "../../registry/datGui.js";
import {localStorageGet, localStorageSet} from "../../tools/local/storage.js";
import {Toolbar} from "./toolbar/Toolbar.js";

const ENABLED = false;

const draw = (scene, camera, renderer) => {
    const toolbar = new Toolbar(!!isEnabled());

    let plantsFolder = toolbar.addFolder('plants');
    plantsFolder.setIcon('plants');
    plantsFolder.setLabel('Plants');

    let treeFolder = plantsFolder.addFolder('Trees');
    treeFolder.setIcon('tree');
    treeFolder.setLabel('Trees');

    let simpleTree = treeFolder.addItem('simpleTree');
    simpleTree.setLabel('Simple');
    simpleTree.setIcon('tree-simple');

    let harvestTree = treeFolder.addItem('harvestTree');
    harvestTree.setLabel('Harvest');
    harvestTree.setIcon('tree-harvest')

    let christmasTree = treeFolder.addItem('christmasTree');
    christmasTree.setLabel('Christmas');
    christmasTree.setIcon('tree')

    let bush = plantsFolder.addFolder('bushes');
    bush.setIcon('bush');
    bush.setLabel('Bushes');

    toolbar.init();

    let folder = getGui().addFolder('Toolbar');
    folder.add({'enabled': isEnabled()}, 'enabled').onChange((value) => {
        localStorageSet('isToolbarEnabled', value ? 1 : 0)
        toolbar.visible(value);
    })
}

const isEnabled = () => {
    let isEnabled = localStorageGet('isToolbarEnabled');
    isEnabled = isEnabled === undefined ? ENABLED : !!parseInt(isEnabled);

    return isEnabled;
}

export {draw}