"""Port of js/component/controls/firstPerson.js (PointerLockControls + WASD, jump and gravity), now
walking on the world: the player follows the terrain, collides with objects and trees, steps onto
low colliders and wades slower through water (Player tab of the settings).

Click captures the mouse like requestPointerLock(), Escape releases it. While captured, clicks are
forwarded as the 'first-person-click' event so selection can pick at the crosshair.
"""
import math

from direct.gui.OnscreenText import OnscreenText
from direct.showbase.DirectObject import DirectObject
from panda3d.core import TextNode

from .. import registry, settings
from ..paths import asset, panda_filename
from ..update import add_update_callback
from ..world.collision import Colliders
from .mouse_look import MouseLook

KEYS = ('w', 'a', 's', 'd', 'lshift', 'rshift')
STEP_SOUND = 'sound/player/snow_step.mp3'


class Footsteps:
    """The player's steps: the step sound loops for as long as the player walks and fades out within a
    moment of stopping. Running plays it faster and louder (Player tab)."""

    FADE = .06  # seconds to silence it when the player stops (an instant cut clicks)

    def __init__(self, app):
        self.app = app
        self.sound = None
        self.fade = None  # (start volume, seconds left) while fading out
        path = asset(STEP_SOUND)
        if not path.is_file():
            print(f'footsteps disabled: {path} not found')
            return
        try:
            self.sound = app.loader.load_sfx(panda_filename(path))
            self.sound.set_loop(True)
        except Exception as error:  # no audio device should not stop the game
            print(f'footsteps disabled: {error}')
            self.sound = None

    @property
    def playing(self):
        return self.sound is not None and self.sound.status() == self.sound.PLAYING

    def update(self, delta, walking, running):
        sound = self.sound
        if sound is None:
            return
        get = settings.get
        if walking and get('env.footsteps'):
            self.fade = None
            sound.set_volume(min(get('env.footstep_volume') * (get('env.footstep_run_volume') if running else 1), 1))
            sound.set_play_rate(get('env.footstep_run_rate') if running else 1.0)
            if not self.playing:
                self.app.sfxManagerList[0].set_volume(get('env.master_volume'))
                sound.play()
            return
        if self.playing:
            if self.fade is None:
                self.fade = (sound.get_volume(), self.FADE)
            start, left = self.fade
            left -= delta
            if left <= 0:
                sound.stop()
                self.fade = None
            else:
                sound.set_volume(start * left / self.FADE)
                self.fade = (start, left)


