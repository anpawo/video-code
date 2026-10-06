/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** ScreenSize
*/

#include "core/ScreenSize.hpp"

#include <pybind11/embed.h>
#include <pybind11/stl.h>

#include <argparse/argparse.hpp>
#include <filesystem>
#include <format>
#include <iostream>

#include "input/Metadata.hpp"

namespace py = pybind11;

namespace
{
    // The shapes --for knows, by the name of the place the film is watched
    // rather than by its pixels: what an author picks is a destination, and
    // 1080x1920 is a consequence of it. A shape is a RESOLUTION and nothing
    // else — the scene runs again inside it and lays itself out (Split.AUTO,
    // W/H, TOP_SIDE...), so nothing here crops or scales anything.
    struct Shape
    {
        const char *name;
        float       width;
        float       height;
    };

    constexpr Shape kShapes[] = {
        {"youtube", 1920.f, 1080.f},
        {"tiktok", 1080.f, 1920.f},
        {"square", 1080.f, 1080.f},
    };

    std::string shapeNames()
    {
        std::string list;
        for (const Shape &s : kShapes)
            list += (list.empty() ? "" : ", ") + std::string(s.name);
        return list;
    }

    // "out/film.mp4" + "tiktok" -> "out/film-tiktok.mp4". The shape has to be
    // in the NAME: three renders of one command otherwise overwrite each other,
    // and the survivor says nothing about which one it is.
    std::string named(const std::string &path, const std::string &shape)
    {
        const std::filesystem::path out(path);
        return (out.parent_path() / std::format("{}-{}{}", out.stem().string(), shape, out.extension().string())).string();
    }
}

void VC::applyScreenSize(float width, float height)
{
    config::screen = {width, height};
    config::screenOffset = {width / 2.f, height / 2.f};

    // How Python learns the resolution: constants.py reads this at import time
    // and builds the world box from it. os.environ also putenv()s, so it
    // survives into anything the scene shells out to.
    try {
        py::module_::import("os").attr("environ")["VC_SCREEN"] =
            std::format("{}x{}", (int)width, (int)height);

        // Too late for the import-time read if the package is already loaded —
        // which happens when one process renders several sizes in a row (the
        // visual-regression suite). Then, and only then, re-derive in place.
        py::dict modules = py::module_::import("sys").attr("modules");
        if (modules.contains("videocode.constants"))
            modules["videocode.constants"].attr("setScreen")(int(width), int(height));
    } catch (const py::error_already_set &e) {
        std::cerr << "Could not export VC_SCREEN:\n"
                  << e.what() << "\n";
    }
}

Config VC::makeConfig(const argparse::ArgumentParser &parser)
{
    // The resolution comes from the command line and nowhere else — a scene
    // cannot change it. Python is TOLD the answer (applyScreenSize), never
    // asked for it, which keeps the world box, the preview surface and the
    // encoder on the same numbers by construction.
    const float width = parser.get<float>("--width");
    const float height = parser.get<float>("--height");

    if (width < 2.f || height < 2.f) {
        std::cerr << "Invalid resolution " << (int)width << "x" << (int)height << ".\n";
        std::exit(EXIT_FAILURE);
    }
    if ((int)width % 2 != 0 || (int)height % 2 != 0)
        std::cerr << "Warning: " << (int)width << "x" << (int)height
                  << " has an odd dimension — H.264/VP9 encoding will fail. Use even values.\n";

    applyScreenSize(width, height);

    return Config{
        .screenWidth = width,
        .screenHeight = height,

        .windowRatio = parser.get<float>("--windowRatio"),

        .framerate = parser.get<int>("--framerate"),

        .hwEncode = parser.get<bool>("--hwencode"),

        .sourceFile = parser.get("--file"),
        .outputFile = parser.get("--generate"),

        .renderFrom = parser.present("--from").value_or(""),
        .renderTo = parser.present("--to").value_or(""),

        .sheetTiles = parser.present<int>("--sheet").value_or(1),
        .sheetAt = parser.present("--at").value_or(""),
    };
}

namespace
{
    // One entry per render asked by --set/--data, from videocode/params.py —
    // which reads the CSV, fills "{column}" in the output path, and refuses
    // before the first frame what would otherwise fail half way through a
    // batch. Called after makeConfig has pointed Python at the resolution:
    // importing videocode builds the world box.
    struct Row
    {
        std::string params;
        std::string output;
        std::string note;
    };

