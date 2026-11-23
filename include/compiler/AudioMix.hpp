#pragma once

#include <memory>
#include <optional>
#include <string>
#include <utility>
#include <vector>

#include "input/IInput.hpp"

// The scene's sound as one ffmpeg graph — the SAME graph for the file the
// render writes and for the WAV the editor plays. One mixer, so what is heard
// in the preview is what comes out of the export; a second mix would be a
// preview that lies.
namespace VC::Audio
{
    // Extra ffmpeg input arguments (one "-ss .. -to .. -i file" per track) and
    // the output arguments that mix/map them onto the encoded video. Empty
    // when nothing carries sound — output keeps its current "-an" behaviour.
    struct AudioArgs
    {
        std::string inputs; // appended after the rawvideo "-i -"
        std::string output; // appended before the output filename
        // How many `-i` the inputs above are. Anything appended AFTER them is
        // input 1 + this, and the audio filter already counts on the video
        // being input 0 — so a chapter file added at the end shifts nothing.
        size_t count = 0;
    };

    // The graph alone, before any container is decided.
    struct AudioGraph
    {
        std::vector<std::string> inputArgs; // "-ss", "0.5", "-i", "file", … one argument each
        std::string              inputs;    // the same, as one command-line string
        std::string              filter;    // the filter_complex text, unquoted
        std::string              label;     // what to -map: a0, aout or arange
        size_t                   count = 0; // tracks — 0 means silence
    };

    // `firstInput` is the ffmpeg input index of the first sound: 1 at the
    // render, where the picture is input 0; 0 at the preview, which has none.
    AudioGraph buildAudioGraph(const std::vector<std::unique_ptr<IInput>>& inputs, std::optional<std::pair<double, double>> window, size_t frames, size_t firstInput);

    // --loudness: what the measurement pass found in the mix. The values are
    // kept as the text ffmpeg printed, so the render hands loudnorm back
    // exactly what it measured rather than a number rounded on the way.
    struct Loudness
    {
        enum class State {
            NoSound, // nothing in the scene carries sound: nothing to measure
            Silent,  // the mix measures -70 LUFS or lower: no gain is bounded
            Failed,  // ffmpeg did not measure; `note` holds what it said
            Ready,   // measured, and the render can apply it
        };
        State       state = State::NoSound;
        double      target = 0.0; // the LUFS asked for
        std::string inputI;       // loudnorm's input_i, input_tp, input_lra, input_thresh, target_offset
        std::string inputTP;
        std::string inputLRA;
        std::string inputThresh;
        std::string targetOffset;
        std::string statsFile; // where the render's loudnorm writes what it did; set by the caller
        std::string note;
    };

    // Pass 1 of two-pass loudnorm: one audio-only ffmpeg run over the graph
    // the render will mix — the same inputs, filter, window, and clamp to the
    // film's length as buildAudioArgs — ending in loudnorm's JSON report.
    Loudness measureLoudness(const std::vector<std::unique_ptr<IInput>>& inputs, std::optional<std::pair<double, double>> window, size_t frames, double target);

    // Pass 2: the filter stage that applies a Ready measurement — linear
    // loudnorm, -1 dBTP ceiling — then brings the rate back to 48 kHz,
    // because loudnorm itself outputs 192 kHz (measured, ffmpeg 9.0.2).
    std::string loudnormStage(const Loudness& measured);

    // After the render: "linear" or "dynamic", as the render's loudnorm wrote
    // it to `statsFile`. Empty when the file holds no answer.
    std::string appliedNormalisation(const Loudness& measured);

    // `loudness` is a Ready measurement to apply, or nullptr — and then the
    // string is exactly the one this function returned before --loudness.
    AudioArgs buildAudioArgs(const std::vector<std::unique_ptr<IInput>>& inputs, const std::string& audioCodec, std::optional<std::pair<double, double>> window, size_t frames, const Loudness* loudness = nullptr);
} // namespace VC::Audio
