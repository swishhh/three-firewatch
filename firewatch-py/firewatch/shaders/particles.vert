#version 430

// GPU particles: each particle is a camera-facing quad animated entirely in this shader.
// Mode 0: snow falling through a box that follows the camera. Mode 1: fireflies around a point.
// Mode 2: campfire embers rising from box_center (spread box_size.xy, up to box_size.z, drift.z m/s).

uniform mat4 p3d_ViewMatrix;
uniform mat4 p3d_ProjectionMatrix;
uniform float osg_FrameTime;
uniform int particle_mode;
uniform vec3 box_center;
uniform vec3 box_size;
uniform vec3 drift;  // world-space velocity (snow)
uniform float particle_size;

// Snow settling (components/snow.py): depth of the first surface seen from above, over the snow box.
uniform sampler2D snow_map;
uniform vec4 snow_map_area;   // x, y of the map's corner, width, height (world)
uniform vec3 snow_map_depth;  // camera height, near, far
uniform float snow_settle;    // 0: flakes fall through and wrap, as before
uniform float snow_melt;      // seconds a settled flake takes to fade
uniform float snow_spin;      // flake rotation speed (radians per second, per flake varied)
uniform float snow_streak;    // falling flakes stretch along their fall by this much

in vec4 p3d_Vertex;  // xyz: random position in [0, 1), w: random
in vec2 corner;      // quad corner in [-1, 1]

out vec2 v_corner;
out float v_pulse;
out float v_fog_depth;
out float v_fade;
out float v_settled;  // 0 while falling, then 0..1 through the time it rests
out float v_rotation;  // flake shape rotation

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}

float surface_height(vec2 xy) {
    vec2 uv = (xy - snow_map_area.xy) / snow_map_area.zw;
    float depth = textureLod(snow_map, clamp(uv, 0.0, 1.0), 0.0).r;
    return snow_map_depth.x - mix(snow_map_depth.y, snow_map_depth.z, depth);  // orthographic: linear depth
}

