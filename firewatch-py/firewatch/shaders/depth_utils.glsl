// View-space reconstruction from the depth prepass (OpenGL view space: x right, y up, -z forward).

uniform sampler2D depth_texture;
uniform vec2 near_far;
uniform vec2 tan_half_fov;  // tan of half the horizontal and vertical field of view

float linear_depth(float depth) {
    float z = depth * 2.0 - 1.0;
    return 2.0 * near_far.x * near_far.y / (near_far.y + near_far.x - z * (near_far.y - near_far.x));
}

vec3 view_position(vec2 uv) {
    float z = linear_depth(textureLod(depth_texture, uv, 0.0).r);
    return vec3((uv * 2.0 - 1.0) * tan_half_fov * z, -z);
}

// Center of the prepass pixel containing uv. A half-resolution mask texel sits between four depth
// pixels; sampling there would blend an object's depth with the ground behind it.
vec2 snap_to_depth_pixel(vec2 uv) {
    vec2 size = vec2(textureSize(depth_texture, 0));
    return (floor(uv * size) + 0.5) / size;
}

float pixel_depth(vec2 uv) {
    return linear_depth(texelFetch(depth_texture, ivec2(uv * vec2(textureSize(depth_texture, 0))), 0).r);
}

vec2 project(vec3 position) {
    return position.xy / (-position.z * tan_half_fov) * 0.5 + 0.5;
}
