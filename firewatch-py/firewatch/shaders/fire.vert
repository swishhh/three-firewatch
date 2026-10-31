#version 430

// Low-poly campfire flames (components/fire.py). Each vertex belongs to one flame tongue; the tongue
// stretches, flickers and sways on its own rhythm, more towards its tip, and leans with the wind.

uniform mat4 p3d_ModelMatrix;
uniform mat4 p3d_ViewProjectionMatrix;
uniform float osg_FrameTime;
uniform vec3 wind_direction;
uniform float wind_strength;

uniform float flame_height;
uniform float flame_width;
uniform float flame_speed;
uniform float flame_flicker;
uniform float flame_sway;

in vec3 p3d_Vertex;  // position in unit tongue space: xy around the axis, z = 0 (base) .. 1 (tip)
in vec4 tongue;      // tongue offset x, y, radius, height (campfire model units)
in vec4 flame;       // seed, face height (0..1), layer (0 outer, 1 core), unused

flat out vec3 v_face;  // face height, layer, brightness wobble: one value per face (low-poly shading)
out float v_fog_depth;

void main() {
    float seed = flame.x;
    float t = osg_FrameTime * flame_speed + seed * 13.7;
    float tip = p3d_Vertex.z;

    // Height flicker: a few sines at unrelated rates per tongue.
    float flick = 1.0 + flame_flicker * (0.55 * sin(t * 2.3) + 0.3 * sin(t * 5.1 + seed * 4.0)
                                         + 0.15 * sin(t * 11.7 + seed * 9.0));
    float height = tongue.w * flame_height * max(flick, 0.15);
    float radius = tongue.z * flame_width * (1.0 + 0.15 * sin(t * 3.7 + seed * 2.0));
    vec3 local = vec3(tongue.xy * flame_width + p3d_Vertex.xy * radius, tip * height);

    // Sideways wander, growing towards the tip.
    vec2 wander = vec2(sin(t * 1.9 + seed * 3.0 + tip * 2.5), cos(t * 1.6 + seed * 5.0 + tip * 2.0));
    local.xy += wander * flame_sway * pow(tip, 1.5) * height;

    vec4 world = p3d_ModelMatrix * vec4(local, 1.0);
    // Lean with the wind (world space), measured in the model's scale.
    float scale = length(p3d_ModelMatrix[0].xyz);
    world.xyz += wind_direction * wind_strength * 0.35 * pow(tip, 2.0) * height * scale;

    v_face = vec3(flame.y, flame.z, 0.85 + 0.15 * sin(t * 7.3 + seed));
    gl_Position = p3d_ViewProjectionMatrix * world;
    v_fog_depth = gl_Position.w;
}
