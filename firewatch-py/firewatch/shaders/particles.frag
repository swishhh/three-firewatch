#version 430

uniform int particle_mode;
uniform vec4 particle_color;
uniform vec4 settled_color;  // snow: the color a flake turns once it has landed
uniform int snow_shape;      // 0 round, 1 soft, 2 crystal, 3 star, 4 square
uniform float snow_softness;
uniform float particle_intensity;
uniform float use_fog;
// FogExp2. Plain uniforms: Panda only re-sends p3d_Fog when the fog attribute itself changes.
uniform vec3 fog_color;
uniform float fog_density;

in vec2 v_corner;
in float v_pulse;
in float v_fog_depth;
in float v_fade;
in float v_settled;
in float v_rotation;

out vec4 o_color;

// Coverage of a snowflake shape at a point of the quad (-1..1, already rotated).
float flake(vec2 p) {
    float r = length(p);
    float soft = 0.03 + snow_softness * 0.5;
    if (snow_shape == 1) {
        return exp(-r * r * (2.5 + 3.0 * (1.0 - snow_softness)));  // soft blur
    }
    if (snow_shape == 2) {
        // Six arms with small side branches, plus a center.
        float angle = atan(p.y, p.x);
        float sector = abs(mod(angle + 0.5236, 1.0472) - 0.5236);  // angle from the nearest arm
        float across = r * sin(sector);
        float arms = 1.0 - smoothstep(0.07, 0.07 + soft * 0.35, across);
        float side = abs(r * cos(sector) - 0.55) - abs(across) * 0.9;  // V-shaped branch half way out
        float branch = (1.0 - smoothstep(0.05, 0.05 + soft * 0.3, abs(side))) * step(abs(across), 0.3);
        float shape = max(arms, branch) * (1.0 - smoothstep(0.9 - soft * 0.3, 1.0, r));
        return max(shape, 1.0 - smoothstep(0.15, 0.15 + soft * 0.3, r));
    }
    if (snow_shape == 3) {
        // Exact five-pointed star: straight edges from each point (radius 1) to the inner corners.
        float sector = mod(atan(p.y, p.x) + 6.2831853, 1.2566371);
        sector = sector > 0.6283185 ? 1.2566371 - sector : sector;  // fold onto one half-point
        vec2 tip = vec2(1.0, 0.0);
        vec2 inner = 0.42 * vec2(cos(0.6283185), sin(0.6283185));
        vec2 direction = vec2(cos(sector), sin(sector));
        vec2 side = inner - tip;
        float edge = (tip.x * inner.y - tip.y * inner.x) / (direction.x * side.y - direction.y * side.x);
        return 1.0 - smoothstep(edge - soft, edge, r);
    }
    if (snow_shape == 4) {
        float box = max(abs(p.x), abs(p.y));
        return 1.0 - smoothstep(0.75 - soft * 0.5, 0.75, box);
    }
    return 1.0 - smoothstep(1.0 - soft * 1.4, 1.0, r);  // round
}

void main() {
    float distance_squared = dot(v_corner, v_corner);
    if (distance_squared > 1.0 && particle_mode != 0) {
        discard;
    }
    float fog = use_fog > 0.5 ? 1.0 - exp(-pow(fog_density * v_fog_depth, 2.0)) : 0.0;

    if (particle_mode == 0) {
        float c = cos(v_rotation), s = sin(v_rotation);
        float shape = flake(mat2(c, -s, s, c) * v_corner);
        if (shape < 0.01) {
            discard;
        }
        float alpha = shape * particle_color.a * v_fade;
        // Landed flakes take the settled color over the first part of their rest, then fade out.
        float settle = v_settled > 0.0 ? smoothstep(0.0, 0.3, v_settled) : 0.0;
        vec3 color = mix(particle_color.rgb, settled_color.rgb, settle);
        o_color = vec4(mix(color, fog_color, fog), alpha);
    } else {
        // Additive glow, bright enough to bloom.
        float glow = (exp(-distance_squared * 7.0) + 0.6 * exp(-distance_squared * 40.0)) * v_pulse;
        o_color = vec4(particle_color.rgb * particle_intensity * glow * (1.0 - fog), 1.0);
    }
}
