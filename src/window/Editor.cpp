/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** Editor
*/

#include "window/Editor.hpp"

#ifdef VC_HAS_QPA_FOCUS
    #include <QtGui/qpa/qwindowsysteminterface.h>
#endif
#include <QtQml/qqml.h>
#include <pybind11/embed.h>
#include <unistd.h>

#include <QColorDialog>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileDialog>
#include <QFileInfo>
#include <QGuiApplication>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QKeyEvent>
#include <QLocalSocket>
#include <QMenu>
#include <QMouseEvent>
#include <QQmlContext>
#include <QQmlExpression>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QRegularExpression>
#include <QSGRendererInterface>
#include <QStandardPaths>
#include <QTextCursor>
#include <QTimer>
#include <QUrl>
#include <QUrlQuery>
#include <chrono>
#include <format>
#include <iostream>

#include "agent/AgentSession.hpp"
#include "compiler/AudioMix.hpp"
#include "input/Metadata.hpp"
#include "lsp/LanguageServer.hpp"
#include "utils/ImageIO.hpp"
#include "utils/Logger.hpp"
#include "utils/Paths.hpp"

namespace py = pybind11;
#include "window/MacApplication.hpp"
#include "window/PreviewItem.hpp"
#include "window/PythonHighlighter.hpp"
#include "window/ThumbProvider.hpp"

#ifndef QML_DIR
// Set by CMake to <source>/qml.  The fallback keeps a hand-rolled build
// compiling; it just will not find the chrome.
    #define QML_DIR "qml"
#endif

VC::Editor::~Editor()
{
}

VC::Editor::Editor(QObject* parent)
    : QObject(parent)
{
    // Controls default to the native macOS style, which would fight a chrome that
    // paints every surface itself — and would look different on Linux.  Basic
    // draws almost nothing on its own, which is exactly what we want under our
    // own Theme, and it keeps the window reproducible across machines.
    QQuickStyle::setStyle("Basic");

    // The chrome asks the shell for the one thing QML cannot do on its own:
    // read and write the saved dock layout.
    _engine.rootContext()->setContextProperty("Shell", this);

    // On the application, not on the window: a key event is delivered to
    // whatever holds the focus — a text field, a list, a menu — and the side a
    // modifier is on has to be known wherever it lands.
    if (qApp != nullptr)
        qApp->installEventFilter(this);

    // What the code pane asks about Python. Owned by the shell so it outlives a
    // chrome reload — a language server is slow to start and has nothing to do
    // with how the window is drawn.
    _engine.rootContext()->setContextProperty("Lsp", &_language);

    // Claude Code, for the Agent pane. Same arrangement as the language server
    // and for the same reason — a conversation outlives a chrome reload.
    _engine.rootContext()->setContextProperty("Agent", &_agent);

    // The preview pane. A C++ item rather than an Image, because a frame is
    // produced on demand by a Vulkan device that lives here, and there is no URL
    // to give it.
    //
    // Its own URI, not "VideoCode": that module is a directory with a qmldir
    // listing three singletons, and importing it by name replaces the implicit
    // directory import the chrome relies on — every sibling `.qml` type then
    // stops resolving.
    qmlRegisterType<PreviewItem>("VideoCode.Engine", 1, 0, "PreviewItem");

    // The module lives in qml/VideoCode, so qml/ is what has to be importable
    // for `import VideoCode` (and for the Theme singleton its qmldir declares).
    // The bin's pictures come through here rather than off disk as files: no
    // temporary images to write, no format to encode, and Qt caches what it has
    // already drawn.  The engine takes ownership.
    _engine.addImageProvider(QStringLiteral("thumb"), new ThumbProvider);

    _engine.addImportPath(qmlDirectory());
    _mainFile = QDir(qmlDirectory()).filePath("VideoCode/Main.qml");

    buildMenuBar();

    watchQmlFiles();
    // `path` is only read by the log, which VC_SLOG compiles out of a quiet build.
    connect(&_watcher, &QFileSystemWatcher::fileChanged, this, [this]([[maybe_unused]] const QString& path) {
        VC_SLOG(std::format("[editor] {} changed — reloading chrome\n", path.toStdString()));
        // A save that goes through a temporary file drops the watch, so it has
        // to be re-armed on every change.  Doing it on the next tick lets the
        // editor finish writing before we read.
        QTimer::singleShot(30, this, [this] {
            watchQmlFiles();
            reload();
        });
    });
}

void VC::Editor::buildMenuBar()
{
    _menuBar = std::make_unique<QMenuBar>(nullptr);

    // The menu has to hang somewhere for Qt to see it, but macOS relocates an
    // action carrying PreferencesRole into the application menu and leaves this
    // one empty — so it is never shown, and never named anything a user reads.
    QMenu* application = _menuBar->addMenu(QStringLiteral("Video-Code"));

    auto* settings = application->addAction(QStringLiteral("Settings…"));
    settings->setMenuRole(QAction::PreferencesRole);
    settings->setShortcut(QKeySequence::Preferences);
    connect(settings, &QAction::triggered, this, &Editor::settingsRequested);

    // Opening something is the first thing a person looks for, and macOS puts
    // File immediately after the application menu — so it is declared first and,
    // being filled here rather than from QML, it is also populated first, which
    // is what actually decides the order (see below).
    QMenu* file = _menuBar->addMenu(QStringLiteral("File"));

    // Filled on the first tick of the event loop, not here.
    //
    // Qt's Cocoa bridge inserts a menu into the native bar when its contents
    // CHANGE, and a menu whose every action was added while the bar was being
    // built never changes afterwards — so it is never inserted and the title
    // does not appear at all. Every other menu here is filled from QML after
    // startup, which is why they were visible and this one alone was missing.
    QTimer::singleShot(0, this, [this, file] { fillFileMenu(file); });

    // ── The order of the menus IS the order they are added in ──────────────
    // The dock, its theme, its keys, then the guide: what you ARRANGE, then how
    // it LOOKS and ANSWERS, then what you READ. The application menu is not part
    // of this — macOS always keeps it leftmost, whatever we do.
    //
    // Each its own menu, and no submenu deeper than one: Qt's Cocoa bridge never
    // attaches a submenu nested inside another submenu, so when these lived under
    // System › Dock display, Layout, Docks and Load display were empty items to
    // macOS — and ⌘1..4, which live in Layout, were keys it had never heard of.

    // Named for what it holds rather than borrowed from every other application:
    // everything in here is about the dock — which arrangement, which panes,
    // back to the start.  "View" would also collide with the ⋯ menu's Display,
    // which is about one panel rather than the whole window.
    //
    // A panel dragged somewhere silly or closed by accident has to be
    // recoverable from a place that does not depend on finding that panel again
    // — which the dock's own ⋯ menu does.
    QMenu* view = _menuBar->addMenu(QStringLiteral("Dock"));

    // Layout first: which arrangement you are in decides where everything else
    // is, so it reads before the list of what is in it.
    _templatesMenu = view->addMenu(QStringLiteral("Layout"));
    view->addSeparator();
    _docksMenu = view->addMenu(QStringLiteral("Docks"));

    view->addSeparator();

    // What the arrangement you are looking at actually IS, in numbers. Beside
    // the two ways of keeping it, because you measure a display for the same
    // reason you save one: you are deciding whether it is the one you want.
    auto* measure = view->addAction(QStringLiteral("Show proportions"));
    connect(measure, &QAction::triggered, this, &Editor::dockMeasureRequested);

    view->addSeparator();

    // Keeping what you are looking at, two ways round: under the name it already
    // has, or under a new one.  The first is what you want nine times out of ten
    // — you dragged the display you were in into better shape — so it goes
    // first and costs no typing.
    auto* update = view->addAction(QStringLiteral("Update default"));
    connect(update, &QAction::triggered, this, &Editor::dockDefaultRequested);

    auto* save = view->addAction(QStringLiteral("Save display…"));
    connect(save, &QAction::triggered, this, &Editor::dockSaveRequested);

    _displaysMenu = view->addMenu(QStringLiteral("Load display"));

    view->addSeparator();
    auto* reset = view->addAction(QStringLiteral("Reset UI"));
    connect(reset, &QAction::triggered, this, &Editor::dockResetRequested);

    QMenu* theme = _menuBar->addMenu(QStringLiteral("Theme"));
    _codeThemesMenu = theme->addMenu(QStringLiteral("Code theme"));

    // "Show Colors" rather than "Colors…": the ellipsis is the macOS way of
    // saying a window follows, but the verb says it in a word instead of in a
    // convention, and it is the name the system gives its own colour panel —
    // with the same key.
    auto* colors = theme->addAction(QStringLiteral("Show Colors"));
    colors->setShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+C")));
    connect(colors, &QAction::triggered, this, &Editor::colorsRequested);

    // Settings is NOT repeated in any of these.  Qt recognises the title and
    // macOS moves any such item into the application menu next to About and
    // Quit, which is where a Mac user looks for it — a second one would either
    // vanish or, if renamed to escape the rule, sit in the wrong place on purpose.

    // Every key the application answers to, and where you change them.  ⌘/
    // because that is where the rest of the world put it, and because a list of
    // shortcuts that itself needs a shortcut nobody knows is a list nobody reads.
    QMenu* keyboard = _menuBar->addMenu(QStringLiteral("Keys"));
    auto*  keys = keyboard->addAction(QStringLiteral("Keyboard Shortcuts"));
    keys->setShortcut(QKeySequence(QStringLiteral("Ctrl+/")));
    connect(keys, &QAction::triggered, this, &Editor::shortcutsRequested);

    // Guide is kept and left empty on purpose. It is where what the chrome
    // MEANS will go — the legend moved to Keys because it became something
    // you change rather than something you read. macOS greys the title of a
    // menu with nothing in it, which is the honest picture: the place exists,
    // it holds nothing yet.
    _menuBar->addMenu(QStringLiteral("Guide"));

    // The menu bar Cocoa draws does not exist yet — Qt hands it over later, when
    // the window first becomes active. So the name is offered until it is taken,
    // and the timer stops itself the moment it is.
    auto* naming = new QTimer(this);
    naming->setInterval(200);
    connect(naming, &QTimer::timeout, this, [naming] {
        if (nameApplication(QStringLiteral("Video-Code")))
            naming->stop();
    });
    naming->start();
}

