/*
** EPITECH PROJECT, 2025
** video-code
** File description:
** Compiler
*/

#include "compiler/Compiler.hpp"

#include <argparse/argparse.hpp>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdlib>
#include <deque>
#include <filesystem>
#include <format>
#include <fstream>
#include <iostream>
#include <mutex>
#include <optional>
#include <string>
#include <thread>
#include <vector>

#include "compiler/AudioMix.hpp"
#include "input/media/Sound.hpp"
#include "input/media/Video.hpp"
#include "utils/ImageIO.hpp"
#include "vulkan/VulkanHeadlessRenderer.hpp"

namespace
{
    // ── Output-container format profile ───────────────────────────────────────
    // Selects encoder args purely by output extension, mirroring the image-vs-
    // video dispatch already done via ImageIO::hasImageExtension. `.mp4` and any
    // unrecognized extension fall through to the historical h264 behavior
    // byte-for-byte. `.mov`/`.webm` add real per-pixel alpha (and require the
    // renderer's transparent-clear mode); `.gif` is palette-quantized, no alpha.
    struct VideoProfile
    {
        std::string videoArgs;                // "-c:v … -pix_fmt …", or the gif -vf palette graph
        bool        transparentClear = false; // main pass clears to {0,0,0,0}
        bool        faststart = true;         // append "-movflags +faststart" (mp4/mov only)
        bool        allowAudio = true;        // false for gif (container can't carry audio)
        std::string audioCodec = "aac";       // aac for mp4/mov; libopus for webm
    };

    std::string lowerExt(const std::string& path)
    {
        auto dot = path.find_last_of('.');
        if (dot == std::string::npos)
            return "";
        std::string ext = path.substr(dot);
        for (char& c : ext) c = (char)std::tolower((unsigned char)c);
        return ext;
    }

    VideoProfile videoProfileFor(const std::string& outputFile, bool hwEncode, int framerate)
    {
        const std::string ext = lowerExt(outputFile);
        VideoProfile      p;

        if (ext == ".mov") {
            // ProRes 4444 carries a real alpha plane. prores_ks (software) is the
            // required baseline; prores_videotoolbox (hardware, opt-in via
            // --hwencode) also accepts a 4444 alpha profile on Apple silicon.
            p.videoArgs = hwEncode
                              ? " -c:v prores_videotoolbox -profile:v 4444 -pix_fmt yuva444p10le"
                              : " -c:v prores_ks -profile:v 4444 -pix_fmt yuva444p10le";
            p.transparentClear = true;
            p.faststart = true; // valid for the mov/mp4 muxer
        } else if (ext == ".webm") {
            // VP9 with alpha. -b:v 0 + -crf gives constant-quality mode. The webm
            // muxer rejects aac, so audio (if any) must be Opus.
            p.videoArgs = " -c:v libvpx-vp9 -pix_fmt yuva420p -b:v 0 -crf 30";
            p.transparentClear = true;
            p.faststart = false; // faststart is an mp4/mov flag; invalid for webm
            p.audioCodec = "libopus";
        } else if (ext == ".gif") {
            // Two-pass palette: generate an optimal 256-color palette from the
            // stream, then apply it. No real alpha (binary transparency at best,
            // accepted limitation) and no audio track. The -vf graph fully
            // replaces the -c:v/-pix_fmt args; the renderer stays opaque.
            p.videoArgs = std::format(
                " -vf \"fps={},split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer\" -loop 0",
                framerate
            );
            p.transparentClear = false;
            p.faststart = false;
            p.allowAudio = false;
        } else {
            // .mp4 and anything unrecognized — unchanged from the original path.
            p.videoArgs = hwEncode
                              ? " -c:v h264_videotoolbox"
                                " -pix_fmt yuv420p"
                                " -q:v 65"
                              : " -c:v libx264"
                                " -preset veryfast"
                                " -pix_fmt yuv420p"
                                " -crf 23";
            p.transparentClear = false;
            p.faststart = true;
        }
        return p;
    }

    // ── Progress bar (pip-style) ──────────────────────────────────────────────

