/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** Editor
*/

#pragma once

#include <QFileSystemWatcher>
#include <QImage>
#include <QLocalServer>
#include <QMenu>
#include <QMenuBar>
#include <QObject>
#include <QPointF>
#include <QProcess>
#include <QQmlApplicationEngine>
#include <QQuickTextDocument>
#include <QString>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>
#include <memory>

#include "agent/AgentSession.hpp"
#include "core/Config.hpp"
#include "core/Core.hpp"
#include "lsp/LanguageServer.hpp"
#include "vulkan/VulkanHeadlessRenderer.hpp"
#include "window/Speaker.hpp"

namespace VC
{
    // -----------------------------------------------------------------------
    // Editor
    //   The editing shell: a QML chrome (dock, timeline, properties, source
    //   buffer) around the same engine the preview window and --generate use.
    //
    //   Why QML and not widgets
    //   ───────────────────────
    //   The chrome is described in qml/VideoCode/*.qml and loaded at RUNTIME,
    //   so moving a panel or retuning a colour costs a reload instead of a
    //   rebuild.  In a debug build the files are read from the source tree and
    //   watched: save a .qml and the window rebuilds itself.  A release build
    //   reads the same files from QML_DIR — swapping that for a qrc: URL is the
    //   only change needed to ship them inside the binary.
    //
    //   Graphics API
    //   ────────────
    //   Quick runs on the platform default — Metal on macOS — and NOT on Vulkan,
    //   even though sharing one API with the renderer sounded better on paper.
    //   Measured on the same scripted run: Vulkan through MoltenVK blocked the GUI
    //   thread for 5012 ms per frame (QSG_RENDER_TIMING's blockedForSync) against
    //   0 ms on Metal, 16.8 s of wall time against 4.5 s, plus three "Timed out
    //   waiting for display lock" warnings from MoltenVK.  A five-second stall per
    //   frame is not a trade-off, it is an unusable window: clicks land while the
    //   UI thread is blocked and look like they did nothing.
    //
    //   QSG_RHI_BACKEND still overrides this, so the Vulkan path can be re-measured
    //   whenever MoltenVK or Qt moves.
    // -----------------------------------------------------------------------
    class Editor : public QObject
    {
        Q_OBJECT

    public:

        explicit Editor(QObject* parent = nullptr);
        ~Editor() override;

        // configureGraphicsApi() — pick the scene graph's backend.
        // MUST run before the first QQuickWindow exists, so call it before the
        // QApplication is even constructed.
        static void configureGraphicsApi();

        // load() — bring the shell up.  False if Main.qml failed to compile,
        // with the reason already on stderr from the QML engine.
        bool load();

        // captureTo() — write the shell's first painted frame to a PNG and quit.
        //
        // The window grabs ITSELF rather than being screenshotted from outside:
        // a desktop capture picks up whatever floats above the window, and on a
        // developer's machine something always does.  This is also what a golden
        // test would call, which is why it lives here and not in a script.
        void captureTo(const QString& path);

        // ── What the chrome may ask of the shell ────────────────────────────
        // The dock's arrangement is the user's, so it outlives the process. QML
        // has no way to write a file, so the shell holds the pen: the chrome
        // hands over one JSON string and gets it back on the next launch.

        // saveLayout() — persist the dock's arrangement. Written next to the
        // application's other settings, not into the project: a layout belongs
        // to the person, not to the scene they happen to have open.
        // reducedMotion() — what the system has been told about movement. Read
        // once by the chrome at startup and folded into every duration it owns.
        // modifierSides() — WHICH ⌘, ⌥, ⇧ or ⌃ is physically down: the left one,
        // the right one, or both.
        //
        // Qt's `modifiers()` cannot say. `Qt::AltModifier` means "an Alt key",
        // and the two Alt keys are the same key as far as every shortcut in Qt
        // is concerned. macOS does know: an NSEvent carries device-dependent
        // bits beside the ordinary ones, and Qt hands them through untouched as
        // `nativeModifiers()`. This reads those bits off every key event —
        // modifier presses included, since pressing ⌥ alone is a key event on
        // macOS — and reports them as the flags in `Side` below.
        //
        // Zero on any platform that does not carry the bits, which reads as
        // "no side is known" rather than as "neither side is down".
        enum Side {
            LeftCommand = 1 << 0,
            RightCommand = 1 << 1,
            LeftOption = 1 << 2,
            RightOption = 1 << 3,
            LeftShift = 1 << 4,
            RightShift = 1 << 5,
            LeftControl = 1 << 6,
            RightControl = 1 << 7,
        };
        Q_ENUM(Side)