void VC::Editor::setDockDisplays(const QVariantList& displays)
{
    if (!_displaysMenu)
        return;

    _displaysMenu->clear();

    if (displays.isEmpty()) {
        // An empty submenu is a dead end you can still open. Say why it is empty.
        auto* nothing = _displaysMenu->addAction(QStringLiteral("Nothing saved yet"));
        nothing->setEnabled(false);
        return;
    }

    for (const QVariant& entry : displays) {
        const QString name = entry.toMap().value(QStringLiteral("name")).toString();
        auto*         open = _displaysMenu->addAction(name);
        connect(open, &QAction::triggered, this, [this, name] { Q_EMIT dockDisplayChosen(name); });
    }
}

void VC::Editor::setCodeThemes(const QVariantList& themes)
{
    if (!_codeThemesMenu)
        return;

    _codeThemesMenu->clear();

    for (const QVariant& entry : themes) {
        const QVariantMap theme = entry.toMap();
        const QString     key = theme.value(QStringLiteral("key")).toString();

        auto* action = _codeThemesMenu->addAction(theme.value(QStringLiteral("label")).toString());
        action->setCheckable(true);
        action->setChecked(theme.value(QStringLiteral("current")).toBool());

        connect(action, &QAction::triggered, this, [this, key] { Q_EMIT codeThemeChosen(key); });
    }
}

void VC::Editor::setDockTemplates(const QVariantList& templates)
{
    if (!_templatesMenu)
        return;

    _templatesMenu->clear();

    // Numbered ⌘1, ⌘2, ⌘3 in the order they are declared: switching arrangement
    // is a thing you do mid-thought, and a menu you have to open for it is a
    // menu you stop using.  Qt's portable "Ctrl" is ⌘ on macOS.
    int number = 1;

    for (const QVariant& entry : templates) {
        const QVariantMap arrangement = entry.toMap();
        const QString     key = arrangement.value(QStringLiteral("key")).toString();

        auto* action = _templatesMenu->addAction(arrangement.value(QStringLiteral("label")).toString());
        action->setCheckable(true);
        action->setChecked(arrangement.value(QStringLiteral("current")).toBool());
        if (number <= 9)
            action->setShortcut(QKeySequence(QStringLiteral("Ctrl+%1").arg(number)));
        ++number;

        connect(action, &QAction::triggered, this, [this, key] { Q_EMIT dockTemplateChosen(key); });
    }
}

void VC::Editor::setDockPanels(const QVariantList& panels)
{
    if (!_docksMenu)
        return;

    // Rebuilt rather than reconciled: five items cost nothing to recreate, and
    // a menu that is rebuilt cannot drift out of step with the dock.
    _docksMenu->clear();

    for (const QVariant& entry : panels) {
        const QVariantMap panel = entry.toMap();
        const QString     key = panel.value(QStringLiteral("key")).toString();

        auto* action = _docksMenu->addAction(panel.value(QStringLiteral("label")).toString());
        action->setCheckable(true);
        action->setChecked(panel.value(QStringLiteral("shown")).toBool());
        connect(action, &QAction::triggered, this, [this, key] { Q_EMIT dockPanelToggled(key); });
    }
}

void VC::Editor::configureGraphicsApi()
{
    // Leave the platform default alone unless asked otherwise. On macOS that is
    // Metal, which is the only one of the two that renders this chrome without
    // stalling the GUI thread for seconds at a time — see the header for the
    // measurements. An explicit QSG_RHI_BACKEND wins, which is how the Vulkan
    // path stays testable.
    if (!qEnvironmentVariableIsEmpty("QSG_RHI_BACKEND"))
        return;

#if !QT_CONFIG(vulkan)
    // Nothing to do, but worth saying out loud: without Qt's Vulkan support the
    // renderer and the chrome can never share a device, whatever we measure.
    VC_SLOG("[editor] this Qt has no Vulkan support; Quick uses the platform default\n");
#elif defined(__linux__)
    // Linux's default is OpenGL, and on an NVIDIA card under XWayland there is
    // no GLX context to be had: the chrome aborted before its first frame. The
    // preview already needs Vulkan, so the chrome asks for it too.
    qputenv("QSG_RHI_BACKEND", "vulkan");
#endif
}

bool VC::Editor::load()
{
    _engine.load(QUrl::fromLocalFile(_mainFile));
    if (_engine.rootObjects().isEmpty()) {
        std::cerr << std::format("Failed to load the editor chrome from {}\n", _mainFile.toStdString());
        return false;
    }
    return true;
}

void VC::Editor::captureHidden(const QString& path)
{
    const auto roots = _engine.rootObjects();
    if (roots.isEmpty())
        return;

    auto* window = qobject_cast<QQuickWindow*>(roots.first());
    if (window == nullptr) {
        std::cerr << "no window object\n";
        return;
    }

    // Rendering and DISPLAYING are two different things, and only the second
    // one lands on a desktop. The scene graph draws into a buffer whether or not
    // the compositor was ever asked to map the window — so a picture of the
    // chrome costs nothing but the draw, and interrupts nobody.
    //
    // (`QQuickRenderControl` is the documented way to render QML with no window
    // at all. It is not needed here: measured, `grabWindow()` on a window that
    // was created and never shown returns a full 2880x1800 frame.)
    // Twice, and the first one thrown away. A Canvas paints on a POLISH and
    // shows on the frame after it, so anything drawn that way and created since
    // the last frame — an effect row's easing curve, on a card opened by the
    // probe itself — is simply missing from a single grab. The hidden window
    // renders on nothing but these calls, so the throwaway is the only polish
    // those items will ever get.
    window->grabWindow();
    const QImage frame = window->grabWindow();
    if (frame.isNull()) {
        std::cerr << "grabWindow() returned nothing on the unshown window.\n";
        return;
    }

    // Same road as every other picture this project writes: Qt here is built
    // without PNG, so the frame goes out through OpenCV.
    const QImage  argb = frame.convertToFormat(QImage::Format_ARGB32);
    const cv::Mat bgra(
        argb.height(), argb.width(), CV_8UC4,
        const_cast<uchar*>(argb.bits()), argb.bytesPerLine()
    );
    if (VC::ImageIO::write(path.toStdString(), bgra))
        std::cout << std::format("chrome captured ({}x{}) → {}\n", argb.width(), argb.height(), path.toStdString());
    else
        std::cerr << std::format("Could not write {}\n", path.toStdString());
}

void VC::Editor::captureTo(const QString& path)
{
    const auto roots = _engine.rootObjects();
    if (roots.isEmpty())
        return;

    auto* window = qobject_cast<QQuickWindow*>(roots.first());
    if (!window) {
        std::cerr << "The chrome's root object is not a window, so there is nothing to grab.\n";
        return;
    }

    // frameSwapped fires once the scene graph has actually presented, which is
    // the earliest moment a grab returns the finished picture rather than a
    // half-built one.  Fonts load asynchronously, so we let a couple of frames
    // go by before reading back.
    connect(window, &QQuickWindow::frameSwapped, this, [this, window, path] {
        if (_captured)
            return;
        _captured = true;

        // VC_SHOT_DELAY lets a script drive the window — click something, switch
        // layout — before the picture is taken, which is how the chrome's input
        // handling gets verified without a human at the mouse.
        const int delay = qEnvironmentVariableIntValue("VC_SHOT_DELAY") > 0
                              ? qEnvironmentVariableIntValue("VC_SHOT_DELAY")
                              : 400;

        const int lastProbe = probeClicks(delay);

        // VC_HOVER="x,y" — the pointer coming to REST somewhere, which is a
        // third kind of input entirely: hovers, tooltips and the language
        // server's replies only happen when nothing is clicked at all. Sent
        // twice a few hundred milliseconds apart because a single move tells
        // the pane nothing has settled yet.
        const QStringList hovered = qEnvironmentVariable("VC_HOVER").split(',', Qt::SkipEmptyParts);
        if (hovered.size() == 2) {
            const QPointF at(hovered[0].toDouble(), hovered[1].toDouble());
            QTimer::singleShot(delay / 2, this, [this, at] { hoverAt(at); });
            QTimer::singleShot(delay / 2 + 120, this, [this, at] { hoverAt(at + QPointF(1, 0)); });
        }

        // VC_TYPE="text" — characters, sent as a person would send them. The
        // editor's intelligence only ever appears in response to typing, so
        // without this none of it can be checked without a human at the
        // keyboard. It runs after the clicks, which is what put the caret
        // somewhere worth typing.
        const QString typed = qEnvironmentVariable("VC_TYPE");
        for (int i = 0; i < typed.size(); ++i) {
            const QChar c = typed.at(i);
            QTimer::singleShot(delay / 2 + 400 + i * 90, this, [this, c] { typeCharacter(c); });
        }

        // VC_OPEN="/path/to/scene.py" — what File → Open Scene… ends with. The
        // panel itself is the system's and cannot be driven, so the probe skips
        // it and delivers the answer a person would have given.
        const QString opened = qEnvironmentVariable("VC_OPEN");
        if (!opened.isEmpty()) {
            QTimer::singleShot(delay / 2 - 400, this, [this, opened] {
                Q_EMIT sceneOpened(QFileInfo(opened).absoluteFilePath());
            });
        }

        // VC_RENDER="/tmp/frame.png" — build the scene and write one rendered
        // frame from inside the EDITOR process, where MoltenVK and Quick's
        // Metal have never coexisted before. The one thing worth proving before
        // any of this reaches a pane.
        const QString rendered = qEnvironmentVariable("VC_RENDER");
        if (!rendered.isEmpty()) {
            // After the keys: the scene has to have been executed first.
            QTimer::singleShot(delay / 2 + 2500, this, [this, rendered] {
                std::cout << "[preview] frames: " << sceneBuilt() << "\n";
                const QImage frame = renderFrame(0, 960, 540);
                std::cout << "[preview] image: " << frame.width() << "x" << frame.height() << "\n";
                if (!frame.isNull()) {
                    const QImage  argb = frame.convertToFormat(QImage::Format_ARGB32);
                    const cv::Mat bgra(argb.height(), argb.width(), CV_8UC4, const_cast<uchar*>(argb.bits()), argb.bytesPerLine());
                    std::cout << "[preview] written: "
                              << VC::ImageIO::write(rendered.toStdString(), bgra) << "\n";
                }
            });
        }

        // VC_DROP="/path/to/file.mp4" — what dropping a file from the Finder
        // ends with. The drag itself belongs to the window server and cannot be
        // synthesised, so the probe delivers its result.
        const QString dropped = qEnvironmentVariable("VC_DROP");
        if (!dropped.isEmpty()) {
            QTimer::singleShot(delay / 2 + 300, this, [this, dropped] {
                Q_EMIT mediaDropped(QFileInfo(dropped).absoluteFilePath());
            });
        }

        // VC_DRAG="x1,y1,x2,y2" — the same idea for the dock's one gesture, with
        // an optional fifth field "hold" that leaves the button down.
        const QStringList dragged = qEnvironmentVariable("VC_DRAG").split(',', Qt::SkipEmptyParts);
        if (dragged.size() == 4 || dragged.size() == 5) {
            const bool hold = dragged.size() == 5 && dragged[4].trimmed() == QStringLiteral("hold");
            QTimer::singleShot(delay / 2, this, [this, dragged, hold] {
                dragProbe(QPointF(dragged[0].toDouble(), dragged[1].toDouble()), QPointF(dragged[2].toDouble(), dragged[3].toDouble()), hold);
            });
        }

        QTimer::singleShot(std::max(delay, lastProbe + 300), this, [window, path] {
            const QImage frame = window->grabWindow();
            if (frame.isNull()) {
                std::cerr << "grabWindow() returned nothing — the scene graph refused the readback.\n";
            } else {
                // This Qt is built without PNG support (`png` is not among the
                // qtbase features), so QImage::save can only write bmp/ppm/xbm.
                // The project already writes images through OpenCV — the same
                // path the preview window's frame export uses — so the grab goes
                // out that way instead of rebuilding Qt for one encoder.
                const QImage  argb = frame.convertToFormat(QImage::Format_ARGB32);
                const cv::Mat bgra(
                    argb.height(), argb.width(), CV_8UC4,
                    const_cast<uchar*>(argb.bits()), argb.bytesPerLine()
                );
                if (VC::ImageIO::write(path.toStdString(), bgra))
                    std::cout << std::format(
                        "Captured the editor chrome ({}x{}) → {}\n",
                        argb.width(), argb.height(), path.toStdString()
                    );
                else
                    std::cerr << std::format("Could not write {}\n", path.toStdString());
            }
            QCoreApplication::quit();
        });
    });
}

