/*
** EPITECH PROJECT, 2025
** video-code
** File description:
** Register
*/

#pragma once

#include <algorithm>
#include <functional>
#include <map>
#include <nlohmann/json.hpp>
#include <string>

#include "shader/IFragmentShader.hpp"

using json = nlohmann::json;

// -----------------------------------------------------------------------------
// Registered fragment shaders
// -----------------------------------------------------------------------------

// Pure pixel functions — params pass through to the GLSL untouched.
#define SHADERS(X)         \
    X(Blur)                \
    X(Glow)                \
    X(Grayscale)           \
    X(Gamma)               \
    X(Grain)               \
    X(Brightness)          \
    X(Contrast)            \
    X(Sharpen)             \
    X(Pixelate)            \
    X(Duotone)             \
    X(Sepia)               \
    X(Invert)              \
    X(Posterize)           \
    X(HueRotate)           \
    X(Halftone)            \
    X(ChromaKey)           \
    X(Lut)                 \
    X(Spotlight)           \
    X(Saturation)          \
    X(Temperature)         \
    X(ChromaticAberration) \
    X(Letterbox)

// Object-relative shaders — resolveEffectParams() prepends the mesh's own
// screen-space bounding box, so their GLSL reads p[0..3] = (uMin, vMin,
// uMax, vMax) followed by the regular alphabetical args.
#define BBOX_SHADERS(X) \
    X(Crop)             \
    X(Vignette)         \
    X(ZoomBlur)         \
    X(RoundCorners)     \
    X(Feather)

