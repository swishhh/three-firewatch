let storage = {};

/**
 * Add object to registry.
 *
 * @param key
 * @param object
 */
const registryAdd = (key, object) => {
    storage[key] = object;
}

/**
 * Retrieve object from registry.
 *
 * @param key
 * @returns {*}
 */
const registryGet = (key) => {
    return storage[key];
}

export {registryAdd, registryGet}