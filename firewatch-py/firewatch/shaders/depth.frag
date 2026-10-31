#version 430

in vec3 v_view_normal;

out vec4 o_color;  // prepass: view-space normal; the shadow map buffer has no color target

void main() {
    o_color = vec4(normalize(v_view_normal), 1.0);
}
