#version 430

#pragma include "common.glsl"

uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ViewMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform mat3 p3d_NormalMatrix;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;
in vec4 p3d_Color;

out vec3 v_world_position;
out vec3 v_world_normal;
out vec3 v_view_position;
out vec3 v_view_normal;
out vec4 v_color;
out float v_fog_depth;

void main() {
    vec4 world_position = apply_sway(p3d_ModelMatrix * p3d_Vertex);
    vec4 view_position = p3d_ViewMatrix * world_position;

    v_world_position = world_position.xyz;
    v_world_normal = mat3(p3d_ModelMatrix) * p3d_Normal;  // models are uniformly scaled
    v_view_position = view_position.xyz;
    v_view_normal = p3d_NormalMatrix * p3d_Normal;
    v_color = p3d_Color;

    gl_Position = p3d_ProjectionMatrix * view_position;
    // Perspective w is the view-space depth, which is what three.js fog uses (-mvPosition.z).
    v_fog_depth = gl_Position.w;
}