        Q_PROPERTY(int modifierSides READ modifierSides NOTIFY modifierSidesChanged)

        int modifierSides() const { return _modifierSides; }

        bool eventFilter(QObject* watched, QEvent* event) override;

        Q_INVOKABLE bool reducedMotion() const;

        // bringToFront() — raise the application, once the window is on screen.
        // See VC::bringToFront(): requestActivate() alone leaves the process
        // behind whatever launched it, and macOS then keeps the cursor and the
        // ⌘ keys for that other application.
        Q_INVOKABLE void bringToFront() const;

        Q_INVOKABLE void saveLayout(const QString& json) const;

        // loadLayout() — the arrangement from last time, or an empty string,
        // which the chrome reads as "open with the default dock".
        Q_INVOKABLE QString loadLayout() const;

        // clearLayout() — forget it, so the next launch starts from the default.
        // This is what Reset UI leaves behind.
        Q_INVOKABLE void clearLayout() const;

        // setDockPanels() — restate what the View → Docks menu should show.
        //
        // The dock's arrangement lives in QML, so the menu cannot know on its
        // own which panels are open; the chrome pushes the list every time the
        // tree changes.  Each entry is { key, label, shown }.
        Q_INVOKABLE void setDockPanels(const QVariantList& panels);

        // setDockTemplates() — restate the named arrangements and which one is
        // in use.  Each entry is { key, label, current }.
        Q_INVOKABLE void setDockTemplates(const QVariantList& templates);

        // setDockDisplays() — restate the arrangements the user has named and
        // kept.  Each entry is { name }.
        Q_INVOKABLE void setDockDisplays(const QVariantList& displays);

        // setCodeThemes() — restate the code pane's palettes and which is on.
        // Each entry is { key, label, current }.
        Q_INVOKABLE void setCodeThemes(const QVariantList& themes);

        // saveColors() / loadColors() — the legend's overrides, the same way
        // round as the layout. One file for the person rather than one per
        // project: a colour is what a kind LOOKS like to them, in every scene.
        Q_INVOKABLE void    saveColors(const QString& json) const;
        Q_INVOKABLE QString loadColors() const;

        // scenePath() / readTextFile() — the scene on disk, for the pane that
        // edits it and the server that analyses it. Both need a real path: a
        // language server reasons about files, not about buffers in memory.
        Q_INVOKABLE QString scenePath() const;
        Q_INVOKABLE QString readTextFile(const QString& path) const;
        Q_PROPERTY(bool headless READ headless CONSTANT)

        // The frame the scene is made in: --width/--height, 1920x1080 unless the
        // editor was started with others. The preview draws its picture at this
        // aspect, and its safe margins and platform zones are fractions of it.
        Q_PROPERTY(int frameWidth READ frameWidth CONSTANT)
        Q_PROPERTY(int frameHeight READ frameHeight CONSTANT)
        int frameWidth() const;
        int frameHeight() const;

        //: Try to read pixels out of a window that was never shown. Whether
        //: this works at all is what it is here to find out: Qt's documented
        //: path for a picture with no window is QQuickRenderControl, and the
        //: cheap alternative — grabbing a window the compositor never mapped —
        //: is either fine or returns nothing, with no way to know but to ask.
        void captureHidden(const QString& path);

        // probeClicks() — the clicks a scripted run asks for, on its own clock.
        //
        // Both capture paths need them and only one had them: `captureTo` hangs
        // its scripting off `frameSwapped`, which a window that is never
        // presented never emits. So the hidden path — the one that leaves the
        // desktop alone, and therefore the only one an agent may use — was
        // photographing a window nothing had ever been sent to, and every click
        // it appeared to test proved nothing.
        //
        // Returns the millisecond at which the LAST thing it scheduled fires, so
        // the caller can take its picture after the run instead of racing it: a
        // key list spaced 700 ms apart outlives the default settle, and every
        // key past the first landed after the shutter with nothing to say so.
        int probeClicks(int delay);

        bool headless() const { return _headless; }

        void setHeadless(bool headless) { _headless = headless; }

