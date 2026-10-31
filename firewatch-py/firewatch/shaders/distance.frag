#version 430

uniform vec3 point_shadow_position;  // world space

in vec3 v_world_position;

out vec4 o_color;

void main() {
    o_color = vec4(distance(v_world_position, point_shadow_position), 0.0, 0.0, 1.0);
}
