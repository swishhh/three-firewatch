const loaded = {};

const head = document.getElementsByTagName('head')[0];

const loadCss = (path, callback) => {
    if (!loaded.hasOwnProperty(path)) {
        let link = document.createElement('link');
        link.rel  = 'stylesheet';
        link.type = 'text/css';
        link.href = path;
        link.onload = callback;

        head.appendChild(link);
    } else {
        callback();
    }
}

export {loadCss}