        // serve() — the editor answers an agent on a local socket.
        //
        // One JSON object per line in, one per line out; `video-code tell
        // <verb> k=v…` is the client. The verbs are the things an author does
        // with the keyboard — where am I, seek, select, run, open, export —
        // and they live in Main.qml's `control()`, next to the state they
        // read. The scripted-run specs (a key, a click, a panel, a capture)
        // are answered here, since that machinery is C++ already.
        //
        // Why a socket and not the file: an agent already edits the FILE, and
        // that is the right channel for edits. What it could not do was reach
        // the editor the author is LOOKING AT — the playhead, the selection,
        // the last run — from the panel or from a terminal. Now both use the
        // same line.
        void                    serve();
        static QString          socketPath();
        Q_INVOKABLE QVariantMap control(const QVariantMap& request);

        // The preview's sound. After every run the scene's audio graph — the
        // render's own, see compiler/AudioMix.hpp — is mixed by ffmpeg into a
        // WAV, and the speaker plays that. The audio is the clock while it
        // plays: the picture follows `audioPosition()`, never the reverse.
        Q_PROPERTY(bool hasAudio READ hasAudio NOTIFY audioChanged)
        //: Why there is nothing to hear, when a person should know: ffmpeg
        //: missing, a mix that failed. Empty for a scene with no sound.
        Q_PROPERTY(QString audioWhy READ audioWhy NOTIFY audioChanged)
        Q_PROPERTY(bool audioMuted READ audioMuted WRITE setAudioMuted NOTIFY audioChanged)
        //: Seconds the speaker runs ahead of what is heard — Bluetooth adds a
        //: tenth or two. ponytail: a plain number, a settings row if it is
        //: ever set twice.
        Q_PROPERTY(double audioLatency MEMBER _audioLatency NOTIFY audioChanged)

        bool hasAudio() const { return _speaker.loaded(); }

        QString audioWhy() const { return _audioWhy; }

        bool audioMuted() const { return _speaker.muted(); }

        void setAudioMuted(bool muted);

        Q_INVOKABLE void audioPlay(double at) { _speaker.play(at); }

        Q_INVOKABLE void audioPause() { _speaker.pause(); }

        Q_INVOKABLE void audioSeek(double at) { _speaker.seek(at); }

        Q_INVOKABLE double audioPosition() const { return _speaker.position(); }

        Q_INVOKABLE QString projectRoot() const;

        // writable() — whether writeTextFile would accept this path.  The pane
        // asks before you type, not after: a save that refuses in silence is
        // worse than a file that says it is read-only.
        Q_INVOKABLE bool writable(const QString& path) const;

        // writeTextFile() — a file back to disk, project-only.  What a rename
        // across files needs, and the one door the chrome has to the disk.
        Q_INVOKABLE bool writeTextFile(const QString& path, const QString& text) const;

        // executeScene() — run the buffer, and say what happened.
        //
        // The BUFFER, not the file: the scene is what is on screen, and it
        // reaches disk only on ⌘S.  Returns { ok, ms, line, column, message,
        // inputs, frames, fps } — a failure is an answer, not an exception,
        // because a scene being written fails most of the time.
        Q_INVOKABLE QVariantMap executeScene(const QString& source, const QString& path);

        // ── The picture ─────────────────────────────────────────────────────
        // The engine lives HERE, as a member, never in a QML item: a `.qml`
        // save destroys and rebuilds every root object (see reload()), and a
        // Vulkan device torn down mid-frame is a crash rather than a reload.
        //
        // Both are built on the first frame anyone asks for, so an editor that
        // never shows the preview never pays for a Vulkan device.

        // renderFrame() — the scene's frame `index`, at `width` × `height`
        // PHYSICAL pixels.  Empty when the scene has not been executed yet.
        QImage renderFrame(int index, int width, int height);

        // sceneBuilt() — hand the C++ side the scene the buffer just made.
        // Called after an execute; returns the frame count.
        Q_INVOKABLE int sceneBuilt();

        // effects() — every effect name the library exposes, discovered at run
        // time so the list cannot drift from what `apply()` will accept.
        // stateAt() — what element `index` is worth at scene frame `at`: its
        // position, scale, rotation, opacity and align, resolved.
        //
        // The card's chips say what the CALL takes — `side`, `fillColor`. They
        // never say where the thing is, because that is not an argument: it is
        // what every line above has done to it by that frame. This is the only
        // answer to "where is it now", and it reads the same stack S1's second
        // pass reads.
        Q_INVOKABLE QVariantMap stateAt(int index, int at);