    constexpr const char* kReset = "\033[0m";
    constexpr const char* kGreenB = "\033[1;32m";
    constexpr const char* kDim = "\033[2m";
    constexpr const char* kBold = "\033[1m";

    std::string rep(const char* s, int n)
    {
        std::string out;
        out.reserve(std::string(s).size() * (size_t)n);
        for (int k = 0; k < n; ++k) out += s;
        return out;
    }

    // Red (0%) → yellow (50%) → green (100%) via 24-bit ANSI RGB.
    std::string barColor(double frac)
    {
        frac = frac < 0.0 ? 0.0 : frac > 1.0 ? 1.0
                                             : frac;
        int r, g;
        if (frac <= 0.5) {
            r = 210;
            g = (int)(frac * 2.0 * 180);
        } else {
            r = (int)((1.0 - frac) * 2.0 * 210);
            g = 180;
        }
        return std::format("\033[38;2;{};{};0m", r, g);
    }

    // What a scene named, as the container's own chapter list.
    //
    // `timestamp("the build")` is already written in these scenes — it is how
    // the author jumps around while editing — and it is exactly what a chapter
    // is. A chapter runs until the next one starts, and the last runs to the
    // end of what was rendered; times are counted from the start of the FILE,
    // so a `--from` render moves them all rather than pointing outside it.
    std::string chapterMetadata(const std::map<size_t, std::string>& stamps, size_t first, size_t last)
    {
        std::vector<std::pair<size_t, std::string>> kept;
        for (const auto& [frame, name] : stamps)
            if (frame >= first && frame < last)
                kept.emplace_back(frame - first, name);
        if (kept.empty())
            return "";

        std::string out = ";FFMETADATA1\n";
        for (size_t i = 0; i < kept.size(); ++i) {
            const size_t end = i + 1 < kept.size() ? kept[i + 1].first : last - first;
            out += std::format(
                "[CHAPTER]\nTIMEBASE=1/{}\nSTART={}\nEND={}\ntitle={}\n",
                (int)Config::SCENE_FRAMERATE, kept[i].first, end, kept[i].second
            );
        }
        return out;
    }

    std::string clock(double seconds)
    {
        const int whole = (int)seconds;
        return whole >= 3600
                   ? std::format("{}:{:02d}:{:02d}", whole / 3600, whole / 60 % 60, whole % 60)
                   : std::format("{}:{:02d}", whole / 60, whole % 60);
    }

    // The same list again, in the form a description box takes — and what
    // YouTube will do with it. It refuses a list silently: no first chapter at
    // 0:00, fewer than three, or one shorter than ten seconds, and the whole
    // list is simply not shown. A tool that printed it anyway would be handing
    // over something that quietly does nothing.
    void printChapters(const std::map<size_t, std::string>& stamps, size_t first, size_t last, const std::string& refused)
    {
        std::vector<std::pair<size_t, std::string>> kept;
        for (const auto& [frame, name] : stamps)
            if (frame >= first && frame < last)
                kept.emplace_back(frame - first, name);
        if (kept.empty())
            return;

        std::cout << "\n"
                  << kBold << "Chapters" << kReset << kDim << "  paste into the description" << kReset << "\n";
        for (const auto& [frame, name] : kept)
            std::cout << std::format("   {}  {}\n", clock((double)frame / Config::SCENE_FRAMERATE), name);

        // Judged on what is PRINTED, not on the frame: YouTube reads the
        // pasted line, so a chapter three frames in is a chapter at 0:00 to it
        // and saying otherwise would contradict the list right above.
        std::vector<std::string> broken;
        if (clock((double)kept.front().first / Config::SCENE_FRAMERATE) != "0:00")
            broken.push_back("the first one is not at 0:00");
        if (kept.size() < 3)
            broken.push_back(std::format("there are {}, and it wants three", kept.size()));
        for (size_t i = 0; i < kept.size(); ++i) {
            const size_t end = i + 1 < kept.size() ? kept[i + 1].first : last - first;
            if ((double)(end - kept[i].first) / Config::SCENE_FRAMERATE < 10.0) {
                broken.push_back(std::format("\"{}\" is under ten seconds", kept[i].second));
                break;
            }
        }
        if (!broken.empty()) {
            std::cout << kDim << "   YouTube will show none of them: ";
            for (size_t i = 0; i < broken.size(); ++i)
                std::cout << (i > 0 ? ", " : "") << broken[i];
            std::cout << "." << (refused.empty() ? " They are in the file itself either way." : "") << kReset << "\n";
        }
        if (!refused.empty())
            std::cout << kDim << std::format("   a {} file carries no chapters of its own — this list is all of them.", refused) << kReset << "\n";
    }

