#pragma once

// Which mode ffmpeg's loudnorm will use for the render's second pass. Header
// only, so test/cpp/unit_test.cpp checks it without linking the renderer.
//
// The render cannot ask ffmpeg: `stats_file`, the one way the type leaves a
// run that logs at "warning", exists only from FFmpeg 9.0 (absent from
// af_loudnorm.c at n6.1.1, n8.0 and n8.0.1, read 2026-11-23; Ubuntu 24.04
// ships 6.1, and a render there failed on the unknown option). So the
// type is worked out from the values the render writes into the filter, by
// loudnorm's own two rules, the same text at n6.1.1 and n9.0:
//
//   init(), n6.1.1 lines 807-818, n9.0 lines 815-826: linear when all four
//   measured values are given (measured_tp != 99, measured_thresh != -70,
//   measured_lra != 0, measured_i != 0), the gain keeps the peak at or under
//   the TP ceiling, and the measured range fits under the target range.
//
//   filter_frame(), n6.1.1 line 446, n9.0 line 450: in dynamic mode the first
//   frame asks for 3 s of samples, and a stream shorter than that switches to
//   linear with a gain cut back to the peak ceiling. Measured on n9.0.2: 2 s
//   of pink noise at -40.74 LUFS asked for -5 reported linear, and came out
//   at -11.0 LUFS.
namespace VC::Audio
{
    // The numbers of loudnorm's pass-2 options, as the render writes them, and
    // the length of the mixed stream in seconds (negative when unknown).
    struct LoudnormPass2
    {
        double targetI;
        double targetTP;
        double targetLRA;
        double measuredI;
        double measuredTP;
        double measuredLRA;
        double measuredThresh;
        double seconds;
    };

    // True when loudnorm will report "linear", false for "dynamic". The
    // comparisons are ffmpeg's, on the same doubles it parses from the text.
    inline bool loudnormLinear(const LoudnormPass2& p)
    {
        const double offset = p.targetI - p.measuredI;
        const double offsetTP = p.measuredTP + offset;
        if (p.measuredTP != 99 && p.measuredThresh != -70 && p.measuredLRA != 0 && p.measuredI != 0)
            if (offsetTP <= p.targetTP && p.measuredLRA <= p.targetLRA)
                return true;
        return p.seconds >= 0 && p.seconds < 3.0;
    }
} // namespace VC::Audio
