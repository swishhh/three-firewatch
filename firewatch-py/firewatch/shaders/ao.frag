#version 430

// Screen-space lighting mask from the depth prepass: ambient occlusion (R), sun contact shadows (G)
// and the sun shadow map lookup (B). Sample rotations follow a 4x4 Bayer tile, which the 4x4
// blur in ao_blur.frag averages out exactly: smooth penumbrae instead of per-pixel grain.

#pragma include "depth_utils.glsl"

uniform mat4 view_to_world;  // OpenGL view space of the main camera -> world
uniform sampler2D normal_texture;  // prepass view-space normals

uniform float ao_enabled;
uniform float ao_radius;
uniform float ao_strength;
uniform int ao_samples;
uniform float contact_enabled;
uniform float contact_length;
uniform float contact_strength;
uniform vec3 sun_view_direction;

// Sun shadow map (sun.py)
uniform sampler2DShadow sun_shadow_compare;
uniform sampler2D sun_shadow_depth;
uniform mat4 trans_world_to_clip_of_sun;
uniform int shadow_mode;  // 0 off, 1 hard, 2 PCF, 3 PCSS
uniform int shadow_samples;
uniform float shadow_film;          // world size covered by the shadow map
uniform float shadow_resolution;
uniform float shadow_depth_range;   // far - near of the shadow camera
uniform float shadow_light_size;    // tan of the sun's angular radius (PCSS)
uniform float shadow_blur;          // filter radius in texels (PCF)
uniform float shadow_bias;          // normal offset in texels

const float PI = 3.141592653589793;
const int CONTACT_STEPS = 16;
const float CONTACT_THICKNESS = 0.35;
const float CONTACT_FADE_START = 15.0;
const float CONTACT_FADE_END = 30.0;
const float BLOCKER_SEARCH_DISTANCE = 12.0;  // world units above a receiver that can still blur its shadow

in vec2 v_uv;

out vec4 o_color;

float bayer4(vec2 pixel) {
    const float matrix[16] = float[](0, 8, 2, 10, 12, 4, 14, 6, 3, 11, 1, 9, 15, 7, 13, 5);
    ivec2 cell = ivec2(mod(pixel, 4.0));
    return (matrix[cell.y * 4 + cell.x] + 0.5) / 16.0;
}

// Vogel disk: evenly spread samples for any count, rotated per pixel.
vec2 vogel_disk(int index, int count, float rotation) {
    float radius = sqrt((float(index) + 0.5) / float(count));
    float angle = float(index) * 2.39996323 + rotation;
    return vec2(cos(angle), sin(angle)) * radius;
}

float sun_shadow(vec3 world_position, vec3 world_normal, float rotation) {
    vec3 to_sun = normalize((view_to_world * vec4(sun_view_direction, 0.0)).xyz);
    float dot_nl = dot(world_normal, to_sun);
    if (dot_nl <= 0.0) {
        // Facing away from the sun is self-shadowed. Storing "lit" here made no difference to
        // this surface, but the blur bled it into the shadowed ground where they meet (a white
        // line between objects and their shadows).
        return 0.0;
    }

    // Normal offset, larger at grazing angles, keeps lit faces from shadowing themselves.
    float texel_world = shadow_film / shadow_resolution;
    vec3 position = world_position + world_normal * texel_world * shadow_bias * (1.0 + 2.0 * (1.0 - dot_nl));
    vec3 coords = (trans_world_to_clip_of_sun * vec4(position, 1.0)).xyz * 0.5 + 0.5;
    if (any(lessThan(coords, vec3(0.0))) || any(greaterThan(coords, vec3(1.0)))) {
        return 1.0;  // like three.js, anything outside the shadow camera is lit
    }
    float depth = coords.z - 0.00003;

    if (shadow_mode == 1) {
        return texture(sun_shadow_compare, vec3(coords.xy, depth));
    }

    // Receiver plane: how this face's shadow-map depth changes per unit of shadow-map uv, from two
    // tangents projected into the (orthographic) shadow camera. Each filter tap then compares
    // against the face itself instead of a flat depth.
    vec3 tangent = normalize(cross(world_normal, abs(world_normal.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0)));
    vec3 a = (trans_world_to_clip_of_sun * vec4(tangent, 0.0)).xyz;
    vec3 b = (trans_world_to_clip_of_sun * vec4(cross(world_normal, tangent), 0.0)).xyz;
    float determinant = a.x * b.y - a.y * b.x;
    vec2 gradient = abs(determinant) > 1e-8 ? vec2(a.z * b.y - b.z * a.y, a.x * b.z - b.x * a.z) / determinant : vec2(0.0);

    float texel = 1.0 / shadow_resolution;
    float radius = shadow_blur * texel;

    if (shadow_mode == 3) {
        // Blocker search: average depth of the occluders around the receiver.
        float search = shadow_light_size * BLOCKER_SEARCH_DISTANCE / shadow_film;
        float blocker_sum = 0.0;
        int blockers = 0;
        for (int i = 0; i < 16; ++i) {
            vec2 offset = vogel_disk(i, 16, rotation) * search;
            float sample_depth = texture(sun_shadow_depth, coords.xy + offset).r;
            if (sample_depth < depth + clamp(dot(offset, gradient), -0.002, 0.002) - 0.0002) {
                blocker_sum += sample_depth;
                blockers += 1;
            }
        }
        if (blockers == 0) {
            return 1.0;
        }
        // The penumbra grows with the blocker-receiver distance: sharp at contact, soft away from it.
        float blocker_distance = (depth - blocker_sum / float(blockers)) * shadow_depth_range;
        radius = max(blocker_distance * shadow_light_size / shadow_film, texel);
    }

    float lit = 0.0;
    for (int i = 0; i < shadow_samples; ++i) {
        vec2 offset = vogel_disk(i, shadow_samples, rotation) * radius;
        lit += texture(sun_shadow_compare, vec3(coords.xy + offset, depth + clamp(dot(offset, gradient), -0.002, 0.002)));
    }
    return lit / float(shadow_samples);
}

