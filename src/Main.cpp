/*
** EPITECH PROJECT, 2024
** video-code
** File description:
** Main
*/

#include <pybind11/embed.h>
#include <pybind11/stl.h>
#include <sys/socket.h>

#include <QApplication>
#include <QGuiApplication>
#include <QIcon>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLocalSocket>
#include <QMainWindow>
#include <QMessageLogContext>
#include <QSocketNotifier>
#include <QTimer>
#include <algorithm>
#include <argparse/argparse.hpp>
#include <csignal>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <format>
#include <fstream>
#include <opencv2/core/utils/logger.hpp>
#include <tuple>

#include "compiler/Compiler.hpp"
#include "core/ScreenSize.hpp"
#include "test/VisualTest.hpp"
#include "utils/Paths.hpp"
#include "window/Editor.hpp"
#include "window/Window.hpp"

namespace py = pybind11;

// `video-code tell <verb> key=value…` — one line to the editor that is open,
// its answer on stdout. Numbers are sent as numbers, `true`/`false` as
// booleans, the rest as text; a first argument that starts with `{` is sent as
// the JSON it is. Exit status follows the answer's `ok`, so a script can chain
// calls with `&&`.
static int tell(int argc, char *argv[])
{
    QCoreApplication app(argc, argv);
    QJsonObject      request;
    if (argv[2][0] == '{') {
        QJsonParseError err{};
        request = QJsonDocument::fromJson(QByteArray(argv[2]), &err).object();
        if (err.error != QJsonParseError::NoError) {
            std::cerr << std::format("not JSON: {}\n", err.errorString().toStdString());
            return EXIT_FAILURE;
        }
    } else {
        request["do"] = QString::fromLocal8Bit(argv[2]);
        for (int i = 3; i < argc; ++i) {
            const QString arg = QString::fromLocal8Bit(argv[i]);
            const auto    eq = arg.indexOf('=');
            if (eq <= 0) {
                std::cerr << std::format("expected key=value, got {}\n", argv[i]);
                return EXIT_FAILURE;
            }
            const QString value = arg.mid(eq + 1);
            bool          isNumber = false;
            const double  number = value.toDouble(&isNumber);
            request[arg.left(eq)] = isNumber                          ? QJsonValue(number)
                                    : value == QLatin1String("true")  ? QJsonValue(true)
                                    : value == QLatin1String("false") ? QJsonValue(false)
                                                                      : QJsonValue(value);
        }
    }

    // VC_SOCKET, else the editor that opened last.
    const QString path = qEnvironmentVariable("VC_SOCKET").isEmpty() ? QString::fromStdString(VC::latestSocketPath()) : qEnvironmentVariable("VC_SOCKET");
    QLocalSocket  socket;
    socket.connectToServer(path);
    if (!socket.waitForConnected(2000)) {
        std::cerr << std::format("no editor is listening on {} — open one with ./video-code --editor\n", path.toStdString());
        return EXIT_FAILURE;
    }
    socket.write(QJsonDocument(request).toJson(QJsonDocument::Compact) + "\n");
    socket.flush();
    while (!socket.canReadLine()) {
        if (!socket.waitForReadyRead(60000)) {
            std::cerr << "the editor did not answer\n";
            return EXIT_FAILURE;
        }
    }
    const QByteArray line = socket.readLine();
    std::cout << line.constData();
    return QJsonDocument::fromJson(line).object().value("ok").toBool() ? EXIT_SUCCESS : EXIT_FAILURE;
}