void main() {
    float time = osg_FrameTime;
    vec3 seed = p3d_Vertex.xyz;
    float random = p3d_Vertex.w;
    vec3 position;

    v_fade = 1.0;
    v_settled = 0.0;
    v_rotation = random * 6.2831853 + time * snow_spin * (0.5 + fract(random * 13.7)) * (fract(random * 3.3) > 0.5 ? 1.0 : -1.0);
    bool resting = false;
    if (particle_mode == 0 && snow_settle > 0.5) {
        // Life cycle: fall from the top of the box, land where the path meets the surface map, stay
        // and fade, then start again from a new random spot (one cycle per `period`).
        vec3 box_min = box_center - box_size * 0.5;
        float speed = max(-drift.z, 0.05) * (0.75 + 0.5 * random);
        float melt = snow_melt * (0.7 + 0.6 * fract(random * 7.31));
        float period = box_size.z / speed + melt;
        float local = time + seed.z * period;
        float cycle = floor(local / period);
        float t = local - cycle * period;
        vec2 start = vec2(hash(seed.xy + cycle), hash(seed.yx * 1.7 + cycle + 3.1)) * box_size.xy;
        vec2 wind = drift.xy * (0.75 + 0.5 * random);
        float top = box_center.z + box_size.z * 0.5;
        // Where (and when) the falling path first meets a surface: march it from the top in steps, then
        // refine the crossing. (Under a roof the map holds the roof's height, so a flake blown under
        // the eaves stops at the roof edge instead of getting inside.)
        float fall = box_size.z / speed;
        float landing = fall;
        float before = 0.0;
        if (top <= surface_height(box_min.xy + mod(start - box_min.xy, box_size.xy))) {
            landing = 0.0;  // starts inside something tall
        } else {
            const int STEPS = 16;
            for (int i = 1; i <= STEPS; ++i) {
                float when = fall * float(i) / float(STEPS);
                vec2 xy = box_min.xy + mod(start + wind * when - box_min.xy, box_size.xy);
                if (top - speed * when <= surface_height(xy)) {
                    float low = before, high = when;
                    for (int j = 0; j < 5; ++j) {
                        float middle = (low + high) * 0.5;
                        vec2 point = box_min.xy + mod(start + wind * middle - box_min.xy, box_size.xy);
                        if (top - speed * middle <= surface_height(point)) {
                            high = middle;
                        } else {
                            low = middle;
                        }
                    }
                    landing = high;
                    break;
                }
                before = when;
            }
        }
        float moving = min(t, landing);
        vec2 sway = vec2(sin(moving * 1.1 + random * 40.0), cos(moving * 0.9 + random * 23.0)) * 0.15;
        position.xy = box_min.xy + mod(start + wind * moving + sway - box_min.xy, box_size.xy);
        position.z = top - speed * moving;
        if (t >= landing) {
            position.z = surface_height(position.xy) + 0.006;  // resting on the surface
            v_settled = clamp((t - landing) / melt, 0.0, 1.0);
            v_fade = 1.0 - smoothstep(0.3, 1.0, v_settled);  // darkens first (fragment shader), then fades
            resting = true;
        }
        v_pulse = 1.0;
    } else if (particle_mode == 0) {
        vec3 box_min = box_center - box_size * 0.5;
        vec3 travel = seed * box_size + drift * time * (0.75 + 0.5 * random);
        travel.xy += vec2(sin(time * 1.1 + random * 40.0), cos(time * 0.9 + random * 23.0)) * 0.15;
        position = box_min + mod(travel - box_min, box_size);  // wraps, anchored to the world
        v_pulse = 1.0;
    } else if (particle_mode == 2) {
        float speed = max(drift.z, 0.05) * (0.6 + 0.8 * random);
        float life = box_size.z / speed;
        float local = time + seed.z * life * 3.0;
        float cycle = floor(local / life);
        float t = local - cycle * life;
        float rise = t / life;
        vec2 start = (vec2(hash(seed.xy + cycle), hash(seed.yx * 1.3 + cycle + 2.0)) - 0.5) * box_size.xy;
        vec2 swirl = vec2(sin(t * 3.0 + random * 20.0), cos(t * 2.6 + random * 11.0)) * 0.15 * rise;
        position = box_center + vec3(start + drift.xy * t * 0.6 + swirl, rise * box_size.z);
        // Glow, then cool and fade as it climbs; a quick twinkle.
        v_pulse = (1.0 - rise) * smoothstep(0.0, 0.05, rise) * (0.7 + 0.3 * sin(time * 20.0 + random * 50.0));
        v_fade = 1.0 - rise * 0.6;
    } else {
        position = box_center + (seed - 0.5) * box_size;
        position += vec3(
            sin(time * 0.31 * (1.0 + random) + random * 20.0),
            cos(time * 0.27 * (1.0 + seed.x) + random * 13.0),
            sin(time * 0.45 * (1.0 + seed.y) + random * 7.0) * 0.4) * 0.9;
        v_pulse = smoothstep(0.5, 1.0, sin(time * (0.8 + random * 1.6) + random * 50.0) * 0.5 + 0.5);
    }

    float size = particle_size * step(0.001, v_fade) * (particle_mode == 2 ? v_fade : 1.0);  // faded out: no quad
    if (resting) {
        position.xy += corner * size * 1.3;  // a settled flake lies flat on what it landed on
    }
    vec4 view_position = p3d_ViewMatrix * vec4(position, 1.0);
    if (!resting) {
        vec2 offset = corner * size;
        if (particle_mode == 0 && snow_streak > 0.0) {
            // Stretch along the fall as seen on screen (view-space direction of the fall velocity).
            vec3 fall = (p3d_ViewMatrix * vec4(drift, 0.0)).xyz;
            vec2 along = length(fall.xy) > 1e-4 ? normalize(fall.xy) : vec2(0.0, -1.0);
            offset += along * dot(corner, along) * size * snow_streak;
        }
        view_position.xy += offset;  // falling: faces the camera
    }
    v_corner = corner;
    gl_Position = p3d_ProjectionMatrix * view_position;
    v_fog_depth = gl_Position.w;
}