void main() {
    vec2 uv = snap_to_depth_pixel(v_uv);
    if (textureLod(depth_texture, uv, 0.0).r >= 1.0) {
        o_color = vec4(1.0);  // sky
        return;
    }

    vec3 position = view_position(uv);
    vec2 texel = 1.0 / vec2(textureSize(depth_texture, 0));

    // The prepass normal: the interpolated one the lighting uses. Normals rebuilt from depth would be
    // per triangle, and AO would draw the terrain's triangles onto smooth hills.
    vec3 normal = texture(normal_texture, uv).xyz;
    if (dot(normal, normal) < 0.25) {
        // No normal written: rebuild the face normal from depth, using neighbors on the same surface.
        vec3 right = view_position(uv + vec2(texel.x, 0.0));
        vec3 left = view_position(uv - vec2(texel.x, 0.0));
        vec3 up = view_position(uv + vec2(0.0, texel.y));
        vec3 down = view_position(uv - vec2(0.0, texel.y));
        vec3 dx = abs(right.z - position.z) < abs(position.z - left.z) ? right - position : position - left;
        vec3 dy = abs(up.z - position.z) < abs(position.z - down.z) ? up - position : position - down;
        normal = cross(dx, dy);
    }
    normal = normalize(normal);
    if (dot(normal, position) > 0.0) {
        normal = -normal;
    }

    float noise = bayer4(gl_FragCoord.xy);
    float view_distance = -position.z;
    float tolerance = 0.01 + 0.002 * view_distance;  // depth precision falls off with distance

    float ao = 1.0;
    if (ao_enabled > 0.5) {
        vec3 random = vec3(cos(noise * 2.0 * PI), sin(noise * 2.0 * PI), 0.3);
        vec3 tangent = normalize(random - normal * dot(random, normal));
        vec3 bitangent = cross(normal, tangent);

        float occlusion = 0.0;
        for (int i = 0; i < ao_samples; ++i) {
            // Cosine-weighted hemisphere, samples concentrated near the surface.
            float radius = sqrt((float(i) + 0.5) / float(ao_samples));
            float angle = float(i) * 2.39996323 + noise * 2.0 * PI;
            vec3 hemisphere = vec3(cos(angle) * radius, sin(angle) * radius, sqrt(1.0 - radius * radius));
            float scale = mix(0.12, 1.0, fract(float(i) * 0.618034 + noise));
            vec3 sample_position = position + (tangent * hemisphere.x + bitangent * hemisphere.y + normal * hemisphere.z)
                                   * ao_radius * scale * scale;

            vec2 sample_uv = project(sample_position);
            if (any(lessThan(sample_uv, vec2(0.0))) || any(greaterThan(sample_uv, vec2(1.0)))) {
                continue;
            }
            float scene_z = view_position(sample_uv).z;
            float range = smoothstep(0.0, 1.0, ao_radius / max(abs(position.z - scene_z), 1e-4));
            occlusion += (scene_z >= sample_position.z + tolerance ? 1.0 : 0.0) * range;
        }
        ao = pow(clamp(1.0 - occlusion / float(ao_samples), 0.0, 1.0), ao_strength);
    }

    // Contact shadows only add detail up close; the shadow map covers the distance.
    float contact = 1.0;
    float contact_fade = smoothstep(CONTACT_FADE_END, CONTACT_FADE_START, view_distance);
    if (contact_enabled > 0.5 && dot(normal, sun_view_direction) <= 0.0) {
        contact = 1.0 - contact_fade;  // facing away: self-shadowed, same reason as in sun_shadow()
    } else if (contact_enabled > 0.5 && contact_fade > 0.0) {
        float step_length = contact_length / float(CONTACT_STEPS);
        vec3 ray = position + normal * tolerance + sun_view_direction * step_length * noise;
        for (int i = 0; i < CONTACT_STEPS; ++i) {
            ray += sun_view_direction * step_length;
            vec2 ray_uv = project(ray);
            if (any(lessThan(ray_uv, vec2(0.0))) || any(greaterThan(ray_uv, vec2(1.0)))) {
                break;
            }
            float delta = view_position(ray_uv).z - ray.z;  // > 0: the surface there is in front of the ray
            if (delta > tolerance && delta < CONTACT_THICKNESS) {
                contact = 1.0 - contact_strength * contact_fade * (1.0 - float(i) / float(CONTACT_STEPS));
                break;
            }
        }
    }

    float shadow = 1.0;
    if (shadow_mode > 0) {
        vec3 world_position = (view_to_world * vec4(position, 1.0)).xyz;
        vec3 world_normal = normalize((view_to_world * vec4(normal, 0.0)).xyz);
        shadow = sun_shadow(world_position, world_normal, noise * 2.0 * PI);
    }

    o_color = vec4(ao, contact, shadow, 1.0);
}
