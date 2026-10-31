#version 430

// GPU particles: each particle is a camera-facing quad animated entirely in this shader.
// Mode 0: snow falling through a box that follows the camera. Mode 1: fireflies around a point.

uniform mat4 p3d_ViewMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform float osg_FrameTime;
uniform int particle_mode;
uniform vec3 box_center;
uniform vec3 box_size;
uniform vec3 drift;  // world-space velocity (snow)
uniform float particle_size;

in vec4 p3d_Vertex;  // xyz: random position in [0, 1), w: random
in vec2 corner;      // quad corner in [-1, 1]

out vec2 v_corner;
out float v_pulse;
out float v_fog_depth;

void main() {
    float time = osg_FrameTime;
    vec3 seed = p3d_Vertex.xyz;
    float random = p3d_Vertex.w;
    vec3 position;

    if (particle_mode == 0) {
        vec3 box_min = box_center - box_size * 0.5;
        vec3 travel = seed * box_size + drift * time * (0.75 + 0.5 * random);
        travel.xy += vec2(sin(time * 1.1 + random * 40.0), cos(time * 0.9 + random * 23.0)) * 0.15;
        position = box_min + mod(travel - box_min, box_size);  // wraps, anchored to the world
        v_pulse = 1.0;
    } else {
        position = box_center + (seed - 0.5) * box_size;
        position += vec3(
            sin(time * 0.31 * (1.0 + random) + random * 20.0),
            cos(time * 0.27 * (1.0 + seed.x) + random * 13.0),
            sin(time * 0.45 * (1.0 + seed.y) + random * 7.0) * 0.4) * 0.9;
        v_pulse = smoothstep(0.5, 1.0, sin(time * (0.8 + random * 1.6) + random * 50.0) * 0.5 + 0.5);
    }

    vec4 view_position = p3d_ViewMatrix * vec4(position, 1.0);
    view_position.xy += corner * particle_size;
    v_corner = corner;
    gl_Position = p3d_ProjectionMatrix * view_position;
    v_fog_depth = gl_Position.w;
}