// -------------------------------------------------------------------------
// Generated class for each registered shader
// -------------------------------------------------------------------------
#define DECLARE_SHADERS_COMMON(name)                                    \
public:                                                                 \
                                                                        \
    name(const json::object_t& args)                                    \
        : _start(args.at("start").get<size_t>())                        \
        , _duration(args.at("duration").get<size_t>())                  \
        , _args(args) {}                                                \
                                                                        \
    size_t                start() const override { return _start; }     \
    std::string_view      shaderName() const override { return #name; } \
    const json::object_t& args() const override { return _args; }       \
                                                                        \
private:                                                                \
                                                                        \
    const size_t         _start;                                        \
    const size_t         _duration;                                     \
    const json::object_t _args;

#define DECLARE_SHADERS(name)                 \
    class name final : public IFragmentShader \
    {                                         \
        DECLARE_SHADERS_COMMON(name)          \
    };

#define DECLARE_BBOX_SHADERS(name)                       \
    class name final : public IFragmentShader            \
    {                                                    \
    public:                                              \
                                                         \
        bool needsBBox() const override { return true; } \
                                                         \
        DECLARE_SHADERS_COMMON(name)                     \
    };

SHADERS(DECLARE_SHADERS)
BBOX_SHADERS(DECLARE_BBOX_SHADERS)

// -------------------------------------------------------------------------
// Time-driven shaders (declared by hand: they override paramsAtFrame)
// -------------------------------------------------------------------------

// LightSweep — a bright band sweeping across the input over the effect's
// duration. shaderParams() yields [angle, group, intensity, width]
// (alphabetical); paramsAtFrame appends the 0..1 progress so the GLSL side
// only interpolates. groupParamIndex() = 1 makes resolveEffectParams()
// replace the group id with the group's union bounding box (prepended).
class LightSweep final : public IFragmentShader
{
public:

    LightSweep(const json::object_t& args)
        : _start(args.at("start").get<size_t>())
        , _duration(args.at("duration").get<size_t>())
        , _args(args)
    {
    }

    size_t start() const override { return _start; }

    std::string_view shaderName() const override { return "LightSweep"; }

    const json::object_t& args() const override { return _args; }

    int groupParamIndex() const override { return 1; }

    std::vector<float> paramsAtFrame(size_t frame) const override
    {
        std::vector<float> out = shaderParams();
        // Single-frame application: show the band mid-sweep instead of off-object.
        float progress = _duration <= 1
                             ? 0.5f
                             : static_cast<float>(frame - _start) / static_cast<float>(_duration - 1);
        out.push_back(std::clamp(progress, 0.f, 1.f));
        return out;
    }

private:

    const size_t         _start;
    const size_t         _duration;
    const json::object_t _args;
};

// Glitch — RGB split + random horizontal slice offsets. shaderParams() yields
// [amount, seed, slices] (alphabetical); paramsAtFrame appends the 0..1
// progress that drives the per-tick slice re-roll in the GLSL.
class Glitch final : public IFragmentShader
{
public:

    Glitch(const json::object_t& args)
        : _start(args.at("start").get<size_t>())
        , _duration(args.at("duration").get<size_t>())
        , _args(args)
    {
    }

    size_t start() const override { return _start; }

    std::string_view shaderName() const override { return "Glitch"; }

    const json::object_t& args() const override { return _args; }

    std::vector<float> paramsAtFrame(size_t frame) const override
    {
        std::vector<float> out = shaderParams();
        float              progress = _duration <= 1
                                          ? 0.5f
                                          : static_cast<float>(frame - _start) / static_cast<float>(_duration - 1);
        out.push_back(std::clamp(progress, 0.f, 1.f));
        return out;
    }

private:

    const size_t         _start;
    const size_t         _duration;
    const json::object_t _args;
};

// Vhs — scanlines + chroma shift + analog noise. Time-driven like Glitch:
// paramsAtFrame appends the 0..1 progress that re-rolls the noise/jitter.
class Vhs final : public IFragmentShader
{
public:

    Vhs(const json::object_t& args)
        : _start(args.at("start").get<size_t>())
        , _duration(args.at("duration").get<size_t>())
        , _args(args)
    {
    }

    size_t start() const override { return _start; }

    std::string_view shaderName() const override { return "Vhs"; }

    const json::object_t& args() const override { return _args; }

    std::vector<float> paramsAtFrame(size_t frame) const override
    {
        std::vector<float> out = shaderParams();
        float              progress = _duration <= 1
                                          ? 0.5f
                                          : static_cast<float>(frame - _start) / static_cast<float>(_duration - 1);
        out.push_back(std::clamp(progress, 0.f, 1.f));
        return out;
    }

private:

    const size_t         _start;
    const size_t         _duration;
    const json::object_t _args;
};

// MathShader — generic runtime-loaded procedural shader (fragcoord.xyz
// ports; `silk` is a bundled preset). The `filepath` arg names an arbitrary
// fragment-GLSL file: it is excluded from the numeric params by
// shaderParams()'s is_number() filter and instead rides ActiveEffect::strParam
// (the same channel Lut's .cube path uses — AInput::getActiveEffectsAtFrame
// lifts any "filepath" arg into it), where the renderers compile + cache one
// pipeline per file (ensureMathPipeline). Replaces the input's RGB with the
// generated pattern, keeping the input's own alpha as coverage.
// Time-driven like Vhs, but paramsAtFrame appends the raw elapsed FRAME COUNT
// (unclamped, not 0..1 progress): a procedural animation needs an unbounded
// clock, and the GLSL derives seconds as elapsed / fps — fps rides the params
// from the Python binding. The params themselves come from pushMathParams
// (IFragmentShader.hpp), NOT shaderParams(): a fixed 3-float head sits ahead
// of the alphabetical args, so every math shader reads the point it draws
// around at the same index. A stock preset ends up as [originX, originY,
// originUnit, fps, quality, scale, speed] + the clock (filepath excluded — it
// is a string; space/group excluded — they ride ActiveEffect).
// isMathPaint, not needsBBox: the effect pass is a fullscreen quad over
// absolute frame UV, so a generated pattern needs to be told where its host
// is — but handing over the raw box is what made patterns SWIM, because each
// GLSL then re-derived the origin from a box that moved while dividing by a
// scale that didn't. resolveEffectParams now resolves origin AND unit from
// one box, chosen by ShaderSpace, and patches them over the head in place.
class MathShader final : public IFragmentShader
{
public:

    MathShader(const json::object_t& args)
        : _start(args.at("start").get<size_t>())
        , _args(args)
    {
    }

    size_t start() const override { return _start; }

    // Spelled once. AInput reads it too, from the paint path, where there is
    // no shader object to ask.
    static constexpr std::string_view kName = "MathShader";

    std::string_view shaderName() const override { return kName; }

    const json::object_t& args() const override { return _args; }

    bool isMathPaint() const override { return true; }

    std::vector<float> paramsAtFrame(size_t frame) const override
    {
        std::vector<float> out;
        pushMathParams(_args, out);
        out.push_back(static_cast<float>(frame - _start));
        return out;
    }

private:

    const size_t         _start;
    const json::object_t _args;
};

// -------------------------------------------------------------------------
// Factory map: shader name → constructor
// -------------------------------------------------------------------------

#define BIND_SHADERS(name) \
    {#name, [](const json::object_t& args) -> std::unique_ptr<IFragmentShader> { return std::make_unique<name>(args); }},

const std::map<std::string, std::function<std::unique_ptr<IFragmentShader>(const json::object_t&)>> transformation{
    SHADERS(BIND_SHADERS)
        BBOX_SHADERS(BIND_SHADERS)
            BIND_SHADERS(LightSweep)
                BIND_SHADERS(Glitch)
                    BIND_SHADERS(Vhs)
                        BIND_SHADERS(MathShader)
};

// Does a fill of this name draw around a POINT rather than across the frame?
//
// There are two ways an effect reaches the renderer and only one of them can
// ask the question properly. A timeline effect is built by the factory above,
// so it can be asked `isMathPaint()`. A FILL is built straight from the json —
// it never becomes an IFragmentShader at all — so it has only a name, and the
// answer used to be a bare `== "MathShader"` sitting in AInput.cpp, three files
// away from the class that knows.
//
// It is still a name comparison, but it is the ONE name comparison, next to the
// class it is about: a second math paint is added here and both paths change
// together. Getting it wrong is invisible to every golden — a shader that
// misses the 3-float origin head still renders a plausible image, with its
// uniforms shifted by three slots.
inline bool isMathPaintName(std::string_view name)
{
    return name == MathShader::kName;
}