QString VC::Editor::layoutPath()
{
    // VC_DOCK_FILE moves the saved layout somewhere else for the duration of a
    // run.  It exists because a scripted check that wants to see a particular
    // arrangement has to write one somewhere — and the obvious somewhere is the
    // file holding the arrangement a person is working in.  That file belongs to
    // them; a test has no business in it.
    const QString override = qEnvironmentVariable("VC_DOCK_FILE");
    if (!override.isEmpty()) {
        QDir().mkpath(QFileInfo(override).absolutePath());
        return override;
    }

    const QString dir = QStandardPaths::writableLocation(QStandardPaths::AppConfigLocation);
    QDir().mkpath(dir);

    // One arrangement PER PROJECT.  Two folders open at once shared a single
    // file and overwrote each other's dock, and the second window silently
    // inherited the first one's panes.  The name carries the folder so it can be
    // read by a person, and a hash of its full path so two folders called `demo`
    // are still two files.
    const QString    root = QDir::currentPath();
    const QByteArray digest =
        QCryptographicHash::hash(root.toUtf8(), QCryptographicHash::Sha1).toHex().left(8);
    const QString mine =
        QDir(dir).filePath(QStringLiteral("dock-%1-%2.json").arg(QFileInfo(root).fileName(), QString::fromUtf8(digest)));

    // A dock saved before this split is adopted once, rather than thrown away.
    const QString legacy = QDir(dir).filePath(QStringLiteral("dock.json"));
    if (!QFile::exists(mine) && QFile::exists(legacy))
        QFile::copy(legacy, mine);

    return mine;
}

bool VC::Editor::reducedMotion() const
{
    return prefersReducedMotion();
}

void VC::Editor::bringToFront() const
{
    VC::bringToFront();
}

void VC::Editor::saveLayout(const QString& json) const
{
    QFile file(layoutPath());
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        // A layout that cannot be saved is a nuisance, never a reason to lose
        // the window the user is working in.
        VC_SLOG(std::format("[editor] could not write {}\n", layoutPath().toStdString()));
        return;
    }
    file.write(json.toUtf8());
}

QString VC::Editor::loadLayout() const
{
    QFile file(layoutPath());
    if (!file.open(QIODevice::ReadOnly))
        return {};
    return QString::fromUtf8(file.readAll());
}

void VC::Editor::clearLayout() const
{
    QFile::remove(layoutPath());
}

QString VC::Editor::colorsPath()
{
    // VC_COLORS_FILE, for the reason VC_DOCK_FILE exists: a scripted run that
    // picks a colour must not repaint the person's own timeline.
    const QString override = qEnvironmentVariable("VC_COLORS_FILE");
    if (!override.isEmpty()) {
        QDir().mkpath(QFileInfo(override).absolutePath());
        return override;
    }

    const QString dir = QStandardPaths::writableLocation(QStandardPaths::AppConfigLocation);
    QDir().mkpath(dir);
    return QDir(dir).filePath(QStringLiteral("colors.json"));
}

void VC::Editor::saveColors(const QString& json) const
{
    QFile file(colorsPath());
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        VC_SLOG(std::format("[editor] could not write {}\n", colorsPath().toStdString()));
        return;
    }
    file.write(json.toUtf8());
}

QString VC::Editor::loadColors() const
{
    QFile file(colorsPath());
    if (!file.open(QIODevice::ReadOnly))
        return {};
    return QString::fromUtf8(file.readAll());
}

// The scene the pane should open on. VC_SCENE_FILE names it outright; otherwise
// the project's own scene, if it has an obvious one.
QString VC::Editor::editorScenePath()
{
    const QString named = qEnvironmentVariable("VC_SCENE_FILE");
    if (!named.isEmpty())
        return QFileInfo(named).absoluteFilePath();

    const QDir project(QDir::currentPath());
    // scene.py first: it is the scene this editor opens on, kept small on
    // purpose.  eg.py is the project's showcase — every feature at once, and
    // rendered by CI — which makes it the wrong thing to greet anyone with.
    for (const QString& candidate : {QStringLiteral("scene.py"), QStringLiteral("eg.py")}) {
        if (project.exists(candidate))
            return project.absoluteFilePath(candidate);
    }
    return {};
}

QString VC::Editor::scenePath() const
{
    return editorScenePath();
}

QString VC::Editor::projectRoot() const
{
    return QDir::currentPath();
}

QString VC::Editor::readTextFile(const QString& path) const
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly | QIODevice::Text))
        return {};
    return QString::fromUtf8(file.readAll());
}

bool VC::Editor::writable(const QString& path) const
{
    return !path.isEmpty() && QFileInfo(path).absoluteFilePath().startsWith(projectRoot() + "/");
}

bool VC::Editor::writeTextFile(const QString& path, const QString& text) const
{
    // Renaming a symbol edits every file that uses it, and most of those are
    // not open in the pane — the edit has to reach the disk or the rename is a
    // lie. Only files inside the project may be written: a language server will
    // happily return edits in site-packages, and this is the line where that
    // stops being our business.
    if (!writable(path)) {
        std::cerr << std::format("Refused to write outside the project: {}\n", path.toStdString());
        return false;
    }

    QFile file(path);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text))
        return false;
    return file.write(text.toUtf8()) >= 0;
}

void VC::Editor::applySemanticTokens(QQuickTextDocument* document, const QVariantList& spans)
{
    if (!document || !document->textDocument())
        return;

    if (auto* highlighter = document->textDocument()->findChild<PythonHighlighter*>())
        highlighter->setTokens(spans);
}

void VC::Editor::fillFileMenu(QMenu* file)
{
    auto* openScene = file->addAction(QStringLiteral("Open Scene…"));
    openScene->setShortcut(QKeySequence::Open);
    connect(openScene, &QAction::triggered, this, [this] {
        const QString chosen = pickScene(QString());
        if (!chosen.isEmpty())
            Q_EMIT sceneOpened(chosen);
    });

    // Export lives in File beside the two Opens, because that is where a person
    // looks for "make me the file" — not in a panel they have to find first.
    // No key of its own: ⌘E is one macOS already answers.
    auto* exportVideo = file->addAction(QStringLiteral("Export Video…"));
    connect(exportVideo, &QAction::triggered, this, [this] { Q_EMIT exportRequested(); });

    auto* openFolder = file->addAction(QStringLiteral("Open Folder…"));
    openFolder->setShortcut(QKeySequence(QStringLiteral("Ctrl+Shift+O")));
    connect(openFolder, &QAction::triggered, this, [this] {
        const QString folder = pickFolder();
        if (folder.isEmpty())
            return;
        // A folder is only useful once something in it is open, so the file
        // panel comes back rooted there rather than leaving an empty window.
        const QString chosen = pickScene(folder);
        if (!chosen.isEmpty())
            Q_EMIT folderOpened(folder, chosen);
    });
}

QVariantMap VC::Editor::executeScene(const QString& source, const QString& path)
{
    using Clock = std::chrono::high_resolution_clock;
    using Ms = std::chrono::duration<double, std::milli>;

    QVariantMap answer;
    const auto  started = Clock::now();

    try {
        py::gil_scoped_acquire hold;
        const py::module       serialize = py::module::import("videocode.serialize");
        const py::dict         result = serialize.attr("execSource")(
                                                     source.toStdString(), path.toStdString()
        )
                                            .cast<py::dict>();

        for (auto item : result)
            answer.insert(
                QString::fromStdString(py::str(item.first).cast<std::string>()),
                QString::fromStdString(py::str(item.second).cast<std::string>())
            );
        // Python's bools stringify as True/False; QML wants a bool.
        answer["ok"] = answer.value("ok").toString() == QLatin1String("True");
    } catch (const py::error_already_set& error) {
        // The scene never got as far as reporting for itself — an import that
        // fails, or the module missing entirely.
        answer["ok"] = false;
        answer["line"] = 0;
        answer["column"] = 0;
        answer["message"] = QString::fromUtf8(error.what()).section('\n', -2, -2).trimmed();
    }

    // A successful run leaves a populated `Context`; the engine reads it here,
    // in the same call, so the preview never has to ask whether the picture and
    // the timeline are looking at the same execution. A failure to build is not
    // a failure to run — the buffer executed, the report stands, and the pane
    // keeps whatever frame it had.
    if (answer.value("ok").toBool()) {
        try {
            answer["frames"] = sceneBuilt();
            bakeAudio();
        } catch (const std::exception& error) {
            VC_SLOG(std::format("[preview] scene not built: {}\n", error.what()));
        }
    }

    answer["ms"] = std::chrono::duration_cast<Ms>(Clock::now() - started).count();
    return answer;
}

int VC::Editor::frameWidth() const
{
    return static_cast<int>(config::screen.w());
}

int VC::Editor::frameHeight() const
{
    return static_cast<int>(config::screen.h());
}

