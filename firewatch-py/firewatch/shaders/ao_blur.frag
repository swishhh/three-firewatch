#version 430

// Depth-aware 4x4 box blur of the lighting mask (AO, contact shadows, sun shadow). Four by four
// matches the Bayer tile ao.frag rotates its samples with, so the pattern cancels out exactly.

#pragma include "depth_utils.glsl"

uniform sampler2D source;

in vec2 v_uv;

out vec4 o_color;

void main() {
    ivec2 pixel = ivec2(gl_FragCoord.xy);
    vec2 texel = 1.0 / vec2(textureSize(source, 0));
    float center_depth = pixel_depth((vec2(pixel) + 0.5) * texel);
    vec3 sum = vec3(0.0);
    float weight_sum = 0.0;
    for (int x = -2; x <= 1; ++x) {
        for (int y = -2; y <= 1; ++y) {
            vec2 uv = (vec2(pixel + ivec2(x, y)) + 0.5) * texel;
            float depth = pixel_depth(uv);
            float weight = max(1.0 - abs(depth - center_depth) / (0.04 * center_depth), 0.0) + 1e-4;
            sum += texelFetch(source, clamp(pixel + ivec2(x, y), ivec2(0), textureSize(source, 0) - 1), 0).rgb * weight;
            weight_sum += weight;
        }
    }
    o_color = vec4(sum / weight_sum, 1.0);
}
