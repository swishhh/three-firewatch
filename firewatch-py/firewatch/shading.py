"""Shader setup and per-object material switches shared by every component (see shaders/scene.frag)."""
from panda3d.core import BitMask32, CullFaceAttrib, RenderState, Shader, ShaderAttrib, Texture

from .colors import rgb
from .paths import shader

# Separate camera bits let objects opt out of a pass without disappearing from the others.
MAIN_CAMERA_MASK = BitMask32.bit(0)
SHADOW_CAMERA_MASK = BitMask32.bit(1)
PREPASS_CAMERA_MASK = BitMask32.bit(2)

_shaders = {}


def load_shader(vertex, fragment=None):
    key = (vertex, fragment or vertex)
    if key not in _shaders:
        _shaders[key] = Shader.load(Shader.SL_GLSL, vertex=shader(f'{vertex}.vert'),
                                    fragment=shader(f'{fragment or vertex}.frag'))
    return _shaders[key]


def white_texture():
    texture = Texture('white')
    texture.setup_2d_texture(1, 1, Texture.T_unsigned_byte, Texture.F_rgba8)
    texture.set_ram_image(b'\xff\xff\xff\xff')
    return texture


def init(app):
    app.cam.node().set_camera_mask(MAIN_CAMERA_MASK)

    render = app.render
    render.set_shader(load_shader('scene'))
    white = white_texture()
    defaults = {
        'unlit': 0.0, 'shininess': 0.0, 'roughness': 0.0, 'receive_shadow': 1.0, 'specular_scale': 1.0,
        'snow_cover': 0.0, 'sway_amount': 0.0, 'wind_direction': (1, 0, 0), 'wind_strength': 0.0,
        'hemi_sky': (1, 1, 1), 'hemi_ground': (1, 1, 1), 'hemi_intensity': 0.0,
        'sun_direction': (0, 0, 1), 'sun_color': (0, 0, 0), 'use_fog': 0.0, 'fog_color': (0, 0, 0), 'fog_density': 0.0,
        'ao_texture': white, 'ao_enabled': 0.0, 'ao_direct': 0.0, 'screen_size': (1, 1),
        'depth_texture': white, 'near_far': (0.1, 500),
        'fire_shadow_enabled': 0.0, 'fire_shadow_softness': 0.0, 'fire_shadow_position': (0, 0, 0),
    }
    for name, value in defaults.items():
        render.set_shader_input(name, value)


def depth_state(reverse_cull=False):
    """Initial state for depth-only cameras. A high shader priority (rather than an attribute
    override) replaces the scene shaders while keeping per-node inputs such as sway_amount."""
    state = RenderState.make(ShaderAttrib.make(load_shader('depth'), 100))
    if reverse_cull:
        # Back faces into the shadow map, like three.js' default shadowSide.
        state = state.add_attrib(CullFaceAttrib.make_reverse())
    return state


def light_color(color, intensity):
    """three.js r146 with `physicallyCorrectLights` uses color * intensity unscaled; the shader
    applies BRDF_Lambert's 1 / PI itself."""
    r, g, b = rgb(color) * intensity
    return float(r), float(g), float(b), 1.0


def set_point_light(light, color, intensity, distance, decay):
    light.set_color(light_color(color, intensity))
    # scene.frag reads this as three.js' (decay, distance) pair.
    light.set_attenuation((decay, distance, 0))


def set_unlit(node_path):
    node_path.set_shader_input('unlit', 1.0)


def set_shininess(node_path, shininess):
    node_path.set_shader_input('shininess', float(shininess))


def set_standard_material(node_path, roughness=1.0):
    node_path.set_shader_input('roughness', float(roughness))


def set_receive_shadow(node_path, receive):
    node_path.set_shader_input('receive_shadow', 1.0 if receive else 0.0)


def set_cast_shadow(node_path, cast):
    if cast:
        node_path.show(SHADOW_CAMERA_MASK)
    else:
        node_path.hide(SHADOW_CAMERA_MASK)


def set_in_depth_prepass(node_path, included):
    """Transparent and unlit things stay out of the prepass that AO and contact shadows read."""
    if included:
        node_path.show(PREPASS_CAMERA_MASK)
    else:
        node_path.hide(PREPASS_CAMERA_MASK)
