#version 450

// Spotlight — dim the whole frame except a rounded-rect pool of light.
//
// Frame-absolute, NOT bbox-relative: the pool is placed in frame UV so a
// caller can point at a spot on screen ("the square at 42% / 61%") without
// knowing anything about the mesh it lands on. That is the whole reason it
// is a plain SHADERS() entry and not a BBOX_SHADERS() one.
//
// p[] is ALPHABETICAL by the Python attribute name (see docs/ADDING_EFFECTS.md):
//   centerX, centerY, corner, darkness, halfHeight, halfWidth, softness
//
// halfWidth is a fraction of the frame WIDTH, halfHeight a fraction of the
// frame HEIGHT — so the shader never needs the aspect ratio, and the Python
// side converts a round radius into the two once, where SW/SH are known.

layout(location = 0) in vec2 fragUV;
layout(set = 0, binding = 0) uniform sampler2D tex;
layout(push_constant) uniform PC {
    float texelX;
    float texelY;
    float p[7];
} pc;
layout(location = 0) out vec4 outColor;

void main() {
    vec4 src = texture(tex, fragUV);

    vec2  center     = vec2(pc.p[0], pc.p[1]);
    float corner     = clamp(pc.p[2], 0.0, 1.0);
    float darkness   = clamp(pc.p[3], 0.0, 1.0);
    vec2  half_      = max(vec2(pc.p[5], pc.p[4]), vec2(1e-5));
    float softness   = max(pc.p[6], 1e-5);

    // Rounded-box SDF. corner=1 rounds it all the way to a stadium/ellipse,
    // corner=0 leaves a hard rectangle — one shader for both the round
    // spotlight and the rectangular zone focus.
    float cr = corner * min(half_.x, half_.y);
    vec2  q  = abs(fragUV - center) - half_ + cr;
    float sd = length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - cr;

    float inside = 1.0 - smoothstep(0.0, softness, sd);
    float gain   = mix(1.0 - darkness, 1.0, inside);

    outColor = vec4(src.rgb * gain, src.a);
}