int VC::Editor::sceneBuilt()
{
    if (!_scene) {
        _sceneConfig.sourceFile = editorScenePath().toStdString();
        _sceneConfig.framerate = Config::SCENE_FRAMERATE;
        // The mesh's NDC divisor reads the Config, not config::screen: left at
        // its default, every frame would be laid out as a 1920x1080 one.
        _sceneConfig.screenWidth = config::screen.w();
        _sceneConfig.screenHeight = config::screen.h();
        _scene = std::make_unique<Core>(_sceneConfig);
    }

    // The Python side has just run the buffer; this reads what it left.
    _scene->rebuildFromContext();
    return static_cast<int>(_scene->_nbFrame);
}

QImage VC::Editor::renderFrame(int index, int width, int height)
{
    if (!_scene || width <= 0 || height <= 0)
        return {};

    // The renderer is sized to the PANE, not to the output. A 1080p frame is a
    // 7680x4320 offscreen image at 4x SSAA and an 8 MB readback; the pane is a
    // fraction of that, and it is what you are looking at.
    if (!_renderer || _renderWidth != width || _renderHeight != height) {
        _renderer.reset();
        _renderer = std::make_unique<VulkanHeadlessRenderer>(
            static_cast<uint32_t>(width), static_cast<uint32_t>(height)
        );
        if (!_renderer->init()) {
            std::cerr << "[preview] the Vulkan renderer would not start\n";
            _renderer.reset();
            return {};
        }
        _renderWidth = width;
        _renderHeight = height;
        // The pane changed size — a layout switch, a splitter — and the clips'
        // textures lived in the renderer just thrown away: the preview went black.
        _scene->requeueTextures();
    }

    // Every frame, not only when the renderer is built.
    //
    // `executeStack` queues each freshly-constructed Image/Video for an upload
    // and clears the queue on the next rebuild; the only thing that ever
    // emptied it was the branch above, which runs once. So a clip built while
    // the renderer was already up — every hot reload that changes the set of
    // inputs rebuilds them all — kept a null descriptor and drew nothing, for
    // the rest of the session, with nothing said. Costs an empty loop when
    // there is nothing waiting, which is almost always.
    _scene->uploadTextures(
        [this](const cv::Mat& mat) { return _renderer->uploadTexture(mat); },
        [this](VkDescriptorSet desc, const cv::Mat& mat) { _renderer->updateTexturePixels(desc, mat); }
    );

    _scene->_index = static_cast<size_t>(std::max(0, index));
    _renderer->setMeshes(_scene->generateMeshes());
    _renderer->setBackgroundColor(_scene->_bgColor);

    // readFrame() answers with the PREVIOUS submission's pixels — it pipelines,
    // which is what makes a render loop fast and a single frame wrong. flush()
    // waits for the one just asked for.
    _renderer->readFrame();
    const cv::Mat frame = _renderer->flush();
    if (frame.empty())
        return {};

    // Deep copy: the Mat belongs to the renderer's readback buffer and is
    // overwritten by the next frame.
    return QImage(frame.data, frame.cols, frame.rows, static_cast<int>(frame.step), QImage::Format_ARGB32).copy();
}

bool VC::Editor::eventFilter(QObject* watched, QEvent* event)
{
    const QEvent::Type type = event->type();
    if (type == QEvent::KeyPress || type == QEvent::KeyRelease || type == QEvent::ShortcutOverride) {
        // The device-dependent bits of an NSEvent's modifierFlags, which Qt
        // passes through as nativeModifiers(). They are not in any public Qt
        // header — IOKit's <IOKit/hidsystem/IOLLEvent.h> names them
        // NX_DEVICELCMDKEYMASK and friends — so they are written here with the
        // names they carry there, once.
        constexpr quint32 deviceLeftControl = 0x00000001;
        constexpr quint32 deviceLeftShift = 0x00000002;
        constexpr quint32 deviceRightShift = 0x00000004;
        constexpr quint32 deviceLeftCommand = 0x00000008;
        constexpr quint32 deviceRightCommand = 0x00000010;
        constexpr quint32 deviceLeftOption = 0x00000020;
        constexpr quint32 deviceRightOption = 0x00000040;
        constexpr quint32 deviceRightControl = 0x00002000;

        const auto*   key = static_cast<QKeyEvent*>(event);
        const quint32 native = static_cast<quint32>(key->nativeModifiers());

        int sides = 0;
        if (native & deviceLeftCommand) sides |= LeftCommand;
        if (native & deviceRightCommand) sides |= RightCommand;
        if (native & deviceLeftOption) sides |= LeftOption;
        if (native & deviceRightOption) sides |= RightOption;
        if (native & deviceLeftShift) sides |= LeftShift;
        if (native & deviceRightShift) sides |= RightShift;
        if (native & deviceLeftControl) sides |= LeftControl;
        if (native & deviceRightControl) sides |= RightControl;

        if (sides != _modifierSides) {
            _modifierSides = sides;
            Q_EMIT modifierSidesChanged();
        }
    }

    // Never consumed: this only watches. A filter that eats a key event here
    // would eat it for the whole application.
    return QObject::eventFilter(watched, event);
}

QVariantMap VC::Editor::stateAt(int index, int at)
{
    QVariantMap out;
    try {
        py::gil_scoped_acquire hold;
        const py::object       context = py::module::import("videocode.context").attr("Context");
        for (auto item : context.attr("stateAt")(index, at).cast<py::dict>()) {
            const QString key = QString::fromStdString(py::str(item.first).cast<std::string>());
            // A transform channel is a number; an animated ARGUMENT is whatever
            // its argument is, and a colour comes back as a tuple. Asking for a
            // double on that throws, and one `fill()` would take the whole
            // read-out down with it.
            try {
                out.insert(key, item.second.cast<double>());
            } catch (const py::cast_error&) {
                out.insert(key, QString::fromStdString(py::str(item.second).cast<std::string>()));
            }
        }
    } catch (const py::error_already_set&) {
        // A scene that has not run has no state to read, and a card open on the
        // element of an older run asks about an index that is gone. Neither is
        // worth a message: the row simply has nothing to show.
    }
    return out;
}

QVariantList VC::Editor::effects()
{
    QVariantList found;
    try {
        py::gil_scoped_acquire hold;
        const py::module       serialize = py::module::import("videocode.serialize");
        // Told which project, rather than left to read the process's working
        // directory: the panel and the rest of the shell then mean the same
        // folder by "the project" even if anything ever moves that directory.
        for (const auto& item : serialize.attr("effectCatalogue")(projectRoot().toStdString()).cast<py::list>()) {
            const py::dict one = item.cast<py::dict>();

            // The parameters come across with the name: the pane asks for them
            // before an effect is placed, and a field list written in QML would
            // be a copy of a signature, going stale the first time a default
            // moves.
            QVariantList params;
            for (const auto& entry : one["params"].cast<py::list>()) {
                const py::dict parameter = entry.cast<py::dict>();
                params.append(QVariantMap{{"name", QString::fromStdString(parameter["name"].cast<std::string>())}, {"value", QString::fromStdString(parameter["default"].cast<std::string>())}, {"kind", QString::fromStdString(parameter["kind"].cast<std::string>())}, {"optional", parameter["optional"].cast<bool>()}});
            }

            // "form" is how the call is written — a method on the element, a
            // generator handed the element, or a factory `apply` calls.
            found.append(QVariantMap{{"name", QString::fromStdString(one["name"].cast<std::string>())}, {"module", QString::fromStdString(one["module"].cast<std::string>())}, {"form", QString::fromStdString(one["form"].cast<std::string>())}, {"params", params}});
        }
    } catch (const py::error_already_set&) {
        // An editor that cannot list the effects simply offers none.
    }
    return found;
}

QVariantList VC::Editor::templates()
{
    QVariantList found;
    try {
        py::gil_scoped_acquire hold;
        const py::module       serialize = py::module::import("videocode.serialize");
        for (const auto& item : serialize.attr("templateCatalogue")(projectRoot().toStdString()).cast<py::list>()) {
            const py::dict one = item.cast<py::dict>();

            QVariantList params;
            for (const auto& entry : one["params"].cast<py::list>()) {
                const py::dict parameter = entry.cast<py::dict>();
                params.append(QVariantMap{
                    {"name", QString::fromStdString(parameter["name"].cast<std::string>())},
                    {"value", QString::fromStdString(parameter["default"].cast<std::string>())},
                    {"kind", QString::fromStdString(parameter["kind"].cast<std::string>())},
                    {"optional", parameter["optional"].cast<bool>()},
                });
            }

            QStringList needs;
            for (const auto& entry : one["required"].cast<py::list>())
                needs.append(QString::fromStdString(entry.cast<std::string>()));

            found.append(QVariantMap{
                {"name", QString::fromStdString(one["name"].cast<std::string>())},
                {"group", QString::fromStdString(one["group"].cast<std::string>())},
                {"module", QString::fromStdString(one["module"].cast<std::string>())},
                {"says", QString::fromStdString(one["says"].cast<std::string>())},
                {"params", params},
                {"required", needs},
                // A file of yours the catalogue could not use: the row is its
                // name and the reason, and nothing can be placed from it.
                {"broken", one["broken"].cast<bool>()},
            });
        }
    } catch (const py::error_already_set&) {
        // An editor that cannot list them simply offers none.
    }
    return found;
}

QVariantMap VC::Editor::setArgument(
    const QString& source, int line, const QString& call, const QString& name, const QString& value,
    int occurrence
)
{
    QVariantMap answer{{"ok", false}, {"source", source}, {"message", QStringLiteral("unavailable")}};
    try {
        py::gil_scoped_acquire hold;
        const py::module       edit = py::module::import("videocode.edit");
        const py::object       result = edit.attr("setArgument")(
            source.toStdString(), line, call.toStdString(), name.toStdString(), value.toStdString(),
            occurrence
        );
        answer["ok"] = result.attr("changed").cast<bool>();
        answer["source"] = QString::fromStdString(result.attr("source").cast<std::string>());
        answer["message"] = QString::fromStdString(result.attr("message").cast<std::string>());
    } catch (const py::error_already_set& error) {
        answer["message"] = QString::fromUtf8(error.what());
    }
    return answer;
}

namespace
{
    // What `argumentSpan`/`positionalSpan` answered, as the map QML reads.
    // Three shapes come back: nothing, which is a plain refusal; a sentence,
    // when the value written is not the gesture's to replace and the person has
    // to be told which one; or the span and what goes in it.
    QVariantMap spanAnswer(const py::object& result)
    {
        QVariantMap answer{{"ok", false}, {"start", 0}, {"end", 0}, {"text", QString()}, {"message", QString()}};
        if (result.is_none())
            return answer;
        if (py::isinstance<py::str>(result)) {
            answer["message"] = QString::fromStdString(result.cast<std::string>());
            return answer;
        }

        const py::tuple span = result.cast<py::tuple>();
        answer["ok"] = true;
        answer["start"] = span[0].cast<int>();
        answer["end"] = span[1].cast<int>();
        answer["text"] = QString::fromStdString(span[2].cast<std::string>());
        return answer;
    }
}

