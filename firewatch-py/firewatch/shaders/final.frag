#version 430

// Graded image -> window: FXAA, sharpening, vignette, film grain and dithering. Also upscales or
// downscales when the render scale isn't 100%.

uniform sampler2D image;
uniform float fxaa_enabled;
uniform float sharpen;
uniform float vignette;
uniform float vignette_softness;
uniform float grain;
uniform float dither_enabled;
uniform float osg_FrameTime;

in vec2 v_uv;

out vec4 o_color;

float hash(vec2 pixel) {
    vec3 p = fract(pixel.xyx * 0.1031);
    p += dot(p, p.yzx + 33.33);
    return fract((p.x + p.y) * p.z);
}

vec3 fxaa(vec2 uv, vec2 texel) {
    const float REDUCE_MIN = 1.0 / 128.0, REDUCE_MUL = 1.0 / 8.0, SPAN_MAX = 8.0;
    float luma_nw = texture(image, uv + vec2(-1.0, -1.0) * texel).a;
    float luma_ne = texture(image, uv + vec2(1.0, -1.0) * texel).a;
    float luma_sw = texture(image, uv + vec2(-1.0, 1.0) * texel).a;
    float luma_se = texture(image, uv + vec2(1.0, 1.0) * texel).a;
    vec4 center = texture(image, uv);
    float luma_min = min(center.a, min(min(luma_nw, luma_ne), min(luma_sw, luma_se)));
    float luma_max = max(center.a, max(max(luma_nw, luma_ne), max(luma_sw, luma_se)));

    vec2 direction = vec2(-((luma_nw + luma_ne) - (luma_sw + luma_se)), (luma_nw + luma_sw) - (luma_ne + luma_se));
    float reduce = max((luma_nw + luma_ne + luma_sw + luma_se) * 0.25 * REDUCE_MUL, REDUCE_MIN);
    float scale = 1.0 / (min(abs(direction.x), abs(direction.y)) + reduce);
    direction = clamp(direction * scale, vec2(-SPAN_MAX), vec2(SPAN_MAX)) * texel;

    vec3 near = 0.5 * (texture(image, uv + direction * (1.0 / 3.0 - 0.5)).rgb +
                       texture(image, uv + direction * (2.0 / 3.0 - 0.5)).rgb);
    vec3 far = near * 0.5 + 0.25 * (texture(image, uv - direction * 0.5).rgb + texture(image, uv + direction * 0.5).rgb);
    float far_luma = dot(far, vec3(0.299, 0.587, 0.114));
    return (far_luma < luma_min || far_luma > luma_max) ? near : far;
}

void main() {
    vec2 texel = 1.0 / vec2(textureSize(image, 0));
    vec3 color = fxaa_enabled > 0.5 ? fxaa(v_uv, texel) : texture(image, v_uv).rgb;

    if (sharpen > 0.0) {
        vec3 north = texture(image, v_uv + vec2(0.0, texel.y)).rgb;
        vec3 south = texture(image, v_uv - vec2(0.0, texel.y)).rgb;
        vec3 east = texture(image, v_uv + vec2(texel.x, 0.0)).rgb;
        vec3 west = texture(image, v_uv - vec2(texel.x, 0.0)).rgb;
        vec3 low = min(color, min(min(north, south), min(east, west)));
        vec3 high = max(color, max(max(north, south), max(east, west)));
        color = clamp(color + (color - (north + south + east + west) * 0.25) * sharpen * 2.0, low, high);
    }

    vec2 size = vec2(textureSize(image, 0));
    vec2 offset = (v_uv - 0.5) * vec2(size.x / size.y, 1.0);
    float edge = length(offset) / length(vec2(size.x / size.y, 1.0) * 0.5);
    color *= mix(1.0, smoothstep(1.0, 1.0 - vignette_softness, edge), vignette);

    color += (hash(gl_FragCoord.xy + fract(osg_FrameTime) * 917.0) - 0.5) * grain;
    if (dither_enabled > 0.5) {
        // +-1 step of triangular noise: dark gradients otherwise band into stripes at 8 bits.
        color += (hash(gl_FragCoord.xy) + hash(gl_FragCoord.xy + 71.3) - 1.0) / 255.0;
    }

    o_color = vec4(max(color, 0.0), 1.0);
}
