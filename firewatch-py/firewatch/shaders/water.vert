#version 430

uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ModelViewProjectionMatrix;

in vec4 p3d_Vertex;
in vec4 p3d_Color;  // alpha: soft mask coverage

out vec3 v_world_position;
out float v_view_depth;
out float v_coverage;

void main() {
    v_world_position = (p3d_ModelMatrix * p3d_Vertex).xyz;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
    v_view_depth = gl_Position.w;
    v_coverage = p3d_Color.a;
}