QVariantMap VC::Editor::argumentSpan(
    const QString& source, int line, const QString& call, const QString& name, const QString& value,
    const QString& owner, int occurrence
)
{
    try {
        py::gil_scoped_acquire hold;
        const py::module       edit = py::module::import("videocode.edit");
        const int              slot = py::module::import("videocode.serialize")
                                          .attr("parameterSlot")(owner.toStdString(), call.toStdString(), name.toStdString())
                                          .cast<int>();
        return spanAnswer(edit.attr("argumentSpan")(
            source.toStdString(), line, call.toStdString(), name.toStdString(), value.toStdString(),
            occurrence, slot
        ));
    } catch (const py::error_already_set&) {
    }
    return QVariantMap{{"ok", false}, {"start", 0}, {"end", 0}, {"text", QString()}, {"message", QString()}};
}

QVariantMap VC::Editor::positionalSpan(
    const QString& source, int line, const QString& call, int index, const QString& value,
    int occurrence
)
{
    try {
        py::gil_scoped_acquire hold;
        const py::module       edit = py::module::import("videocode.edit");
        return spanAnswer(edit.attr("positionalSpan")(
            source.toStdString(), line, call.toStdString(), index, value.toStdString(), occurrence
        ));
    } catch (const py::error_already_set&) {
    }
    return QVariantMap{{"ok", false}, {"start", 0}, {"end", 0}, {"text", QString()}, {"message", QString()}};
}

QVariantMap VC::Editor::waitLinkSpan(
    const QString& source, int line, const QStringList& calls, double seconds
)
{
    try {
        py::gil_scoped_acquire hold;
        py::list               names;
        for (const QString& call : calls)
            names.append(call.toStdString());
        return spanAnswer(py::module::import("videocode.edit").attr("waitLinkSpan")(source.toStdString(), line, names, seconds));
    } catch (const py::error_already_set&) {
    }
    return QVariantMap{{"ok", false}, {"start", 0}, {"end", 0}, {"text", QString()}, {"message", QString()}};
}

QVariantMap VC::Editor::constantOffer(
    const QString& source, int line, const QString& call, const QVariant& key, const QString& value,
    int occurrence
)
{
    QVariantMap answer{{"ok", false}, {"name", QString()}, {"start", 0}, {"end", 0}, {"text", QString()}, {"uses", 0}};
    try {
        py::gil_scoped_acquire hold;
        const py::module       edit = py::module::import("videocode.edit");
        // A keyword is named and a positional is numbered, and the one function
        // answers both: which of the two it was is the caller's own knowledge.
        const py::object which = key.typeId() == QMetaType::Int
                                     ? py::cast(key.toInt())
                                     : py::cast(key.toString().toStdString());
        const py::object result = edit.attr("constantOffer")(
            source.toStdString(), line, call.toStdString(), which, value.toStdString(), occurrence
        );
        if (result.is_none())
            return answer;

        const py::tuple offer = result.cast<py::tuple>();
        answer["ok"] = true;
        answer["name"] = QString::fromStdString(offer[0].cast<std::string>());
        answer["start"] = offer[1].cast<int>();
        answer["end"] = offer[2].cast<int>();
        answer["text"] = QString::fromStdString(offer[3].cast<std::string>());
        answer["uses"] = offer[4].cast<int>();
    } catch (const py::error_already_set&) {
    }
    return answer;
}

QVariantMap VC::Editor::removeCallSpan(
    const QString& source, int line, const QString& call, int occurrence
)
{
    QVariantMap answer{{"ok", false}, {"start", 0}, {"end", 0}, {"text", QString()}};
    try {
        py::gil_scoped_acquire hold;
        const py::module       edit = py::module::import("videocode.edit");
        const py::object       result = edit.attr("removeCallSpan")(source.toStdString(), line, call.toStdString(), occurrence);
        if (result.is_none())
            return answer;

        const py::tuple span = result.cast<py::tuple>();
        answer["ok"] = true;
        answer["start"] = span[0].cast<int>();
        answer["end"] = span[1].cast<int>();
        answer["text"] = QString::fromStdString(span[2].cast<std::string>());
    } catch (const py::error_already_set&) {
    }
    return answer;
}

QString VC::Editor::readArgument(
    const QString& source, int line, const QString& call, const QString& name, int occurrence
)
{
    try {
        py::gil_scoped_acquire hold;
        const py::module       edit = py::module::import("videocode.edit");
        const py::object       result = edit.attr("readArgument")(
            source.toStdString(), line, call.toStdString(), name.toStdString(), occurrence
        );
        if (result.is_none())
            return {};
        return QString::fromStdString(result.cast<std::string>());
    } catch (const py::error_already_set&) {
        return {};
    }
}

QString VC::Editor::readPositional(
    const QString& source, int line, const QString& call, int index, int occurrence
)
{
    try {
        py::gil_scoped_acquire hold;
        const py::module       edit = py::module::import("videocode.edit");
        const py::object       result = edit.attr("readPositional")(source.toStdString(), line, call.toStdString(), index, occurrence);
        if (result.is_none())
            return {};
        return QString::fromStdString(result.cast<std::string>());
    } catch (const py::error_already_set&) {
        return {};
    }
}

QStringList VC::Editor::callsOnLine(const QString& source, int line)
{
    QStringList found;
    try {
        py::gil_scoped_acquire hold;
        const py::module       edit = py::module::import("videocode.edit");
        for (const auto& name : edit.attr("findCalls")(source.toStdString(), line).cast<py::list>())
            found.append(QString::fromStdString(name.cast<std::string>()));
    } catch (const py::error_already_set&) {
    }
    return found;
}

QStringList VC::Editor::enumValues(const QString& name)
{
    QStringList found;
    try {
        py::gil_scoped_acquire hold;
        const py::module       serialize = py::module::import("videocode.serialize");
        for (const auto& value : serialize.attr("enumValues")(name.toStdString()).cast<py::list>())
            found.append(QString::fromStdString(value.cast<std::string>()));
    } catch (const py::error_already_set&) {
    }
    return found;
}

QString VC::Editor::pickColor(const QString& hex)
{
    const QColor picked = QColorDialog::getColor(QColor(hex), nullptr, QStringLiteral("Choose a colour"));
    return picked.isValid() ? picked.name() : QString();
}

QString VC::Editor::pickFile(const QString& near)
{
    const QFileInfo at(near);
    const QString   start = at.isDir() ? near : at.absolutePath();
    return QFileDialog::getOpenFileName(nullptr, QStringLiteral("Choose a file"), start);
}

QString VC::Editor::evalText(const QString& expression)
{
    try {
        py::gil_scoped_acquire hold;
        const py::module       scope = py::module::import("videocode");
        const py::object       value = py::eval(expression.toStdString(), scope.attr("__dict__"));
        return QString::fromStdString(py::str(value).cast<std::string>());
    } catch (const py::error_already_set&) {
        return {};
    }
}

QVariantList VC::Editor::inputParams(const QString& className)
{
    QVariantList found;
    try {
        py::gil_scoped_acquire hold;
        const py::module       serialize = py::module::import("videocode.serialize");
        for (const auto& entry : serialize.attr("inputSignature")(className.toStdString()).cast<py::list>()) {
            const py::dict parameter = entry.cast<py::dict>();
            found.append(QVariantMap{{"name", QString::fromStdString(parameter["name"].cast<std::string>())}, {"value", QString::fromStdString(parameter["default"].cast<std::string>())}, {"kind", QString::fromStdString(parameter["kind"].cast<std::string>())}});
        }
    } catch (const py::error_already_set&) {
    }
    return found;
}

QVariantMap VC::Editor::easingCurves()
{
    QVariantMap found;
    try {
        py::gil_scoped_acquire hold;
        const py::module       bezier = py::module::import("videocode.utils.bezier");
        for (const auto& item : bezier.attr("curves")().cast<py::dict>()) {
            QVariantList points;
            for (const auto& value : item.second.cast<py::tuple>())
                points.append(value.cast<double>());
            found.insert(QString::fromStdString(item.first.cast<std::string>()), points);
        }
    } catch (const py::error_already_set&) {
        // A shell that cannot read the presets offers none of them, and the
        // curve still works on what the line already spells out.
    }
    return found;
}

QString VC::Editor::pickScene(const QString& startIn) const
{
    return QFileDialog::getOpenFileName(
        nullptr,
        QStringLiteral("Open scene"),
        startIn.isEmpty() ? QDir::currentPath() : startIn,
        QStringLiteral("Python scenes (*.py);;All files (*)")
    );
}

QString VC::Editor::pickExport(const QString& suggested) const
{
    const QString scripted = qEnvironmentVariable("VC_EXPORT");
    if (!scripted.isEmpty())
        return QFileInfo(scripted).absoluteFilePath();

    return QFileDialog::getSaveFileName(
        nullptr,
        QStringLiteral("Export video"),
        suggested.isEmpty() ? QDir::currentPath() : suggested,
        QStringLiteral("Video (*.mp4 *.mov *.webm *.gif);;Still (*.png *.jpg);;All files (*)")
    );
}

// The buffer on disk, ready to hand to a second copy of this binary.
//
// What is rendered is what you are LOOKING at, which is not always what is on
// disk. The copy goes beside the author's own file rather than into a temporary
// folder: a scene says `Video("clips/shot.mp4")`, and a copy rendered from
// anywhere else would fail on paths that are correct.
//
// `temp` comes back holding the copy's path when one was made, so the caller
// can delete it; empty when the file on disk was already right. The empty
// string is the failure — a path that could not be written.
QString VC::Editor::sceneToRender(const QString& scenePath, const QString& source, const QString& tag, QString* temp) const
{
    if (scenePath.isEmpty() || source == readTextFile(scenePath))
        return scenePath;

    const QFileInfo scene(scenePath);
    const QString   copyPath = scene.absolutePath() + QStringLiteral("/.") + scene.completeBaseName() + QStringLiteral(".") + tag + QStringLiteral(".py");
    QFile           copy(copyPath);
    if (!copy.open(QIODevice::WriteOnly | QIODevice::Truncate))
        return {};
    copy.write(source.toUtf8());
    copy.close();
    if (temp != nullptr)
        *temp = copyPath;
    return copyPath;
}

