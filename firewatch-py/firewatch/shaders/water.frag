#version 430

// Water surface (world/water.py). Depth of water under each pixel comes from the depth prepass,
// which water stays out of: shallow water is clear and fades out at the shore, deep water takes
// the deep color. Waves are a sum of directional sines (normals only, the surface stays flat).

#pragma include "depth_utils.glsl"

const float RECIPROCAL_PI = 0.3183098861837907;

uniform mat4 p3d_ViewMatrixInverse;
uniform float osg_FrameTime;
uniform vec2 screen_size;
uniform float depth_available;

uniform vec3 sun_direction;
uniform vec3 sun_color;
uniform vec3 moon_direction;
uniform vec3 moon_color;
uniform vec3 hemi_sky;
uniform vec3 hemi_ground;
uniform float hemi_intensity;
uniform vec3 reflect_sky_top;
uniform vec3 reflect_sky_horizon;
uniform vec3 fog_color;
uniform float fog_density;
uniform float use_fog;
uniform vec3 wind_direction;

uniform vec3 shallow_color;
uniform vec3 deep_color;
uniform vec3 foam_color;
uniform float opacity;        // everywhere, even at the shore: 1 = solid (ice)
uniform float depth_opacity;  // how much depth adds on top
uniform float clarity;       // meters of water before it takes the deep color
uniform float reflectivity;
uniform float water_specular;
uniform float wave_height;
uniform float wave_scale;
uniform float wave_speed;
uniform float foam;

in vec3 v_world_position;
in float v_view_depth;
in float v_coverage;

out vec4 o_color;

vec2 wave_slope(vec2 p, float time) {
    // (direction angle offset from the wind, wavelength in meters, relative amplitude)
    const vec3 waves[6] = vec3[](vec3(0.0, 3.1, 1.0), vec3(0.6, 1.9, 0.6), vec3(-0.7, 1.3, 0.45),
                                 vec3(1.9, 0.83, 0.3), vec3(-2.3, 0.57, 0.22), vec3(2.9, 0.37, 0.15));
    float wind_angle = atan(wind_direction.y, wind_direction.x);
    vec2 slope = vec2(0.0);
    for (int i = 0; i < 6; ++i) {
        float angle = wind_angle + waves[i].x;
        vec2 direction = vec2(cos(angle), sin(angle));
        float k = 6.2831853 / (waves[i].y * wave_scale);
        float speed = sqrt(9.81 / k) * wave_speed;  // deep water dispersion
        float phase = dot(direction, p) * k - time * speed * k;
        slope += direction * cos(phase) * waves[i].z;
    }
    return slope * 0.08;
}

float foam_noise(vec2 p) {
    return 0.5 + 0.25 * sin(p.x * 3.1 + osg_FrameTime * 0.7) * sin(p.y * 2.7 - osg_FrameTime * 0.5)
               + 0.25 * sin((p.x + p.y) * 7.3 + osg_FrameTime * 1.3);
}

void main() {
    vec3 camera_position = p3d_ViewMatrixInverse[3].xyz;
    vec3 to_camera = camera_position - v_world_position;
    float distance_to_camera = length(to_camera);
    vec3 view_dir = to_camera / distance_to_camera;

    vec2 slope = wave_slope(v_world_position.xy, osg_FrameTime) * wave_height;
    // Calm the waves with distance, or they alias into noise.
    slope *= 1.0 / (1.0 + distance_to_camera * 0.02);
    vec3 normal = normalize(vec3(-slope, 1.0));

    // Water thickness along the view ray from the prepass depth (scene behind the surface).
    float thickness = 50.0;
    if (depth_available > 0.5) {
        vec2 uv = gl_FragCoord.xy / screen_size;
        thickness = max(pixel_depth(uv) - v_view_depth, 0.0);
    }
    float deep = 1.0 - exp(-thickness / max(clarity, 0.01));

    vec3 sky_up = mix(hemi_ground, hemi_sky, 0.75) * hemi_intensity;
    vec3 sun_light = sun_color * max(sun_direction.z, 0.0) + moon_color * max(moon_direction.z, 0.0);
    vec3 body = mix(shallow_color, deep_color, deep) * (sky_up + sun_light) * RECIPROCAL_PI;

    vec3 reflected = reflect(-view_dir, normal);
    vec3 sky = mix(reflect_sky_horizon, reflect_sky_top, pow(clamp(reflected.z, 0.0, 1.0), 0.45));
    float fresnel = 0.02 + 0.98 * pow(1.0 - clamp(dot(normal, view_dir), 0.0, 1.0), 5.0);
    fresnel *= reflectivity;

    vec3 color = mix(body, sky, fresnel);
    color += sun_color * pow(max(dot(reflected, sun_direction), 0.0), 600.0) * water_specular * 6.0;
    color += moon_color * pow(max(dot(reflected, moon_direction), 0.0), 400.0) * water_specular * 4.0;

    float alpha = opacity + (1.0 - opacity) * deep * depth_opacity;
    alpha = max(alpha, fresnel);

    // Foam along the shore, broken up by a moving pattern.
    float shore = 1.0 - smoothstep(0.0, 0.25 + 0.2 * wave_height, thickness);
    float foam_amount = shore * foam * smoothstep(0.35, 0.75, foam_noise(v_world_position.xy * 2.0));
    color = mix(color, foam_color * (sky_up + sun_light) * RECIPROCAL_PI * 1.5, foam_amount);
    alpha = max(alpha, foam_amount);

    // Fade out where the water meets the ground, and along the painted edge's smooth contour.
    alpha *= mix(smoothstep(0.0, 0.04, thickness), 1.0, opacity * opacity) * smoothstep(0.3, 0.55, v_coverage);
    if (alpha < 0.002) {
        discard;
    }

    if (use_fog > 0.5) {
        float fog = 1.0 - exp(-fog_density * fog_density * v_view_depth * v_view_depth);
        color = mix(color, fog_color, fog);
    }
    o_color = vec4(color, alpha);
}
