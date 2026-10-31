#version 430

uniform float sky_gradient;  // 0: flat color like the JS clear color, 1: gradient
uniform vec3 sky_flat;
uniform vec3 sky_top;
uniform vec3 sky_horizon;
uniform vec3 sun_direction;  // world space, towards the sun (or the moon at night)
uniform vec3 disk_color;     // HDR color of the sun / moon disk and its glow
uniform float sun_glow;
uniform float sun_disk;
uniform float stars;
uniform float osg_FrameTime;

in vec3 v_direction;

out vec4 o_color;

float hash(vec3 p) {
    p = fract(p * 0.3183099 + 0.1);
    p *= 17.0;
    return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

void main() {
    if (sky_gradient < 0.5) {
        o_color = vec4(sky_flat, 1.0);
        return;
    }

    vec3 direction = normalize(v_direction);
    float height = direction.z;
    vec3 color = mix(sky_horizon, sky_top, pow(clamp(height, 0.0, 1.0), 0.45));
    float above_horizon = smoothstep(-0.02, 0.02, height);

    float facing = max(dot(direction, sun_direction), 0.0);
    color += disk_color * sun_glow * (0.06 * pow(facing, 4.0) + 0.2 * pow(facing, 40.0)) * above_horizon;
    float disk_radius = 0.012 * sun_disk;  // radians
    float disk = smoothstep(cos(disk_radius * 1.15), cos(disk_radius * 0.85), facing);
    color += disk_color * 3.0 * disk * above_horizon * step(0.001, sun_disk);

    if (stars > 0.0 && height > 0.0) {
        vec3 point = direction * 180.0;
        vec3 cell = floor(point);
        float seed = hash(cell);
        if (seed > 0.982) {
            vec3 center = cell + 0.5 + (vec3(hash(cell + 1.3), hash(cell + 2.7), hash(cell + 4.1)) - 0.5) * 0.6;
            float twinkle = 0.65 + 0.35 * sin(osg_FrameTime * (1.5 + seed * 4.0) + seed * 40.0);
            float star = smoothstep(0.32, 0.0, length(point - center)) * twinkle;
            color += vec3(0.9, 0.95, 1.0) * star * stars * 1.6 * smoothstep(0.0, 0.25, height);
        }
    }

    o_color = vec4(color, 1.0);
}
