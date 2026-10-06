// The picture, plus the transport that moves through it.
//
// The picture is real: `PreviewItem` asks the shell to render the current frame
// with the same engine `--generate` uses, headless into an offscreen image, and
// hands it to the scene graph as a texture. Not the old `VulkanWidget` path —
// that paints onto a native surface with WA_PaintOnScreen, which Qt Quick cannot
// composite over; two devices in one process turned out to be cheaper than
// making one device serve two masters.
//
// It renders at PANE size, not at output size: 4x SSAA makes a 1080p frame a
// 7680x4320 offscreen buffer, and this is a viewport, not a deliverable. What
// you see is the scene; what you see is not the file.
import QtQuick

import VideoCode.Engine

Item {
    id: root

    property real playhead: 0
    property int frameWidth: 1920
    property int frameHeight: 1080
    property int framerate: 30
    property bool playing: false

    // Which scene: bumped on every successful execute, so the same frame index
    // is re-rendered when the buffer behind it has changed.
    property int revision: 0

    // Whether there is a scene at all. Before the first ⌘R there is nothing to
    // draw, and drawing nothing is better than drawing the last thing.
    property bool ready: false

    // Safe margins over the picture, as Premiere's Program Monitor draws them:
    // a guide for the person looking, never part of the frame — the renderer
    // does not know they exist, so nothing reaches --generate.
    property bool guides: false

    signal togglePlay()
    signal toggleGuides()

    // The button in the transport bar: make a file of this.
    signal seek(real seconds)

    // Where TikTok, Reels and Shorts draw over a 9:16 film, in pixels of a
    // 1080x1920 frame — the union of the three, so a title clear of these is
    // clear in all of them. APPROXIMATE, and not measured here: rounded from
    // the creator safe-zone templates and the apps' ad guidelines (2024–25) —
    // about 130 px of tabs at the top, a ~140 px column of like / comment /
    // share on the right, ~400 px of handle, caption, sound and subscribe row
    // at the bottom. No app publishes a pixel spec for an ordinary post, and
    // every redesign moves them: one table, so the day they move is one edit.
    readonly property var platformZones: [
        { name: "tabs",    x: 0,   y: 0,    w: 1080, h: 130 },
        { name: "buttons", x: 940, y: 700,  w: 140,  h: 820 },
        { name: "caption", x: 0,   y: 1520, w: 1080, h: 400 }
    ]

    // One safe rectangle: a share of the frame, centred. A light line with a
    // dark one just outside it, so the guide reads on a white picture as
    // well as on a black one.
    component SafeBox: Rectangle {
        property real share: 0.9
        anchors.centerIn: parent
        width: parent.width * share
        height: parent.height * share
        color: "transparent"
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.75)

        Rectangle {
            anchors.fill: parent
            anchors.margins: -1
            z: -1
            color: "transparent"
            border.width: 1
            border.color: Qt.rgba(0, 0, 0, 0.5)
        }
    }

    // Clicking the picture is working in the picture: the caret leaves the code
    // pane, and the transport keys — Space, the arrows, Home, End — come back
    // from the text editor that owns them while you are typing.
    MouseArea {
        anchors.fill: parent
        onPressed: root.forceActiveFocus()
    }

    // ── Stage: the frame is letterboxed inside whatever room the dock gives ──
    Item {
        id: stage
        anchors {
            left: parent.left; right: parent.right
            top: parent.top; bottom: viewbar.top
            // Tight, because the pane is sized to the picture rather than the
            // picture floated in whatever pane was left over.
            margins: 5
        }

        Rectangle {
            id: frame
            anchors.centerIn: parent
            readonly property real aspect: root.frameWidth / root.frameHeight
            width: Math.min(parent.width, parent.height * aspect)
            height: width / aspect
            color: Theme.sunk
            border.color: Theme.edge
            border.width: 1

            PreviewItem {
                id: picture
                anchors.fill: parent
                anchors.margins: 1
                visible: root.ready
                shell: Shell
                revision: root.revision
                // The playhead is in seconds because that is what a person
                // reads; a renderer only knows frames.
                frame: Math.round(root.playhead * root.framerate)
            }

            // ── Safe margins ──────────────────────────────────────────────
            // Over the picture's own rect, not the pane's: the frame is
            // letterboxed in whatever room the dock gives, and a guide drawn
            // against the pane would sit on the bars.
            Item {
                id: guides
                anchors.fill: picture
                visible: root.guides && root.ready

                // A phone's UI covers a 9:16 film where a TV's overscan covers
                // a 16:9 one, so the zones only make sense on that frame —
                // compared with a tolerance, 1080x1920 and 720x1280 are both it.
                readonly property bool portrait: Math.abs(root.frameWidth / root.frameHeight - 9 / 16) < 0.01

                Repeater {
                    model: guides.portrait ? root.platformZones : []
                    Rectangle {
                        x: modelData.x / 1080 * guides.width
                        y: modelData.y / 1920 * guides.height
                        width: modelData.w / 1080 * guides.width
                        height: modelData.h / 1920 * guides.height
                        color: Qt.rgba(0, 0, 0, 0.45)
                        border.width: 1
                        border.color: Qt.rgba(1, 1, 1, 0.25)

                        Text {
                            anchors { left: parent.left; top: parent.top; margins: 4 }
                            text: modelData.name
                            color: Qt.rgba(1, 1, 1, 0.7)
                            font.family: Theme.mono
                            font.pixelSize: 9
                        }
                    }
                }

                SafeBox { share: 0.9 }   // action safe
                SafeBox { share: 0.8 }   // title safe: the lint's rectangle (videocode/serialize.py)

                // The centre, small: a cross the size of the frame would cut
                // through exactly what is being framed.
                Rectangle {
                    anchors.centerIn: parent
                    width: 15; height: 1
                    color: Qt.rgba(1, 1, 1, 0.7)
                }
                Rectangle {
                    anchors.centerIn: parent
                    width: 1; height: 15
                    color: Qt.rgba(1, 1, 1, 0.7)
                }
            }

            Text {
                anchors.centerIn: parent
                visible: !root.ready
                text: "⌘R to run the scene"
                color: Theme.inkFaint
                font.family: Theme.mono
                font.pixelSize: 11
            }
        }
    }

    // ── Viewbar ───────────────────────────────────────────────────────────
    Rectangle {
        id: viewbar
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 30
        color: Theme.rail
        // The viewbar is the panel's bottom edge, so it carries the panel's
        // corners; left square, it paints over them.
        bottomLeftRadius: Theme.radiusInner
        bottomRightRadius: Theme.radiusInner

        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 1
            color: Theme.edge
        }

        Row {
            anchors.verticalCenter: parent.verticalCenter
            anchors.left: parent.left
            anchors.leftMargin: 8
            spacing: 2

            TransportButton { glyph: "⏮"; onTriggered: { root.forceActiveFocus(); root.seek(0); } }
            // Deux chevrons, pas un : un triangle seul est le triangle de LECTURE
            // à l'envers, et les deux se confondaient de loin. Doublé, il dit
            // « image par image » comme sur tous les transports.
            TransportButton { glyph: "◀◀"; onTriggered: root.seek(root.playhead - 1 / root.framerate) }
            TransportButton {
                glyph: root.playing ? "❙❙" : "▶"
                active: root.playing
                onTriggered: { root.forceActiveFocus(); root.togglePlay(); }
            }
            TransportButton { glyph: "▶▶"; onTriggered: root.seek(root.playhead + 1 / root.framerate) }
            // Apart from the four that move the playhead: this one changes what
            // you see, not when.
            Item { width: 8; height: 1 }
            TransportButton {
                glyph: "▣"
                active: root.guides
                onTriggered: { root.forceActiveFocus(); root.toggleGuides(); }
            }
        }

        // Timecode counts frames, because a video editor's smallest unit is a
        // frame — not a tenth of a second.
        Text {
            anchors.centerIn: parent
            color: Theme.ink
            font.family: Theme.mono
            font.pixelSize: 12
            text: {
                const total = Math.floor(root.playhead);
                const h = String(Math.floor(total / 3600)).padStart(2, "0");
                const m = String(Math.floor(total / 60) % 60).padStart(2, "0");
                const s = String(total % 60).padStart(2, "0");
                const f = String(Math.round((root.playhead - total) * root.framerate)).padStart(2, "0");
                return h + ":" + m + ":" + s + ":" + f;
            }
        }

        Text {
            anchors.verticalCenter: parent.verticalCenter
            anchors.right: parent.right
            anchors.rightMargin: 12
            text: root.frameWidth + "×" + root.frameHeight + "  ·  " + root.framerate + " fps"
            color: Theme.inkFaint
            font.family: Theme.mono
            font.pixelSize: 10
        }
    }
}
