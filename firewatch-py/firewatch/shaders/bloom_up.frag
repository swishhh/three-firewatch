#version 430

// 3x3 tent upsample of the next smaller level, blended over this level.

uniform sampler2D current;
uniform sampler2D lower;
uniform float radius;

in vec2 v_uv;

out vec4 o_color;

void main() {
    vec2 texel = 1.0 / vec2(textureSize(lower, 0));
    vec3 tent = vec3(0.0);
    for (int x = -1; x <= 1; ++x) {
        for (int y = -1; y <= 1; ++y) {
            tent += texture(lower, v_uv + vec2(x, y) * texel).rgb * float((2 - abs(x)) * (2 - abs(y)));
        }
    }
    o_color = vec4(mix(texture(current, v_uv).rgb, tent / 16.0, radius), 1.0);
}