    std::vector<Row> planRows(const argparse::ArgumentParser &parser, const std::string &output)
    {
        const auto        sets = parser.get<std::vector<std::string>>("--set");
        const std::string data = parser.present("--data").value_or("");
        if (sets.empty() && data.empty())
            return {{"", output, ""}};

        std::vector<Row> rows;
        try {
            for (const py::handle entry : py::module_::import("videocode.params").attr("plan")(sets, data, output)) {
                rows.push_back({entry["params"].cast<std::string>(), entry["output"].cast<std::string>(), entry["note"].cast<std::string>()});
            }
        } catch (const py::error_already_set &e) {
            // A ParamError is a sentence written for the person at the
            // terminal; anything else is a bug, and keeps its traceback.
            std::cerr << "video-code: " << (e.matches(py::module_::import("videocode.params").attr("ParamError")) ? std::string(py::str(e.value())) : std::string(e.what())) << "\n";
            std::exit(EXIT_FAILURE);
        }
        return rows;
    }
}

void VC::applyParams(const Config &config)
{
    if (config.params.empty())
        return;
    try {
        py::module_::import("videocode.params").attr("provide")(config.params);
    } catch (const py::error_already_set &e) {
        std::cerr << "Could not export VC_PARAMS:\n"
                  << e.what() << "\n";
    }
}

std::vector<VC::NamedShape> VC::shapesFor(const argparse::ArgumentParser &parser)
{
    const std::string asked = parser.present("--for").value_or("");
    if (asked.empty())
        return {};

    // The shapes decide the size, so the size flags cannot also. Said rather
    // than resolved quietly: `-w 800 --for tiktok` is a person expecting one
    // of the two to win, and silence would let them believe it was theirs.
    if (parser.is_used("--width") || parser.is_used("--height"))
        std::cerr << "video-code: --for decides the resolution — the --width/--height you gave are not used.\n";

    std::vector<NamedShape> shapes;
    for (size_t start = 0; start <= asked.size();) {
        const size_t      comma = std::min(asked.find(',', start), asked.size());
        const size_t      from = asked.find_first_not_of(" \t", start);
        const size_t      to = asked.find_last_not_of(" \t", comma - 1);
        const std::string name = (from == std::string::npos || from >= comma) ? "" : asked.substr(from, to - from + 1);
        start = comma + 1;

        const Shape *shape = nullptr;
        for (const Shape &candidate : kShapes)
            if (name == candidate.name)
                shape = &candidate;
        if (!shape) {
            std::cerr << std::format("video-code: --for does not know the shape \"{}\". It knows {}.\n", name, shapeNames());
            std::exit(EXIT_FAILURE);
        }
        shapes.push_back({name, shape->width, shape->height});
    }
    return shapes;
}

std::vector<Config> VC::makeConfigs(const argparse::ArgumentParser &parser)
{
    const Config           base = makeConfig(parser);
    const std::vector<Row> rows = planRows(parser, base.outputFile);

    // Each row, then each shape inside it: a row's files sit together, and a
    // row that fails stops the batch with the rows after it named as not made.
    const auto withRow = [](Config config, const Row &row) {
        config.params = row.params;
        config.outputFile = row.output;
        config.shapeNote = row.note;
        return config;
    };

    const std::vector<NamedShape> asked = shapesFor(parser);
    if (asked.empty()) {
        std::vector<Config> configs;
        for (const Row &row : rows)
            configs.push_back(withRow(base, row));
        return configs;
    }

    std::vector<Config> shapes;
    for (const NamedShape &shape : asked) {
        Config config = base;
        config.screenWidth = shape.width;
        config.screenHeight = shape.height;
        config.windowWidth = config.screenWidth * config.windowRatio;
        config.windowHeight = config.screenHeight * config.windowRatio;
        config.shapeNote = shape.name;
        shapes.push_back(config);
    }

    // Numbered only when there is a run to be somewhere in.
    std::vector<Config> configs;
    for (const Row &row : rows) {
        for (size_t i = 0; i < shapes.size(); ++i) {
            Config config = withRow(shapes[i], row);
            config.outputFile = named(row.output, shapes[i].shapeNote);
            config.shapeNote = (row.note.empty() ? "" : row.note + " · ") + shapes[i].shapeNote;
            if (shapes.size() > 1)
                config.shapeNote += std::format(", {} of {}", i + 1, shapes.size());
            configs.push_back(config);
        }
    }
    return configs;
}
