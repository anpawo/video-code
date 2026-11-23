#include "compiler/AudioMix.hpp"

#include <algorithm>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <format>
#include <fstream>
#include <iostream>
#include <iterator>

#include "core/Config.hpp"
#include "input/media/Sound.hpp"
#include "input/media/Video.hpp"

namespace VC::Audio
{
    // A video with no audio stream must not be mapped: ffmpeg refuses the
    // whole mux over a "[3:a]" that matches nothing, picture included.
    bool hasAudioStream(const std::string& filepath)
    {
        FILE* p = popen(std::format("ffprobe -v error -select_streams a -show_entries stream=codec_type -of csv=p=0 \"{}\"", filepath).c_str(), "r");
        if (!p)
            return false;
        char buf[16];
        bool any = fgets(buf, sizeof buf, p) != nullptr;
        pclose(p);
        return any;
    }

    // A Video's own track. Its picture starts where the script put the clip,
    // so the sound is delayed to meet it — the same `adelay` a Sound carries,
    // written after the retime so the milliseconds are output time. Keeping
    // the audio between the cut ranges and butting the pieces together is what
    // leaves it under the frames that are actually shown. atrim over
    // asplit rather than one aselect expression, because aselect on audio
    // drops nothing at all in ffmpeg 8.0.1 (measured: `gte(t,1)` kept 2.005 s
    // of 2.005). The picture is nearest-frame at one source frame per scene
    // frame, so a source not at the scene's rate plays at SCENE_FRAMERATE/fps
    // speed and the sound follows with atempo.
    // ponytail: atempo floors at 0.5, so a source above 60 fps fails the mux;
    // neither speed ramps nor a paused VIDEOS clock (freeze) reach the sound.
    // The kept source audio, retimed, written to [out] with `tail` as its last filters.
    std::string cutChain(const Video& v, size_t ffmpegInput, const std::string& out, const std::string& tail)
    {
        double      fps = v.sourceFps() > 0.0 ? v.sourceFps() : Config::SCENE_FRAMERATE;
        std::string tempo = (fps != Config::SCENE_FRAMERATE ? std::format(",atempo={}", Config::SCENE_FRAMERATE / fps) : "") + tail;

        if (v.cuts().empty())
            return std::format("[{}:a]anull{}[{}];", ffmpegInput, tempo, out);

        // Kept ranges in source seconds; an end of -1 runs to the end of the file.
        std::vector<std::pair<double, double>> keep;
        size_t                                 at = 0;
        for (const auto& [start, end] : v.cuts()) {
            if (start > at)
                keep.push_back({at / fps, start / fps});
            at = end;
        }
        if (at < v._nbFrame)
            keep.push_back({at / fps, -1.0});

        auto trim = [&](const std::pair<double, double>& range) {
            return std::format("atrim=start={}{},asetpts=PTS-STARTPTS", range.first, range.second < 0 ? "" : std::format(":end={}", range.second));
        };

        if (keep.empty())
            return std::format("[{}:a]atrim=end=0{}[{}];", ffmpegInput, tempo, out);
        if (keep.size() == 1)
            return std::format("[{}:a]{}{}[{}];", ffmpegInput, trim(keep[0]), tempo, out);

        std::string chain = std::format("[{}:a]asplit={}", ffmpegInput, keep.size());
        for (size_t k = 0; k < keep.size(); ++k)
            chain += std::format("[s{}_{}]", out, k);
        chain += ";";
        for (size_t k = 0; k < keep.size(); ++k)
            chain += std::format("[s{}_{}]{}[k{}_{}];", out, k, trim(keep[k]), out, k);
        for (size_t k = 0; k < keep.size(); ++k)
            chain += std::format("[k{}_{}]", out, k);
        chain += std::format("concat=n={}:v=0:a=1{}[{}];", keep.size(), tempo, out);
        return chain;
    }