    // Overwrites the current terminal line with the progress bar.
    void printProgress(size_t done, size_t total, double /*elapsed*/)
    {
        constexpr int W = 40;
        double        frac = total > 0 ? (double)done / (double)total : 0.0;
        int           filled = std::min(W, (int)(frac * W + 0.5));
        int           empty = W - filled;
        int           pct = std::min(100, (int)(frac * 100 + 0.5));

        std::string bar = "   ";
        bar += barColor(frac);
        bar += rep("━", filled);
        if (empty > 0) {
            bar += kDim;
            bar += rep("╌", empty);
        }
        bar += kReset;
        bar += std::format("  {:3d}%  {}/{} frames", pct, done, total);
        std::cout << "\r" << bar << std::flush;
    }
}

VC::Compiler::Compiler(const argparse::ArgumentParser& parser, Config config)
    : config(std::move(config))
    , _core(parser, this->config)
{
}

VC::Compiler::~Compiler() = default;

int VC::Compiler::generateVideo()
{
    // The scene never ran. Rendering it produces a file no player will open —
    // 261 bytes of container and no stream — and the progress bar reaches 100%
    // of nothing and prints its tick. The error is already on stderr; this is
    // what makes it count.
    if (_core._sceneFailed) {
        std::cerr << "video-code: the scene did not run, so there is nothing to render.\n";
        return EXIT_FAILURE;
    }

    // A sheet is stills laid side by side; asked of a video it would have to
    // mean something else, and guessing which is how a flag becomes a shrug.
    if (config.sheetTiles > 1 && !VC::ImageIO::hasImageExtension(config.outputFile)) {
        std::cerr << std::format("video-code: --sheet lays stills side by side in one image, and {} is a video.\n", config.outputFile);
        return EXIT_FAILURE;
    }
    if (config.sheetTiles < 1) {
        std::cerr << std::format("video-code: --sheet {} is not a number of moments to show.\n", config.sheetTiles);
        return EXIT_FAILURE;
    }

    VulkanHeadlessRenderer renderer(
        (uint32_t)config.screenWidth,
        (uint32_t)config.screenHeight
    );

    if (!renderer.init()) {
        std::cerr << "Vulkan headless init failed.\n";
        return 1;
    }

    _core.uploadTextures(
        [&](const cv::Mat& mat) { return renderer.uploadTexture(mat); },
        [&](VkDescriptorSet desc, const cv::Mat& mat) { renderer.updateTexturePixels(desc, mat); }
    );

    // The stretch to render, in scene frames. Seconds are what an author
    // thinks in; a timestamp() name is what they already wrote in the scene,
    // and Core recorded it — so both are accepted. Asking past the end clamps
    // rather than refuses: the fix was at 12 s and the scene is 10 s long, so
    // the range ends at the last frame.
    const size_t sceneFrames = _core._nbFrame;
    auto         sceneFrame = [&](const std::string& spec, size_t fallback) -> std::optional<size_t> {
        if (spec.empty())
            return fallback;
        char*  end = nullptr;
        double secs = std::strtod(spec.c_str(), &end);
        if (end != spec.c_str() && *end == '\0')
            return std::min(sceneFrames, (size_t)std::llround(std::max(secs, 0.0) * Config::SCENE_FRAMERATE));
        for (const auto& [frame, name] : _core._timestamps)
            if (name == spec)
                return std::min(frame, sceneFrames);
        return std::nullopt;
    };
    // --at, resolved by the same rule and refused by the same message. Held on
    // the Compiler because the sheet is laid out in generateImage(), which is
    // past the point where the scene's names are still in scope.
    _sheetFrames.clear();
    for (size_t cut = 0, next = 0; cut <= config.sheetAt.size(); cut = next + 1) {
        next = config.sheetAt.find(',', cut);
        if (next == std::string::npos)
            next = config.sheetAt.size();
        std::string one = config.sheetAt.substr(cut, next - cut);
        const auto  from = one.find_first_not_of(" \t");
        if (from == std::string::npos)
            continue;
        one = one.substr(from, one.find_last_not_of(" \t") - from + 1);
        const auto when = sceneFrame(one, 0);
        if (!when) {
            std::cerr << std::format("video-code: --at \"{}\" is neither seconds nor a timestamp() of this scene.\n", one);
            return EXIT_FAILURE;
        }
        _sheetFrames.push_back(*when);
    }

    const auto first = sceneFrame(config.renderFrom, 0);
    const auto last = sceneFrame(config.renderTo, sceneFrames);
    if (!first || !last) {
        std::cerr << std::format("video-code: --{} \"{}\" is neither seconds nor a timestamp() of this scene.", first ? "to" : "from", first ? config.renderTo : config.renderFrom);
        if (!_core._timestamps.empty()) {
            std::cerr << " Its timestamps:";
            for (const auto& [frame, name] : _core._timestamps)
                std::cerr << std::format("\n  {:>7.2f}s  {}", (double)frame / Config::SCENE_FRAMERATE, name);
        }
        std::cerr << "\n";
        return EXIT_FAILURE;
    }

    if (VC::ImageIO::hasImageExtension(config.outputFile)) {
        if (config.loudness)
            std::cout << "Loudness: not normalised — an image carries no sound.\n";
        return generateImage(renderer, *first, *last);
    }

    if (*first >= *last) {
        std::cerr << std::format("video-code: nothing to render between {} and {} — the scene is {:.2f} s long.\n", config.renderFrom, config.renderTo.empty() ? "the end" : config.renderTo, (double)sceneFrames / Config::SCENE_FRAMERATE);
        return EXIT_FAILURE;
    }
    const bool ranged = *first > 0 || *last < sceneFrames;

    // Encoder args are chosen purely by output extension (see videoProfileFor):
    // .mov → ProRes 4444+alpha, .webm → VP9+alpha, .gif → palette-quantized,
    // everything else → the historical h264 path. Alpha-capable formats need the
    // main pass to clear transparent so empty regions reach ffmpeg with alpha=0.
    const VideoProfile profile = videoProfileFor(config.outputFile, config.hwEncode, config.framerate);
    renderer.setTransparentBackground(profile.transparentClear);

    const auto window = ranged ? std::optional{std::pair{(double)*first / Config::SCENE_FRAMERATE, (double)*last / Config::SCENE_FRAMERATE}} : std::nullopt;

    // --loudness, pass 1: the mix is measured before the first frame, over the
    // stretch this file will hold. Each file of a --for or --data run comes
    // through here with its own scene run, so each one is measured on its own.
    // Where nothing can be normalised the render goes on as it would have, and
    // says so in one line: a flag that changed nothing must not look obeyed.
    VC::Audio::Loudness loudness;
    if (config.loudness) {
        if (!profile.allowAudio)
            std::cout << "Loudness: not normalised — a GIF carries no sound.\n";
        else {
            loudness = VC::Audio::measureLoudness(_core._inputs, window, sceneFrames, *config.loudness);
            switch (loudness.state) {
                case VC::Audio::Loudness::State::NoSound:
                    std::cout << "Loudness: not normalised — the scene has no sound.\n";
                    break;
                case VC::Audio::Loudness::State::Silent:
                    std::cout << std::format("Loudness: not normalised — the mix measures {} LUFS, which loudnorm takes for silence (-70 or lower).\n", loudness.inputI);
                    break;
                case VC::Audio::Loudness::State::Failed:
                    std::cerr << std::format("video-code: --loudness could not measure the mix. ffmpeg said:\n{}\n", loudness.note);
                    return EXIT_FAILURE;
                case VC::Audio::Loudness::State::Ready:
                    break;
            }
        }
    }
    const bool normalised = loudness.state == VC::Audio::Loudness::State::Ready;

    // GIF can't carry audio, so skip the audio graph entirely for it.
    VC::Audio::AudioArgs audio = profile.allowAudio
                                     ? VC::Audio::buildAudioArgs(_core._inputs, profile.audioCodec, window, sceneFrames, normalised ? &loudness : nullptr)
                                     : VC::Audio::AudioArgs{"", " -an"};

    // -movflags +faststart is an mp4/mov-only flag; omit it for webm/gif.
    const std::string movflags = profile.faststart ? " -movflags +faststart" : "";

    // The chapters go in as one more input, written after the audio so the
    // filter's own indices still hold. Only where the container carries them:
    // a GIF cannot, and claiming otherwise would be worse than not writing any.
    const std::string ext = VC::ImageIO::lowerExtension(config.outputFile);
    const std::string chapters = (ext == ".mp4" || ext == ".m4v" || ext == ".mov" || ext == ".mkv")
                                     ? chapterMetadata(_core._timestamps, *first, *last)
                                     : "";
    std::string       chapterInput;
    std::string       chapterMap;
    const auto        chapterFile = std::filesystem::temp_directory_path() / std::format("video-code-{}.ffmeta", (void*)this);
    if (!chapters.empty()) {
        std::ofstream out(chapterFile);
        out << chapters;
        out.close();
        chapterInput = std::format(" -f ffmetadata -i \"{}\"", chapterFile.string());
        chapterMap = std::format(" -map_metadata {}", audio.count + 1);
    }

    FILE* pipe = popen(
        std::format(
            "ffmpeg"
            " -y"
            " -f rawvideo"
            " -pixel_format bgra"
            " -video_size {}x{}"
            " -framerate {}"
            " -i -"
            "{}"
            "{}"
            "{}"
            "{}"
            "{}"
            "{}"
            " -loglevel warning"
            " {}",
            (int)config.screenWidth,
            (int)config.screenHeight,
            config.framerate,
            audio.inputs,
            chapterInput,
            profile.videoArgs,
            audio.output,
            chapterMap,
            movflags,
            config.outputFile
        )
            .c_str(),
        "w"
    );
    if (!pipe) {
        std::cerr << "Could not start the ffmpeg pipe.\n";
        return 1;
    }

    // Pipelined encode: the blocking fwrite into the FFmpeg pipe (~8 MB/frame,
    // paced by x264) runs on a writer thread behind a small bounded queue, so
    // frame N is encoded while frame N+1 is being built and rendered.
    constexpr size_t        QUEUE_CAP = 4;
    std::deque<cv::Mat>     queue;
    std::mutex              mtx;
    std::condition_variable notFull, notEmpty;
    bool                    producerDone = false;
    bool                    writeFailed = false;

    std::thread writer([&] {
        while (true) {
            cv::Mat frame;
            {
                std::unique_lock lock(mtx);
                notEmpty.wait(lock, [&] { return !queue.empty() || producerDone; });
                if (queue.empty())
                    break;
                frame = std::move(queue.front());
                queue.pop_front();
            }
            notFull.notify_one();

            size_t bytes = frame.total() * frame.elemSize();
            if (fwrite(frame.data, 1, bytes, pipe) != bytes) {
                std::lock_guard lock(mtx);
                writeFailed = true;
                queue.clear();
                notFull.notify_all();
                break;
            }
        }
    });

    // Scenes are authored at Config::SCENE_FRAMERATE (30fps): _nbFrame and all
    // start/duration values are expressed in that unit. When the requested
    // output framerate differs, resample by mapping each output frame to the
    // nearest scene frame — duplicating frames if framerate > SCENE_FRAMERATE,
    // dropping them if framerate < SCENE_FRAMERATE.
    const size_t rangeFrames = *last - *first;
    size_t       total = (config.framerate == Config::SCENE_FRAMERATE)
                             ? rangeFrames
                             : (size_t)std::llround((double)rangeFrames * config.framerate / Config::SCENE_FRAMERATE);

    // Header line — printed once; ETA is appended in-place after the first frame.
    auto fmtDur = [](double secs) -> std::string {
        return secs < 60.0
                   ? std::format("{:.1f}s", secs)
                   : std::format("{:d}:{:02d} min", (int)secs / 60, (int)secs % 60);
    };
    double      durSecs = config.framerate > 0 ? (double)total / config.framerate : 0.0;
    std::string headerBase = std::string(kBold) + "Generating" + kReset + "  " + config.outputFile + "   " + kDim + std::format("{}x{} · {} fps · {} · {} frames", (int)config.screenWidth, (int)config.screenHeight, config.framerate, fmtDur(durSecs), total);
    if (ranged)
        headerBase += std::format(" · {} → {} of {}", fmtDur((double)*first / Config::SCENE_FRAMERATE), fmtDur((double)*last / Config::SCENE_FRAMERATE), fmtDur((double)sceneFrames / Config::SCENE_FRAMERATE));
    if (!config.shapeNote.empty())
        headerBase += " · " + config.shapeNote;
    headerBase += kReset;
    std::cout << headerBase << "\n";

    auto   t0 = std::chrono::steady_clock::now();
    double etaSecs = -1.0; // set once after the first frame, never updated again

    for (size_t i = 0; i < total; ++i) {
        size_t sceneIndex = *first + ((config.framerate == Config::SCENE_FRAMERATE)
                                          ? i
                                          : (size_t)std::llround((double)i * Config::SCENE_FRAMERATE / config.framerate));
        if (sceneIndex >= *last)
            sceneIndex = *last - 1;
        _core._index = sceneIndex;

        const auto& meshes = _core.generateMeshes();
        renderer.setMeshes(meshes);
        renderer.setBackgroundColor(_core._bgColor);

        // readFrame() is one-frame pipeline-delayed: it returns the PREVIOUS
        // frame's pixels (empty on the first call) while this frame's GPU
        // work runs asynchronously. The final frame is retrieved via flush()
        // after the loop.
        cv::Mat frame = renderer.readFrame();
        if (!frame.empty()) {
            if (!frame.isContinuous())
                frame = frame.clone();

            std::unique_lock lock(mtx);
            notFull.wait(lock, [&] { return queue.size() < QUEUE_CAP || writeFailed; });
            if (writeFailed) {
                std::cerr << std::format("\nFrame {}: ffmpeg pipe write failed.\n", i);
                break;
            }
            queue.push_back(std::move(frame));
            lock.unlock();
            notEmpty.notify_one();
        }

        double elapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        if (etaSecs < 0.0 && elapsed > 0.0) {
            etaSecs = elapsed * (double)total; // first frame time × total
            // Go up one line and reprint the header with ETA appended.
            std::cout << "\033[1A\r\033[2K"
                      << headerBase << kDim << " · eta " << fmtDur(etaSecs)
                      << kReset << "\n";
        }
        printProgress(i + 1, total, elapsed);
    }

    {
        cv::Mat frame = renderer.flush();
        if (!frame.empty()) {
            if (!frame.isContinuous())
                frame = frame.clone();

            std::unique_lock lock(mtx);
            notFull.wait(lock, [&] { return queue.size() < QUEUE_CAP || writeFailed; });
            if (!writeFailed)
                queue.push_back(std::move(frame));
            lock.unlock();
            notEmpty.notify_one();
        }
    }

    {
        std::lock_guard lock(mtx);
        producerDone = true;
    }
    notEmpty.notify_all();
    writer.join();

    pclose(pipe);
    if (!chapters.empty())
        std::filesystem::remove(chapterFile);
    if (writeFailed)
        return 1;

    double totalElapsed = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();

    std::string doneBar = std::string(kGreenB) + "✓" + kReset + "  ";
    doneBar += barColor(1.0);
    doneBar += rep("━", 40);
    doneBar += kReset;
    doneBar += std::format("  100%  {:.1f}s", totalElapsed);
    doneBar += "                    "; // clear leftover frame-count text
    std::cout << "\r" << doneBar << "\n";

    // The type is loudnorm's own rule applied to the values the render passed
    // (LoudnormMode.hpp): a dynamic fallback would otherwise go unsaid.
    if (normalised)
        std::cout << std::format("Loudness: {:.1f} LUFS -> {:.1f} LUFS target ({})\n", std::strtod(loudness.inputI.c_str(), nullptr), loudness.target, VC::Audio::normalisationType(loudness));

    printChapters(_core._timestamps, *first, *last, chapters.empty() ? ext : "");
    return 0;
}

