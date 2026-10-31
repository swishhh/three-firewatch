#version 430

// Lighting for everything under render. Base: the parts of three.js r146 shading the JS scene used
// (Phong with specular 0x111111, a dielectric MeshStandardMaterial for the terrain, physically
// correct point lights, FogExp2). On top: a hemisphere world light, the sun (its shadow, AO and
// contact shadows come from the screen-space mask built in ao.frag), and snow cover.
// Output is HDR; tone mapping and grading happen in post.frag.

#define MAX_LIGHTS 8

#pragma include "depth_utils.glsl"

const float RECIPROCAL_PI = 0.3183098861837907;
const vec3 PHONG_SPECULAR = vec3(17.0 / 255.0);
const vec3 SNOW_COLOR = vec3(0.86, 0.9, 0.96);

// Point lights (the campfire) and spotlights (flashlights). The sun is not a Panda light, see sun.py.
uniform struct p3d_LightSourceParameters {
    vec4 diffuse;
    vec4 position;
    vec3 attenuation;  // (decay, distance) as in THREE.PointLight, not Panda's constant/linear/quadratic
    vec3 spotDirection;  // view space
    float spotCosCutoff;  // -1 for point lights
    float spotExponent;   // spotlights: edge softness 0..1 (world/items.py)
} p3d_LightSource[MAX_LIGHTS];

// FogExp2. Plain uniforms: Panda only re-sends p3d_Fog when the fog attribute itself changes.
uniform vec3 fog_color;
uniform float fog_density;

uniform vec4 p3d_ColorScale;
uniform sampler2D p3d_Texture0;  // the material's base color texture (Panda binds white when there is none)
uniform mat4 p3d_ViewMatrixInverse;

// Material
uniform float unlit;           // 1 for MeshBasicMaterial objects: no lighting, fog only
uniform float shininess;       // MeshPhongMaterial.shininess
uniform float roughness;       // > 0 switches to MeshStandardMaterial (metalness 0) with this roughness
uniform float receive_shadow;  // three.js receiveShadow
uniform float specular_scale;
uniform float snow_cover;

// World light and sun
uniform vec3 hemi_sky;
uniform vec3 hemi_ground;
uniform float hemi_intensity;
uniform vec3 sun_direction;  // world space, towards the sun
uniform vec3 sun_color;      // color * intensity * fade
uniform vec3 moon_direction;
uniform vec3 moon_color;
uniform float sun_casts;     // 1 for the light that owns the shadow map and contact shadows
uniform float moon_casts;

// Terrain paint layer: vertex color = painted color, alpha = paint weight over this base color.
uniform vec4 paint_base;     // w = 0 for everything that isn't terrain

uniform int shadow_mode;  // 0: shadows off
uniform float shadow_strength;

// Point light shadows (point_shadow.py): up to three cube maps, each belonging to the point light at
// its position (the campfire, or placed lamps with shadows).
uniform samplerCube fire_shadow_map0;
uniform samplerCube fire_shadow_map1;
uniform samplerCube fire_shadow_map2;
uniform vec3 fire_shadow_position0;
uniform vec3 fire_shadow_position1;
uniform vec3 fire_shadow_position2;
uniform float fire_shadow_enabled0;
uniform float fire_shadow_enabled1;
uniform float fire_shadow_enabled2;
uniform float fire_shadow_softness;  // filter radius, in direction units (about radians)

// Flashlight shadow (spot_shadow.py): perspective depth map from the lens of one spotlight, found
// among the light slots by its world position.
uniform sampler2DShadow flash_shadow_map;
uniform mat4 trans_world_to_clip_of_flashshadow;
uniform float flash_shadow_enabled;
uniform vec3 flash_shadow_position;
uniform float flash_shadow_softness;  // filter radius in texels
uniform float flash_shadow_texel;

// Screen-space lighting mask: AO (R), contact shadows (G), sun shadow (B); see ao.frag
uniform sampler2D ao_texture;
uniform float ao_enabled;
uniform float ao_direct;
uniform vec2 screen_size;

