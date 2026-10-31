#version 430

// Lighting for everything under render. Base: the parts of three.js r146 shading the JS scene used
// (Phong with specular 0x111111, a dielectric MeshStandardMaterial for the terrain, physically
// correct point lights, FogExp2). On top: a hemisphere world light, the sun (its shadow, AO and
// contact shadows come from the screen-space mask built in ao.frag), and snow cover.
// Output is HDR; tone mapping and grading happen in post.frag.

#define MAX_LIGHTS 4

#pragma include "depth_utils.glsl"

const float RECIPROCAL_PI = 0.3183098861837907;
const vec3 PHONG_SPECULAR = vec3(17.0 / 255.0);
const vec3 SNOW_COLOR = vec3(0.86, 0.9, 0.96);

// Point lights (the campfire). The sun is not a Panda light, see sun.py.
uniform struct p3d_LightSourceParameters {
    vec4 diffuse;
    vec4 position;
    vec3 attenuation;  // (decay, distance) as in THREE.PointLight, not Panda's constant/linear/quadratic
} p3d_LightSource[MAX_LIGHTS];

// FogExp2. Plain uniforms: Panda only re-sends p3d_Fog when the fog attribute itself changes.
uniform vec3 fog_color;
uniform float fog_density;

uniform vec4 p3d_ColorScale;
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
uniform vec3 sun_color;      // color * intensity

uniform int shadow_mode;  // 0: shadows off
uniform float shadow_strength;

// Campfire shadows (point_shadow.py): distance from the fire to the nearest caster, per direction.
uniform samplerCube fire_shadow_map;
uniform vec3 fire_shadow_position;
uniform float fire_shadow_enabled;
uniform float fire_shadow_softness;  // filter radius, in direction units (about radians)

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

float fire_shadow(vec3 normal) {
    if (fire_shadow_enabled < 0.5 || receive_shadow < 0.5) {
        return 1.0;
    }
    vec3 offset = v_world_position + normal * 0.03 - fire_shadow_position;
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
        lit += texture(fire_shadow_map, sample_direction).r + bias >= dist ? 1.0 : 0.0;
    }
    return lit / float(SAMPLES);
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
    vec4 base = v_color * p3d_ColorScale;
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

        float sun_nl = dot(normal, sun_direction);
        if (sun_nl > 0.0) {
            vec3 irradiance = sun_color * sun_nl * mix(1.0, shadow * occlusion.g, shadow_strength) * direct_occlusion;
            diffuse += irradiance;
            specular += irradiance * specular_brdf(sun_direction, view_dir, normal);
        }

        vec3 view_normal = normalize(v_view_normal);
        vec3 view_view_dir = normalize(-v_view_position);
        float point_shadow = fire_shadow(normal);  // the campfire's lights are the only point lights
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

            vec3 irradiance = light_color * max(dot(view_normal, to_light), 0.0) * falloff * direct_occlusion * point_shadow;
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
