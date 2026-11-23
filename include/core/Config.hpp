/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** Config
*/

#pragma once

#include <optional>
#include <string>

struct Config
{
    float screenWidth = 1920.f;
    float screenHeight = 1080.f;

    float windowRatio = 0.5f;

    float windowWidth = screenWidth * windowRatio;
    float windowHeight = screenHeight * windowRatio;

    ///< Output video framerate (fps) — independent of SCENE_FRAMERATE. The
    ///< Compiler resamples (duplicates/drops) scene frames to reach this rate.
    int framerate;

    ///< Framerate that scene-side frame indices/durations are expressed in —
    ///< matches videocode/constants.py FRAMERATE. Fixed: scenes are authored
    ///< in this unit regardless of the output framerate.
    static constexpr int SCENE_FRAMERATE = 30;

    ///< Use the hardware H.264 encoder (h264_videotoolbox) instead of libx264.
    bool hwEncode = false;

    ///< Source & Output file
    std::string sourceFile;
    std::string outputFile;

    ///< --from / --to as typed: seconds or a timestamp() name, empty when
    ///< absent. Resolved to scene frames by the Compiler, once the scene has
    ///< run and the names exist.
    std::string renderFrom;
    std::string renderTo;

    ///< --sheet: how many moments an image output holds side by side. 1 is a
    ///< plain still.
    int sheetTiles = 1;

    ///< --at: the exact moments a sheet shows, as typed — seconds or
    ///< timestamp() names, comma-separated, empty when absent. An even spread
    ///< across a stretch is the right sheet when nothing in the scene says
    ///< where to look; when the scene HAS named its moments, spreading evenly
    ///< spends tiles on stillness and misses the ones that were named. Given,
    ///< it decides both which frames are shown and how many.
    std::string sheetAt;

    ///< --loudness: the integrated loudness the written file is brought to,
    ///< in LUFS, already checked to be in loudnorm's -70..-5. Empty without
    ///< the flag, and then the audio is mixed exactly as it always was.
    std::optional<double> loudness;

    ///< --for: which named shape this render is and its place in the run
    ///< ("tiktok, 2 of 3"), for the Generating line. Empty for a lone render.
    std::string shapeNote;

    ///< --set / --data: what this render's scene is given, as the VC_PARAMS
    ///< JSON videocode/params.py reads. Empty when neither flag is used — the
    ///< environment is then left as it was.
    std::string params;
};
