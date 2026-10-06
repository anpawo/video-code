/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** ScreenSize
*/

#pragma once

#include <string>
#include <vector>

#include "core/Config.hpp"

// argparse is a COMMAND-LINE parser, and it was reaching five headers through
// this one — 1381 of the 1754 include events of a 75-line ScreenSize.cpp. Every
// use here is by reference, so a forward declaration is all a header needs; the
// definition belongs to the .cpp files that actually read a flag.
namespace argparse
{
    class ArgumentParser;
}

namespace VC
{
    ///< A frame --for knows by the place it is watched: "tiktok", 1080x1920.
    struct NamedShape
    {
        std::string name;
        float       width;
        float       height;
    };

    ///< The shapes --for names, in the order asked; empty without --for. An
    ///< unknown name exits with the list of known ones. Shared by the renders
    ///< (makeConfigs) and --lint, which checks the scene in each frame.
    std::vector<NamedShape> shapesFor(const argparse::ArgumentParser &parser);

    ///< Build the render Config. The resolution comes from --width/--height
    ///< (1920x1080 by default) and from nothing else — a scene cannot change
    ///< it, so the world box, the preview surface and the encoder agree by
    ///< construction rather than by negotiation.
    Config makeConfig(const argparse::ArgumentParser &parser);

    ///< One Config per shape named by --for, in the order asked, each with its
    ///< own resolution and its own output filename; a single Config — the
    ///< --width/--height one — when --for is absent. With --set/--data, that
    ///< for every row: rows × shapes, the row's values in Config::params. Deliberately does NOT
    ///< applyScreenSize: that transform is process-global, so it belongs to
    ///< the moment a render starts, not to the moment its Config is built.
    std::vector<Config> makeConfigs(const argparse::ArgumentParser &parser);

    ///< Point the world->pixel transform (config::screen / config::screenOffset)
    ///< and Python's VC_SCREEN at a resolution. Called by makeConfig; only worth
    ///< calling directly when a Config is built by hand, as in VisualTest.
    void applyScreenSize(float width, float height);

    ///< Hand the next run of the scene its --set/--data values (VC_PARAMS). A
    ///< no-op for a Config made without either flag.
    void applyParams(const Config &config);
}