        Q_INVOKABLE QVariantList effects();

        // templates() — everything a scene can be GIVEN, as opposed to what can
        // be done to it: shapes, media, and the composite templates the library
        // assembles out of them. Same discovery as the effects, same reason —
        // and the module travels with the name, because a template is not part
        // of `from videocode import *` either.
        Q_INVOKABLE QVariantList templates();

        // setArgument() — rewrite ONE value in the scene's source.
        //
        // The layer every gesture writes through: dragging a clip's edge sets
        // `endFrame` on the call that made it, moving an effect sets its
        // `start`. The call is found by line and name — `Group(a, b).rotateBy(…)`
        // is two calls on one line — and only that value's characters change, so
        // the buffer stays what the person wrote, comments and spacing included.
        //
        // Answers {ok, source, message}. A call it cannot find leaves the source
        // alone and says so: a gesture that silently edits the wrong line is
        // worse than one that does nothing.
        Q_INVOKABLE QVariantMap setArgument(
            const QString& source, int line, const QString& call, const QString& name,
            const QString& value, int occurrence = 0
        );

        // argumentSpan() — the same edit as setArgument(), as a range and what
        // goes in it: {ok, start, end, text, message}. `message` is filled when
        // the refusal is one to show — a value written as a name or an
        // expression, which no gesture may overwrite with a number.
        //
        // The pane applies it to its own document rather than being handed a new
        // buffer, because Qt records edits and not assignments: replacing the
        // text wholesale wiped the undo history, and ⌘Z after a gesture did
        // nothing. Through the document, a gesture lands in the same history as
        // typing and takes one ⌘Z to undo.
        //
        // `owner` is the class of the element the call is about: with it the
        // name is looked up in the call's signature, and a value the line gives
        // by position — `Text("Merci")`, `rotateBy(180)` — is rewritten where it
        // stands instead of being given a second time by name.
        Q_INVOKABLE QVariantMap argumentSpan(
            const QString& source, int line, const QString& call, const QString& name,
            const QString& value, const QString& owner = QString(), int occurrence = 0
        );

        // positionalSpan() — the same as argumentSpan(), for an argument written
        // without a name. `wait(0.3)` is the case that asked for it.
        Q_INVOKABLE QVariantMap positionalSpan(
            const QString& source, int line, const QString& call, int index, const QString& value,
            int occurrence = 0
        );

        // waitLinkSpan() — the span that makes what a line starts happen
        // `seconds` later or sooner: the `.wait()` in front of the first of
        // `calls`, changed, added or taken away. What a dragged clip writes.
        Q_INVOKABLE QVariantMap waitLinkSpan(
            const QString& source, int line, const QStringList& calls, double seconds
        );

        // removeCallSpan() — the span that takes a call OUT, as a range to
        // replace with nothing. A link in a chain loses just its link; a call
        // that is a statement on its own loses the whole line, because
        // `square.` left alone is not a program.
        Q_INVOKABLE QVariantMap removeCallSpan(
            const QString& source, int line, const QString& call, int occurrence = 0
        );

        // readArgument() — what a value is currently written as, verbatim, or an
        // empty string when the argument is not in the call. The TEXT, because
        // `Easing.Out` is not a number and the editor must show what was typed.
        Q_INVOKABLE QString readArgument(
            const QString& source, int line, const QString& call, const QString& name,
            int occurrence = 0
        );

        // readPositional() — what an argument written without a name says,
        // verbatim, or an empty string when that slot is empty. `Video("a.mp4")`
        // keeps its file there, and dragging that clip out of the bin has to
        // write the same file into a new call.
        Q_INVOKABLE QString readPositional(
            const QString& source, int line, const QString& call, int index, int occurrence = 0
        );

        // callsOnLine() — the chain on a line, left to right, so a gesture can
        // say which link it means.
        Q_INVOKABLE QStringList callsOnLine(const QString& source, int line);

        // enumValues() — what an argument of this type accepts, when the type
        // is one the library closes. Empty for everything else: a field with no
        // list is a field you type into, which is the normal case.
        Q_INVOKABLE QStringList enumValues(const QString& name);

