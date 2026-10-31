// Wind sway shared by scene.vert and depth.vert, so swaying geometry casts matching shadows and AO.

uniform float osg_FrameTime;
uniform vec3 wind_direction;  // world space, unit length
uniform float wind_strength;
uniform float sway_amount;    // per node; 0 for rigid objects

in vec2 sway;  // (weight, phase), baked per vertex by instancing.py; absent on rigid geometry

vec4 apply_sway(vec4 world_position) {
    if (sway_amount <= 0.0 || wind_strength <= 0.0) {
        return world_position;
    }
    float time = osg_FrameTime;
    float gust = sin(time * 0.6 + sway.y * 0.37) * 0.5 + 0.5;
    float wave = sin(time * 1.7 + sway.y) * 0.6 + sin(time * 3.9 + sway.y * 1.9) * 0.2;
    world_position.xyz += wind_direction * (wave + gust * 0.9) * wind_strength * sway_amount * sway.x;
    return world_position;
}
