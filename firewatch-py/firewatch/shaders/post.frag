#version 430

// HDR scene -> graded LDR image: depth of field, bloom, exposure, tone mapping, white balance,
// contrast, saturation, brightness. Luma goes to alpha for FXAA in final.frag.

#pragma include "depth_utils.glsl"

uniform sampler2D scene;
uniform sampler2D bloom;
uniform sampler2D dof_blur_texture;
uniform float bloom_enabled;
uniform float bloom_intensity;
uniform float bloom_fast;    // bloom holds one thresholded image with mipmaps instead of the upsampled chain
uniform float bloom_radius;
uniform float dof_enabled;
uniform float dof_focus;
uniform float dof_range;
uniform float exposure;
uniform int tonemap;  // 0 none, 1 Reinhard, 2 ACES, 3 AgX, 4 filmic
uniform float temperature;
uniform float tint;
uniform float saturation;
uniform float contrast;
uniform float brightness;

in vec2 v_uv;

out vec4 o_color;

// The scene's colors are display values (three.js legacy color mode), so curves meant for linear
// light run between a 2.2 decode and encode.
vec3 to_linear(vec3 color) { return pow(max(color, 0.0), vec3(2.2)); }
vec3 to_display(vec3 color) { return pow(max(color, 0.0), vec3(1.0 / 2.2)); }

vec3 aces(vec3 x) {  // Narkowicz fit
    return clamp((x * (2.51 * x + 0.03)) / (x * (2.43 * x + 0.59) + 0.14), 0.0, 1.0);
}

vec3 hable(vec3 x) {
    const float A = 0.15, B = 0.50, C = 0.10, D = 0.20, E = 0.02, F = 0.30;
    return ((x * (A * x + C * B) + D * E) / (x * (A * x + B) + D * F)) - E / F;
}

vec3 agx(vec3 color) {  // Minimal AgX (Benjamin Wrensch), base look
    const mat3 inset = mat3(0.842479062253094, 0.0423282422610123, 0.0423756549057051,
                            0.0784335999999992, 0.878468636469772, 0.0784336,
                            0.0792237451477643, 0.0791661274605434, 0.879142973793104);
    const mat3 outset = mat3(1.19687900512017, -0.0528968517574562, -0.0529716355144438,
                             -0.0980208811401368, 1.15190312990417, -0.0980434501171241,
                             -0.0990297440797205, -0.0989611768448433, 1.15107367264116);
    color = inset * color;
    color = clamp((log2(max(color, 1e-10)) + 12.47393) / 16.5, 0.0, 1.0);
    vec3 x2 = color * color, x4 = x2 * x2;
    color = 15.5 * x4 * x2 - 40.14 * x4 * color + 31.96 * x4 - 6.868 * x2 * color + 0.4298 * x2 + 0.1191 * color - 0.00232;
    return pow(max(outset * color, 0.0), vec3(2.2));
}

vec3 apply_tonemap(vec3 color) {
    if (tonemap == 0) {
        return color;
    }
    vec3 linear = to_linear(color);
    if (tonemap == 1) {
        linear = linear * (1.0 + linear / 4.0) / (1.0 + linear);  // extended Reinhard, white = 2
    } else if (tonemap == 2) {
        linear = aces(linear);
    } else if (tonemap == 3) {
        linear = agx(linear);
    } else {
        linear = hable(linear * 2.0) / hable(vec3(11.2));
    }
    return to_display(linear);
}

// Same level weights as the High chain's upsampling: each level mixes in the next by bloom_radius.
vec3 bloom_from_mipmaps(vec2 uv) {
    const int LEVELS = 6;
    vec3 sum = vec3(0.0);
    float weight = 1.0;
    for (int level = 0; level < LEVELS; ++level) {
        vec2 texel = 1.0 / vec2(textureSize(bloom, level));
        vec3 tent = vec3(0.0);
        for (int x = -1; x <= 1; ++x) {
            for (int y = -1; y <= 1; ++y) {
                tent += textureLod(bloom, uv + vec2(x, y) * texel, float(level)).rgb * float((2 - abs(x)) * (2 - abs(y)));
            }
        }
        float share = level == LEVELS - 1 ? weight : weight * (1.0 - bloom_radius);
        sum += tent / 16.0 * share;
        weight *= bloom_radius;
    }
    return sum;
}

void main() {
    vec3 color = texture(scene, v_uv).rgb;

    if (dof_enabled > 0.5) {
        float depth = linear_depth(textureLod(depth_texture, v_uv, 0.0).r);
        float blur = clamp(abs(depth - dof_focus) / dof_range, 0.0, 1.0);
        color = mix(color, texture(dof_blur_texture, v_uv).rgb, blur);
    }
    if (bloom_enabled > 0.5) {
        color += (bloom_fast > 0.5 ? bloom_from_mipmaps(v_uv) : texture(bloom, v_uv).rgb) * bloom_intensity;
    }

    color = apply_tonemap(color * exposure);

    // White balance: temperature warms (red up, blue down), tint pushes magenta (green down).
    color *= vec3(1.0 + 0.12 * temperature + 0.04 * tint, 1.0 - 0.08 * tint, 1.0 - 0.12 * temperature + 0.04 * tint);
    color = (color - 0.5) * contrast + 0.5;
    float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
    color = mix(vec3(luma), color, saturation);
    color = pow(clamp(color, 0.0, 1.0), vec3(1.0 / brightness));

    o_color = vec4(color, dot(color, vec3(0.299, 0.587, 0.114)));
}