uniform float use_fog;

in vec3 v_world_position;
in vec3 v_world_normal;
in vec3 v_view_position;
in vec3 v_view_normal;
in vec4 v_color;
in vec2 v_uv;
in float v_fog_depth;

out vec4 o_color;

// The lighting mask is computed once per prepass pixel. At silhouettes (MSAA edge pixels, or a
// half-resolution mask) the nearest texel can belong to the object in front, which lit a fringe of
// ground between objects and their shadows; use the neighboring texel whose depth matches ours.
vec3 lighting_mask() {
    vec2 mask_size = vec2(textureSize(ao_texture, 0));
    vec2 center = floor(gl_FragCoord.xy / screen_size * mask_size) + 0.5;
    vec2 best_uv = center / mask_size;
    if (abs(pixel_depth(best_uv) - v_fog_depth) < 0.02 * v_fog_depth) {
        return textureLod(ao_texture, best_uv, 0.0).rgb;  // same surface: the common case
    }
    float best = 1e20;
    for (int x = -1; x <= 1; ++x) {
        for (int y = -1; y <= 1; ++y) {
            vec2 uv = (center + vec2(x, y)) / mask_size;
            float depth = pixel_depth(uv);
            float difference = abs(depth - v_fog_depth) * (x == 0 && y == 0 ? 0.5 : 1.0);  // prefer the center
            if (difference < best) {
                best = difference;
                best_uv = uv;
            }
        }
    }
    return textureLod(ao_texture, best_uv, 0.0).rgb;
}

float cube_distance(int slot, vec3 direction) {
    if (slot == 0) {
        return texture(fire_shadow_map0, direction).r;
    }
    if (slot == 1) {
        return texture(fire_shadow_map1, direction).r;
    }
    return texture(fire_shadow_map2, direction).r;
}

