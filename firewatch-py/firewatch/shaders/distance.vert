#version 430

// Cube shadow map pass for point lights (point_shadow.py): writes each surface's distance from the light.

#pragma include "common.glsl"

uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ViewProjectionMatrix;

in vec4 p3d_Vertex;

out vec3 v_world_position;

void main() {
    vec4 world_position = apply_sway(p3d_ModelMatrix * p3d_Vertex);
    v_world_position = world_position.xyz;
    gl_Position = p3d_ViewProjectionMatrix * world_position;
}
