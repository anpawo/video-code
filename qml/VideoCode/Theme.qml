// Every colour and metric the chrome uses, in one place — the same palette the
// zoning mockup (docs/ui/editor.html) reasons about, so the two cannot drift.
//
// The rules behind the numbers, worth keeping when you edit them:
//   · One hue per media kind, all four kept cool, so the warm accent always
//     wins: the playhead has to be the most urgent thing on screen.
//   · An effect never borrows its host's hue — it takes the complement, because
//     an effect is something DONE to a medium, not a second smaller medium.
pragma Singleton

import QtQuick

QtObject {
    // ── Surfaces ──
    readonly property color ground:   "#101319"
    readonly property color panel:    "#171b23"
    readonly property color rail:     "#1d222c"
    readonly property color sunk:     "#0b0e13"
    readonly property color edge:     "#2a3140"
    readonly property color edgeSoft: "#212734"

    // What the pointer is on. A veil rather than a surface, so the same token
    // lifts a transparent row, a rail and a panel alike — `rail` as a hover
    // vanished on everything that was already rail.
    readonly property color hover:    Qt.rgba(1, 1, 1, 0.05)

    // ── Text ──
    readonly property color ink:      "#e3e7ef"
    readonly property color inkDim:   "#8a93a6"
    readonly property color inkFaint: "#5d6577"

    // ── Accent: reserved for what is live or about to happen ──
    readonly property color live:     hue("live")
    readonly property color liveSoft: Qt.alpha(live, 0.149)

    // Where the keyboard is. Gold rather than the accent, because the accent is
    // for what is live or about to happen and "you are typing here" is neither;
    // dimmer than the ruler's own gold, since this is a whole pane's outline and
    // has to be findable without becoming the thing you look at.
    readonly property color focusEdge: "#8a6f34"

    readonly property color ok:       hue("ok")
    readonly property color warn:     "#d9a94e"

    // A scene that RAN but says something wrong. Hotter than `warn`, which is
    // the gold of "stale" and "read-only", and short of `bad`, which says the
    // scene never ran at all — the two states have to stay apart at a glance.
    readonly property color flaw:     "#e07a3a"
    readonly property color bad:      "#e0605c"
    readonly property color ai:       "#6aa6e0"

    // ── The scene's source, coloured ──
    // A reader of this buffer is looking for three things: what a line DOES,
    // what it is doing it TO, and with what numbers. So flow words, names and
    // numbers are the three that carry a hue, and everything else stays ink.
    // Close to the dark theme every editor ships, on purpose: a scene file
    // should not look like a different language here than in your editor.
    // Each theme carries its tokens AND its surface: a palette read on the wrong
    // background is a different palette.
    //
    // "dark-2026" is the default and it is not an approximation.
    //
    // It was resolved from VS Code's own theme files rather than from a
    // screenshot: 2026-dark.json INCLUDES dark_modern → dark_plus → dark_vs and
    // then overrides part of them, which is why it is a hybrid — GitHub's hues
    // for keywords, functions and variables, Dark+'s teal for types. Reading
    // only one of those files, or the cached theme blob (which holds entries
    // from more than one theme), gives the wrong answer for half the tokens.
    // Every value below was then checked against the pixels of the same file
    // open in VS Code.
    readonly property var codeThemes: ({
        "dark-2026": {
            "label": "Dark 2026",
            "ground": "#121314", "ink": "#bbbebf", "line": "#858889", "band": "#242526",
            "hover": "#202122", "edge": "#2a2b2c",
            "tokens": {
                "keyword":  "#ff7b72",
                "flow":     "#c586c0",
                "constant": "#569cd6",
                "string":   "#a5d6ff",
                "number":   "#b5cea8",
                "call":     "#d2a8ff",
                "type":     "#4ec9b0",
                "argument": "#ffa657",
                "variable": "#c9d1d9",
                "comment":  "#8b949e",
                "caps":     "#79c0ff"
            }
        },
        "github-dark": {
            "label": "GitHub Dark",
            "ground": "#0d1117", "ink": "#e6edf3", "line": "#6e7681", "band": "#161b22", "hover": "#1c2128", "edge": "#30363d",
            "tokens": {
                "keyword":  "#ff7b72",
                "flow":     "#ff7b72",
                "constant": "#79c0ff",
                "string":   "#a5d6ff",
                "number":   "#79c0ff",
                "call":     "#d2a8ff",
                "type":     "#ffa657",
                "argument": "#ffa657",
                "variable": "#c9d1d9",
                "comment":  "#8b949e",
                "caps":     "#79c0ff"
            }
        },
        "video-code": {
            "label": "Video-Code",
            "ground": "#0b0e13", "ink": "#e3e7ef", "line": "#5d6577", "band": "#161a22", "hover": "#161a22", "edge": "#2a3140",
            "tokens": {
                "keyword":  "#6aa6e0",
                "flow":     "#f0703c",
                "constant": "#6aa6e0",
                "string":   "#4fbe86",
                "number":   "#d9a94e",
                "call":     "#e3e7ef",
                "type":     "#46a3a0",
                "argument": "#8a93a6",
                "variable": "#c3c9d4",
                "comment":  "#5d6577",
                "caps":     "#7cc4f0"
            }
        }
    })

    // Which one is on. Written by the menu bar, kept with the dock's options, so
    // the choice outlives the process like every other thing the user set.
    property string codeTheme: "dark-2026"

    readonly property var codeSkin: codeThemes[codeTheme] !== undefined
                                    ? codeThemes[codeTheme] : codeThemes["dark-2026"]

    readonly property var code: codeSkin.tokens

    // ── What the timeline paints, as shipped ──
    // Keyed by the legend's label, because these are the hues a person may
    // repaint from Guide → Colors. `overrides` holds only what was changed, so
    // the file it is written to can tell a choice from a default; everything
    // below reads through hue(), and the readers of `live`, `ok` and `kind`
    // never learn that a value was overridden.
    readonly property var shipped: ({
        // One hue per media kind.
        "polygon": "#7c5f94",
        "image":   "#6f6a9a",
        "video":   "#3f6f8c",
        "sound":   "#3f8a6c",
        // Subtitles are derived text, so they borrow the neutral rather than
        // spending a fifth hue on themselves.
        "subs":    "#5d6577",
        // A template call: the cool teal between video's blue and sound's
        // green, since it usually holds both.
        "template": "#2f7f86",
        "live":    "#f0703c",
        "ok":      "#4fbe86"
    })

    // Written #RRGGBBAA, the way the panel shows it and the file keeps it.
    property var overrides: ({})

    function hue(label) {
        const chosen = overrides[label];
        if (chosen === undefined)
            return shipped[label];
        // Qt reads a colour name as #AARRGGBB.
        return "#" + chosen.substr(7, 2) + chosen.substr(1, 6);
    }

    readonly property var kind: ({
        "polygon": hue("polygon"),
        "image":   hue("image"),
        "video":   hue("video"),
        "sound":   hue("sound"),
        "subs":    hue("subs"),
        "template": hue("template")
    })

    // ── The host's complement, for what animates it ──
    readonly property var fxKind: ({
        "video":   "#e08a3a",
        "sound":   "#d8604a",
        "polygon": "#d24a5c",
        "image":   "#ddb63f",
        "subs":    "#c09a5c"
    })

    // ── Type ──
    // Named fonts are a portability trap: "SF Mono" is not installed on this Mac
    // (only Menlo and Monaco are), and Qt then spends ~77 ms populating family
    // aliases before falling back to something else entirely. So the UI face is
    // the one the repo already ships and loads by path, and the monospace face is
    // a family macOS always has.
    //
    // The mono face is still machine-dependent, which is the one thing standing
    // between this chrome and reproducible screenshots — see docs/ui/BACKLOG.md.
    readonly property string mono: "Menlo"
    readonly property string ui:   inter.status === FontLoader.Ready ? inter.font.family : "Helvetica"

    readonly property FontLoader inter: FontLoader {
        source: Qt.resolvedUrl("../../assets/fonts/Inter-Regular.ttf")
    }

    // ── Movement ──
    // Every duration in the chrome goes through here, so "less movement" is one
    // answer given once rather than a switch in every file. Set by the shell at
    // startup from the system's own accessibility setting; zero means the same
    // state changes still happen, just without the travel.
    property bool reducedMotion: false

    function motion(ms) { return reducedMotion ? 0 : ms; }

    // ── Metrics ──
    readonly property int radius:     6
    // What anything drawn flush against a panel's inside edge has to use: the
    // panel's own radius minus its 1 px border. Without it the child's square
    // corner paints over the curve and the panel reads as a plain box.
    readonly property int radiusInner: radius - 1
    readonly property int radiusSmall: 3
    readonly property int gap:        8
    readonly property int headerHeight: 26
    readonly property int statusHeight: 24

    // A tenth of a second is the coarsest thing the timeline ever snaps to; the
    // real quantum is the frame, filled in by the scene's framerate.
    // The zoom the timeline opens at: 20 px per second on 7 Sept, 50 on the
    // 9th. The slider's floor stays at 25, so this opens mid-travel and there
    // is somewhere to go in both directions.
    readonly property real pxPerSecond: 50
}