void setParserArgument(argparse::ArgumentParser &p)
{
    p
        .add_argument("--file")
        .default_value("video.py")
        .help("File containing the code to generate the video.");

    p
        .add_argument("--generate")
        .nargs(0, 1)
        .default_value("output.mp4")
        .help("Generate the video, otherwise the program runs in edit mode where you can visualize the video as you write it.");

    p
        .add_argument("-w", "--width")
        .default_value(1920.f)
        .scan<'f', float>()
        .help("Output width in pixels. The only way to change it — a scene cannot.");

    p
        .add_argument("--height")
        .default_value(1080.f)
        .scan<'f', float>()
        .help("Output height in pixels. (No -h: argparse reserves it for --help.)");

    p
        .add_argument("--windowRatio")
        .default_value(0.5f)
        .scan<'f', float>()
        .help("Ratio of preview window compared to the video size.");

    p
        .add_argument("--framerate")
        .default_value(30)
        .scan<'i', int>()
        .help(
            "Output video framerate (fps). Scenes are authored at 30fps regardless "
            "of this value — frames are duplicated or dropped to resample to it."
        );

    p
        .add_argument("--showstack")
        .flag()
        .help("Show the steps of the video while being generated.");

    p
        .add_argument("--showtimeline")
        .flag()
        .help("Show the timeline of the video.");

    p
        .add_argument("--visual-test")
        .flag()
        .help("Run the visual regression suite (golden-frame + hot-reload equivalence checks) and exit.");

    p
        .add_argument("--inspect")
        .flag()
        .help(
            "Run --file and print what it makes as JSON on stdout — the elements with their class, "
            "line, on-screen span and effects, the waits and the moments it named — then exit. "
            "The timeline as text, for a script or an agent that cannot see the window."
        );

    p
        .add_argument("--lint")
        .flag()
        .help(
            "Run --file without rendering and print what is wrong with it, one "
            "`file:line: error|warning: message [rule]` per line: the scene failing to run, a Sound "
            "starting on or after the last frame, a write before frame 0, an element never on screen "
            "or only on the last frame, a Text resting outside title safe (the inner 80 %) — in each --for shape, "
            "or the --width/--height frame — and the warnings the editor shows. Exits 1 if any line is an error."
        );

    p
        .add_argument("--update-golden")
        .flag()
        .help("With --visual-test, (re)write the golden images instead of comparing against them.");

    p
        .add_argument("--editor")
        .flag()
        .help(
            "Open the editing shell (dock, timeline, properties, scene buffer) instead of the "
            "bare preview window. The chrome is QML read from disk, so it reloads when you save it."
        );

    p
        .add_argument("--serve")
        .flag()
        .help("With --check-chrome, keep the windowless chrome alive and answering `tell` until told to quit. --editor always serves.");

    p
        .add_argument("--check-chrome")
        .flag()
        .help(
            "Load the editor chrome, report whether it loaded, and exit — WITHOUT showing a "
            "window. macOS has no public API for choosing a window's Space, so a check that "
            "opens one lands on whichever desktop you are working on."
        );

    p
        .add_argument("--check-widget")
        .flag()
        .help(
            "Render a few scenes through the preview widget AND through the headless "
            "renderer and report how far apart they are, then exit — WITHOUT showing a "
            "window. The two are near-duplicates maintained by hand; this is what says "
            "so when one of them changes and the other does not."
        );

    p
        .add_argument("--screenshot")
        .help(
            "With --editor, write the shell's first painted frame to this PNG and exit. The window "
            "grabs itself, so nothing floating above it ends up in the picture."
        );

    p
        .add_argument("--hwencode")
        .flag()
        .help("Encode with the hardware H.264 encoder (h264_videotoolbox) instead of libx264. Faster and lighter on CPU, but quality/bitrate behavior differs from CRF.");

    p
        .add_argument("--from")
        .help(
            "With --generate, render from this point: seconds (\"12.5\") or the name of a "
            "timestamp() in the scene. Sounds keep their place — one that began earlier is "
            "cut, not moved. Clamped to the scene."
        );

    p
        .add_argument("--to")
        .help("With --generate, stop at this point — seconds or a timestamp() name. Clamped to the scene.");

    p
        .add_argument("--for")
        .help(
            "With --generate, render the scene once per named shape — youtube (1920x1080), "
            "tiktok (1080x1920), square (1080x1080) — writing one file per shape, its name in "
            "the filename. Each one RE-RUNS the scene in that frame, so the scene lays itself "
            "out for it (Split.AUTO, W/H, TOP_SIDE); nothing is cropped or scaled. With --lint, "
            "check the scene in each of them instead."
        );

    p
        .add_argument("--set")
        .append()
        .default_value(std::vector<std::string>{})
        .help(
            "Give the scene's param(\"key\", default) a value: --set name=Ada --set score=12. Read as the "
            "default's type (a number, true/false, a colour \"#ff8800\"). A key no param() reads is refused — "
            "a typo would render the default. Works with --generate, --lint and --editor."
        );

    p
        .add_argument("--data")
        .help(
            "With --generate, render the scene once per row of this .csv (a header line, then rows) or .json "
            "(a list of objects), each column a param(). Name the files from the rows: --generate \"out/{name}.mp4\"; "
            "without a {column} they are numbered. An empty cell leaves the param() its default."
        );

    p
        .add_argument("--sheet")
        .scan<'i', int>()
        .help(
            "With an image --generate, lay this many moments side by side in the one file, "
            "evenly spaced from --from to --to and each labelled with its time. One look shows the motion."
        );

    p
        .add_argument("--at")
        .help(
            "With --generate to an image, the exact moments the sheet shows — seconds or timestamp() names, "
            "comma-separated: \"0,3.9,the camera\". An even spread is right when nothing says where to look; "
            "a scene that named its moments has already said, and spreading evenly spends tiles on stillness. "
            "Overrides --sheet, which then only says a sheet is wanted."
        );
}