        // inputParams() — what the call that makes an input takes, by class
        // name. A `Video` answers with `startFrame`, `endFrame`, `cuts`… which is
        // how the card offers the right fields per kind without knowing what a
        // video is.
        Q_INVOKABLE QVariantList inputParams(const QString& className);
        // What a scene expression is worth, as text — `BLUE_C` → "(105, 165, 241, 255)".
        // "" when it does not evaluate.
        Q_INVOKABLE QString evalText(const QString& expression);
        // The system's own file chooser, started in `near` (a file or a folder);
        // the path picked, or "" when none was.
        Q_INVOKABLE QString pickFile(const QString& near);
        // The system colour picker, opened on `hex`; "#rrggbb" picked, or "".
        Q_INVOKABLE QString pickColor(const QString& hex);

        // easingCurves() — the `Easing` presets that ARE curves, as the four
        // control points behind each, keyed by the spelling a scene uses. The
        // card's curve opens on what the line says, and `Easing.Out` has to
        // mean handles before it can be dragged away from.
        Q_INVOKABLE QVariantMap easingCurves();

        // pickScene() / pickFolder() — the system's panels for opening work.
        // `startIn` roots the file panel; empty means the current directory.
        Q_INVOKABLE QString pickScene(const QString& startIn) const;
        Q_INVOKABLE QString pickFolder() const;

        // pickMedia() — the system's file panel, returning what was chosen.
        //
        // A native panel rather than one the chrome draws: this is the one dialog
        // that has to look like every other application's, because it is where a
        // person's own filing system is, complete with their sidebar, their
        // favourites and their search.  QtQuick.Dialogs would drag two more static
        // plugins in for a worse copy of what Qt Widgets already has here.
        Q_INVOKABLE QStringList pickMedia() const;

        // highlightPython() — colour a TextArea's document as Python.
        //
        // The chrome passes its own `textDocument` and the palette out of
        // Theme.qml; the highlighter is parented to the document, so it lives
        // and dies with the panel and a chrome reload leaves nothing behind.
        Q_INVOKABLE void highlightPython(QQuickTextDocument* document, const QVariantMap& colours, bool signature = false);

        // replaceRange() — one edit, one undo.
        //
        // A gesture replaces a span: take out what is there, put in what it
        // wrote. Done through QML's `remove` and `insert` that is TWO entries in
        // the undo stack, and one ⌘Z leaves `side=` with nothing after it — the
        // insert undone, the removal still standing. A cursor's edit block makes
        // the pair a single step, so the gesture undoes the way it happened.
        Q_INVOKABLE bool replaceRange(QQuickTextDocument* document, int start, int end, const QString& text);

        // constantOffer() — the OTHER edit, when a gesture was refused because
        // the value it aimed at is a named constant: where that name's own
        // number is written, and how many places read it.
        //
        // {ok, name, start, end, text, uses}. `ok` false whenever the argument
        // is not a plain name assigned a plain number at the top of this file —
        // anything cleverer is a decision no gesture should make for anyone.
        Q_INVOKABLE QVariantMap constantOffer(const QString& source, int line, const QString& call, const QVariant& key, const QString& value, int occurrence = 0);

        // pickExport() — where the video should be written, asked of the person.
        // Empty when they said no. VC_EXPORT answers for a scripted run, the way
        // VC_OPEN does for Open Scene…: the panel belongs to the system and
        // cannot be driven, so the probe delivers the answer instead.
        Q_INVOKABLE QString pickExport(const QString& suggested) const;

        // startExport() — render `source` to `output` in a second copy of THIS
        // binary, from `from` to `to` seconds (both -1 for the whole scene).
        //
        // A second process rather than a render on this thread: the editor holds
        // a Vulkan device for the preview and Python for the scene, and an export
        // is minutes of both. The child is the same renderer the author would
        // have run by hand, so what comes out is what the command line makes.
        //
        // False when one is already running — two exports of one scene would
        // race for the same file.
        Q_INVOKABLE bool startExport(const QString& scenePath, const QString& source, const QString& output, double from, double to);

        // renderSheet() — `tiles` moments of `source`, side by side and labelled,
        // written to `output` as one PNG. Blocks until it is there.
        //
        // Blocking, where the export does not, because of who calls it: an agent
        // asking `tell verify` wants ONE answer holding the picture, not a path
        // to poll. A contact sheet is stills — 1.6 s for eight moments of a
        // 38-second scene on this machine — and nothing is looking at the window
        // while an agent drives it.
        //
        // False on a timeout or a renderer that refused; the reason is on the
        // child's stderr, which is returned rather than swallowed.
        Q_INVOKABLE QVariantMap renderSheet(const QString& scenePath, const QString& source, const QString& output, int tiles, const QString& at);