    std::string videoAudioChain(const Video& v, size_t ffmpegInput, size_t track)
    {
        std::string delay;
        if (v._origin > 0) {
            long long ms = std::llround(static_cast<double>(v._origin) * 1000.0 / Config::SCENE_FRAMERATE);
            delay = std::format(",adelay={0}|{0}", ms);
        }

        const auto& holds = v.holds();
        if (holds.empty())
            return cutChain(v, ffmpegInput, std::format("a{}", track), delay);

        // A held picture holds the sound too: silence over the held frames, cut
        // into the track after the cuts and the retime — where one second of
        // audio is one second of the clip as it plays — and before the delay.
        const std::string played = std::format("p{}", track);
        std::string       chain = cutChain(v, ffmpegInput, played, "");
        chain += std::format("[{}]asplit={}", played, holds.size() + 1);
        for (size_t k = 0; k <= holds.size(); ++k)
            chain += std::format("[hs{}_{}]", track, k);
        chain += ";";
        for (size_t k = 0; k <= holds.size(); ++k) {
            const double from = k == 0 ? 0.0 : holds[k - 1].first / Config::SCENE_FRAMERATE;
            chain += std::format("[hs{}_{}]atrim=start={}", track, k, from);
            if (k < holds.size())
                chain += std::format(":end={},asetpts=PTS-STARTPTS,apad=pad_dur={}", holds[k].first / Config::SCENE_FRAMERATE, holds[k].second / Config::SCENE_FRAMERATE);
            else
                chain += ",asetpts=PTS-STARTPTS";
            chain += std::format("[hg{}_{}];", track, k);
        }
        for (size_t k = 0; k <= holds.size(); ++k)
            chain += std::format("[hg{}_{}]", track, k);
        chain += std::format("concat=n={}:v=0:a=1{}[a{}];", holds.size() + 1, delay, track);
        return chain;
    }

    // `window` is the rendered stretch in seconds when --from/--to narrowed
    // it. The whole timeline is still mixed as one, with every delay and cut
    // above kept absolute, and the window is cut out of the RESULT: that is
    // what keeps a sound that began before --from at the right moment, heard
    // from where the range enters it, instead of re-delaying each track and
    // trimming each file by hand. Decoding the part before the window costs
    // audio decode time, which is nothing next to one rendered frame.
    // The gain a scene CLAIMED, frame by frame, as one ffmpeg expression.
    //
    // `Sound(volume=0.8)` is a constructor argument and was the only volume the
    // mux ever read. But `music.over(duration=1.5).volume = 0` is the same
    // sentence every visual property answers to, and it lands on the timeline
    // as a per-frame claim exactly like a fade does — the renderer just threw
    // it away, so a fade-out written that way came out at full level with
    // nothing said. The claims are per FRAME, so the expression is too: one
    // term per run of equal frames, each one holding for the frames it covers.
    //
    // "" when the scene claimed nothing but the constructor's value — a plain
    // `volume=0.8` reads better in the command and in a log.
    std::string volumeExpression(const IInput& input, double fallback, size_t frames)
    {
        std::vector<std::pair<size_t, double>> runs; // first frame → value
        for (size_t frame = 0; frame < frames; ++frame) {
            const json::object_t& args = const_cast<IInput&>(input).getMetadata(frame).args();
            const auto            found = args.find("volume");
            const double          level = found != args.end() && found->second.is_number()
                                              ? found->second.get<double>()
                                              : fallback;
            if (runs.empty() || runs.back().second != level)
                runs.emplace_back(frame, level);
        }
        if (runs.size() <= 1)
            return "";

        std::string expression;
        for (size_t i = 0; i < runs.size(); ++i) {
            const double from = (double)runs[i].first / Config::SCENE_FRAMERATE;
            if (!expression.empty())
                expression += "+";
            // The last run holds to the end of the track, which may be longer
            // than the scene: a sound that outlives the picture keeps the level
            // it was left at rather than dropping to nothing.
            expression += i + 1 < runs.size()
                              ? std::format("{:.6g}*gte(t,{:.6f})*lt(t,{:.6f})", runs[i].second, from, (double)runs[i + 1].first / Config::SCENE_FRAMERATE)
                              : std::format("{:.6g}*gte(t,{:.6f})", runs[i].second, from);
        }

        // A ramp is tens of terms; a scene that claims a different level on
        // every frame of a long track is thousands, and the command line is
        // what breaks. Said out loud rather than quietly coarsened.
        if (expression.size() > 32000) {
            std::cerr << std::format(
                "video-code: the volume claimed on this sound changes {} times — too many for one filter, so the average is used instead.\n",
                runs.size()
            );
            double total = 0;
            for (const auto& [frame, level] : runs)
                total += level;
            return std::format("{:.6g}", total / (double)runs.size());
        }
        return expression;
    }

