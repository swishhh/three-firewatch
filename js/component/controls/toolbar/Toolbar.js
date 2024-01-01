import {loadCss} from "../../../tools/files/cssLoader.js";
import {IconsManager} from "./IconsManager.js";

class Toolbar {
    containerClass = 'toolbar__container'
    containerId = 'toolbar'
    folders = {}
    constructor(visible = true) {
        this.isVisible = visible;
        this.iconsManager = new IconsManager(10, 10);
    }
    init() {
        loadCss('./css/toolbar.css', () => {
            this.container = document.createElement('div');
            this.container.className = this.containerClass;
            this.container.id = this.containerId;

            this.grid = this.getGridElement();
            this.container.appendChild(this.grid);

            this.renderChildren();
            this.visible(this.isVisible)

            document.body.appendChild(this.container);

        })
    }
    renderChildren(root = null) {
        this.rebuildGrid();
        this.addBackButton(root);
        for (const [name, folder] of Object.entries(root !== null ? root.children : this.folders)) {
            let element = this.createGridElement(folder.label, folder.icon);
            element.classList.add(folder.className);
            if (folder.isFolder) {
                folder.onClick(() => {
                    this.renderChildren(folder)
                })
            }
            element.addEventListener('click', folder.click.bind(folder))

            this.grid.appendChild(element);
        }
    }
    getGridElement() {
        let element = document.createElement('div');
        element.classList.add('toolbar__grid');

        return element;
    }
    rebuildGrid() {
        let newGrid = this.getGridElement();
        this.grid.replaceWith(newGrid);
        this.grid = newGrid;
    }
    addBackButton(root) {
        if (root) {
            let element = this.createGridElement('Back');
            element.classList.add('toolbar__back')
            element.addEventListener('click', () => {
                this.renderChildren(root.parent instanceof Toolbar ? null : root.parent);
            })
            let icon = document.createElement('i');
            icon.classList.add(...['fa', 'fa-chevron-circle-left', 'grid__item-icon']);
            element.appendChild(icon);

            this.grid.appendChild(element);
        }
    }
    createGridElement(name, icon) {
        let item = document.createElement('div');
        item.classList.add('grid__item')
        if (name) {
            let label = document.createElement('span');
            label.innerHTML = name;

            item.appendChild(label);
        }
        if (icon) {
            let iconElement = this.iconsManager.getIconElement(icon);
            iconElement.classList.add(...['grid__item-icon'])
            item.appendChild(iconElement)
        }

        return item;
    }
    visible(visible = true) {
        this.container.classList.remove('hide');
        this.container.classList.remove('show');
        this.container.classList.add(visible ? 'show' : 'hide');
    }
    addFolder(name, label, icon) {
        let folder = new ToolbarFolder(name, this);
        folder.setLabel(label);
        folder.setIcon(icon);

        return this.folders[name] = folder;
    }
    getFolder(name = null) {
        if (name === null) return this.folders;

        return this.folders[name];
    }
}

class ToolbarChild {
    icon = null
    label = null
    click(event) {
        this.clickCallback && this.clickCallback(event)
    }
    onClick(callback) {
        this.clickCallback = callback;
    }
    setIcon(name) {
        this.icon = name;
    }
    setLabel(label) {
        this.label = label;
    }
}

class ToolbarFolderItem extends ToolbarChild {
    className = 'toolbar__item'
    isItem = true
    constructor(name) {
        super();
        this.name = name;
    }
}

class ToolbarFolder extends ToolbarChild {
    className = 'toolbar__folder'
    isFolder = true
    children = {}
    constructor(name, parent) {
        super();
        this.name = name;
        this.parent = parent;
    }
    addFolder(name, label, icon) {
        let folder = new ToolbarFolder(name, this);
        folder.setLabel(label);
        folder.setIcon(icon);

        return this.children[name] = folder;
    }
    addItem(name, label, icon) {
        let item = new ToolbarFolderItem(name);
        item.setLabel(label)
        item.setIcon(icon)

        return this.children[name] = item;
    }
}

export {Toolbar}