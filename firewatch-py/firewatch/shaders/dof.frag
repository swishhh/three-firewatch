#version 430

// Wide disk blur of the scene for depth of field; post.frag blends it in by distance from focus.

uniform sampler2D source;
uniform float dof_blur;

in vec2 v_uv;

out vec4 o_color;

void main() {
    vec2 texel = 1.0 / vec2(textureSize(source, 0));
    vec3 sum = vec3(0.0);
    for (int i = 0; i < 24; ++i) {
        float radius = sqrt((float(i) + 0.5) / 24.0) * 5.0 * dof_blur;
        float angle = float(i) * 2.39996323;
        sum += texture(source, v_uv + vec2(cos(angle), sin(angle)) * radius * texel).rgb;
    }
    o_color = vec4(sum / 24.0, 1.0);
}
