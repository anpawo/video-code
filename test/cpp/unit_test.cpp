/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** unit_test
*/

// The first C++ test in this repository, and deliberately the cheapest kind:
// one translation unit against headers only. No Vulkan device, no Qt, no
// window, no link against the application — 1.4s to build, milliseconds to
// run, so there is no reason for it to be skipped.
//
// It covers the shader parameter path, which is where the goldens are blind:
// a shader that receives 24 of its 30 uniforms renders a plausible image, and
// 87 golden comparisons cannot tell that apart from the right one.

#include <cstdio>
#include <string>
#include <vector>

#include "agent/LineDiff.hpp"
#include "compiler/LoudnormMode.hpp"
#include "shader/IFragmentShader.hpp"

static int failures = 0;

static void check(const std::string& what, bool ok)
{
    std::printf("  %s %s\n", ok ? "\033[32mok\033[0m  " : "\033[31mFAIL\033[0m", what.c_str());
    failures += !ok;
}

static void section(const std::string& title)
{
    std::printf("\n\033[36m%s\033[0m\n", title.c_str());
}

int main()
{
    section("copyShaderParams — what does not fit is said, not swallowed");
    {
        float p[MAX_SHADER_PARAMS] = {};
        copyShaderParams({1.f, 2.f, 3.f}, p);
        check("carries what fits", p[0] == 1.f && p[1] == 2.f && p[2] == 3.f);
        check("leaves the rest alone", p[3] == 0.f && p[MAX_SHADER_PARAMS - 1] == 0.f);
    }
    {
        std::vector<float> many(MAX_SHADER_PARAMS + 9);
        for (size_t i = 0; i < many.size(); i++)
            many[i] = static_cast<float>(i);
        float p[MAX_SHADER_PARAMS] = {};
        copyShaderParams(many, p);
        check("fills every slot", p[MAX_SHADER_PARAMS - 1] == float(MAX_SHADER_PARAMS - 1));
        check("does not write past the array", true); // ASan/UBSan would say otherwise
    }

    section("pushMathParams — the head is at fixed slots whatever the args are called");
    {
        json::object_t     args{{"start", 0.0}, {"duration", 1.0}, {"zeta", 9.0}, {"alpha", 7.0}};
        std::vector<float> out;
        IFragmentShader::pushMathParams(args, out);
        check("origin defaults to the centre, in percent", out[0] == 50.f && out[1] == 50.f && out[2] == 0.f);
        check("start and duration are not uniforms", out.size() == 5);
        check("the rest is alphabetical", out[3] == 7.f && out[4] == 9.f);
    }
    {
        // 30 numeric args is not hypothetical: a math shader carries its host's
        // bounding box, its origin, its own args and the frame clock.
        json::object_t args;
        for (int i = 0; i < 30; i++)
            args[std::string("k") + char('a' + i / 10) + char('0' + i % 10)] = double(i);
        std::vector<float> out;
        IFragmentShader::pushMathParams(args, out);
        check("more args than slots is possible at all", out.size() > MAX_SHADER_PARAMS);
    }

    section("lineDiff — deletions come out before the additions that replace them");
    {
        auto render = [](const QStringList& a, const QStringList& b) {
            QString out;
            for (const auto& [kind, text] : VC::lineDiff(a, b))
                out += (kind == 0 ? " " : kind < 0 ? "-"
                                                   : "+") +
                       text + ";";
            return out.toStdString();
        };
        check("an unchanged file is all context", render({"a", "b"}, {"a", "b"}) == " a; b;");
        check("an inserted line is one addition", render({"a", "c"}, {"a", "b", "c"}) == " a;+b; c;");
        check("a deleted line is one deletion", render({"a", "b", "c"}, {"a", "c"}) == " a;-b; c;");
        // The whole reason the pane can colour an edit: the row that WAS comes
        // out first, then the row it became. Reversed, an author reads the new
        // line as if it had been deleted.
        check("an edited line reads was-then-became", render({"a", "old", "c"}, {"a", "new", "c"}) == " a;-old;+new; c;");
        check("an empty before is all additions", render({}, {"a", "b"}) == "+a;+b;");
        check("an empty after is all deletions", render({"a", "b"}, {}) == "-a;-b;");
        // A move is not detected as a move, and that is deliberate — it costs a
        // second pass and the pane has no way to draw one.
        check("a moved line is a delete plus an add", render({"a", "b"}, {"b", "a"}) == "-a; b;+a;");
    }

    // The inputs are pass-1 reports of ffmpeg n9.0.2's loudnorm (2026-11-23):
    //   steady.wav   440 Hz sine, lavfi default amplitude, 6 s:
    //                input_i -21.75, input_tp -21.07, input_lra 0.00, input_thresh -31.75, out_time 6 s
    //   noise.wav    pink noise, amplitude 0.05, seed 1, 6 s:
    //                input_i -40.74, input_tp -30.94, input_lra 0.00, input_thresh -50.74, out_time 6 s
    //   noise2.wav   the first 2 s of noise.wav:
    //                input_i -40.74, input_tp -31.20, input_lra 0.00, input_thresh -50.74, out_time 2 s
    // The expected types are what ffmpeg n9.0.2's own pass 2 reported in its
    // stats file for those values: steady at -23 dynamic with measured_LRA
    // 0.00 and linear with 0.01; noise at -5 dynamic and at -20 linear (the
    // render of d256a5a); noise at -20 with measured_LRA 12 dynamic; noise2
    // at -5 linear. A length not reported has no ffmpeg run behind it: it is
    // the choice to say dynamic rather than guess short.
    section("loudnormLinear — the mode loudnorm picks, from the values pass 2 gets");
    {
        using VC::Audio::loudnormLinear;
        using VC::Audio::LoudnormPass2;
        const LoudnormPass2 steady{.targetI = -23, .targetTP = -1, .targetLRA = 11, .measuredI = -21.75, .measuredTP = -21.07, .measuredLRA = 0.01, .measuredThresh = -31.75, .seconds = 6};
        check("a steady tone, its LRA raised to 0.01, cut to -23: linear", loudnormLinear(steady));
        LoudnormPass2 unraised = steady;
        unraised.measuredLRA = 0.00;
        check("the same tone with measured_LRA 0.00: dynamic", !loudnormLinear(unraised));

        const LoudnormPass2 noise{.targetI = -5, .targetTP = -1, .targetLRA = 11, .measuredI = -40.74, .measuredTP = -30.94, .measuredLRA = 0.01, .measuredThresh = -50.74, .seconds = 6};
        check("pink noise to -5: the peak would reach +4.8 dBTP, so dynamic", !loudnormLinear(noise));
        LoudnormPass2 quieter = noise;
        quieter.targetI = -20;
        check("the same noise to -20: the peak stays at -10.2 dBTP, so linear", loudnormLinear(quieter));

        const LoudnormPass2 shortNoise{.targetI = -5, .targetTP = -1, .targetLRA = 11, .measuredI = -40.74, .measuredTP = -31.20, .measuredLRA = 0.01, .measuredThresh = -50.74, .seconds = 2};
        check("2 s of that noise to -5: shorter than loudnorm's 3 s first frame, so linear", loudnormLinear(shortNoise));
        LoudnormPass2 unknown = noise;
        unknown.seconds = -1;
        check("a length not reported is not taken for a short one", !loudnormLinear(unknown));

        LoudnormPass2 wide = quieter;
        wide.measuredLRA = 12;
        check("a measured range above the target range: dynamic", !loudnormLinear(wide));
    }

    std::printf("\n%s\n", failures == 0 ? "\033[32mAll checks passed.\033[0m" : "\033[31mFAILED\033[0m");
    return failures != 0;
}