        // cancelExport() — stop the child. What it had already written stays on
        // disk, and `exportFinished` says so rather than leaving a half video
        // looking finished.
        Q_INVOKABLE void cancelExport();

        // applySemanticTokens() — hand the analyser's answer to the document's
        // highlighter.  A document with no highlighter is ignored rather than
        // given one: colouring is the pane's decision, not this call's.
        Q_INVOKABLE void applySemanticTokens(QQuickTextDocument* document, const QVariantList& spans);

    Q_SIGNALS:
        void audioChanged();

        // settingsRequested() — the menu bar's Settings item was chosen.
        //
        // The chrome decides what that means; the shell only owns the menu,
        // because the menu is not drawn by the chrome at all (see below).
        void settingsRequested();

        // dockPanelToggled() — a panel was ticked or unticked in View → Docks.
        void dockPanelToggled(const QString& key);

        // modifierSidesChanged() — a modifier went down or came up, and which
        // one it physically was may have changed with it.
        void modifierSidesChanged();

        // dockTemplateChosen() — a named arrangement was picked in View → Layout.
        void dockTemplateChosen(const QString& key);

        // dockDisplayChosen() — a saved arrangement was picked in Load display.
        void dockDisplayChosen(const QString& name);

        // dockSaveRequested() — Save display…, which the chrome answers with a
        // dialog: naming a thing is the chrome's job, not the menu's.
        void dockSaveRequested();

        // dockMeasureRequested() — Show proportions.  The chrome blanks every
        // pane and writes what share of the window each one takes, until the
        // next click.
        void dockMeasureRequested();

        // dockDefaultRequested() — Update default.  Save display… under the name
        // of the arrangement you are already in, without being asked to type it:
        // bending a display into shape and then keeping it is one gesture in the
        // hand and should be one in the menu.
        void dockDefaultRequested();

        // mediaDropped() — a file arrived from the Finder (or from the probe).
        void mediaDropped(const QString& path);

        // sceneOpened() — File → Open Scene… chose this file.
        void sceneOpened(const QString& path);

        // exportRequested() — File → Export Video…, or a probe asking for it.
        // The chrome answers, because the range to render and the scene as it
        // stands in the buffer are both its own.
        void exportRequested();

        // exportProgress() — frames written, of how many. Read off the child's
        // own progress line: the renderer already says it, and a second count
        // invented here could disagree with the file being written.
        void exportProgress(int done, int total);

        // exportFinished() — the child is gone, and whether the file is a video.
        void exportFinished(bool ok, const QString& message);

        // folderOpened() — File → Open Folder… chose this folder, and this file
        // inside it. The folder is what the language server is rooted at.
        void folderOpened(const QString& folder, const QString& path);

        // codeThemeChosen() — a palette was picked in Guide → Code theme.
        void codeThemeChosen(const QString& key);

        // shortcutsRequested() — Guide → Keyboard Shortcuts.  The list itself is
        // drawn by the chrome: it is the chrome's own keys it describes.
        void shortcutsRequested();

        // colorsRequested() — Guide → Colors.  It used to be a native submenu,
        // which a legend is well served by — you point, you read. But a legend
        // you can EDIT needs a swatch to click, a field to type in and a
        // palette to pick from, and an NSMenu holds none of those.
        void colorsRequested();

        // dockResetRequested() — Dock display → Reset UI.  The same thing the slot menu
        // offers, because a user who has lost a panel looks in the menu bar
        // first and cannot be asked to find a ⋯ on a panel they cannot see.
        void dockResetRequested();

    private:

        // The export running now, and the copy of the buffer it is rendering —
        // written beside the author's scene so relative media paths still
        // resolve, and removed when the child is done.
        QProcess* _export = nullptr;
        // The buffer written beside the author's file for a child render, and
        // deleted after. Shared by the export and the verify sheet.
        QString sceneToRender(const QString& scenePath, const QString& source, const QString& tag, QString* temp) const;

        QString _exportTemp;
        QString _exportSaid;

        // editorScenePath() — the file the pane opens on.
        static QString editorScenePath();

