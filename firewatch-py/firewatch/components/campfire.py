"""Port of js/component/objects/campFire/index.js: flickering lights, crackling sound and smoke."""
import io
import random
import wave

import numpy as np
from direct.showbase.Audio3DManager import Audio3DManager
from panda3d.core import Datagram, MovieAudio, PointLight, VirtualFileMountRamdisk, VirtualFileSystem

from .. import interactables, objects, registry, settings, shading
from ..coords import three_to_panda
from ..paths import asset, panda_filename
from ..point_shadow import PointShadow
from ..update import add_update_callback, fixed_step
from .smoke import create_smoke

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


def add_sound(app, model):
    try:
        audio = Audio3DManager(app.sfxManagerList[0], app.camera)
        sound = audio.load_sfx(load_mono(asset('sound/campFire/sound.mp3')))
    except Exception as error:  # no audio device should not stop the scene
        print(f'campfire sound disabled: {error}')
        return

    # Panda's OpenAL distance model is the Web Audio 'inverse' model three's PositionalAudio used.
    audio.attach_sound_to_object(sound, model)
    audio.set_sound_min_distance(sound, 1)  # setRefDistance(1)
    audio.set_drop_off_factor(3)  # setRolloffFactor(3)
    sound.set_loop(True)
    sound.play()

    def apply_volume(_keys=None):
        sound.set_volume(settings.get('env.fire_volume'))
        app.sfxManagerList[0].set_volume(settings.get('env.master_volume'))

    settings.subscribe(apply_volume, 'env.')
    apply_volume()


def draw(app):
    model = objects.get('camp-fire')
    model.set_scale(.7)
    model.set_pos(three_to_panda(2.7, 0, -2.5))
    # The JS set `recieveShadow` (sic), so the campfire never received shadows.
    shading.set_receive_shadow(model, False)
    interactables.add(model)

    # Colors, intensities (2 and 3), distances (10 and .5) and decays (.9 and 5.2) are settings.
    camp_light = PointLight('camp-light')
    camp_light_path = model.attach_new_node(camp_light)
    camp_light_path.set_pos(three_to_panda(0, .8, 0))

    glow_light = PointLight('camp-glow-light')
    glow_light_path = model.attach_new_node(glow_light)
    glow_light_path.set_pos(three_to_panda(0, .75, 0))

    app.render.set_light(camp_light_path)
    app.render.set_light(glow_light_path)

    # campLight.castShadow = true; reaches as far as the light's default distance.
    registry.add('fireShadow', PointShadow(app, camp_light_path, far=12))

    blink = Blink(camp_light, glow_light)
    blink.apply()
    settings.subscribe(lambda _keys: blink.apply(), 'env.')
    add_update_callback(fixed_step(blink))

    add_sound(app, model)

    model.reparent_to(app.render)
    create_smoke(app, 2.7, .7 + .5, -2.5)