    AudioGraph buildAudioGraph(const std::vector<std::unique_ptr<IInput>>& inputs, std::optional<std::pair<double, double>> window, size_t frames, size_t firstInput)
    {
        AudioGraph graph;
        size_t     tracks = 0;

        auto arg = [&graph](std::string one) {
            graph.inputs += " " + one;
            graph.inputArgs.push_back(std::move(one));
        };
        auto file = [&graph](const std::string& path) {
            graph.inputs += std::format(" -i \"{}\"", path);
            graph.inputArgs.push_back("-i");
            graph.inputArgs.push_back(path);
        };

        for (const auto& i : inputs) {
            if (auto* s = dynamic_cast<Sound*>(i.get())) {
                if (s->trimStart() > 0.0) {
                    arg("-ss");
                    arg(std::format("{}", s->trimStart()));
                }
                if (s->trimEnd()) {
                    arg("-to");
                    arg(std::format("{}", *s->trimEnd()));
                }
                file(s->filepath());

                int delayMs = (int)std::llround(s->delay() * 1000.0);
                // The delay comes FIRST so the gain expression is written in
                // the scene's own clock: after `adelay`, `t` is the moment the
                // author sees on the timeline, which is what their claim said.
                const std::string claimed = volumeExpression(*i, s->volume(), frames);
                graph.filter += claimed.empty()
                                    ? std::format("[{}:a]volume={},adelay={}|{}[a{}];", tracks + firstInput, s->volume(), delayMs, delayMs, tracks)
                                    : std::format("[{}:a]adelay={}|{},volume=volume='{}':eval=frame[a{}];", tracks + firstInput, delayMs, delayMs, claimed, tracks);
                ++tracks;
            } else if (auto* v = dynamic_cast<Video*>(i.get()); v && hasAudioStream(v->filepath())) {
                file(v->filepath());
                graph.filter += videoAudioChain(*v, tracks + firstInput, tracks);
                ++tracks;
            }
        }

        if (tracks == 0)
            return graph;

        graph.label = "a0"; // single chain, no amix needed
        if (tracks > 1) {
            for (size_t i = 0; i < tracks; ++i)
                graph.filter += std::format("[a{}]", i);
            // normalize=0: amix otherwise divides every track by the number of
            // tracks and scales the rest back up as each one ends — so a voice
            // over music played the music at HALF its claimed level while the
            // voice lasted, then let it back up when the voice stopped, which is
            // a duck turned inside out. Measured: 0.6 claimed came out as 0.3
            // beside a voice and 0.6 after it. A level claimed is the level
            // mixed; what sums past 1.0 clips, which is what the author asked for.
            graph.filter += std::format("amix=inputs={}:duration=longest:dropout_transition=0:normalize=0[aout];", tracks);
            graph.label = "aout";
        }
        if (window) {
            graph.filter += std::format("[{}]atrim=start={}:end={},asetpts=PTS-STARTPTS[arange];", graph.label, window->first, window->second);
            graph.label = "arange";
        }
        graph.filter.pop_back(); // every chain ends in ';'
        graph.count = tracks;
        return graph;
    }

    // A sound longer than the film would otherwise stretch the file past its
    // last frame. Shared by the render and its measurement: a measurement of
    // a longer stretch than the one written would aim at the wrong loudness.
    std::pair<double, double> filmWindow(std::optional<std::pair<double, double>> window, size_t frames)
    {
        return window ? *window : std::pair{0.0, static_cast<double>(frames) / Config::SCENE_FRAMERATE};
    }

    // loudnorm's JSON report: the last `{ … }` that holds "input_i". Values
    // are strings in it, every one of them (ffmpeg 9.0.2, measured).
    std::optional<json> loudnormReport(const std::string& said)
    {
        const size_t key = said.rfind("\"input_i\"");
        if (key == std::string::npos)
            return std::nullopt;
        const size_t open = said.rfind('{', key);
        const size_t close = said.find('}', key);
        if (open == std::string::npos || close == std::string::npos)
            return std::nullopt;
        json report = json::parse(said.substr(open, close - open + 1), nullptr, false);
        if (report.is_discarded() || !report.is_object())
            return std::nullopt;
        return report;
    }