QVariantMap VC::Editor::renderSheet(const QString& scenePath, const QString& source, const QString& output, int tiles, const QString& at)
{
    if (scenePath.isEmpty())
        return {{"ok", false}, {"error", "nothing is open to render"}};

    QString       temp;
    const QString rendered = sceneToRender(scenePath, source, QStringLiteral("verify"), &temp);
    if (rendered.isEmpty())
        return {{"ok", false}, {"error", "could not write the scene to render"}};

    // The editor's frame, or the child renders 1920x1080 whatever the preview showed.
    QStringList args{QStringLiteral("--file"), rendered, QStringLiteral("--generate"), output, QStringLiteral("--width"), QString::number(frameWidth()), QStringLiteral("--height"), QString::number(frameHeight())};
    // The scene's own named moments when it has any; an even spread otherwise.
    if (at.isEmpty())
        args << QStringLiteral("--sheet") << QString::number(std::max(tiles, 2));
    else
        args << QStringLiteral("--at") << at;

    QProcess sheet;
    sheet.setProcessChannelMode(QProcess::SeparateChannels);
    sheet.start(QCoreApplication::applicationFilePath(), args);

    // Two minutes. A scene that takes longer than that to lay eight stills side
    // by side has a problem the sheet was not going to show anyway.
    const bool done = sheet.waitForFinished(120000);
    if (!done)
        sheet.kill();
    const QString said = QString::fromUtf8(sheet.readAllStandardError()).trimmed();

    if (!temp.isEmpty())
        QFile::remove(temp);

    if (!done)
        return {{"ok", false}, {"error", "the render did not finish in two minutes"}};
    if (sheet.exitCode() != 0 || !QFile::exists(output))
        return {{"ok", false}, {"error", said.isEmpty() ? QStringLiteral("the render refused") : said}};
    return {{"ok", true}, {"out", output}};
}

bool VC::Editor::startExport(const QString& scenePath, const QString& source, const QString& output, double from, double to)
{
    if (_export != nullptr)
        return false;

    _exportTemp.clear();
    const QString rendered = sceneToRender(scenePath, source, QStringLiteral("export"), &_exportTemp);
    if (rendered.isEmpty()) {
        Q_EMIT exportFinished(false, QStringLiteral("could not write the scene to render"));
        return false;
    }

    // The editor's frame, or the child renders 1920x1080 whatever the preview showed.
    QStringList args{QStringLiteral("--file"), rendered, QStringLiteral("--generate"), output, QStringLiteral("--width"), QString::number(frameWidth()), QStringLiteral("--height"), QString::number(frameHeight())};
    if (from >= 0)
        args << QStringLiteral("--from") << QString::number(from, 'f', 3);
    if (to > from)
        args << QStringLiteral("--to") << QString::number(to, 'f', 3);

    _exportSaid.clear();
    _export = new QProcess(this);
    _export->setProcessChannelMode(QProcess::SeparateChannels);

    connect(_export, &QProcess::readyReadStandardOutput, this, [this] {
        // The renderer's own count, read off the progress line it already
        // prints. Inventing a second one here would give the pane a number that
        // can disagree with the file being written.
        static const QRegularExpression counted(QStringLiteral("(\\d+)/(\\d+) frames"));
        const QString                   chunk = QString::fromUtf8(_export->readAllStandardOutput());
        QRegularExpressionMatchIterator every = counted.globalMatch(chunk);
        QRegularExpressionMatch         last;
        while (every.hasNext())
            last = every.next();
        if (last.hasMatch())
            Q_EMIT exportProgress(last.captured(1).toInt(), last.captured(2).toInt());
    });

    // Kept, not printed: when the render fails, the last thing it said is the
    // only useful sentence, and it is on stderr.
    connect(_export, &QProcess::readyReadStandardError, this, [this] {
        const QString said = QString::fromUtf8(_export->readAllStandardError()).trimmed();
        if (!said.isEmpty())
            _exportSaid = said.section('\n', -1).trimmed();
    });

    connect(_export, &QProcess::finished, this, [this, output](int code, QProcess::ExitStatus status) {
        const bool killed = status == QProcess::CrashExit;
        const bool ok = !killed && code == 0;
        if (!_exportTemp.isEmpty()) {
            QFile::remove(_exportTemp);
            _exportTemp.clear();
        }
        _export->deleteLater();
        _export = nullptr;
        Q_EMIT exportFinished(
            ok,
            ok       ? QFileInfo(output).fileName()
            : killed ? QStringLiteral("stopped — %1 holds only what was rendered").arg(QFileInfo(output).fileName())
                     : (_exportSaid.isEmpty() ? QStringLiteral("the render failed") : _exportSaid)
        );
    });

    _export->start(QCoreApplication::applicationFilePath(), args);
    return true;
}

void VC::Editor::cancelExport()
{
    if (_export != nullptr)
        _export->kill();
}

QString VC::Editor::pickFolder() const
{
    return QFileDialog::getExistingDirectory(
        nullptr,
        QStringLiteral("Open folder"),
        QDir::currentPath()
    );
}

QStringList VC::Editor::pickMedia() const
{
    return QFileDialog::getOpenFileNames(
        nullptr,
        QStringLiteral("Add media"),
        QStandardPaths::writableLocation(QStandardPaths::MoviesLocation),
        QStringLiteral(
            "Media (*.mp4 *.mov *.mkv *.webm *.avi *.wav *.mp3 *.aac *.flac *.m4a *.ogg "
            "*.png *.jpg *.jpeg *.svg *.gif *.webp);;All files (*)"
        )
    );
}

bool VC::Editor::replaceRange(QQuickTextDocument* document, int start, int end, const QString& text)
{
    if (!document || !document->textDocument() || start < 0 || end < start)
        return false;

    QTextDocument* doc = document->textDocument();
    if (end > doc->characterCount() - 1)
        return false;

    QTextCursor cursor(doc);
    cursor.beginEditBlock();
    cursor.setPosition(start);
    cursor.setPosition(end, QTextCursor::KeepAnchor);
    cursor.insertText(text);
    cursor.endEditBlock();
    return true;
}

void VC::Editor::highlightPython(QQuickTextDocument* document, const QVariantMap& colours, bool signature)
{
    if (!document || !document->textDocument())
        return;

    // Attaching twice would paint the same document from two highlighters, so a
    // panel that has one keeps it.  The child is found by type, not remembered
    // here: the document outlives nothing and the chrome may be rebuilt at any
    // save.
    // A document that already has one is REPAINTED rather than given a second:
    // this is also how switching theme reaches the buffer.
    if (auto* existing = document->textDocument()->findChild<PythonHighlighter*>()) {
        existing->recolour(colours);
        existing->rehighlight();
        return;
    }

    new PythonHighlighter(document->textDocument(), colours, signature);
}

void VC::Editor::setAudioMuted(bool muted)
{
    _speaker.setMuted(muted);
    Q_EMIT audioChanged();
}

// A failure here has to SPEAK: an app launched from the Dock has a PATH
// without /opt/homebrew/bin, so `ffmpeg` is not found — and a preview that
// stays quietly silent is the very bug this exists to end.
static QString findFfmpeg()
{
    QString found = QStandardPaths::findExecutable(QStringLiteral("ffmpeg"));
    for (const char* where : {"/opt/homebrew/bin/ffmpeg", "/usr/local/bin/ffmpeg", "/usr/bin/ffmpeg"})
        if (found.isEmpty() && QFile::exists(QString::fromLatin1(where)))
            found = QString::fromLatin1(where);
    return found;
}

void VC::Editor::bakeAudio()
{
    if (_bake != nullptr) {
        // Unhooked before it is killed: its `finished` would otherwise fire
        // from inside the destructor, into a slot that reads `_bake` — by then
        // null, or the NEXT process.
        disconnect(_bake, nullptr, this, nullptr);
        _bake->kill();
        _bake->deleteLater();
        _bake = nullptr;
    }
    if (!_scene)
        return;

    const VC::Audio::AudioGraph graph = VC::Audio::buildAudioGraph(_scene->_inputs, std::nullopt, _scene->_nbFrame, 0);
    if (graph.count == 0) {
        _speaker.unload();
        _audioWhy.clear();
        Q_EMIT audioChanged();
        return;
    }

    const QString ffmpeg = findFfmpeg();
    if (ffmpeg.isEmpty()) {
        _speaker.unload();
        _audioWhy = QStringLiteral("no sound: ffmpeg is not installed (brew install ffmpeg)");
        Q_EMIT audioChanged();
        return;
    }

    // A new name per run: the speaker holds the last one decoded in memory,
    // and ffmpeg must never write under a file being read.
    const QString wav = QStringLiteral("/tmp/videocode-preview-%1-%2.wav").arg(getpid()).arg(++_bakeRevision);
    QStringList   args{QStringLiteral("-y"), QStringLiteral("-loglevel"), QStringLiteral("error")};
    for (const std::string& one : graph.inputArgs)
        args << QString::fromStdString(one);
    args << QStringLiteral("-filter_complex") << QString::fromStdString(graph.filter)
         << QStringLiteral("-map") << QStringLiteral("[%1]").arg(QString::fromStdString(graph.label))
         << QStringLiteral("-ar") << QStringLiteral("48000") << QStringLiteral("-ac") << QStringLiteral("2")
         << QStringLiteral("-c:a") << QStringLiteral("pcm_s16le") << wav;

    // The last WAV goes with the editor; one per run would pile up in /tmp.
    static bool sweeps = false;
    if (!sweeps) {
        sweeps = true;
        connect(qApp, &QCoreApplication::aboutToQuit, this, [this] {
            if (_bake != nullptr)
                _bake->kill();
            _speaker.unload();
            if (!_bakeWav.isEmpty())
                QFile::remove(_bakeWav);
        });
    }

    _bake = new QProcess(this);
    _bake->setProcessChannelMode(QProcess::SeparateChannels);
    connect(_bake, &QProcess::finished, this, [this, wav, bake = _bake](int code, QProcess::ExitStatus status) {
        if (bake != _bake)
            return;
        const QString said = QString::fromUtf8(bake->readAllStandardError()).trimmed().section('\n', -1);
        bake->deleteLater();
        _bake = nullptr;
        if (status != QProcess::NormalExit || code != 0) {
            QFile::remove(wav);
            _audioWhy = QStringLiteral("no sound: the preview mix failed — %1").arg(said.isEmpty() ? QStringLiteral("ffmpeg gave no reason") : said);
            Q_EMIT audioChanged();
            return;
        }
        // Reloaded in flight: a run during playback keeps its place.
        const bool    wasPlaying = _speaker.playing();
        const double  at = _speaker.position();
        const QString previous = _bakeWav;
        if (_speaker.load(wav.toStdString())) {
            _bakeWav = wav;
            _audioWhy.clear();
            if (wasPlaying)
                _speaker.play(at);
            if (!previous.isEmpty() && previous != wav)
                QFile::remove(previous);
        } else {
            _audioWhy = QStringLiteral("no sound: %1").arg(QString::fromStdString(_speaker.why()));
        }
        Q_EMIT audioChanged();
    });
    _bake->start(ffmpeg, args);
}