float point_light_shadow(int slot, vec3 light_world, vec3 normal) {
    if (receive_shadow < 0.5) {
        return 1.0;
    }
    vec3 offset = v_world_position + normal * 0.03 - light_world;
    float dist = length(offset);
    vec3 direction = offset / dist;
    vec3 tangent = normalize(cross(direction, abs(direction.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));
    vec3 bitangent = cross(direction, tangent);

    // Vogel disk around the direction; fixed (no per-pixel rotation) so the penumbra has no grain.
    const int SAMPLES = 16;
    float bias = 0.04 + 0.015 * dist;
    float lit = 0.0;
    for (int i = 0; i < SAMPLES; ++i) {
        float radius = sqrt((float(i) + 0.5) / float(SAMPLES)) * fire_shadow_softness;
        float angle = float(i) * 2.39996323;
        vec3 sample_direction = direction + (tangent * cos(angle) + bitangent * sin(angle)) * radius;
        lit += cube_distance(slot, sample_direction) + bias >= dist ? 1.0 : 0.0;
    }
    return lit / float(SAMPLES);
}

// The shadow of the point light at `light_world`, if one of the cube maps belongs to it (the campfire's
// glow light sits a few cm from its main light and shares its map).
float matching_point_shadow(vec3 light_world, vec3 normal) {
    if (fire_shadow_enabled0 > 0.5 && distance(light_world, fire_shadow_position0) < 0.15) {
        return point_light_shadow(0, fire_shadow_position0, normal);
    }
    if (fire_shadow_enabled1 > 0.5 && distance(light_world, fire_shadow_position1) < 0.15) {
        return point_light_shadow(1, fire_shadow_position1, normal);
    }
    if (fire_shadow_enabled2 > 0.5 && distance(light_world, fire_shadow_position2) < 0.15) {
        return point_light_shadow(2, fire_shadow_position2, normal);
    }
    return 1.0;
}

float flash_shadow(vec3 normal, vec3 to_light_world, float dist) {
    if (receive_shadow < 0.5) {
        return 1.0;
    }
    // Normal offset grows with distance (texels get bigger further from the lens).
    float facing = clamp(dot(normal, to_light_world), 0.0, 1.0);
    vec3 position = v_world_position + normal * (0.01 + 0.004 * dist) * (1.0 + 2.0 * (1.0 - facing));
    vec4 clip = trans_world_to_clip_of_flashshadow * vec4(position, 1.0);
    if (clip.w <= 0.0) {
        return 1.0;
    }
    vec3 coords = clip.xyz / clip.w * 0.5 + 0.5;
    if (any(lessThan(coords.xy, vec2(0.0))) || any(greaterThan(coords.xy, vec2(1.0)))) {
        return 1.0;
    }
    float depth = coords.z - 0.00004;
    // 12-tap Vogel disk, fixed rotation (no grain); softer with distance like a real penumbra.
    const int TAPS = 12;
    float radius = flash_shadow_softness * flash_shadow_texel * (1.0 + 0.05 * dist);
    float lit = 0.0;
    for (int i = 0; i < TAPS; ++i) {
        float r = sqrt((float(i) + 0.5) / float(TAPS)) * radius;
        float angle = float(i) * 2.39996323;
        lit += texture(flash_shadow_map, vec3(coords.xy + vec2(cos(angle), sin(angle)) * r, depth));
    }
    return lit / float(TAPS);
}

vec3 F_Schlick(vec3 f0, float f90, float dot_vh) {
    float fresnel = exp2((-5.55473 * dot_vh - 6.98316) * dot_vh);
    return f0 * (1.0 - fresnel) + f90 * fresnel;
}

vec3 specular_brdf(vec3 to_light, vec3 view_dir, vec3 normal) {
    vec3 half_dir = normalize(to_light + view_dir);
    float dot_nh = clamp(dot(normal, half_dir), 0.0, 1.0);
    float dot_vh = clamp(dot(view_dir, half_dir), 0.0, 1.0);

    if (roughness > 0.0) {
        // BRDF_GGX with V_GGX_SmithCorrelated and D_GGX
        float a2 = pow(roughness, 4.0);
        float dot_nl = clamp(dot(normal, to_light), 0.0, 1.0);
        float dot_nv = clamp(dot(normal, view_dir), 0.0, 1.0);
        float gv = dot_nl * sqrt(a2 + (1.0 - a2) * dot_nv * dot_nv);
        float gl = dot_nv * sqrt(a2 + (1.0 - a2) * dot_nl * dot_nl);
        float visibility = 0.5 / max(gv + gl, 1e-6);
        float denominator = dot_nh * dot_nh * (a2 - 1.0) + 1.0;
        float distribution = RECIPROCAL_PI * a2 / (denominator * denominator);
        return F_Schlick(vec3(0.04), 1.0, dot_vh) * (visibility * distribution);
    }

    // BRDF_BlinnPhong: G = 0.25, D_BlinnPhong
    float distribution = RECIPROCAL_PI * (shininess * 0.5 + 1.0) * (shininess > 0.0 ? pow(dot_nh, shininess) : 1.0);
    return F_Schlick(PHONG_SPECULAR, 1.0, dot_vh) * (0.25 * distribution);
}

void main() {
    vec4 base = v_color * p3d_ColorScale * texture(p3d_Texture0, v_uv);
    if (paint_base.w > 0.5) {
        base = vec4(mix(paint_base.rgb, v_color.rgb, v_color.a), 1.0) * p3d_ColorScale;
    }
    vec3 color = base.rgb;

    if (unlit < 0.5) {
        vec3 normal = normalize(v_world_normal);
        if (snow_cover > 0.0) {
            base.rgb = mix(base.rgb, SNOW_COLOR, snow_cover * smoothstep(0.35, 0.8, normal.z));
        }

        vec3 mask = lighting_mask();
        vec2 occlusion = ao_enabled > 0.5 ? mask.rg : vec2(1.0);
        float shadow = shadow_mode > 0 && receive_shadow > 0.5 ? mask.b : 1.0;
        vec3 camera_position = p3d_ViewMatrixInverse[3].xyz;
        vec3 view_dir = normalize(camera_position - v_world_position);

        // HemisphereLight: sky color from above, ground color from below.
        vec3 diffuse = mix(hemi_ground, hemi_sky, normal.z * 0.5 + 0.5) * hemi_intensity * occlusion.r;
        vec3 specular = vec3(0.0);
        float direct_occlusion = mix(1.0, occlusion.r, ao_direct);

        float shadowed = mix(1.0, shadow * occlusion.g, shadow_strength);
        float sun_nl = dot(normal, sun_direction);
        if (sun_nl > 0.0 && dot(sun_color, sun_color) > 0.0) {
            vec3 irradiance = sun_color * sun_nl * mix(1.0, shadowed, sun_casts) * direct_occlusion;
            diffuse += irradiance;
            specular += irradiance * specular_brdf(sun_direction, view_dir, normal);
        }
        float moon_nl = dot(normal, moon_direction);
        if (moon_nl > 0.0 && dot(moon_color, moon_color) > 0.0) {
            vec3 irradiance = moon_color * moon_nl * mix(1.0, shadowed, moon_casts) * direct_occlusion;
            diffuse += irradiance;
            specular += irradiance * specular_brdf(moon_direction, view_dir, normal);
        }

        vec3 view_normal = normalize(v_view_normal);
        vec3 view_view_dir = normalize(-v_view_position);
        for (int i = 0; i < MAX_LIGHTS; ++i) {
            vec3 light_color = p3d_LightSource[i].diffuse.rgb;
            vec4 light_position = p3d_LightSource[i].position;
            if (dot(light_color, light_color) == 0.0 || light_position.w == 0.0) {
                continue;  // unused slot
            }

            vec3 offset = light_position.xyz - v_view_position;
            float dist = length(offset);
            vec3 to_light = offset / dist;

            // getDistanceAttenuation() with PHYSICALLY_CORRECT_LIGHTS
            float decay = p3d_LightSource[i].attenuation.x;
            float cutoff_distance = p3d_LightSource[i].attenuation.y;
            float falloff = 1.0 / max(pow(dist, decay), 0.01);
            if (cutoff_distance > 0.0) {
                float window = clamp(1.0 - pow(dist / cutoff_distance, 4.0), 0.0, 1.0);
                falloff *= window * window;
            }

            vec3 light_world = (p3d_ViewMatrixInverse * vec4(light_position.xyz, 1.0)).xyz;
            float cutoff = p3d_LightSource[i].spotCosCutoff;
            float shadowing = cutoff > -0.999 ? 1.0 : matching_point_shadow(light_world, normal);
            if (cutoff > -0.999) {
                // Spotlight cone: full inside, fading to zero at the edge over `softness` of the angle.
                float along = dot(-to_light, normalize(p3d_LightSource[i].spotDirection));
                float inner = cos(acos(cutoff) * (1.0 - clamp(p3d_LightSource[i].spotExponent, 0.0, 0.98)));
                float cone = smoothstep(cutoff, inner, along);
                falloff *= cone * cone;
                shadowing = 1.0;
                if (flash_shadow_enabled > 0.5 && cone > 0.0) {
                    if (distance(light_world, flash_shadow_position) < 0.02) {
                        vec3 to_light_world = normalize(light_world - v_world_position);
                        shadowing = flash_shadow(normal, to_light_world, dist);
                    }
                }
            }
            vec3 irradiance = light_color * max(dot(view_normal, to_light), 0.0) * falloff * direct_occlusion * shadowing;
            diffuse += irradiance;
            specular += irradiance * specular_brdf(to_light, view_view_dir, view_normal);
        }

        color = diffuse * base.rgb * RECIPROCAL_PI + specular * specular_scale;  // BRDF_Lambert
    }

    if (use_fog > 0.5) {
        float density = fog_density;
        float fog = 1.0 - exp(-density * density * v_fog_depth * v_fog_depth);
        color = mix(color, fog_color, fog);
    }

    o_color = vec4(color, base.a);
}
