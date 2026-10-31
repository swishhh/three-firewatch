#version 430

uniform int particle_mode;
uniform vec4 particle_color;
uniform float particle_intensity;
uniform float use_fog;
// FogExp2. Plain uniforms: Panda only re-sends p3d_Fog when the fog attribute itself changes.
uniform vec3 fog_color;
uniform float fog_density;

in vec2 v_corner;
in float v_pulse;
in float v_fog_depth;

out vec4 o_color;

void main() {
    float distance_squared = dot(v_corner, v_corner);
    if (distance_squared > 1.0) {
        discard;
    }
    float fog = use_fog > 0.5 ? 1.0 - exp(-pow(fog_density * v_fog_depth, 2.0)) : 0.0;

    if (particle_mode == 0) {
        float alpha = smoothstep(1.0, 0.3, sqrt(distance_squared)) * particle_color.a;
        o_color = vec4(mix(particle_color.rgb, fog_color, fog), alpha);
    } else {
        // Additive glow, bright enough to bloom.
        float glow = (exp(-distance_squared * 7.0) + 0.6 * exp(-distance_squared * 40.0)) * v_pulse;
        o_color = vec4(particle_color.rgb * particle_intensity * glow * (1.0 - fog), 1.0);
    }
}