QString VC::Editor::socketPath()
{
    return QString::fromStdString(VC::ownSocketPath());
}

void VC::Editor::serve()
{
    const QString path = socketPath();
    // A crash leaves the file behind, and listen() then fails on a socket
    // nobody is reading. Removing it first is what every local server does.
    QLocalServer::removeServer(path);
    if (!_server.listen(path)) {
        std::cerr << std::format("The editor could not listen on {}: {}\n", path.toStdString(), _server.errorString().toStdString());
        return;
    }
    // The well-known name follows the editor that opened last. Not when
    // VC_SOCKET named this one: a scripted run stays out of the author's way.
    if (qEnvironmentVariable("VC_SOCKET").isEmpty()) {
        const QString latest = QString::fromStdString(VC::latestSocketPath());
        QFile::remove(latest);
        QFile::link(path, latest);
        // Taken down with this editor, and only while it still points here —
        // an editor opened later owns the name now.
        connect(qApp, &QCoreApplication::aboutToQuit, this, [path, latest] {
            if (QFile::symLinkTarget(latest) == path)
                QFile::remove(latest);
        });
    }
    connect(&_server, &QLocalServer::newConnection, this, [this] {
        while (QLocalSocket* client = _server.nextPendingConnection()) {
            connect(client, &QLocalSocket::disconnected, client, &QObject::deleteLater);
            connect(client, &QLocalSocket::readyRead, this, [this, client] {
                while (client->canReadLine()) {
                    const QByteArray line = client->readLine().trimmed();
                    if (line.isEmpty())
                        continue;
                    QJsonParseError     err{};
                    const QJsonDocument doc = QJsonDocument::fromJson(line, &err);
                    const QVariantMap   reply = (err.error != QJsonParseError::NoError || !doc.isObject())
                                                    ? QVariantMap{{"ok", false}, {"error", "not a JSON object: " + err.errorString()}}
                                                    : control(doc.object().toVariantMap());
                    client->write(QJsonDocument(QJsonObject::fromVariantMap(reply)).toJson(QJsonDocument::Compact) + "\n");
                    client->flush();
                }
            });
        }
    });
    std::cout << std::format("listening on {}\n", path.toStdString());
}

QVariantMap VC::Editor::control(const QVariantMap& request)
{
    const QString verb = request.value("do").toString();
    if (verb == QLatin1String("quit")) {
        QTimer::singleShot(0, qApp, &QCoreApplication::quit);
        return {{"ok", true}};
    }
    if (verb == QLatin1String("key")) {
        pressKey(request.value("spec").toString());
        return {{"ok", true}};
    }
    if (verb == QLatin1String("click")) {
        clickAt(QPointF(request.value("x").toDouble(), request.value("y").toDouble()));
        return {{"ok", true}};
    }
    if (verb == QLatin1String("panel")) {
        pressKey(QStringLiteral("Panel:") + request.value("name").toString());
        return {{"ok", true}};
    }
    if (verb == QLatin1String("audio")) {
        return {{"ok", true}, {"hasAudio", hasAudio()}, {"why", _audioWhy}, {"file", _bakeWav}, {"muted", audioMuted()}, {"position", audioPosition()}, {"baking", _bake != nullptr}};
    }
    if (verb == QLatin1String("mute")) {
        setAudioMuted(request.value("on", true).toBool());
        return {{"ok", true}, {"muted", audioMuted()}};
    }
    if (verb == QLatin1String("screenshot")) {
        // The same grab the windowless probe uses: it reads a shown window too,
        // so an agent can look at the chrome the author is looking at.
        const QString out = request.value("out").toString();
        if (out.isEmpty())
            return {{"ok", false}, {"error", "screenshot wants out=<file.png>"}};
        captureHidden(out);
        return {{"ok", QFile::exists(out)}, {"out", out}};
    }

    const auto roots = _engine.rootObjects();
    if (roots.isEmpty())
        return {{"ok", false}, {"error", "the chrome is not loaded"}};
    QVariant out;
    if (!QMetaObject::invokeMethod(roots.first(), "control", Q_RETURN_ARG(QVariant, out), Q_ARG(QVariant, QVariant(request))))
        return {{"ok", false}, {"error", "the chrome has no control()"}};
    return out.toMap();
}

// VC_CLICK="x,y" — or "x1,y1,x2,y2,…" for a sequence, which is how a scripted
// run reaches anything behind a menu: opening it and choosing from it are two
// clicks, and one of them alone proves nothing.
//
// The clicks land after the drags, never before: a script that resizes something
// and then clicks in it is describing an order, and firing the click first tests
// the opposite of what it says.
int VC::Editor::probeClicks(int delay)
{
    int  last = 0;
    auto at = [&last](int when) {
        last = std::max(last, when);
        return when;
    };

    // Take the window, before anything is sent to it.
    //
    // A window has no ACTIVE FOCUS ITEM until the platform calls it focused, and
    // a window launched while a browser or the terminal holds the desktop's
    // attention never is — so a key event sent to it is delivered to nobody. It
    // vanishes with no error anywhere, and the run looks like a bug in the
    // chrome rather than a window that was never listening. It was asked for on
    // the capture path only, which is why every key sent to the WINDOWLESS path
    // — the one an agent may use — did nothing at all.
    //
    // The fix is NOT to bring the process to the front. That was the first
    // version, and it worked: it also meant a scripted run stole the keyboard
    // from whoever was using the machine, and their typing went into the scene
    // buffer. Saying it at the QPA layer gives the run its keys and leaves the
    // desktop alone.
    const auto roots = _engine.rootObjects();
    auto*      focusTarget = roots.isEmpty() ? nullptr : qobject_cast<QQuickWindow*>(roots.first());
    if (focusTarget != nullptr) {
#ifdef VC_HAS_QPA_FOCUS
        QWindowSystemInterface::handleFocusWindowChanged(focusTarget, Qt::OtherFocusReason);
#else
        // Built against a Qt with no private headers. The run still happens; its
        // keys do not, and saying so beats a scripted run that silently does
        // nothing when a key is sent.
        qWarning() << "VC_CLICK: built without Qt6::GuiPrivate — this window cannot be given focus, so keys will not fire.";
#endif
    }

    const QStringList probe = qEnvironmentVariable("VC_CLICK").split(',', Qt::SkipEmptyParts);
    for (int i = 0; i + 1 < probe.size(); i += 2) {
        const QPointF where(probe[i].toDouble(), probe[i + 1].toDouble());
        QTimer::singleShot(at(delay / 2 + 600 + (i / 2) * 200), this, [this, where] { clickAt(where); });
    }

    // VC_KEYS="F12;Ctrl+R;Click:700,455;Drag:10,10,80,10;Text:name" — named keys,
    // clicks, drags and literals, in the order written. Typing covers what a
    // character does; the pane's intelligence answers to keys that have no
    // character at all, and those are exactly the ones worth checking — Escape
    // closing a panel, for one, which the windowless path could not send until
    // this moved here beside the clicks.
    const QStringList keys = qEnvironmentVariable("VC_KEYS").split(';', Qt::SkipEmptyParts);
    for (int i = 0; i < keys.size(); ++i) {
        const QString spec = keys.at(i);
        QTimer::singleShot(at(delay / 2 + 900 + i * 700), this, [this, spec] { pressKey(spec); });
    }

    // VC_PANEL="settings" | "shortcuts" | "colors" | "save" | "default" | "measure" | "reset" — one of the
    // shell's own overlays. They are reached from the NATIVE menu bar, which a synthetic
    // click cannot touch, so without this none of them can ever be checked in a
    // scripted run. Here rather than in captureTo() for the same reason the
    // clicks are: the hidden path is the one an agent may use, and it had no
    // way to open an overlay at all.
    const QString panel = qEnvironmentVariable("VC_PANEL");
    if (!panel.isEmpty()) {
        // Before the clicks, not with them: an overlay that opens on the
        // same tick as the first click opens UNDER it, and the click lands
        // on whatever was behind.
        QTimer::singleShot(at(delay / 2 - 500), this, [this, panel] { pressKey("Panel:" + panel); });
    }
    return last;
}

