"""Port of js/component/objects/campFire/index.js: flickering lights, crackling sound and smoke.

A world object of kind 'campfire' (world/entities.py) gets a CampfireRig on its model."""
import io
import random
import wave

import numpy as np
from direct.showbase.Audio3DManager import Audio3DManager
from panda3d.core import Datagram, MovieAudio, PointLight, VirtualFileMountRamdisk, VirtualFileSystem

from .. import settings, shading
from ..coords import three_to_panda
from ..paths import asset, panda_filename
from ..update import add_update_callback, fixed_step, remove_update_callback
from .fire import Flames
from .smoke import Smoke

BLINK_STEP_MIN = 0.01
BLINK_STEP_MAX = 0.02

AUDIO_MOUNT = '/firewatch-audio'


class Blink:
    """campLight.blink(): a random walk from the set intensity down to 0.1 below it, plus occasional
    flares. The glow light moves by ten times the same increments."""

    def __init__(self, light, glow_light):
        self.light = light
        self.glow_light = glow_light
        self.offset = 0.0
        self.step = 0.01
        self.mod = 1

    def __call__(self):
        flicker = settings.get('env.fire_flicker')
        rand_step = random.random()
        if BLINK_STEP_MIN <= rand_step <= BLINK_STEP_MAX:
            self.step = rand_step

        increment = (self.step * self.mod
                     + (.3 if random.random() < .005 else 0)
                     + (self.step * 4 if random.random() < .02 else 0))

        self.offset += increment * flicker
        if self.offset > 0:
            self.mod = -1
        elif self.offset < -.1 * flicker:
            self.mod = 1
        self.apply()

    def apply(self):
        get = settings.get
        shading.set_point_light(self.light, get('env.fire_color'), get('env.fire_intensity') + self.offset,
                                get('env.fire_distance'), get('env.fire_decay'))
        shading.set_point_light(self.glow_light, get('env.glow_color'), get('env.glow_intensity') + self.offset * 10,
                                get('env.glow_distance'), get('env.glow_decay'))


def load_mono(path):
    """OpenAL only spatializes mono sources, while three's PositionalAudio downmixed stereo itself.
    Decode to PCM, average the channels and serve the result as a WAV from an in-memory mount."""
    cursor = MovieAudio.get(panda_filename(path)).open()
    samples = Datagram()
    cursor.read_samples(int(cursor.length() * cursor.audio_rate()), samples)  # reading past the end pads silence
    pcm = np.frombuffer(samples.get_message(), dtype=np.int16).reshape(-1, cursor.audio_channels())

    wav = io.BytesIO()
    with wave.open(wav, 'wb') as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(cursor.audio_rate())
        file.writeframes(pcm.mean(axis=1).astype(np.int16).tobytes())

    vfs = VirtualFileSystem.get_global_ptr()
    if not vfs.is_directory(AUDIO_MOUNT):
        vfs.mount(VirtualFileMountRamdisk(), AUDIO_MOUNT, 0)
    filename = f'{AUDIO_MOUNT}/{path.stem}.wav'
    vfs.write_file(filename, wav.getvalue(), False)
    return filename


class CampfireRig:
    """Lights (the first two campfires get them), crackling sound and smoke for a campfire world object
    (its shadow map comes from point_shadow.PointShadows). `model` is its root node."""

    instances = []

    def __init__(self, app, model):
        self.app = app
        self.model = model
        self.lights = []
        self.shadow = None
        self.sound = None
        self.audio = None
        index = len(CampfireRig.instances)
        CampfireRig.instances.append(self)

        if index < 2:
            # Colors, intensities (2 and 3), distances (10 and .5) and decays (.9 and 5.2) are settings.
            camp_light = PointLight('camp-light')
            camp_light_path = model.attach_new_node(camp_light)
            camp_light_path.set_pos(three_to_panda(0, .8, 0))
            glow_light = PointLight('camp-glow-light')
            glow_light_path = model.attach_new_node(glow_light)
            glow_light_path.set_pos(three_to_panda(0, .75, 0))
            for path in (camp_light_path, glow_light_path):
                app.render.set_light(path)
                self.lights.append(path)
            self.blink = Blink(camp_light, glow_light)
            self.blink.apply()
            settings.subscribe(self._apply, 'env.')
            self._step = fixed_step(self.blink)
            add_update_callback(self._step)
            # campLight.castShadow = true: point_shadow.PointShadows gives it a shadow map.

        self._add_sound()
        self.flames = Flames(app, model)
        self.smoke = Smoke(app, app.render, self._smoke_origin())
        settings.subscribe(self._smoke_moved, 'env.smoke_offset')

    def _smoke_origin(self):
        # The JS started the smoke at the model's scale plus half a meter above its base; the World tab's
        # smoke offsets move it from there (world axes, meters).
        position = self.model.get_pos(self.app.render)
        get = settings.get
        return (position.x + get('env.smoke_offset_x'), position.y + get('env.smoke_offset_y'),
                position.z + self.model.get_sz(self.app.render) + .5 + get('env.smoke_offset_z'))

    def _smoke_moved(self, _keys=None):
        self.smoke.move_to(self._smoke_origin())

    def _apply(self, _keys=None):
        self.blink.apply()

    def moved(self):
        """Smoke starts where the fire is (lights and shadow follow the model by themselves)."""
        self.smoke.move_to(self._smoke_origin())

    def _add_sound(self):
        app = self.app
        try:
            self.audio = Audio3DManager(app.sfxManagerList[0], app.camera)
            self.sound = self.audio.load_sfx(load_mono(asset('sound/campFire/sound.mp3')))
        except Exception as error:  # no audio device should not stop the scene
            print(f'campfire sound disabled: {error}')
            self.sound = None
            return
        # Panda's OpenAL distance model is the Web Audio 'inverse' model three's PositionalAudio used.
        self.audio.attach_sound_to_object(self.sound, self.model)
        self.audio.set_sound_min_distance(self.sound, 1)  # setRefDistance(1)
        self.audio.set_drop_off_factor(3)  # setRolloffFactor(3)
        self.sound.set_loop(True)
        self.sound.play()
        settings.subscribe(self._apply_volume, 'env.')
        self._apply_volume()

    def _apply_volume(self, _keys=None):
        if self.sound is not None:
            self.sound.set_volume(settings.get('env.fire_volume'))
            self.app.sfxManagerList[0].set_volume(settings.get('env.master_volume'))

    def destroy(self):
        if self in CampfireRig.instances:
            CampfireRig.instances.remove(self)
        for path in self.lights:
            self.app.render.clear_light(path)
            path.remove_node()
        if self.lights:
            settings.unsubscribe(self._apply)
            remove_update_callback(self._step)
        if self.sound is not None:
            settings.unsubscribe(self._apply_volume)
            self.audio.detach_sound(self.sound)
            self.sound.stop()
        settings.unsubscribe(self._smoke_moved)
        self.flames.destroy()
        self.smoke.destroy()
