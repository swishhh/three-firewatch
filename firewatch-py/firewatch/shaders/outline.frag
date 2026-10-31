#version 430

// Draws `edge_color` on the pixels just outside the silhouette rendered into `mask`.
// The mask is drawn without depth testing, so hidden edges show too, like three's OutlinePass.

uniform sampler2D mask;
uniform vec4 edge_color;
uniform int radius;

in vec2 v_uv;

out vec4 o_color;

void main() {
    vec2 texel = 1.0 / vec2(textureSize(mask, 0));
    float inside = texture(mask, v_uv).r;
    float near = 0.0;
    for (int x = -radius; x <= radius; ++x) {
        for (int y = -radius; y <= radius; ++y) {
            if (x * x + y * y <= radius * radius) {
                near = max(near, texture(mask, v_uv + vec2(x, y) * texel).r);
            }
        }
    }
    o_color = vec4(edge_color.rgb, edge_color.a * near * (1.0 - inside));
}
