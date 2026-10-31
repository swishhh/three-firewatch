"""Post-processing pipeline (stands in for the JS EffectComposer). Passes, in render order:

1. depth prepass            -> depth, normals (lighting mask, depth of field)
2. ao.frag                  -> lighting mask: AO, contact shadows, sun shadow; then a 4x4 blur
3. scene (MSAA, HDR float)  -> scene          (lighting reads the mask from step 2)
4. bloom_down / bloom_up    -> bloom          (6-level downsample chain + tent upsample)
5. dof.frag                 -> blurred scene  (only while depth of field is on)
6. post.frag                -> graded LDR     (tone mapping, white balance, contrast, ...)
7. final.frag               -> window         (FXAA, sharpen, vignette, grain, dither)

Every buffer scales with the window and the render scale. Changing MSAA, render scale or AO
resolution rebuilds the buffers; everything else only updates shader inputs.
"""
import math

from direct.filter.FilterManager import FilterManager
from direct.showbase.DirectObject import DirectObject
from panda3d.core import Camera, FrameBufferProperties, Mat4, SamplerState, Texture, Vec2, Vec3

from . import registry, settings, shading
from .update import add_update_callback

BLOOM_LEVELS = 6
REBUILD_KEYS = {'gfx.msaa', 'gfx.render_scale', 'gfx.ao_resolution'}
TONEMAPS = {'none': 0, 'reinhard': 1, 'aces': 2, 'agx': 3, 'filmic': 4}


def _texture(name):
    texture = Texture(name)
    texture.set_wrap_u(SamplerState.WM_clamp)
    texture.set_wrap_v(SamplerState.WM_clamp)
    texture.set_minfilter(SamplerState.FT_linear)
    texture.set_magfilter(SamplerState.FT_linear)
    return texture


def _float_buffer(multisamples=0):
    properties = FrameBufferProperties()
    properties.set_float_color(True)
    properties.set_rgba_bits(16, 16, 16, 16)
    if multisamples:
        properties.set_multisamples(multisamples)
    return properties


