"""Port of js/component/objects/bird/index.js: a black, flapping bird hovering over the camp.

A world object of kind 'bird' (world/entities.py) holds one; position and scale come from the save.
"""
from direct.actor.Actor import Actor

from .. import settings
from ..paths import asset, panda_filename

ANIMATION = 'ArmatureAction'
CLIP_DURATION = 2.5  # the JS cut the 5 s clip to its first 2.5 s
MODEL = 'obj/bird-animated.glb'


class Bird:
    def __init__(self, parent, model=MODEL):
        self.actor = Actor(panda_filename(asset(model)))
        self.actor.set_color((0, 0, 0, 1), 1)  # MeshBasicMaterial({color: 0x000000})
        self.actor.reparent_to(parent)
        self.parent = parent
        settings.subscribe(self.apply, 'env.bird')
        self.apply()
        try:
            frame_rate = self.actor.get_frame_rate(ANIMATION)
            self.actor.loop(ANIMATION, fromFrame=0, toFrame=int(round(CLIP_DURATION * frame_rate)))
        except Exception as error:  # a different animated model without that clip
            print(f'bird animation: {error}')
            names = self.actor.get_anim_names()
            if names:
                self.actor.loop(names[0])

    def apply(self, _keys=None):
        self.actor.show() if settings.get('env.bird') else self.actor.hide()

    def destroy(self):
        settings.unsubscribe(self.apply)
        self.actor.cleanup()
        self.actor.remove_node()