    // One pass of loudnorm on its own, with `linear=true`, is not linear: it
    // has nothing measured to aim with, and falls back to dynamic mode, which
    // rides the gain through the film. Measured on a 6 s tone: pass 1 said
    // "dynamic". So the mix is measured first, audio only, with nothing
    // written, and the render applies what was found.
    Loudness measureLoudness(const std::vector<std::unique_ptr<IInput>>& inputs, std::optional<std::pair<double, double>> window, size_t frames, double target)
    {
        Loudness         measured{.target = target};
        const AudioGraph graph = buildAudioGraph(inputs, filmWindow(window, frames), frames, 0);
        if (graph.count == 0)
            return measured;

        // -nostdin: this ffmpeg shares the terminal, and would read keys from it.
        // LRA=11 here is only what the report's `output_*` lines assume; the
        // `input_*` values the render needs do not depend on it.
        const std::string command = std::format(
            "ffmpeg -hide_banner -nostats -nostdin{} -filter_complex \"{};[{}]loudnorm=I={}:TP=-1:LRA=11:print_format=json[lmeasure]\" -map \"[lmeasure]\" -f null - 2>&1",
            graph.inputs,
            graph.filter,
            graph.label,
            target
        );
        FILE* p = popen(command.c_str(), "r");
        if (!p) {
            measured.state = Loudness::State::Failed;
            measured.note = "ffmpeg could not be started";
            return measured;
        }
        std::string said;
        char        buf[4096];
        for (size_t n; (n = fread(buf, 1, sizeof buf, p)) > 0;)
            said.append(buf, n);
        const int status = pclose(p);

        const std::optional<json> report = loudnormReport(said);
        const auto                text = [&](const char* key) {
            return report && report->contains(key) && (*report)[key].is_string() ? (*report)[key].get<std::string>() : std::string();
        };
        measured.inputI = text("input_i");
        measured.inputTP = text("input_tp");
        measured.inputLRA = text("input_lra");
        measured.inputThresh = text("input_thresh");
        measured.targetOffset = text("target_offset");
        if (status != 0 || measured.inputI.empty() || measured.inputTP.empty() || measured.inputLRA.empty() || measured.inputThresh.empty() || measured.targetOffset.empty()) {
            measured.state = Loudness::State::Failed;
            const size_t tail = said.size() > 600 ? said.size() - 600 : 0;
            measured.note = said.substr(tail);
            return measured;
        }

        // At -70 LUFS and below loudnorm's gate has nothing left to measure,
        // and the gain to the target has no bound: "-inf" is what silence says.
        measured.state = !(std::strtod(measured.inputI.c_str(), nullptr) > -70.0) ? Loudness::State::Silent : Loudness::State::Ready;
        return measured;
    }

    // linear=true is a request, not a promise. ffmpeg 9.0.2 gave dynamic for a
    // gain that would lift the peak above -1 dBTP (measured). LRA is the
    // larger of 11 and the measured range, capped at loudnorm's 50, as
    // SPEC-loudness.md asks: a target range below the measured one is the
    // spec's named cause of the fallback. The report says which mode happened.
    //
    // measured_LRA is passed as at least 0.01. loudnorm takes 0.00 (its
    // default value) as a reason for dynamic mode, and a short clip can
    // measure 0.00: a steady tone does, and test/tour_music.wav (8 s of real
    // music) did. On that file pass 2 with measured_I=-16.09:measured_TP=-6.16
    // gave dynamic with 0.00 and linear with 0.01, at -14 and at -23 alike,
    // every file at the target by ebur128 (the controller, 2026-11-23). The
    // measurement is changed by 0.01 LU, which is no range either.
    std::string loudnormStage(const Loudness& measured)
    {
        const double lra = std::strtod(measured.inputLRA.c_str(), nullptr);
        const double range = std::min(50.0, std::max(11.0, lra));
        return std::format(
            "loudnorm=I={}:TP=-1:LRA={}:measured_I={}:measured_LRA={}:measured_TP={}:measured_thresh={}:offset={}:linear=true:print_format=json{},aresample=48000",
            measured.target,
            range,
            measured.inputI,
            lra < 0.01 ? std::string("0.01") : measured.inputLRA,
            measured.inputTP,
            measured.inputThresh,
            measured.targetOffset,
            measured.statsFile.empty() ? "" : std::format(":stats_file='{}'", measured.statsFile)
        );
    }

    // The render's ffmpeg logs at "warning", and loudnorm's own report is
    // "info": the stats file is how its answer leaves the process.
    std::string appliedNormalisation(const Loudness& measured)
    {
        std::ifstream in(measured.statsFile);
        if (!in)
            return "";
        const std::string         said((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        const std::optional<json> report = loudnormReport(said);
        if (!report || !report->contains("normalization_type") || !(*report)["normalization_type"].is_string())
            return "";
        return (*report)["normalization_type"].get<std::string>();
    }

    AudioArgs buildAudioArgs(const std::vector<std::unique_ptr<IInput>>& inputs, const std::string& audioCodec, std::optional<std::pair<double, double>> window, size_t frames, const Loudness* loudness)
    {
        const AudioGraph graph = buildAudioGraph(inputs, filmWindow(window, frames), frames, 1);
        if (graph.count == 0)
            return {"", " -an", 0};
        if (loudness && loudness->state == Loudness::State::Ready)
            return {graph.inputs, std::format(" -filter_complex \"{};[{}]{}[aloud]\" -map 0:v -map \"[aloud]\" -c:a {}", graph.filter, graph.label, loudnormStage(*loudness), audioCodec), graph.count};
        return {graph.inputs, std::format(" -filter_complex \"{}\" -map 0:v -map \"[{}]\" -c:a {}", graph.filter, graph.label, audioCodec), graph.count};
    }
} // namespace VC::Audio
