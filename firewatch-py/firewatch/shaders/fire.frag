#version 430

// Flat-shaded flame faces: core color at the base, middle color, tip color at the top; the inner
// core layer stays brighter and yellower. HDR output (bright enough to bloom), then fog.

uniform vec4 core_color;
uniform vec4 mid_color;
uniform vec4 tip_color;
uniform float flame_brightness;
uniform vec3 fog_color;
uniform float fog_density;
uniform float use_fog;

flat in vec3 v_face;
in float v_fog_depth;

out vec4 o_color;

void main() {
    float height = v_face.x;
    float core = v_face.y;
    vec3 outer = height < 0.45 ? mix(core_color.rgb, mid_color.rgb, smoothstep(0.0, 0.45, height))
                               : mix(mid_color.rgb, tip_color.rgb, smoothstep(0.45, 1.0, height));
    vec3 inner = mix(core_color.rgb, mid_color.rgb, smoothstep(0.3, 1.0, height));
    vec3 color = mix(outer, inner, core) * flame_brightness * v_face.z * (1.0 + 0.6 * core);
    if (use_fog > 0.5) {
        float fog = 1.0 - exp(-fog_density * fog_density * v_fog_depth * v_fog_depth);
        color = mix(color, fog_color, fog);
    }
    o_color = vec4(color, 1.0);
}
