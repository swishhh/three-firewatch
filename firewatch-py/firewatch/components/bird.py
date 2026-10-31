"""Port of js/component/objects/bird/index.js: a black, flapping bird hovering over the camp."""
from direct.actor.Actor import Actor

from .. import settings, shading
from ..coords import three_to_panda
from ..objects import DISTANCE_RENDER_TAG
from ..paths import asset, panda_filename

SCALE = .025
ANIMATION = 'ArmatureAction'
CLIP_DURATION = 2.5  # the JS cut the 5 s clip to its first 2.5 s


def draw(app):
    bird = Actor(panda_filename(asset('obj/bird-animated.glb')))
    bird.set_scale(SCALE)
    bird.set_pos(three_to_panda(0, 7, 0))
    bird.set_color((0, 0, 0, 1), 1)  # MeshBasicMaterial({color: 0x000000})
    shading.set_unlit(bird)
    shading.set_cast_shadow(bird, False)
    shading.set_in_depth_prepass(bird, False)
    bird.set_tag(DISTANCE_RENDER_TAG, '1')

    # Toggled through a parent so the distance culling's show()/hide() on the bird doesn't undo it.
    root = app.render.attach_new_node('bird')
    bird.reparent_to(root)
    settings.subscribe(lambda _keys: root.show() if settings.get('env.bird') else root.hide(), 'env.bird')
    if not settings.get('env.bird'):
        root.hide()

    frame_rate = bird.get_frame_rate(ANIMATION)
    bird.loop(ANIMATION, fromFrame=0, toFrame=int(round(CLIP_DURATION * frame_rate)))