namespace
{
    // ── ^C has to work ────────────────────────────────────────────────────
    // A Qt application run from a terminal ignored SIGINT entirely: Control-C
    // printed nothing, the window stayed, the shell never got its prompt back,
    // and the only way out was to hunt the pid. Worse, the signal did reach the
    // language server child — killing it — so the editor announced that pyright
    // "could not be started" and then carried on without it.
    //
    // A signal handler may not touch Qt: it interrupts the process anywhere,
    // including inside the event loop's own bookkeeping. So it does the one
    // thing POSIX promises is safe — a byte down a pipe — and a notifier turns
    // that byte into an ordinary quit on the event loop's own thread, which runs
    // every destructor and takes the child processes with it.
    int signalPipe[2] = {-1, -1};

    void onSignal(int)
    {
        const char                     byte = 1;
        [[maybe_unused]] const ssize_t written = ::write(signalPipe[1], &byte, 1);
    }

    void quitOnSignal(QCoreApplication &app)
    {
        if (::socketpair(AF_UNIX, SOCK_STREAM, 0, signalPipe) != 0)
            return;

        auto *notifier = new QSocketNotifier(signalPipe[0], QSocketNotifier::Read, &app);
        QObject::connect(notifier, &QSocketNotifier::activated, &app, [&app, notifier] {
            notifier->setEnabled(false);
            char                           byte = 0;
            [[maybe_unused]] const ssize_t read = ::read(signalPipe[0], &byte, 1);
            app.quit();
        });

        std::signal(SIGINT, onSignal);
        std::signal(SIGTERM, onSignal);
    }
} // namespace

