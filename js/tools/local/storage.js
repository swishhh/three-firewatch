const storage = window.localStorage;

const localStorageSet = (key, value) => {
    storage.setItem(key, value);
}

const localStorageGet = (key = null) => {
    if (key === null) return storage;

    return storage.getItem(key);
}

const localStorageDelete = (key) => {
    storage.removeItem(key);
}

const localStorageClear = () => {
    storage.clear();
}

export {localStorageSet, localStorageGet, localStorageDelete, localStorageClear}