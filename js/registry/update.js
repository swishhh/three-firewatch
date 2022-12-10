let updateCallbacks = [];

const addUpdateCallback = (callback) => {
    updateCallbacks.push(callback)
}

const getUpdateCallbacks = () => {
    return updateCallbacks;
}

export {addUpdateCallback, getUpdateCallbacks}