class IconsManager {
    constructor(width = 50, height = 50) {
        this.width = width;
        this.height = height;
    }
    getIconElement(name, width = null, height = null) {
        let image = document.createElement('img');
        image.src = this.getUrl(name);
        image.width = width === null ? this.width : width;
        image.height = height === null ? this.height : height;
        image.color = 'red';
        image.classList.add(...['svg-icon', name])

        return image;
    }
    getUrl(name) {
        return './icons/' + name + '.svg';
    }
}

export {IconsManager}