class Pipeline(DirectObject):
    def __init__(self, app):
        super().__init__()
        self.app = app
        self.manager = None

        camera = Camera('depth-prepass', app.camLens)
        camera.set_camera_mask(shading.PREPASS_CAMERA_MASK)
        camera.set_initial_state(shading.depth_state())
        self.prepass_camera = app.cam.attach_new_node(camera)

        self.build()
        settings.subscribe(self._changed, 'gfx.')
        self.accept('window-event', lambda _window: self._apply_sizes())
        add_update_callback(self.update)

    def build(self):
        app = self.app
        scale = settings.get('gfx.render_scale')
        ao_scale = scale * (.5 if settings.get('gfx.ao_resolution') == 'half' else 1)
        self.manager = manager = FilterManager(app.win, app.cam)

        # Linear filtering: depth is affine across a flat face on screen, so filtered reads are exact on
        # low-poly faces and the AO / contact shadow rays don't hit their own surface in bands.
        self.depth = _texture('prepass-depth')
        self.normals = _texture('prepass-normals')
        width, height = manager.getScaledSize(scale, 1, 1)
        self.prepass = manager.createBuffer('depth-prepass', width, height, (self.depth, self.normals, None, None),
                                            fbprops=_float_buffer())
        self.prepass.set_clear_depth_active(True)
        self.prepass.set_clear_depth(1)
        self.prepass.set_clear_color_active(True)
        self.prepass.set_clear_color((0, 0, 0, 0))
        self.prepass.make_display_region().set_camera(self.prepass_camera)
        manager.buffers.append(self.prepass)
        manager.sizes.append((scale, 1, 1))

        self.ao_raw = _texture('ao-raw')
        self.ao_quad = self._pass('ao', ao_scale, self.ao_raw, 'ao')
        self.ao = _texture('ao')
        self.ao_blur_quad = self._pass('ao-blur', ao_scale, self.ao, 'ao_blur', source=self.ao_raw)
        for quad in (self.ao_quad, self.ao_blur_quad):
            quad.set_shader_input('depth_texture', self.depth)
        self.ao_quad.set_shader_input('normal_texture', self.normals)
        environment = registry.get('environment')
        if environment is not None:
            environment.sun.bind(self.ao_quad)

        self.scene = _texture('scene')
        self.final_quad = manager.renderSceneInto(colortex=self.scene, fbprops=_float_buffer(settings.get('gfx.msaa')))
        manager.sizes[-1] = (scale, 1, 1)

        source, self.bloom_down = self.scene, []
        for level in range(BLOOM_LEVELS):
            texture = _texture(f'bloom-down-{level}')
            quad = self._pass(f'bloom-down-{level}', scale / 2 ** (level + 1), texture, 'bloom_down', float_color=True,
                              source=source, first_pass=1.0 if level == 0 else 0.0)
            self.bloom_down.append((quad, texture))
            source = texture
        lower, self.bloom_up = source, []
        for level in reversed(range(BLOOM_LEVELS - 1)):
            texture = _texture(f'bloom-up-{level}')
            quad = self._pass(f'bloom-up-{level}', scale / 2 ** (level + 1), texture, 'bloom_up', float_color=True,
                              current=self.bloom_down[level][1], lower=lower)
            self.bloom_up.append(quad)
            lower = texture
        self.bloom = lower

        self.dof = _texture('dof')
        self.dof_quad = self._pass('dof', scale / 2, self.dof, 'dof', float_color=True, source=self.scene)

        self.ldr = _texture('ldr')
        self.post_quad = self._pass('post', scale, self.ldr, 'post', scene=self.scene, bloom=self.bloom,
                                    dof_blur_texture=self.dof, depth_texture=self.depth)

        self.final_quad.set_shader(shading.load_shader('quad', 'final'))
        self.final_quad.set_shader_input('image', self.ldr)

        app.render.set_shader_input('ao_texture', self.ao)
        app.render.set_shader_input('depth_texture', self.depth)
        manager.resizeBuffers()
        self._apply_sizes()
        self.apply_settings()

    def _pass(self, name, scale, texture, shader, float_color=False, **inputs):
        quad = self.manager.renderQuadInto(name, mul=scale, colortex=texture,
                                           fbprops=_float_buffer() if float_color else None)
        quad.set_shader(shading.load_shader('quad', shader))
        for input_name, value in inputs.items():
            quad.set_shader_input(input_name, value)
        return quad

    def rebuild(self):
        self.manager.cleanup()
        self.manager.ignore_all()
        self.build()

    def _changed(self, keys):
        if REBUILD_KEYS & set(keys):
            self.rebuild()
        else:
            self.apply_settings()

    def _apply_sizes(self):
        scale = settings.get('gfx.render_scale')
        width, height = self.manager.getScaledSize(scale, 1, 1)
        self.app.render.set_shader_input('screen_size', Vec2(width, height))

    def apply_settings(self):
        get = settings.get
        ao, contact, dof, bloom = get('gfx.ao'), get('gfx.contact_shadows'), get('gfx.dof'), get('gfx.bloom')
        mask = ao or contact or get('gfx.shadows')
        lens = self.app.camLens
        near_far = Vec2(lens.get_near(), lens.get_far())

        # Skip passes nothing reads. Buffer order: prepass, AO, AO blur, scene, bloom..., DoF, post.
        buffers = self.manager.buffers
        bloom_count = BLOOM_LEVELS * 2 - 1
        self.prepass.set_active(mask or dof)
        for buffer in buffers[1:3]:
            buffer.set_active(mask)
        for buffer in buffers[4:4 + bloom_count]:
            buffer.set_active(bloom)
        buffers[4 + bloom_count].set_active(dof)

        for node_path in (self.ao_quad, self.ao_blur_quad, self.post_quad, self.app.render):
            node_path.set_shader_input('near_far', near_far)
        self.ao_quad.set_shader_input('ao_enabled', 1.0 if ao else 0.0)
        self.ao_quad.set_shader_input('ao_radius', get('gfx.ao_radius'))
        self.ao_quad.set_shader_input('ao_strength', get('gfx.ao_strength'))
        self.ao_quad.set_shader_input('ao_samples', get('gfx.ao_samples'))
        self.ao_quad.set_shader_input('contact_enabled', 1.0 if contact else 0.0)
        self.ao_quad.set_shader_input('contact_length', get('gfx.contact_length'))
        self.ao_quad.set_shader_input('contact_strength', get('gfx.contact_strength'))

        render = self.app.render
        render.set_shader_input('ao_enabled', 1.0 if ao or contact else 0.0)
        render.set_shader_input('ao_direct', get('gfx.ao_direct'))
        render.set_shader_input('specular_scale', get('gfx.specular'))

        for quad, _ in self.bloom_down:
            quad.set_shader_input('threshold', get('gfx.bloom_threshold'))
        for quad in self.bloom_up:
            quad.set_shader_input('radius', get('gfx.bloom_radius'))
        self.dof_quad.set_shader_input('dof_blur', get('gfx.dof_blur'))

        post = {
            'bloom_enabled': 1.0 if bloom else 0.0, 'bloom_intensity': get('gfx.bloom_intensity'),
            'dof_enabled': 1.0 if dof else 0.0, 'dof_focus': get('gfx.dof_focus'), 'dof_range': get('gfx.dof_range'),
            'exposure': get('gfx.exposure'), 'tonemap': TONEMAPS[get('gfx.tonemap')],
            'temperature': get('gfx.temperature'), 'tint': get('gfx.tint'), 'saturation': get('gfx.saturation'),
            'contrast': get('gfx.contrast'), 'brightness': get('gfx.brightness'),
        }
        for name, value in post.items():
            self.post_quad.set_shader_input(name, value)

        final = {
            'fxaa_enabled': 1.0 if get('gfx.fxaa') else 0.0, 'sharpen': get('gfx.sharpen'),
            'vignette': get('gfx.vignette'), 'vignette_softness': get('gfx.vignette_softness'),
            'grain': get('gfx.grain'), 'dither_enabled': 1.0 if get('gfx.dither') else 0.0,
        }
        for name, value in final.items():
            self.final_quad.set_shader_input(name, value)

    def update(self, _delta):
        lens = self.app.camLens
        horizontal, vertical = lens.get_fov()
        tan_half_fov = Vec2(math.tan(math.radians(horizontal) / 2), math.tan(math.radians(vertical) / 2))
        for quad in (self.ao_quad, self.ao_blur_quad, self.post_quad):
            quad.set_shader_input('tan_half_fov', tan_half_fov)

        # Contact shadows march towards the sun in OpenGL view space (x right, y up, -z forward).
        environment = registry.get('environment')
        direction = environment.light_direction if environment else Vec3(0, 0, 1)
        local = self.app.cam.get_relative_vector(self.app.render, direction)
        self.ao_quad.set_shader_input('sun_view_direction', Vec3(local.x, local.z, -local.y).normalized())
        # OpenGL view space (x, y, -z forward) -> Panda camera space (x, y forward, z up) -> world.
        gl_to_camera = Mat4(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1)
        self.ao_quad.set_shader_input('view_to_world', gl_to_camera * self.app.cam.get_mat(self.app.render))


def init_pipeline(app):
    registry.add('pipeline', Pipeline(app))
