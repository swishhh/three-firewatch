let resizeCallbacks = [];

const addResizeCallback = (callback) => {
    resizeCallbacks.push(callback)
}

const getResieCallbacks = () => {
    return resizeCallbacks;
}

export {addResizeCallback, getResieCallbacks}