class FirstPersonControls(DirectObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.pressed = dict.fromkeys(KEYS, False)
        self.velocity_z = 0.0
        self.on_ground = False
        self.look = MouseLook(app)
        self.world = registry.get('world')
        self.colliders = Colliders(self.world)
        self.feet = 0.0
        self.x = self.y = 0.0
        # Camera bob state: step phase, how much of the walking bob shows (eases in and out), landing dip.
        self.bob_phase = 0.0
        self.bob_weight = 0.0
        self.bob_speed = 0.0
        self.breath = 0.0
        self.landing = 0.0
        self.footsteps = Footsteps(app)
        self.spawn()
        self.world.add_listener(lambda section: self.spawn() if section == 'loaded' else None)

        # raw- events follow physical keys like KeyboardEvent.code, regardless of layout.
        for key in KEYS:
            self.accept(f'raw-{key}', self._set_pressed, [key, True])
            self.accept(f'raw-{key}-up', self._set_pressed, [key, False])
        self.accept('raw-space', self._jump)
        self.accept('mouse1', self._click)
        self.accept('escape', self.unlock)
        self.accept('window-event', self._window_event)

        self.crosshair = OnscreenText(text='+', pos=(0, -.02), scale=.06, fg=(1, 1, 1, .8), mayChange=False)
        self.crosshair.hide()
        OnscreenText(
            text='click: capture mouse   WASD: move   shift: run   space: jump   E: pick up   1-8: items   F: flashlight   click: swing axe   '
                 'G: drop   esc: release   F1: settings',
            parent=app.a2dBottomLeft, align=TextNode.A_left, pos=(.05, .05), scale=.04,
            fg=(1, 1, 1, .8), shadow=(0, 0, 0, .6),
        )
        add_update_callback(self.update)

    @property
    def is_locked(self):
        return self.look.active

    def spawn(self):
        start = self.world.data['player']
        x, y, _z = start['start']
        self.feet = self.world.terrain.height_at(x, y)
        self.x, self.y = x, y
        self.velocity_z = 0.0
        self.app.camera.set_pos(x, y, self.feet + settings.get('env.eye_height'))
        self.app.camera.set_hpr(start['heading'], 0, 0)

    def lock(self):
        self.look.start()
        self.crosshair.show()

    def unlock(self):
        if not self.is_locked:
            return
        self.look.stop()
        self.crosshair.hide()

    def _set_pressed(self, key, value):
        self.pressed[key] = value

    def _jump(self):
        if self.on_ground and self.is_locked:
            self.velocity_z = settings.get('env.player_jump')
            self.on_ground = False

    def _click(self):
        panel = registry.get('settingsPanel')
        if panel is not None and panel.visible:
            return
        if self.is_locked:
            inventory = registry.get('inventory')
            if inventory is not None and inventory.use():
                return  # the held tool used the click (axe swing)
            self.app.messenger.send('first-person-click')
        else:
            self.lock()

    def _window_event(self, window):
        if window == self.app.win and not window.get_properties().get_foreground():
            self.unlock()

    def update(self, delta):
        if self.is_locked:
            self.look.rotate(self.app.camera)
        delta = min(delta, .1)  # no tunneling through walls after a hitch
        get = settings.get
        eye = get('env.eye_height')
        camera = self.app.camera.get_pos()
        if abs(camera.x - self.x) > .5 or abs(camera.y - self.y) > .5:
            self.x, self.y = camera.x, camera.y  # moved from outside (spawn, tests)
        x, y = self.x, self.y
        running = self.pressed['lshift'] or self.pressed['rshift']
        walk_speed = get('env.player_speed')

        if self.is_locked:
            # moveForward()/moveRight() move on the ground plane whatever the pitch is.
            heading = math.radians(self.app.camera.get_h())
            forward = (-math.sin(heading), math.cos(heading))
            right = (math.cos(heading), math.sin(heading))
            speed = get('env.player_speed') * (get('env.player_run') if self.pressed['lshift'] or self.pressed['rshift'] else 1)
            water = self.world.water_at(x, y)
            if water is not None and not water['walkable'] and self.feet < water['level']:
                speed *= get('env.water_slowdown')
            move_x = move_y = 0.0
            if self.pressed['w'] or self.pressed['s']:
                distance = (1 if self.pressed['w'] else -1)
                move_x += forward[0] * distance
                move_y += forward[1] * distance
            if self.pressed['a'] or self.pressed['d']:
                distance = (1 if self.pressed['d'] else -1)
                move_x += right[0] * distance
                move_y += right[1] * distance
            length = math.hypot(move_x, move_y)
            if length > 0:
                x += move_x / length * speed * delta
                y += move_y / length * speed * delta

        radius, step = get('env.player_radius'), get('env.step_height')
        if get('env.collisions'):
            x, y = self.colliders.resolve(x, y, self.feet, eye + .2, radius, step)  # walls (sideways)
        if get('env.world_bounds'):
            half = self.world.terrain.half - radius
            x, y = max(-half, min(half, x)), max(-half, min(half, y))

        ground = (self.colliders.ground_height(x, y, self.feet, step, radius) if get('env.collisions')
                  else self.world.terrain.height_at(x, y))
        water = self.world.water_at(x, y)
        if water is not None and water['walkable'] and self.feet >= water['level'] - step:
            ground = max(ground, water['level'])  # frozen: walk on the ice
        body = eye + .2  # the body height the collisions use (eyes plus a little head)
        head_before = self.feet + body
        self.velocity_z -= get('env.gravity') * delta
        self.feet += self.velocity_z * delta
        if get('env.collisions') and self.velocity_z > 0:
            # Bump your head on what's above (a ceiling, a beam): stop there and fall back, instead of
            # ending up inside it (which then pushed you sideways out of it).
            ceiling = self.colliders.ceiling_height(x, y, head_before, radius)
            if ceiling is not None and self.feet + body > ceiling:
                self.feet = max(ceiling - body, self.feet - self.velocity_z * delta)
                self.velocity_z = 0.0
        falling = self.velocity_z
        was_on_ground = self.on_ground
        if self.feet <= ground:
            # Walk up slopes and steps; fall when the ground drops away.
            if not was_on_ground and falling < -3:
                self.landing = min(-falling / 15, 1.0)  # dip the view on hard landings
            self.feet = ground
            self.velocity_z = 0
            self.on_ground = True
        elif self.on_ground and self.feet - ground < step and self.velocity_z <= 0:
            self.feet = ground  # stick to the ground going downhill
            self.velocity_z = 0
        else:
            self.on_ground = False

        moved = math.hypot(x - self.x, y - self.y) / max(delta, 1e-4)
        self.x, self.y = x, y
        bob_x, bob_y, bob_z, roll = self._bob(delta, moved, walk_speed, running)
        self.app.camera.set_pos(x + bob_x, y + bob_y, self.feet + eye + bob_z)
        self.app.camera.set_r(roll)

    def _bob(self, delta, speed, walk_speed, running):
        """Camera offsets (x, y, z) and roll from walking, breathing and landing (Player tab); also
        runs the footstep sound while walking."""
        get = settings.get
        ease = 1 - math.exp(-get('env.bob_smoothing') * delta)
        walking = self.on_ground and speed > .2 and self.is_locked
        self.bob_weight += ((1.0 if walking else 0.0) - self.bob_weight) * ease
        self.bob_speed += (speed - self.bob_speed) * ease
        ratio = self.bob_speed / max(walk_speed, .1)
        # One step per half cycle (the bounce bottoms out each step, the sway swings once per two).
        # Steps come faster with speed (square root keeps running from looking frantic).
        if walking or self.bob_weight > .05:
            self.bob_phase += delta * math.pi * get('env.bob_rate') * math.sqrt(max(ratio, .3))
        self.footsteps.update(delta, walking, running)
        if not get('env.head_bob'):
            self.landing = 0.0
            return 0.0, 0.0, 0.0, 0.0
        strength = self.bob_weight * max(ratio, 0) ** get('env.bob_speed_influence')
        if running and walking:
            strength *= get('env.bob_run')
        bounce = -abs(math.sin(self.bob_phase)) * get('env.bob_height') * strength * 2 + get('env.bob_height') * strength
        side = math.sin(self.bob_phase) * get('env.bob_sway') * strength
        roll = math.sin(self.bob_phase) * get('env.bob_roll') * strength

        self.breath += delta
        bounce += math.sin(self.breath * 1.6) * get('env.bob_idle') * (1 - self.bob_weight)
        self.landing *= math.exp(-6 * delta)
        bounce -= get('env.bob_landing') * math.sin(min(self.landing, 1) * math.pi / 2)

        heading = math.radians(self.app.camera.get_h())
        return math.cos(heading) * side, math.sin(heading) * side, bounce, roll


def draw(app):
    registry.add('firstPersonControls', FirstPersonControls(app))