        // layoutPath() — the file the three functions above share.
        static QString layoutPath();

        // colorsPath() — the file the legend's overrides live in.
        static QString colorsPath();

        // fillFileMenu() — the File menu's items, added once the event loop is
        // running; see the call site for why it cannot be done any earlier.
        void fillFileMenu(QMenu* file);

        // buildMenuBar() — the application's menu, in the macOS menu bar.
        //
        // A QMenuBar with NO parent is the system-wide one on macOS, which is
        // where a Mac user looks for Settings — not in a strip the application
        // painted for itself.  QAction::PreferencesRole is what moves the item
        // into the application menu next to About and Quit, with ⌘, attached,
        // so the entry obeys the platform instead of imitating it.
        //
        // This is the one piece of chrome that CANNOT be QML: Qt Quick's MenuBar
        // draws its own bar inside the window, and a drawn menu bar on macOS is
        // exactly the wrong answer.
        void buildMenuBar();

        // clickAt() — deliver a synthetic press/release to the chrome.
        //
        // A smoke test for the chrome's own input wiring that needs no
        // accessibility permission and no human: if a synthesized click reaches
        // the handler but a real one does not, the fault is in the window's
        // relationship with macOS, not in the QML.
        void clickAt(const QPointF& pos);

        // dragProbe() — deliver a synthetic press, a few moves and a release.
        //
        // The companion to clickAt() for the one gesture a click cannot express.
        // A dock whose tabs are dragged between slots has no other automatic
        // test: without this, "you can move a tab" is a claim nobody can check
        // without a hand on the mouse.
        void pressKey(const QString& spec);
        void typeCharacter(QChar c);
        void hoverAt(const QPointF& pos);
        // `hold` keeps the button down at the end of the walk, which is the only
        // way a scripted run can photograph what a drag shows WHILE it is being
        // dragged — a splitter's size readout exists exactly that long.
        void dragProbe(
            const QPointF& from, const QPointF& to, bool hold = false,
            Qt::KeyboardModifiers modifiers = Qt::NoModifier
        );

        // reload() — throw away the loaded tree and build it again from disk.
        // Component cache included: without clearing it, an edited .qml is read
        // from memory and the save appears to do nothing.
        void reload();

        // qmlDirectory() — where the .qml files are, as an absolute path.
        static QString qmlDirectory();

        // watchQmlFiles() — watch every .qml in the directory, not the
        // directory itself: editors save through a temporary file and a rename,
        // which a directory watch reports as one change with no way to tell
        // which file it was.
        void watchQmlFiles();

        std::unique_ptr<QMenuBar> _menuBar;
        QMenu*                    _docksMenu = nullptr;
        QMenu*                    _templatesMenu = nullptr;
        QMenu*                    _displaysMenu = nullptr;
        QMenu*                    _codeThemesMenu = nullptr;

        //: Load the chrome, say whether it loaded, show nothing.
        //:
        //: macOS has no public way to put a window on a chosen Space — only
        //: private CoreGraphics calls — so a window opened by a test lands on
        //: whichever desktop its author is working on. The answer is not to
        //: place the window better; it is not to open one. Every runtime check
        //: of the QML runs through here.
        bool _headless = false;

        LanguageServer _language;
        //: Claude Code, for the Agent pane. Owned by the shell for the same
        //: reason as the language server: it holds a conversation, and a chrome
        //: reload must not throw one away.
        AgentSession _agent;

        // Built lazily, torn down with the shell.
        Config                                  _sceneConfig;
        std::unique_ptr<Core>                   _scene;
        std::unique_ptr<VulkanHeadlessRenderer> _renderer;
        int                                     _renderWidth = 0;
        int                                     _renderHeight = 0;

        QQmlApplicationEngine _engine;
        bool                  _captured = false;

        // The sides currently down, as `Side` flags. Read off the last key
        // event rather than tracked by hand: macOS reports the whole state on
        // every event, so there is no pairing of presses with releases to get
        // wrong.
        int                _modifierSides = 0;
        QFileSystemWatcher _watcher;
        QString            _mainFile;
        QLocalServer       _server;

        void      bakeAudio();
        Speaker   _speaker;
        QProcess* _bake = nullptr;
        QString   _bakeWav;
        QString   _audioWhy;
        int       _bakeRevision = 0;
        double    _audioLatency = 0.0;
    };
} // namespace VC