void VC::Editor::clickAt(const QPointF& pos)
{
    const auto roots = _engine.rootObjects();
    if (roots.isEmpty())
        return;
    auto* window = qobject_cast<QQuickWindow*>(roots.first());
    if (!window)
        return;

    QMouseEvent press(QEvent::MouseButtonPress, pos, window->mapToGlobal(pos), Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QCoreApplication::sendEvent(window, &press);
    // Built only once the press has gone. On Qt 6.8 a mouse event's constructor
    // writes its state into a point it still shares with the events built
    // before it (6.11 detaches first): a release built here first turned the
    // waiting press into a release, no item took it, and the click did nothing.
    QMouseEvent release(QEvent::MouseButtonRelease, pos, window->mapToGlobal(pos), Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    QCoreApplication::sendEvent(window, &release);
    std::cout << std::format("Probed a click at ({}, {})\n", pos.x(), pos.y());
}

void VC::Editor::pressKey(const QString& spec)
{
    const auto roots = _engine.rootObjects();
    if (roots.isEmpty())
        return;
    auto* window = qobject_cast<QQuickWindow*>(roots.first());
    if (!window)
        return;

    static const QHash<QString, int> named = {
        {"F2", Qt::Key_F2}, {"F12", Qt::Key_F12}, {"Left", Qt::Key_Left}, {"Right", Qt::Key_Right}, {"Up", Qt::Key_Up}, {"Down", Qt::Key_Down}, {"Return", Qt::Key_Return}, {"Escape", Qt::Key_Escape}, {"Tab", Qt::Key_Tab}, {"Space", Qt::Key_Space}, {"Home", Qt::Key_Home}, {"End", Qt::Key_End}
    };

    // "Click:x,y" — a click, placed IN THE SEQUENCE.
    //
    // VC_CLICK and VC_KEYS run on their own clocks, so a run that must click
    // after a key cannot say so. Here the order is the list.
    if (spec.startsWith("Click:")) {
        const QStringList at = spec.mid(6).split(',', Qt::SkipEmptyParts);
        if (at.size() == 2)
            clickAt(QPointF(at[0].toDouble(), at[1].toDouble()));
        return;
    }

    // "Panel:default" — one of the shell's own menu actions, IN THE SEQUENCE.
    //
    // VC_PANEL fires before the clicks, which is right for an overlay that has
    // to be open before anything is aimed at it and wrong for everything else:
    // "change the arrangement, THEN pin it as the default" cannot be said any
    // other way, and that order is the whole meaning of the gesture.
    // "Menu:1" — ⌘1 through the native menu bar, the only road it takes on macOS.
    if (spec.startsWith("Menu:")) {
        std::cout << std::format("Probed the menu key ⌘{} → {}\n", spec.mid(5).toStdString(), sendMenuKey(spec.mid(5)) ? "taken" : "nobody");
        return;
    }

    if (spec.startsWith("Panel:")) {
        const QString which = spec.mid(6);
        if (which == QStringLiteral("settings"))
            Q_EMIT settingsRequested();
        else if (which == QStringLiteral("shortcuts"))
            Q_EMIT shortcutsRequested();
        else if (which == QStringLiteral("colors"))
            Q_EMIT colorsRequested();
        else if (which == QStringLiteral("measure"))
            Q_EMIT dockMeasureRequested();
        else if (which == QStringLiteral("default"))
            Q_EMIT dockDefaultRequested();
        else if (which == QStringLiteral("save"))
            Q_EMIT dockSaveRequested();
        else if (which == QStringLiteral("reset"))
            Q_EMIT dockResetRequested();
        else if (which == QStringLiteral("export"))
            Q_EMIT exportRequested();
        else
            Q_EMIT dockPanelToggled(which);
        std::cout << std::format("Probed the panel {}\n", which.toStdString());
        return;
    }

    // "Hover:x,y" — the pointer coming to rest somewhere, in the sequence.
    //
    // VC_HOVER runs before the clicks do, so it cannot reach anything a click
    // brought on screen — and a card's rows only show their handles under the
    // pointer. Sent twice, a pixel apart, for the same reason as VC_HOVER: one
    // move says the pointer is passing through, two say it stopped.
    if (spec.startsWith("Hover:")) {
        const QStringList at = spec.mid(6).split(',', Qt::SkipEmptyParts);
        if (at.size() == 2) {
            const QPointF where(at[0].toDouble(), at[1].toDouble());
            hoverAt(where);
            hoverAt(where + QPointF(1, 0));
            std::cout << std::format("Probed a hover at ({}, {})\n", where.x(), where.y());
        }
        return;
    }

    // "Drag:x1,y1,x2,y2" (or "…,hold") — a drag, IN THE SEQUENCE.
    //
    // Same reason as the click above: VC_DRAG runs on its own clock, so a run
    // that must open a panel and only then drag something out of it cannot say
    // so — the drag would land before the panel exists.
    if (spec.startsWith("Drag:")) {
        const QStringList at = spec.mid(5).split(',', Qt::SkipEmptyParts);
        if (at.size() >= 4) {
            // Anything after the four numbers is a flag: "hold" to keep the
            // button down at the end, "cmd" or "shift" to drag with the
            // modifier held — which is a different gesture, not the same one
            // done differently.
            bool                  hold = false;
            Qt::KeyboardModifiers modifiers = Qt::NoModifier;
            for (int i = 4; i < at.size(); ++i) {
                const QString flag = at[i].trimmed();
                if (flag == QStringLiteral("hold"))
                    hold = true;
                else if (flag == QStringLiteral("cmd"))
                    modifiers |= Qt::ControlModifier;
                else if (flag == QStringLiteral("shift"))
                    modifiers |= Qt::ShiftModifier;
            }
            dragProbe(QPointF(at[0].toDouble(), at[1].toDouble()), QPointF(at[2].toDouble(), at[3].toDouble()), hold, modifiers);
        }
        return;
    }

    // "Eval:agentBrief()" — a QML expression, run against the root window and
    // printed as a one-element JSON array (a string with newlines has to survive
    // one line of stdout). The one way a windowless run can read something the
    // chrome BUILT rather than drew — the brief the agent is handed, for one,
    // which otherwise leaves the process unseen.
    if (spec.startsWith("Eval:")) {
        QQmlExpression expression(qmlContext(window), window, spec.mid(5));
        const QVariant value = expression.evaluate();
        const QString  shown = expression.hasError()
                                   ? expression.error().toString()
                                   : QString::fromUtf8(QJsonDocument(QJsonArray{QJsonValue::fromVariant(value)})
                                                           .toJson(QJsonDocument::Compact));
        std::cout << std::format("Probed the expression {} → {}\n", spec.mid(5).toStdString(), shown.toStdString());
        return;
    }

    // "Text:hello" — a literal, so a scripted run can put the keys of a name
    // into a field that only appeared because of an earlier key in the same
    // list. Ordering is the whole point: VC_TYPE runs on its own clock.
    if (spec.startsWith("Text:")) {
        const QString literal = spec.mid(5);
        for (const QChar c : literal)
            typeCharacter(c);
        std::cout << std::format("Probed the text {}\n", literal.toStdString());
        return;
    }

    Qt::KeyboardModifiers modifiers = Qt::NoModifier;
    QStringList           parts = spec.split('+', Qt::SkipEmptyParts);
    const QString         name = parts.takeLast();
    for (const QString& part : parts) {
        if (part == "Meta") modifiers |= Qt::MetaModifier;
        if (part == "Shift") modifiers |= Qt::ShiftModifier;
        if (part == "Ctrl") modifiers |= Qt::ControlModifier;
    }

    // A single character is its own key code — Qt::Key_A is 'A' — which is how
    // the chrome's own Keymap resolves them too.  Without this, every letter
    // shortcut was unreachable from a scripted run and failed silently loud.
    int key = named.value(name, 0);
    if (key == 0 && name.size() == 1)
        key = name.toUpper().at(0).unicode();

    if (key == 0) {
        std::cerr << std::format("VC_KEYS: no key named {}\n", name.toStdString());
        return;
    }

    // With the character the key would have produced, when it has one. A
    // textless QKeyEvent is a key no text editor can insert, so a probe that
    // sends one cannot see the fight over Space and the arrows between the code
    // pane and the transport — the very thing worth checking about them.
    QString text;
    if (modifiers == Qt::NoModifier || modifiers == Qt::ShiftModifier) {
        if (key == Qt::Key_Space)
            text = QStringLiteral(" ");
        else if (name.size() == 1)
            text = modifiers == Qt::ShiftModifier ? name.toUpper() : name.toLower();
    }

    QKeyEvent press(QEvent::KeyPress, key, modifiers, text);
    QKeyEvent release(QEvent::KeyRelease, key, modifiers, text);
    QCoreApplication::sendEvent(window, &press);
    QCoreApplication::sendEvent(window, &release);
    std::cout << std::format("Probed the key {}\n", spec.toStdString());
}

void VC::Editor::typeCharacter(QChar c)
{
    const auto roots = _engine.rootObjects();
    if (roots.isEmpty())
        return;
    auto* window = qobject_cast<QQuickWindow*>(roots.first());
    if (!window)
        return;

    QKeyEvent press(QEvent::KeyPress, 0, Qt::NoModifier, QString(c));
    QKeyEvent release(QEvent::KeyRelease, 0, Qt::NoModifier, QString(c));
    QCoreApplication::sendEvent(window, &press);
    QCoreApplication::sendEvent(window, &release);
}

void VC::Editor::hoverAt(const QPointF& pos)
{
    const auto roots = _engine.rootObjects();
    if (roots.isEmpty())
        return;
    auto* window = qobject_cast<QQuickWindow*>(roots.first());
    if (!window)
        return;

    QMouseEvent move(QEvent::MouseMove, pos, window->mapToGlobal(pos), Qt::NoButton, Qt::NoButton, Qt::NoModifier);
    QCoreApplication::sendEvent(window, &move);
    // The cursor is the one thing a screenshot cannot show, and it is how a
    // handle says what it does before it is pressed. Qt's own number: 0 the
    // arrow, 4 the text caret, 6 the horizontal resize, 18 the closed hand.
    std::cout << std::format("Probed a hover at ({}, {}) cursor {}\n", pos.x(), pos.y(), static_cast<int>(window->cursor().shape()));
}

void VC::Editor::dragProbe(const QPointF& from, const QPointF& to, bool hold, Qt::KeyboardModifiers modifiers)
{
    const auto roots = _engine.rootObjects();
    if (roots.isEmpty())
        return;
    auto* window = qobject_cast<QQuickWindow*>(roots.first());
    if (!window)
        return;

    const auto send = [window, modifiers](QEvent::Type type, const QPointF& at, Qt::MouseButton button, Qt::MouseButtons held) {
        QMouseEvent event(type, at, window->mapToGlobal(at), button, held, modifiers);
        QCoreApplication::sendEvent(window, &event);
    };

    send(QEvent::MouseButtonPress, from, Qt::LeftButton, Qt::LeftButton);

    // One jump would be delivered as a single move, and a drag handler that has
    // not seen the pointer cross its threshold never becomes active.  Walking
    // there in steps is what makes this a drag rather than a teleport.
    constexpr int steps = 12;
    for (int i = 1; i <= steps; ++i) {
        const qreal t = static_cast<qreal>(i) / steps;
        send(QEvent::MouseMove, QPointF(from.x() + (to.x() - from.x()) * t, from.y() + (to.y() - from.y()) * t), Qt::NoButton, Qt::LeftButton);
    }

    if (!hold)
        send(QEvent::MouseButtonRelease, to, Qt::LeftButton, Qt::NoButton);
    std::cout << std::format(
        "Probed a drag ({}, {}) → ({}, {})\n", from.x(), from.y(), to.x(), to.y()
    );
}

void VC::Editor::reload()
{
    _engine.clearComponentCache();
    // Drop the old tree before building the new one: two shells alive at once
    // would both answer the same shortcuts.
    const auto roots = _engine.rootObjects();
    for (QObject* root : roots)
        root->deleteLater();

    load();
}

QString VC::Editor::qmlDirectory()
{
    return QDir(QString::fromStdString(VC::resourceDir(QML_DIR, "qml"))).absolutePath();
}

void VC::Editor::watchQmlFiles()
{
    QDir              dir(QDir(qmlDirectory()).filePath("VideoCode"));
    const QStringList files = dir.entryList({"*.qml"}, QDir::Files);

    QStringList wanted;
    for (const QString& file : files)
        wanted << dir.filePath(file);

    const QStringList already = _watcher.files();
    for (const QString& path : wanted) {
        if (!already.contains(path))
            _watcher.addPath(path);
    }
}
