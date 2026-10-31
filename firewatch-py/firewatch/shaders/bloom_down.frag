#version 430

// 13-tap downsample (Call of Duty: Advanced Warfare). The first pass applies a soft threshold and
// a Karis average so single bright pixels don't flicker.

uniform sampler2D source;
uniform float first_pass;
uniform float threshold;

in vec2 v_uv;

out vec4 o_color;

vec3 sample_at(vec2 offset) {
    return texture(source, v_uv + offset / vec2(textureSize(source, 0))).rgb;
}

float karis_weight(vec3 color) {
    return 1.0 / (1.0 + max(max(color.r, color.g), color.b));
}

vec3 soft_threshold(vec3 color) {
    float brightness = max(max(color.r, color.g), color.b);
    float knee = threshold * 0.5 + 1e-4;
    float soft = clamp(brightness - threshold + knee, 0.0, 2.0 * knee);
    soft = soft * soft / (4.0 * knee);
    return color * max(soft, brightness - threshold) / max(brightness, 1e-4);
}

void main() {
    vec3 a = sample_at(vec2(-2, 2)), b = sample_at(vec2(0, 2)), c = sample_at(vec2(2, 2));
    vec3 d = sample_at(vec2(-2, 0)), e = sample_at(vec2(0, 0)), f = sample_at(vec2(2, 0));
    vec3 g = sample_at(vec2(-2, -2)), h = sample_at(vec2(0, -2)), i = sample_at(vec2(2, -2));
    vec3 j = sample_at(vec2(-1, 1)), k = sample_at(vec2(1, 1));
    vec3 l = sample_at(vec2(-1, -1)), m = sample_at(vec2(1, -1));

    vec3 color;
    if (first_pass > 0.5) {
        vec3 groups[5] = vec3[](
            (j + k + l + m) * 0.25, (a + b + d + e) * 0.25, (b + c + e + f) * 0.25,
            (d + e + g + h) * 0.25, (e + f + h + i) * 0.25);
        float weights[5] = float[](0.5, 0.125, 0.125, 0.125, 0.125);
        color = vec3(0.0);
        float total = 0.0;
        for (int n = 0; n < 5; ++n) {
            float weight = weights[n] * karis_weight(groups[n]);
            color += soft_threshold(groups[n]) * weight;
            total += weight;
        }
        color /= total;
    } else {
        color = e * 0.125 + (a + c + g + i) * 0.03125 + (b + d + f + h) * 0.0625 + (j + k + l + m) * 0.125;
    }
    o_color = vec4(color, 1.0);
}