// Everything main does once the arguments are understood, so that one
// try/catch can stand in front of all of it. A scene that names a file it
// does not have throws from deep in the render, and with nothing catching
// it the process aborted: `libc++abi: terminating due to uncaught exception`
// in front of a message that was actually useful.
static int run(argparse::ArgumentParser &parser, int argc, char *argv[])
{
    // The scene as the editor's timeline reads it. `videocode/serialize.py`'s own
    // __main__ prints the baked stack instead — one entry per input per frame,
    // seventeen thousand lines for a scene of two shapes — which nothing can
    // read. This is the model the timeline is drawn from, and it is small.
    const bool lint = parser.get<bool>("--lint");
    if (lint || parser.get<bool>("--inspect")) {
        const std::string path = parser.get<std::string>("--file");
        std::ifstream     in(path);
        if (!in) {
            std::cerr << (lint ? "--lint" : "--inspect") << ": cannot read " << path << "\n";
            return EXIT_FAILURE;
        }
        const std::string source((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
        if (lint) {
            // The frames to check the scene in: each --for shape, as the renders
            // would re-run it, or the --width/--height one. Title safe is a
            // question about a frame, and a 16:9 answer says nothing of 9:16.
            std::vector<std::tuple<std::string, int, int>> shapes;
            for (const VC::NamedShape &shape : VC::shapesFor(parser))
                shapes.emplace_back(shape.name, (int)shape.width, (int)shape.height);
            if (shapes.empty())
                shapes.emplace_back("", (int)parser.get<float>("--width"), (int)parser.get<float>("--height"));
            const py::tuple said = py::module::import("videocode.serialize")
                                       .attr("lintSource")(source, path, parser.get<std::vector<std::string>>("--set"), parser.present("--data").value_or(""), shapes)
                                       .cast<py::tuple>();
            std::cout << said[0].cast<std::string>() << std::flush;
            return said[1].cast<int>();
        }
        const py::dict result = py::module::import("videocode.serialize")
                                    .attr("execSource")(source, path)
                                    .cast<py::dict>();
        if (!result["ok"].cast<bool>()) {
            std::cerr << path << ":" << result["line"].cast<int>() + 1 << ": "
                      << result["message"].cast<std::string>() << "\n";
            return EXIT_FAILURE;
        }
        std::cout << result["scene"].cast<std::string>() << "\n";
        return EXIT_SUCCESS;
    }

    // Visual regression suite (headless — no window, no Qt event loop)
    if (parser.get<bool>("--visual-test")) {
        VC::VisualTest visualTest(parser);
        return visualTest.run(parser.get<bool>("--update-golden"));
    }

    // --for writes files, and without --generate there is none to write. A
    // flag accepted and then dropped is the failure this repo keeps finding.
    if (parser.is_used("--for") && !parser.is_used("--generate")) {
        std::cerr << "video-code: --for writes one file per shape, so it needs --generate.\n";
        return EXIT_FAILURE;
    }
    if (parser.is_used("--data") && !parser.is_used("--generate")) {
        std::cerr << "video-code: --data writes one file per row, so it needs --generate (or --lint, to check the rows).\n";
        return EXIT_FAILURE;
    }

    // Generate the video (headless — no window, no Qt event loop)
    if (parser.is_used("--generate")) {
        // One Config per shape. Each render runs the scene AGAIN inside its own
        // frame — the world box is process-global, so it is pointed at this
        // shape before Core executes the script, and the scene lays itself out
        // against the W/H it finds. That is what makes 9x16 a re-layout rather
        // than a crop of the 16x9 render.
        const std::vector<Config> configs = VC::makeConfigs(parser);
        for (const Config &config : configs) {
            VC::applyScreenSize(config.screenWidth, config.screenHeight);
            VC::applyParams(config);

            VC::Compiler compiler(parser, config);
            if (const int status = compiler.generateVideo(); status != EXIT_SUCCESS) {
                // Stopping, and saying what was not made: carrying on would
                // repeat the same failure once per shape or row, and finishing
                // quietly would leave a set of files that looks complete and is not.
                if (&config != &configs.back())
                    std::cerr << std::format("video-code: {} failed, so the {} renders after it were not made.\n", config.shapeNote, &configs.back() - &config);
                return status;
            }
        }
        if (parser.is_used("--data"))
            std::cerr << py::module_::import("videocode.params").attr("unreadColumns")().cast<std::string>();
        return EXIT_SUCCESS;
    }

    // The editing shell. The scene graph's backend has to be settled before any
    // QQuickWindow exists, which means before the QApplication.
    const bool checksChrome = parser.get<bool>("--check-chrome");
    const bool wantsEditor = parser.get<bool>("--editor") || checksChrome;
    if (wantsEditor)
        VC::Editor::configureGraphicsApi();

    // What macOS puts in the Dock, the app menu and the ⌘-Tab switcher. Without
    // it the name is the executable's, which is a filename — lower case, hyphen
    // and all — rather than the product's.
    QCoreApplication::setApplicationName(QStringLiteral("Video-Code"));
    QGuiApplication::setApplicationDisplayName(QStringLiteral("Video-Code"));

#if defined(__linux__)
    // The preview draws into an X window (VulkanWidget: xcb surface only). A
    // system Qt — Arch's — also ships the Wayland plugin and picks it in a
    // Wayland session, and the preview then has no surface at all. XWayland is
    // there whenever DISPLAY is, so the X plugin is asked for, unless someone
    // already chose a platform.
    if (qEnvironmentVariableIsEmpty("QT_QPA_PLATFORM") && !qEnvironmentVariableIsEmpty("WAYLAND_DISPLAY") && !qEnvironmentVariableIsEmpty("DISPLAY"))
        qputenv("QT_QPA_PLATFORM", "xcb");
#endif

#ifdef __APPLE__
    // The Dock tile, the ⌘-Tab entry and the name beside the Apple come from
    // the bundle a process was launched from, and a bare executable has none:
    // macOS drew the generic "exec" tile whatever setWindowIcon() was given.
    // Video-Code.app, beside the binary, is that bundle; its executable is a
    // link back to this file, so going through it changes what the system
    // calls the process and nothing else. Only for a run that shows a window.
    if (!checksChrome && !parser.get<bool>("--check-widget")) {
        char       self[4096];
        uint32_t   size = sizeof self;
        const auto bundled = VC::executableDir() / "Video-Code.app" / "Contents" / "MacOS" / "video-code";
        if (_NSGetExecutablePath(self, &size) == 0 && std::string_view(self).find(".app/Contents/MacOS/") == std::string_view::npos && std::filesystem::exists(bundled))
            execv(bundled.c_str(), argv);
    }
#endif

    QApplication app(argc, argv);
    quitOnSignal(app);
    // The Dock tile and ⌘-Tab on macOS, the window and taskbar icon elsewhere.
    app.setWindowIcon(QIcon(QString::fromStdString(VC::resourceDir(SHADER_DIR, "assets/shaders") + "/../logo/icon.png")));

    // Needs a QApplication (a QWidget cannot exist without one) and nothing
    // else — no event loop, no editor chrome, and no window on the desktop.
    if (parser.get<bool>("--check-widget")) {
        VC::VisualTest visualTest(parser);
        return visualTest.checkWidget();
    }

    if (wantsEditor) {
        // `--file` names the scene here too. It used to be read by the renderer
        // alone, so `--editor --file x.py` opened whatever the working directory
        // happened to hold and said nothing about it — a flag accepted and then
        // dropped. Typed now, it outranks an exported VC_SCENE_FILE, the way a
        // flag on the line always outranks the environment it inherited.
        if (parser.is_used("--file"))
            qputenv("VC_SCENE_FILE", QByteArray::fromStdString(parser.get<std::string>("--file")));

        // The frame the editor makes the scene in, from --width/--height like a
        // render's: a 1080x1920 scene is previewed as one, and exported as one.
        VC::makeConfig(parser);

        // --set previews one set of values — a row of the batch, say — in the
        // editor, and reaches the export it launches through the environment.
        if (parser.is_used("--set"))
            VC::applyParams(VC::makeConfigs(parser).front());

        VC::Editor editor;
        editor.setHeadless(checksChrome);
        if (!editor.load())
            return EXIT_FAILURE;
        if (checksChrome) {
            // `load()` already said whether every QML file parsed and every
            // binding resolved — which is the whole question when there is no
            // picture to take.
            std::cout << "chrome loaded\n";
            if (parser.get<bool>("--serve")) {
                // Kept alive, windowless, answering `tell` — the editor a test
                // or an agent drives without touching the desktop.
                editor.serve();
                return app.exec();
            }
            if (!parser.is_used("--screenshot"))
                return EXIT_SUCCESS;

            // With one, the loop has to turn first. The chrome runs the scene
            // through `Qt.callLater`, so a capture taken before any event is
            // delivered photographs an empty timeline and an unpainted preview —
            // a picture of the chrome having done nothing yet.
            const QString shot = QString::fromStdString(parser.get<std::string>("--screenshot"));
            const int     settle = qEnvironmentVariableIntValue("VC_SETTLE") > 0
                                       ? qEnvironmentVariableIntValue("VC_SETTLE")
                                       : 1500;
            // The picture is taken after the last thing the probe schedules,
            // never at a fixed moment: a key list is spaced 700 ms apart and
            // outlives the settle, so the shutter used to close on a window
            // that had received only the first key — and the run reported
            // nothing wrong with that.
            const int lastProbe = editor.probeClicks(settle);
            QTimer::singleShot(std::max(settle, lastProbe + 300), &editor, [&editor, shot] {
                editor.captureHidden(shot);
                QCoreApplication::quit();
            });
            return app.exec();
        }
        if (parser.is_used("--screenshot"))
            editor.captureTo(QString::fromStdString(parser.get<std::string>("--screenshot")));
        editor.serve();
        return app.exec();
    }

    // Preview the video
    VC::Window window(parser);
    return app.exec();
}

int main(int argc, char *argv[])
{
    // Line by line, because something is reading this while it is still being
    // written. `--serve` is driven by a test that starts the editor, keeps it
    // alive and reads its stdout for the answer to each probe. Redirected to a
    // file, stdout is fully buffered on glibc, so the answer sat in a 4 KB
    // buffer until the process exited and the reader saw an empty file —
    // Linux only, since macOS flushed it. Cheap: this stream carries a handful
    // of lines a run.
    std::setvbuf(stdout, nullptr, _IOLBF, 0);

    // Initialize the Python interpreter once for the whole process.
    // false = don't override Qt's signal handlers.
    // A shipped folder carries its own Python — `python/` beside the
    // executable — and the interpreter is pointed at it before it starts.
    // Without this the embedded libpython looks for the stdlib where the
    // build machine kept it, and a copy on another Mac dies on its first line.
    const auto exeDir = VC::executableDir();
    if (std::filesystem::is_directory(exeDir / "python" / "lib") && !std::getenv("PYTHONHOME"))
        setenv("PYTHONHOME", (exeDir / "python").c_str(), 1);

    py::scoped_interpreter guard{false};
    // The library beside the executable, then the working directory: a scene
    // imports `videocode` from wherever the binary was unpacked, and a
    // checkout keeps finding its own.
    std::string beside = exeDir.string();
    for (auto at = beside.find('\''); at != std::string::npos; at = beside.find('\'', at + 2))
        beside.insert(at, "\\");
    py::exec("import sys; sys.path.insert(0, ''); sys.path.insert(1, '" + beside + "')");
    // An activated virtualenv is where `pip install -r requirements.txt` put
    // what a scene imports — on Arch it is the only place pip may write. But an
    // embedded interpreter takes its prefix from this binary, not from the
    // `python3` on PATH, so it never sees the venv on its own: every scene died
    // on `No module named 'typing_extensions'`. addsitedir, not a bare path
    // insert, so the venv's .pth files are honoured too.
    if (const char *venv = std::getenv("VIRTUAL_ENV")) {
        py::dict scope;
        scope["venv"] = venv;
        py::exec(
            "import site, sys\n"
            "site.addsitedir(f'{venv}/lib/python{sys.version_info[0]}.{sys.version_info[1]}/site-packages')",
            py::globals(), scope
        );
    }

    // Suppress the spurious Qt/macOS fullscreen position warning
    // Message: "qt.qpa.window: Window position QRect(-1,0 1470x826) outside any known screen, using primary screen"
    qInstallMessageHandler([](QtMsgType type, const QMessageLogContext &, const QString &msg) {
        if (type == QtWarningMsg && msg.contains("outside any known screen"))
            return;
        fprintf(stderr, "%s\n", msg.toLocal8Bit().constData());
    });

    // Hide OpenCV logs
    cv::utils::logging::setLogLevel(cv::utils::logging::LOG_LEVEL_SILENT);

    // `tell` talks to a running editor and is not a render option: answered
    // before the parser, which would otherwise refuse the word.
    if (argc >= 3 && std::strcmp(argv[1], "tell") == 0)
        return tell(argc, argv);

    // Parse the arguments
    argparse::ArgumentParser parser(
        "./videocode",
        "A video editing software made by Marius Rousset and Hippolyte Lefer.",
        argparse::default_arguments::help
    );
    setParserArgument(parser);
    try {
        parser.parse_args(argc, argv);
    } catch (const std::exception &e) {
        std::cerr << e.what() << std::endl;
        return EXIT_FAILURE;
    }

    try {
        return run(parser, argc, argv);
    } catch (const std::exception &e) {
        // The message the throw carried, and nothing else: a person reading
        // it wants the file they got wrong, not the runtime's opinion of it.
        std::cerr << "video-code: " << e.what() << std::endl;
        return EXIT_FAILURE;
    }
}

// binding python / cpp

// boucle sens prediction video martin baldinger
