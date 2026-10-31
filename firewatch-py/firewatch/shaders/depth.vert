#version 430

// Depth pass for the sun shadow map and the depth prepass. The prepass also writes view-space
// normals (the interpolated ones lighting uses), so AO sees smooth surfaces as smooth.

#pragma include "common.glsl"

uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ViewMatrix;
uniform mat4 p3d_ViewProjectionMatrix;

in vec4 p3d_Vertex;
in vec3 p3d_Normal;

out vec3 v_view_normal;

void main() {
    v_view_normal = mat3(p3d_ViewMatrix) * mat3(p3d_ModelMatrix) * p3d_Normal;  // models are uniformly scaled
    gl_Position = p3d_ViewProjectionMatrix * apply_sway(p3d_ModelMatrix * p3d_Vertex);
}
