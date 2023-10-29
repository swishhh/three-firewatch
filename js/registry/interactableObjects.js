let objects = {};

/**
 * Add object to interactable storage.
 *
 * @param key
 * @param object
 */
const interactableAdd = (key, object) => {
    objects[key] = object;
}

/**
 * Retrieve object from interactable storage.
 *
 * @param key
 * @returns {*}
 */
const interactableGet = (key = null) => {
    return key === null ? objects : objects[key];
}

/**
 * Delete object from interactable storage.
 *
 * @param key
 */
const interactableDelete = (key) => {
    delete objects[key];
}

/**
 * Is object interactable.
 *
 * @param object
 * @returns {boolean}
 */
const isInteractable = (object) => {
    return !!interactableGet(object.uuid);
}

export {interactableAdd, interactableGet, interactableDelete, isInteractable}