int VC::Compiler::generateImage(VulkanHeadlessRenderer& renderer, size_t first, size_t last)
{
    const size_t lastFrame = _core._nbFrame > 0 ? _core._nbFrame - 1 : 0;

    auto still = [&](size_t at) {
        _core._index = std::min(at, lastFrame);

        const auto& meshes = _core.generateMeshes();
        renderer.setMeshes(meshes);
        renderer.setBackgroundColor(_core._bgColor);

        // readFrame() returns the previous (nonexistent) frame's pixels — empty —
        // so the actual frame is retrieved via flush().
        renderer.readFrame();
        cv::Mat out = renderer.flush();
        return out.isContinuous() ? out : out.clone();
    };

    cv::Mat frame = still(first);

    const bool named = !_sheetFrames.empty();

    if (config.sheetTiles > 1 || named) {
        if (!named && last <= first) {
            std::cerr << std::format("video-code: --sheet needs a stretch to sample, and {} → {} is not one.\n", config.renderFrom.empty() ? "the start" : config.renderFrom, config.renderTo.empty() ? "the end" : config.renderTo);
            return EXIT_FAILURE;
        }

        // Both ends included: asked for four moments of a six-second stretch,
        // an author means 0, 2, 4 and 6 — not four samples that stop short of
        // the end they named. Each tile is the still that --from at that time
        // would have written, so what the sheet shows can be trusted against
        // one, and the time goes in a strip beneath rather than over the
        // picture, which would be a change to the frame it claims to show.
        const int    tiles = named ? (int)_sheetFrames.size() : config.sheetTiles;
        const int    strip = std::max(16, frame.rows / 12);
        const double fontScale = strip / 44.0;
        const int    thickness = std::max(1, strip / 22);
        cv::Mat      sheet(frame.rows + strip, frame.cols * tiles, frame.type(), cv::Scalar(0, 0, 0, 255));

        for (int k = 0; k < tiles; ++k) {
            const size_t  at = named ? _sheetFrames[k]
                                     : first + (size_t)std::llround((double)(last - first) * k / std::max(tiles - 1, 1));
            const cv::Mat tile = at == first ? frame : still(at);
            tile.copyTo(sheet(cv::Rect(k * frame.cols, 0, frame.cols, frame.rows)));

            const std::string label = std::format("{:.2f}s", (double)std::min(at, lastFrame) / Config::SCENE_FRAMERATE);
            int               base = 0;
            const cv::Size    size = cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, fontScale, thickness, &base);
            cv::putText(
                sheet,
                label,
                cv::Point(k * frame.cols + (frame.cols - size.width) / 2, frame.rows + (strip + size.height) / 2),
                cv::FONT_HERSHEY_SIMPLEX,
                fontScale,
                cv::Scalar(255, 255, 255, 255),
                thickness,
                cv::LINE_AA
            );
        }
        frame = sheet;
    }

    if (!VC::ImageIO::write(config.outputFile, frame)) {
        std::cerr << std::format("Failed to write image to {}\n", config.outputFile);
        return 1;
    }

    std::cout << kGreenB << "✓" << kReset << "  " << config.outputFile << "\n";
    return 0;
}
