#version 430

// Sky dome centered on the camera, with its axes kept aligned to the world (see sky.py).

uniform mat4 p3d_ModelViewProjectionMatrix;

in vec4 p3d_Vertex;

out vec3 v_direction;

void main() {
    v_direction = p3d_Vertex.xyz;
    gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
}
