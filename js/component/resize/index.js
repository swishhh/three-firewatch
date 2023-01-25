const draw = (scene, camera, renderer) => {
    window.addEventListener( 'resize', () => {
        renderer.setSize(window.innerWidth, window.innerHeight)
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
    }, false);
}

export {draw}