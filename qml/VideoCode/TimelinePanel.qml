// One lane per element, ordered by when it starts — so a longer edit reads as a
// staircase going down and no two things ever share a line.
//
// No left-hand name column: the bar already says what it is, and a second copy
// of the same name is the one thing a timeline never needs twice.
//
// A video is a SINGLE element carrying picture and sound together, drawn as one
// bar with its waveform inside. Splitting it across two lanes would be two rows
// for one object, which is exactly what this rule forbids.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root

    // The scene being shown, and what the user has picked out of it.
    required property var scene
    property int selectedIndex: -1

    // The lane the code pane's caret is standing in, or -1. Lit, not selected:
    // it follows the caret and is gone the moment it moves, so it must not look
    // like the thing you picked and can act on.
    property int litIndex: -1
    property real playhead: 0

    // The range being worked on, in seconds, or -1 for "not set". Drawn rather
    // than obeyed: what it MEANS — play stops there — belongs to the transport.
    property real markIn: -1
    property real markOut: -1

    readonly property bool ranged: markIn >= 0 && markOut > markIn

    // The moments a trim prefers over the tenth it happens to land on: where
    // other clips begin and end, where the scene waits, where the playhead is.
    // Filled by the shell, which is the only thing that can see all of them.
    property var snapPoints: []

    // The moment nearest `seconds` worth snapping to, or the tenth it rounds to.
    // Eight pixels of forgiveness, so the magnet is the same size on screen at
    // every zoom — and none at all unless ⇧ is held: an edge follows the hand,
    // and lining it up with something is asked for.
    function snapped(seconds, exact) {
        if (exact)
            return Math.round(seconds * 100) / 100;

        const reach = 8 / Math.max(root.pxPerSecond, 1);
        let best = -1;
        let near = reach;
        for (const one of root.snapPoints) {
            const d = Math.abs(one - seconds);
            if (d < near) {
                near = d;
                best = one;
            }
        }
        return best >= 0 ? Math.round(best * 100) / 100 : Math.round(seconds * 10) / 10;
    }

    signal elementPicked(int index)

    // hh:mm:ss:ff, the way an NLE writes a moment; `full` keeps the hours.
    function timecode(seconds, full) {
        const fps = root.scene.fps !== undefined ? root.scene.fps : 30;
        const whole = Math.floor(seconds);
        const f = Math.floor((seconds - whole) * fps + 1e-6);
        const two = (n) => String(n).padStart(2, "0");
        const core = two(Math.floor(whole / 60) % 60) + ":" + two(whole % 60) + ":" + two(f);
        return full ? two(Math.floor(whole / 3600)) + ":" + core : core;
    }

    // The lanes' order, as element indices. The scene's own order until the
    // grip in the head column moves a lane; forgotten when the scene changes
    // shape, since the indices would then name other elements.
    property var order: []
    readonly property var lanesOrder: root.order.length === root.scene.elements.length
                                      ? root.order
                                      : Array.from({ length: root.scene.elements.length }, (_, i) => i)

    // 100 %: the scene's whole span in the pane.
    function zoomToFit() {
        if (root.fitZoom > 0)
            zoom.value = Math.max(zoom.from, Math.min(zoom.to, root.fitZoom));
    }

    // A lane on its way: the row being dragged, how far it has gone, and the
    // row it would land on. The whole lane — head and clips — follows the
    // pointer, and the rows it passes step aside, so what you see while
    // dragging is what you get on release.
    property int dragLane: -1
    property real dragDy: 0
    readonly property int dragTarget: dragLane < 0 ? -1
        : Math.max(0, Math.min(root.lanesOrder.length - 1, dragLane + Math.round(dragDy / root.laneHeight)))

    function laneShift(row) {
        if (root.dragLane < 0)
            return 0;
        if (row === root.dragLane)
            return root.dragDy;
        if (root.dragLane < row && row <= root.dragTarget)
            return -root.laneHeight;
        if (root.dragTarget <= row && row < root.dragLane)
            return root.laneHeight;
        return 0;
    }

    function moveLane(from, to) {
        const next = root.lanesOrder.slice();
        to = Math.max(0, Math.min(next.length - 1, to));
        if (from === to)
            return;
        const [one] = next.splice(from, 1);
        next.splice(to, 0, one);
        root.order = next;
    }

    // V1, V2… for what is seen, A1, A2… for what is only heard, top down.
    function trackName(row) {
        const all = root.scene.elements;
        let seen = 0, heard = 0;
        for (let i = 0; i <= row; ++i)
            all[root.lanesOrder[i]].kind === "sound" ? ++heard : ++seen;
        return all[root.lanesOrder[row]].kind === "sound" ? "A" + heard : "V" + seen;
    }

    // The ruler writes a timecode every `rulerStep` seconds: the first step
    // that keeps two stamps at least 120 px apart.
    readonly property int rulerStep: {
        const fit = [1, 2, 5, 10, 15, 30, 60].find(step => step * root.pxPerSecond >= 120);
        return fit === undefined ? 60 : fit;
    }

    // A clip was opened, and this is where it sits on screen. The rect is the
    // whole point: whatever opens it can start there.
    signal elementOpened(var element, rect where)
    signal elementInspected(var element)
    signal renameRequested(var element)
    signal scrubbed(real seconds)

    // The element that is currently open in the middle of the window, by name.
    //
    // Its bar is not drawn here while it is out — it is somewhere else on screen,
    // and one element cannot be in two places. What stays is the outline of where
    // it was: the lane keeps its height and its grid, nothing reflows, and the
    // hollow says where it is going back to.
    property string openedName: ""

    // A moment under a pointer that is somewhere else in the window: what a
    // template being carried over the timeline is worth. Negative when the point
    // is not over the lanes at all, which is how a drop elsewhere does nothing.
    function timeAtWindow(x, y) {
        const at = flick.mapFromItem(null, x, y);
        if (at.x < 0 || at.y < 0 || at.x > flick.width || at.y > flick.height)
            return -1;
        return Math.max(0, (at.x + flick.contentX - root.pad) / root.pxPerSecond);
    }

    // Which element's lane is under a point, or null. An effect is always an
    // effect ON something, so a drop that is not over a clip means nothing —
    // and saying so beats applying it to whatever was last selected.
    function elementAtWindow(x, y) {
        const at = lanes.mapFromItem(null, x, y);
        if (at.x < 0 || at.y < 0 || at.x > lanes.width)
            return null;
        const row = Math.floor(at.y / root.laneHeight);
        if (row < 0 || row >= root.scene.elements.length)
            return null;
        return root.scene.elements[root.lanesOrder[row]];
    }

    // Which lane the pointer is over while something is carried, by index, so
    // it can be lit. -1 for none.
    property int hoverLane: -1

    // The row the pointer is simply resting on — head and track light
    // together, so the eye follows one line across the panel instead of
    // matching a clip to its name by counting rows. Two sources, one answer:
    // leaving the track for the head must not clear what the head just said.
    property int headRow: -1
    readonly property int pointerRow: rowHover.row >= 0 && rowHover.row < root.lanesOrder.length ? rowHover.row : root.headRow

    // Where a carried thing would land — or where the edge being dragged
    // stands — in seconds, or -1 for nothing carried.
    // Drawn, because a drop you cannot aim is a drop you undo.
    property real dropAt: -1

    // A clip's edge was dragged to a moment. What that MEANS is the shell's
    // business, not the timeline's: a video ends by loading fewer frames, a
    // square ends by being hidden, and both are one line of Python — see
    // Main.trimElement.
    //
    // `push` is ⌘ held at the release. Without it the clip moves ALONE: the
    // scene is sequential, so a clip that ends later pushes every gap after
    // it, and the first of those gaps gives the time back — see Main.gesture.
    signal trimmed(var element, string edge, real seconds, bool push)

    // A clip's body was dragged along its lane, by this many seconds. The
    // element's own clock is what moves — see Main.moveElement.
    signal shifted(var element, real seconds, bool push)

    // How far a clip can go later on its own, in seconds: what the gap after
    // it holds. Asked of the shell, which is the one that reads the lines.
    property var roomFor: (element, edge) => Infinity

    // The clip in the hand, by element index, and how far each of its edges has
    // been pulled, in seconds. Held in seconds while the drag lasts, written
    // once on release — the buffer is not rewritten sixty times a second. Here
    // rather than on the bar, so that Escape can drop what the pointer holds.
    property int heldLane: -1
    property real heldIn: 0
    property real heldOut: 0

    // What a hand on a clip is about to write, for the code pane that shows
    // it before the release does — see Main.aimCode. `at` is the moment the
    // edge stands at, `value` what the release would hand `trimmed`/`shifted`,
    // `push` whether ⌘ is down. Null when nothing is aimed at.
    property var aim: null

    function letGo() {
        root.heldLane = -1;
        root.heldIn = 0;
        root.heldOut = 0;
        root.dropAt = -1;
        root.aim = null;
    }

    Keys.onEscapePressed: (event) => {
        if (root.heldLane >= 0)
            root.letGo();
        else
            event.accepted = false;
    }

    // How far an edge that stood at `from` has been pulled, in seconds.
    //
    // The EDGE is what snaps, not the distance it travelled: lining a clip up
    // with the one above it is the whole point, and a snapped distance only
    // ever lines up with where the drag started.
    //
    // Off a magnet, a distance that ends up WRITTEN is rounded itself. A move
    // writes `.wait(0.5)`, and everything that fades in starts on frame 1, not
    // frame 0: rounding the edge there wrote `.wait(0.47)`. On a magnet it is
    // rounded UP to the hundredth, because `.wait()` counts whole frames and
    // drops the rest: 1.0333 s written as 1.03 is thirty frames, not thirty-one,
    // and the clip stops one frame short of the edge it was lined up with.
    function travel(from, px, free, written) {
        const raw = px / root.pxPerSecond;
        const to = root.snapped(from + raw, free);
        if (!written)
            return to - from;
        if (!free && to === Math.round((from + raw) * 10) / 10)
            return Math.round(raw * 10) / 10;
        return Math.ceil((to - from) * 100 - 1e-6) / 100;
    }

    // A gap you can change. The band knows the line it was written on, so
    // clicking it is an edit to that line and nothing else — see Main.writeWait.
    signal waitChanged(int line, string seconds)

    // A gap's label was pulled: the gap now ENDS at that moment. Where a gap
    // starts is not its own to say — it is wherever the work before it ended —
    // so moving a start is this same gesture on the gap before it.
    signal waitDragged(int line, real seconds)

    // Which gap is being typed into, by line. Nothing else can be open at once:
    // two fields over a timeline is two answers to "what am I editing".
    property int editingWait: -1

    readonly property real pxPerSecond: zoom.value

    // A scene shorter than the pane draws a sliver — two seconds at 80 px/s is
    // 160 px of timeline in 1400 px of panel — and a sliver reads as a timeline
    // that has been cut off rather than as a video that is short. So the zoom has
    // a FLOOR: however long the scene lasts, it is drawn 95% of the panel wide.
    // The clips ARE the pane at that point, and the sliver of ground left at each
    // end is what says the scene stops there rather than running past the edge.
    //
    // That last part is why it is not the full width: the margin is never allowed
    // below `minPad`, whatever the pane is doing. On a narrow pane 5% would be a
    // couple of pixels, which reads as a clip touching the border — the same
    // "cut off" the floor exists to prevent, at the other end of the scale.
    //
    // It is the slider's `from`, not a clamp laid over the top of it. A clamp
    // would leave the handle sitting somewhere the picture does not agree with,
    // and half the slider's travel doing nothing; as the range's start, the
    // handle means what it shows — the range simply begins where the picture
    // stops being a sliver.
    readonly property int minPad: 10
    readonly property real fitWidth: Math.max(0, Math.min(width * 0.95, width - 2 * gutter - 2 * minPad))
    readonly property real fitZoom: span > 0 ? fitWidth / span : 0

    // And a CEILING, which the floor above yields to. Two numbers, because they
    // answer two questions:
    //
    //   `minSpan`      — what is on screen when nothing has been zoomed: ten
    //                    seconds, however short the scene.
    //   `tightestSpan` — as far in as the slider will ever go: five seconds,
    //                    which is exactly twice `minSpan` and is the whole of
    //                    the travel the handle has on a short scene.
    //
    // Ten at rest is what makes the ruler mean something. Blown up to fill the
    // pane, a four-second scene is drawn at five hundred pixels a second — every
    // clip is enormous, a tenth of a second is fifty pixels, and dragging an edge
    // moves it further than you meant. Five is as close as it is ever useful to
    // get: past that the numbers along the top stop reading as time.
    //
    // The trade, said plainly because it contradicts the paragraph above: a
    // scene shorter than ten seconds no longer fills the pane. It sits in a
    // ten-second ruler with the rest of it empty — which is what every editor
    // shows for a short clip, and it says "this is four seconds long" far better
    // than a bar touching both edges ever did.
    readonly property real minSpan: 10
    readonly property real tightestSpan: 5

    // What the timeline DRAWS: the scene, or ten seconds, whichever is longer.
    // One name for it, because the ruler's ticks, the lanes and the scroll
    // extent all have to agree — they used to be written separately against
    // `scene.duration`, which is why a ruler asked to run ten seconds still
    // stamped a number only as far as the scene went.
    readonly property real span: Math.max(scene.duration, minSpan)
    readonly property real maxZoom: fitWidth > 0 ? fitWidth / tightestSpan : 0


    readonly property real contentWidth: span * pxPerSecond
    // Half of what it was. A lane is a row in a map, and the map is the whole
    // point: twice as many elements on screen without scrolling is worth more
    // than the waveform the extra height was carrying: it was never read for its
    // shape — a deterministic squiggle, not the file's own — only for the fact
    // that it was there.
    readonly property int laneHeight: 32
    // Blank strip kept to the left of time zero. Wide enough for the playhead's
    // handle to sit at 0 without touching the panel's edge — and, since every
    // ruler stamp is centred on the line it names, wide enough for the FIRST one
    // to centre like the others instead of being nudged right by the clamp
    // below: half of "00:00" at 11px mono is about 17. Wider than that minimum
    // because a clip that nearly touches the panel's edge still reads as one
    // that was cut off there.
    readonly property int gutter: 32

    // ── The runway ────────────────────────────────────────────────────────
    // Blank kept before time zero and after the last frame, half the pane wide
    // on each side. It is what lets ANY moment of the scene be scrolled to the
    // middle of the pane — the first frame and the last included, which a 22 px
    // gutter never could: they were pinned to the edges, and reading a clip
    // that starts at the border means reading it in the corner of your eye.
    //
    // The runway is there to be scrolled INTO, not looked at — see `parked`
    // below, which is what decides where the pane opens.
    readonly property real pad: Math.max(gutter, width * 0.5)

    // Which row each wait's label sits on, by index. A label starts where its
    // gap starts and is as wide as its writing, so two short gaps in a row
    // would print on top of each other: each one takes the lowest row whose
    // last label has already ended. Packed, not counted from the neighbours —
    // counting put a run of four on the same second row, one over the next.
    readonly property var stampRowOf: {
        const waits = root.scene.waits !== undefined ? root.scene.waits : [];
        const ends = [];
        return waits.map((gap) => {
            const x = gap.at * root.pxPerSecond;
            let row = 0;
            while (row < ends.length && ends[row] > x)
                ++row;
            // 74: the widest "wait N.Ns" chip, plus a hair.
            ends[row] = x + 74;
            return row;
        });
    }
    // The tallest stack, which is how much empty ground the content needs
    // under its last lane: the labels are pinned to the foot of the VIEWPORT,
    // so at the end of the scroll they land wherever the content stops.
    readonly property int stampRows: Math.max(0, ...root.stampRowOf)

    // Opening on the runway would be opening on nothing. Once — and only once,
    // or the pane would snap back to the start every time it is resized — the
    // scene is put where it can be read.
    //
    // Two cases, and they are the same question asked of the width: a scene
    // drawn WIDER than the pane opens on its first frame, a gutter in from the
    // left, because that is where it starts and the rest is scrolled to. One
    // drawn NARROWER than the pane is centred: it fits whole either way, and
    // pinned left it sits in the corner with the emptiness all on one side.
    property bool parked: false

    // On the NEXT turn, never in the same one: the runway widens the flickable's
    // own content, and a contentX written before that binding has caught up is
    // clamped straight back to zero by a Flickable that does not yet know it has
    // anywhere to go.
    onPadChanged: if (!root.parked && root.pad > root.gutter) Qt.callLater(root.park)
    // The panel is built before the first run, so the first park can happen
    // with no scene and decide on a ten-second ruler that a 90-second scene
    // then contradicts. The scene arriving is a new object here, which is the
    // moment to ask the width again — and `parked` only latches once there is
    // something to have parked.
    onSceneChanged: if (!root.parked) Qt.callLater(root.park)

    function park() {
        if (root.parked || root.pad <= root.gutter || flick.width <= 0)
            return;
        const slack = flick.width - root.contentWidth;
        flick.contentX = slack > 0 ? root.pad - slack / 2 : root.pad - root.gutter;
        root.parked = root.scene.duration > 0;
    }

    // Lent to the tab strip of whichever slot is showing this panel. A zoom
    // slider is chrome about the panel, not content in it: in the strip it costs
    // no height at all, and it stops covering the ruler it used to sit on.
    property Item stripControl: zoomBox

    // ── Zoom ──────────────────────────────────────────────────────────────
    // It used to have a strip of its own across the top, which cost 28 px of
    // every timeline forever to hold one slider you touch once a session. The
    // timeline is the panel whose height IS its usefulness — a lane you cannot
    // see is an element you forget — so the control floats in the corner
    // instead, quiet until you point at it, and Ctrl+wheel does the same job
    // without it.
    Rectangle {
        id: zoomBox
        z: 8
        width: zoomRow.width + 16
        height: 21
        radius: Theme.radiusSmall
        color: Theme.rail
        border.width: 1
        // Opaque, not translucent: a ruler mark showing through the control was
        // the ruler and the control both being half-readable.
        border.color: zoomHover.hovered ? Theme.inkFaint : Theme.edge

        Behavior on border.color { ColorAnimation { duration: Theme.motion(90) } }
        HoverHandler { id: zoomHover }

        Row {
            id: zoomRow
            anchors.centerIn: parent
            spacing: 6

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "−"
                color: lessHover.hovered ? Theme.ink : Theme.inkDim
                font.family: Theme.ui
                font.pixelSize: 13
                HoverHandler { id: lessHover }
                TapHandler { onTapped: zoom.value = Math.max(zoom.from, zoom.value / 1.25) }
            }

            Slider {
                id: zoom
                anchors.verticalCenter: parent.verticalCenter
                width: 76
                // Sized explicitly: the Basic style's own implicit height is
                // taller than this strip, and the track is centred inside THAT,
                // which left it riding a few pixels above the label beside it.
                height: 14
                padding: 0
                // 25 px per second at the least — or less, down to the whole
                // scene in the pane, once the scene is too long to fit at 25:
                // a floor of 25 alone left a two-minute scene showing a third
                // of itself at the farthest it would go, and ⇧Z short of 100 %.
                from: root.fitZoom > 0 ? Math.min(25, root.fitZoom) : 25
                // Twice that at most: five seconds on screen and no further. A
                // value already past it — saved, or left over from a wider pane —
                // is pulled back by the Slider itself when the range moves.
                to: root.maxZoom > 0 ? Math.max(from, root.maxZoom) : Math.max(200, from * 4)
                value: Theme.pxPerSecond

                // The Basic style's slider is a pale bar with an oversized knob;
                // this one is the chrome's own: a thin rail that fills warm up to
                // where you are.
                background: Rectangle {
                    x: 0
                    y: zoom.availableHeight / 2 - height / 2
                    width: zoom.availableWidth
                    height: 3
                    radius: 2
                    color: Theme.sunk

                    Rectangle {
                        width: zoom.visualPosition * parent.width
                        height: parent.height
                        radius: 2
                        color: Theme.live
                    }
                }

                handle: Rectangle {
                    x: zoom.visualPosition * (zoom.availableWidth - width)
                    y: zoom.availableHeight / 2 - height / 2
                    width: 11; height: 11
                    radius: 6
                    color: zoom.pressed ? Theme.live : Theme.ink
                    border.color: Theme.sunk
                    border.width: 1
                }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: "+"
                color: moreHover.hovered ? Theme.ink : Theme.inkDim
                font.family: Theme.ui
                font.pixelSize: 13
                HoverHandler { id: moreHover }
                TapHandler { onTapped: zoom.value = Math.min(zoom.to, zoom.value * 1.25) }
            }

            Text {
                anchors.verticalCenter: parent.verticalCenter
                width: 36
                horizontalAlignment: Text.AlignRight
                text: root.fitZoom > 0 ? Math.round(root.pxPerSecond / root.fitZoom * 100) + "%" : ""
                color: Theme.inkFaint
                font.family: Theme.mono
                font.pixelSize: 9
            }
        }
    }

    // Nothing has been executed yet — or the scene is empty. Saying so is the
    // whole point of deleting the stand-in: an empty timeline that explains
    // itself beats a full one that is about someone else's video.
    Column {
        anchors.centerIn: parent
        spacing: 6
        visible: root.scene.elements.length === 0

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "nothing on the timeline"
            color: Theme.inkDim
            font.family: Theme.ui
            font.pixelSize: 12
        }

        Text {
            anchors.horizontalCenter: parent.horizontalCenter
            text: "⌘R runs the buffer — what it makes shows up here"
            color: Theme.inkFaint
            font.family: Theme.mono
            font.pixelSize: 11
        }
    }

    MouseArea {
        anchors.fill: parent
        onPressed: root.forceActiveFocus()
    }

    // The track heads, the way Premiere Pro keeps them: a fixed column the
    // clips scroll under, the playhead's timecode in its corner.
    Rectangle {
        id: heads
        visible: flick.visible
        anchors { left: parent.left; top: parent.top; bottom: parent.bottom }
        width: 86
        z: 7
        color: Theme.rail
        clip: true

        Text {
            x: 10
            height: ruler.height
            verticalAlignment: Text.AlignVCenter
            text: root.timecode(root.playhead, true)
            color: Theme.live
            font.family: Theme.mono
            font.pixelSize: 11
        }

        Repeater {
            model: root.lanesOrder

            Item {
                id: head
                required property int index
                required property int modelData
                readonly property var element: root.scene.elements[head.modelData]
                y: ruler.height - flick.contentY + index * root.laneHeight
                width: heads.width
                height: root.laneHeight
                z: root.dragLane === head.index ? 2 : 0
                transform: Translate {
                    y: root.laneShift(head.index)
                    Behavior on y {
                        enabled: root.dragLane >= 0 && root.dragLane !== head.index
                        NumberAnimation { duration: Theme.motion(90) }
                    }
                }

                Rectangle {
                    anchors.fill: parent
                    visible: gripArea.pressed
                    color: Theme.rail
                    border.width: 1
                    border.color: Theme.edge
                }

                Rectangle {
                    anchors.fill: parent
                    color: root.pointerRow === head.index ? Theme.hover : "transparent"
                }
                HoverHandler {
                    onHoveredChanged: {
                        if (hovered)
                            root.headRow = head.index;
                        else if (root.headRow === head.index)
                            root.headRow = -1;
                    }
                }

                // The lane's colour, as a strip along the edge.
                Rectangle {
                    width: 3
                    height: parent.height
                    color: Theme.kind[head.element.kind]
                }

                // The grip: three lines, dragged up or down to move the lane.
                Column {
                    x: 11
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    Repeater {
                        model: 3
                        Rectangle { width: 10; height: 1.5; radius: 1; color: Theme.inkFaint }
                    }
                }

                MouseArea {
                    id: gripArea
                    width: 30
                    height: parent.height
                    cursorShape: Qt.SizeVerCursor
                    HoverTint {}
                    // Measured in the panel's frame, not the grip's: the grip
                    // itself moves with the pointer, so its own y never changes.
                    property real startY: 0
                    onPressed: (mouse) => {
                        startY = mapToItem(root, mouse.x, mouse.y).y;
                        root.dragLane = head.index;
                        root.dragDy = 0;
                        root.forceActiveFocus();
                    }
                    onPositionChanged: (mouse) => {
                        if (pressed)
                            root.dragDy = mapToItem(root, mouse.x, mouse.y).y - startY;
                    }
                    onReleased: {
                        const to = root.dragTarget;
                        const from = root.dragLane;
                        root.dragLane = -1;
                        root.dragDy = 0;
                        if (to !== from)
                            root.moveLane(from, to);
                    }
                }

                Text {
                    x: 30
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.trackName(head.index)
                    color: root.selectedIndex === head.modelData ? Theme.ink : Theme.inkDim
                    font.family: Theme.ui
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }

                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width
                    height: 1
                    color: Theme.edgeSoft
                }
            }
        }

        Rectangle {
            anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
            width: 1
            color: Theme.edge
        }
    }

    Flickable {
        id: flick
        visible: root.scene.elements.length > 0
        anchors {
            left: heads.right; right: parent.right
            top: parent.top; bottom: parent.bottom
        }
        // Time zero needs room to be a time and not a border — flush against the
        // panel's edge the playhead at 0 reads as an orange frame around the
        // pane, and its handle, drawn 5 px to its left, is clipped away — so the
        // room is inside the content, where it scrolls with everything else.
        // The same room after the last frame as before the first: scrolled to
        // the end, a scene used to stop dead against the panel's edge, which is
        // the "cut off" the left gutter exists to prevent.
        contentWidth: root.pad + root.contentWidth + root.pad
        // The lanes start BELOW the ruler, so the content is that much taller
        // than the lanes are: leaving the ruler out of the count made the last
        // lane unreachable — cut off by exactly the ruler's height, however far
        // you scrolled.
        // The few pixels after the last lane used to be so it did not sit flush
        // against the panel's edge. It is a strip now, because the wait labels
        // live down there: scrolled to the bottom, a label with nothing under it
        // was printed straight onto the last clip.
        contentHeight: lanes.height + ruler.height + 34 + root.stampRows * 25
        flickableDirection: Flickable.HorizontalAndVerticalFlick
        clip: true

        ScrollBar.horizontal: ScrollBar {}
        ScrollBar.vertical: ScrollBar {}

        // The row under the pointer, from anywhere in the panel's width — a
        // handler per lane only answered where the scene had frames.
        HoverHandler {
            id: rowHover
            readonly property int row: hovered
                ? Math.floor(lanes.mapFromItem(flick, point.position.x, point.position.y).y / root.laneHeight) : -1
        }

        // An unfolded template is a block: one frame from its own clip down
        // over the lanes of all it made, the templates it calls framed inside.
        Repeater {
            model: root.scene.elements.map((row, at) => ({ row: row, at: at })).filter((one) => one.row.open === true)

            Rectangle {
                required property var modelData
                readonly property int depth: modelData.row.depth !== undefined ? modelData.row.depth : 0
                readonly property real outset: Math.max(8 - 3 * depth, 2)
                x: root.pad + modelData.row.l * root.pxPerSecond - outset
                y: ruler.height + root.lanesOrder.indexOf(modelData.at) * root.laneHeight + 1
                width: modelData.row.d * root.pxPerSecond + 2 * outset
                // A block inside another stops short of its bottom edge, so two
                // that end on the same lane are still two frames.
                height: modelData.row.lanes * root.laneHeight - 2 - 2 * depth
                radius: 8
                color: Qt.alpha(Theme.kind["template"], 0.12)
                border.width: 1
                border.color: Theme.kind["template"]
            }
        }

        Column {
            id: lanes
            x: root.pad
            y: ruler.height
            spacing: 0

            Repeater {
                model: root.lanesOrder.map(i => root.scene.elements[i])

                Item {
                    id: lane
                    required property int index
                    required property var modelData
                    readonly property int elementIndex: root.lanesOrder[lane.index]
                    width: root.contentWidth
                    z: root.dragLane === lane.index ? 2 : 0
                    transform: Translate {
                        y: root.laneShift(lane.index)
                        Behavior on y {
                            enabled: root.dragLane >= 0 && root.dragLane !== lane.index
                            NumberAnimation { duration: Theme.motion(90) }
                        }
                    }

                    height: root.laneHeight

                    // Across the whole visible width, not the scene's: the
                    // row goes on after the last clip, and so does the line.
                    Rectangle {
                        x: -lanes.x
                        width: Math.max(flick.contentWidth, flick.width)
                        height: parent.height
                        color: root.pointerRow === lane.index ? Theme.hover : "transparent"
                    }

                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width
                        height: 1
                        color: Theme.edgeSoft
                    }

                    // Lit while something that needs an element is carried over
                    // it: the drop has a target, and the target says so.
                    Rectangle {
                        anchors.fill: parent
                        visible: root.hoverLane === lane.elementIndex
                        color: Qt.alpha(Theme.live, 0.10)
                        border.width: 1
                        border.color: Qt.alpha(Theme.live, 0.55)
                    }

                    Rectangle {
                        id: bar
                        x: (lane.modelData.l + bar.heldIn) * root.pxPerSecond
                        y: 2
                        width: Math.max(
                            (lane.modelData.d - bar.heldIn + bar.heldOut) * root.pxPerSecond - 2, 8)
                        // The LANE grows when it opens; the bar does not. It is
                        // still one clip, and a clip that swells to hold its own
                        // contents stops reading as a clip.
                        height: root.laneHeight - 4
                        radius: 6

                        readonly property bool away: root.openedName.length > 0
                                                     && root.openedName === lane.modelData.n

                        readonly property bool lit: root.litIndex === lane.elementIndex

                        readonly property bool picked: root.selectedIndex === lane.elementIndex
                        // Which of the three grips has the pointer, by name: the
                        // edges overlap the body, and whether the leave or the
                        // enter arrives first is not ours to choose. Told by a
                        // HoverHandler in each grip, not by the grip's own
                        // containsMouse, which stayed true on the last clip
                        // pressed, wherever the pointer went next.
                        property string pointed: ""

                        // Selection is the clip's own hue lifted, not white: a
                        // white frame outshouted the playhead and the code pane
                        // both. The pointer adds half as much again, on top of
                        // whatever else the clip is, so it never reads as picked.
                        readonly property color hue: Theme.kind[lane.modelData.kind]
                        color: away ? "transparent"
                                    : Qt.lighter(bar.hue, (bar.picked ? 1.10 : bar.lit ? 1.12 : 1)
                                                          + (bar.pointed.length > 0 ? 0.06 : 0))
                        border.width: 1
                        border.color: away
                                      ? Qt.rgba(1, 1, 1, 0.10)
                                      : (bar.picked
                                         ? Qt.lighter(bar.hue, 1.7)
                                         : (bar.lit
                                            ? Qt.alpha(Theme.live, 0.55)
                                            : (bar.pointed.length > 0
                                               ? Qt.lighter(bar.hue, 1.3)
                                               : Qt.darker(bar.hue, 1.35))))

                        // ── A fault the run found on this element ────────
                        // Hazard hatching, the mark every editing tool uses for
                        // "do not trust this yet". Diagonal because nothing else
                        // in a timeline runs diagonally: it cannot be mistaken
                        // for a clip, a waveform or a boundary, and it survives
                        // being drawn over any of them.
                        Item {
                            id: hazard
                            anchors.fill: parent
                            anchors.margins: 1
                            clip: true
                            visible: !bar.away
                                     && lane.modelData.flaws !== undefined
                                     && lane.modelData.flaws.length > 0

                            Repeater {
                                model: hazard.visible
                                       ? Math.ceil((hazard.width + hazard.height) / 14) : 0

                                Rectangle {
                                    required property int index
                                    width: 5
                                    height: hazard.height * 2
                                    x: index * 14 - hazard.height
                                    y: -hazard.height / 2
                                    rotation: -45
                                    color: Qt.alpha(Theme.flaw, 0.28)
                                }
                            }
                        }

                        // The name sits on a band of its own along the top of
                        // the clip, the way every NLE that has to write over a
                        // waveform does it. Outlined text on top of the waveform
                        // was the alternative and it loses: an outline fights the
                        // very peaks it is drawn over, and the eye has to work
                        // out which pixels are letter and which are audio. A band
                        // gives the letters a floor, and it costs the waveform
                        // nothing — the waveform starts underneath it.
                        Rectangle {
                            id: label
                            visible: !bar.away
                            anchors { left: parent.left; right: parent.right; top: parent.top; margins: 1 }
                            height: 18
                            color: "transparent"
                            clip: true

                            Row {
                                anchors.verticalCenter: parent.verticalCenter
                                anchors.left: parent.left
                                anchors.leftMargin: 6
                                anchors.right: parent.right
                                anchors.rightMargin: 6
                                spacing: 5

                                // It breathes rather than blinks. A blink is a
                                // notification — something that just happened and
                                // wants answering; this is a state the scene is
                                // in, and it has to be able to sit there for an
                                // hour without becoming unbearable. The glyph
                                // scales, never the band: a row that changed
                                // height sixty times a second would move every
                                // clip under it.
                                Text {
                                    id: hazardMark
                                    visible: hazard.visible
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "\u26A0"
                                    color: Theme.flaw
                                    font.pixelSize: 11
                                    transformOrigin: Item.Center

                                    SequentialAnimation on scale {
                                        running: hazardMark.visible
                                        loops: Animation.Infinite
                                        NumberAnimation {
                                            from: 1.0; to: 1.20
                                            duration: 460; easing.type: Easing.InOutSine
                                        }
                                        NumberAnimation {
                                            from: 1.20; to: 1.0
                                            duration: 460; easing.type: Easing.InOutSine
                                        }
                                    }
                                }

                                Text {
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: lane.modelData.n
                                    // Near-black on a saturated band, which beats
                                    // white on every hue this palette uses.
                                    color: "#ffffff"
                                    font.family: Theme.ui
                                    font.pixelSize: 11
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }

                                // How many things one line made. A loop, or a
                                // word made of letters: the row is folded, and
                                // without this the bar claims to be one clip
                                // while every gesture on it moves three. Said
                                // here rather than only inside the card,
                                // because the bar is what a hand aims at.
                                Text {
                                    readonly property int count:
                                        lane.modelData.members !== undefined
                                        ? lane.modelData.members.length : 0
                                    visible: count > 0
                                    anchors.verticalCenter: parent.verticalCenter
                                    text: "×" + count
                                    color: Qt.rgba(1, 1, 1, 0.6)
                                    font.family: Theme.mono
                                    font.pixelSize: 10
                                }
                            }
                        }

                        // ── The clip in the hand ──────────────────────────
                        // A clip that can only be opened is a label. Three
                        // gestures, one piece of code: the body moves it, the
                        // left edge says when it appears, the right edge when
                        // it stops.
                        //
                        // The left edge was gone for a while — a handle that
                        // could only refuse is a handle that lies about what it
                        // does — and is back now that it has something true to
                        // write: the element's own `.wait()`, see
                        // Main.moveElement.
                        Repeater {
                            model: ["body", "in", "out"]

                            MouseArea {
                                id: grip
                                required property string modelData
                                readonly property string edge: modelData
                                // Nine pixels inside the bar was a target to
                                // aim at, and on a short clip a third of it. The
                                // handle now reaches as far OUTSIDE the edge as
                                // inside it: the edge is grabbed from either
                                // side, and a short clip keeps its body — a
                                // quarter of the bar at most is taken from it.
                                readonly property real reach: 8
                                readonly property real lip: Math.min(reach, bar.width / 4)

                                x: edge === "out" ? bar.width - lip : edge === "in" ? -reach : 0
                                width: edge === "body" ? bar.width : lip + reach
                                height: bar.height
                                hoverEnabled: true
                                cursorShape: edge !== "body" ? Qt.SizeHorCursor
                                           : pressed && moved ? Qt.ClosedHandCursor : Qt.ArrowCursor
                                preventStealing: true
                                // A sound is not ON SCREEN from a moment: nothing
                                // it has says when it starts, so its left edge
                                // would be a handle with nothing to write.
                                visible: !bar.away && !(edge === "in" && lane.modelData.kind === "sound")
                                HoverHandler {
                                    onHoveredChanged: {
                                        bar.pointed = hovered ? grip.edge
                                                    : bar.pointed === grip.edge ? "" : bar.pointed;
                                        // An edge under the hand says what pulling it
                                        // would touch; the body waits until it is taken.
                                        if (grip.edge === "body" || root.heldLane >= 0)
                                            return;
                                        if (hovered)
                                            root.aim = grip.aimed(false);
                                        else if (root.aim !== null && !root.aim.held
                                                 && root.aim.element === lane.modelData && root.aim.edge === grip.edge)
                                            root.aim = null;
                                    }
                                }

                                function aimed(held) {
                                    return {
                                        element: lane.modelData, edge: edge, held: held, push: grip.push,
                                        at: held ? root.dropAt : lane.modelData.l + (edge === "out" ? lane.modelData.d : 0),
                                        value: edge === "body" ? root.heldIn : root.dropAt
                                    };
                                }

                                property real anchorX: 0
                                property bool moved: false
                                property bool push: false
                                property real room: Infinity

                                onPressed: (mouse) => {
                                    root.forceActiveFocus();
                                    anchorX = mapToItem(lane, mouse.x, 0).x;
                                    moved = false;
                                    push = false;
                                    room = root.roomFor(lane.modelData, edge);
                                }

                                onPositionChanged: (mouse) => {
                                    if (!pressed)
                                        return;
                                    const px = mapToItem(lane, mouse.x, 0).x - anchorX;
                                    // A click is allowed to tremble: at ten
                                    // pixels a second, one pixel is a tenth.
                                    if (!moved && Math.abs(px) < Application.styleHints.startDragDistance)
                                        return;
                                    const free = (mouse.modifiers & Qt.ShiftModifier) === 0;
                                    const from = lane.modelData.l + (edge === "out" ? lane.modelData.d : 0);
                                    const pushing = (mouse.modifiers & Qt.ControlModifier) !== 0;
                                    // Alone, it stops where the gap after it has
                                    // nothing left to give.
                                    const delta = Math.min(root.travel(from, px, free, edge !== "out"),
                                                           pushing ? Infinity : room);
                                    if (Math.abs(delta) > 0.001)
                                        moved = true;
                                    if (!moved)
                                        return;

                                    // Neither edge may pass the other: a clip of
                                    // no length is a clip you can no longer find.
                                    // And nothing starts before the film does.
                                    const early = Math.max(-lane.modelData.l, delta);
                                    root.heldLane = lane.elementIndex;
                                    root.heldOut = edge === "out" ? Math.max(0.1 - lane.modelData.d, delta)
                                                 : edge === "body" ? early : 0;
                                    root.heldIn = edge === "in" ? Math.min(lane.modelData.d - 0.1, early)
                                                : edge === "body" ? early : 0;
                                    root.dropAt = from + (edge === "out" ? root.heldOut : root.heldIn);
                                    // Asked again when the SNAPPED moment moves, not on
                                    // every pixel: the plan parses the scene.
                                    if (root.aim === null || !root.aim.held || root.aim.at !== root.dropAt || push !== pushing) {
                                        push = pushing;
                                        root.aim = grip.aimed(true);
                                    }
                                }

                                onCanceled: root.letGo()

                                onReleased: {
                                    // Escape let go of it first: nothing to write.
                                    const mine = moved && root.heldLane === lane.elementIndex;
                                    const at = root.dropAt;
                                    const by = root.heldIn;
                                    root.letGo();
                                    if (!mine)
                                        return;
                                    if (edge !== "body")
                                        root.trimmed(lane.modelData, edge, at, push);
                                    else if (Math.abs(by) > 0.001)
                                        root.shifted(lane.modelData, by, push);
                                }

                                // A tap picks the clip and fills the Inspector; a double
                                // tap opens the clip's own timeline — somewhere else.
                                //
                                // What is inside a clip does not belong on the timeline:
                                // rows that grow push everything below them down, and a
                                // timeline whose geometry changes when you look at
                                // something has stopped being a map. The bar reports
                                // where it is on screen so the card can start there and
                                // travel, which is what makes it obvious that the big
                                // thing in the middle IS this clip.
                                //
                                // Asked of the area that also drags, not of a
                                // TapHandler beside it: the area takes the press,
                                // and only it knows whether the press then moved.
                                onClicked: {
                                    if (edge !== "body" || moved)
                                        return;
                                    root.elementPicked(lane.elementIndex);
                                    root.elementInspected(lane.modelData);
                                }

                                onDoubleClicked: {
                                    if (edge !== "body")
                                        return;
                                    const at = bar.mapToItem(null, 0, 0);
                                    root.elementOpened(
                                        lane.modelData,
                                        Qt.rect(at.x, at.y, bar.width, bar.height)
                                    );
                                }

                                // The edge, drawn only when the pointer is on it
                                // or pulling it — on the BAR's edge, not the
                                // handle's, which reaches outside the bar.
                                Rectangle {
                                    visible: grip.edge !== "body"
                                    x: grip.edge === "out" ? bar.width - width - grip.x : -grip.x
                                    anchors {
                                        top: parent.top; bottom: parent.bottom
                                        topMargin: 3; bottomMargin: 3
                                    }
                                    width: 2
                                    radius: 1
                                    color: Qt.rgba(1, 1, 1, 0.30)
                                    opacity: parent.containsMouse || parent.pressed ? 0.95 : 0
                                    Behavior on opacity { NumberAnimation { duration: Theme.motion(90) } }
                                }
                            }
                        }

                        // How far this bar's edges are out of place, which is
                        // nothing unless it is the one in the hand.
                        readonly property real heldIn: root.heldLane === lane.elementIndex ? root.heldIn : 0
                        readonly property real heldOut: root.heldLane === lane.elementIndex ? root.heldOut : 0
                    }
                }
            }
        }

        // Sticky: the ruler scrolls with the lanes horizontally but never leaves
        // the top, because a time reading you have to scroll to is not a reading.
        Rectangle {
            id: ruler
            x: root.pad
            y: flick.contentY
            width: root.contentWidth
            // Two storeys: the markers' names along the top, the seconds along
            // the bottom over their ticks. One storey and a name landed on a
            // stamp every even second.
            //
            // The upper storey only exists when a scene named a moment. This is
            // the panel whose height IS its usefulness, and twelve pixels off
            // every lane forever, to hold a row that is empty, is twelve pixels
            // taken from the thing the panel is for.
            height: root.scene.markers !== undefined && root.scene.markers.length > 0 ? 56 : 44
            z: 5
            color: Theme.rail

            Repeater {
                model: Math.floor(root.span / (root.rulerStep / 10)) + 1

                Item {
                    required property int index
                    readonly property real seconds: index * root.rulerStep / 10
                    x: seconds * root.pxPerSecond
                    width: root.rulerStep / 10 * root.pxPerSecond
                    height: ruler.height

                    readonly property bool major: index % 10 === 0
                    readonly property bool middle: index % 5 === 0

                    Rectangle {
                        width: 1
                        height: parent.major ? 10 : parent.middle ? 6 : 4
                        color: parent.major ? Theme.inkDim : Theme.edge
                    }

                    Text {
                        visible: parent.major
                        x: 6
                        y: 12
                        text: root.timecode(parent.seconds, true)
                        color: Theme.inkDim
                        font.family: Theme.mono
                        font.pixelSize: 11
                    }
                }
            }

            // ── The moments the scene named ───────────────────────────────
            // Every `timestamp()` in the code, as a flag on the ruler with its
            // name beside it. Ink, not a hue: on this timeline a colour is a
            // claim — red for a wait that moves what follows, orange for the
            // playhead, green for the range — and a marker claims nothing. It
            // is a note the author left, so it reads a step above the second
            // stamps and stays under everything that has a colour.
            //
            // The name gives way to the next flag rather than running under
            // it: two names on top of each other are no name at all.
            Repeater {
                model: root.scene.markers !== undefined ? root.scene.markers : []

                Item {
                    id: flag
                    required property var modelData
                    required property int index
                    x: modelData.at * root.pxPerSecond
                    width: 1
                    height: ruler.height
                    // How much of the name fits: the gap to the next flag, less
                    // the 10 px this one is offset by and 6 px of air before
                    // the next triangle. Without that air the last letter and
                    // the next flag touch, and the two read as one word.
                    readonly property real room: {
                        const all = root.scene.markers;
                        return index + 1 < all.length
                               ? (all[index + 1].at - modelData.at) * root.pxPerSecond - 16
                               : 1e9;
                    }

                    Rectangle {
                        width: 1
                        height: ruler.height - 2
                        y: 2
                        color: Qt.alpha(Theme.inkDim, 0.5)
                    }

                    Canvas {
                        x: 1; y: ruler.height - 13
                        width: 6; height: 7
                        onPaint: {
                            const ctx = getContext("2d");
                            ctx.reset();
                            ctx.fillStyle = Theme.inkDim;
                            ctx.beginPath();
                            ctx.moveTo(0, 0);
                            ctx.lineTo(width, height / 2);
                            ctx.lineTo(0, height);
                            ctx.closePath();
                            ctx.fill();
                        }
                    }

                    Text {
                        x: 10
                        y: ruler.height - 15
                        width: Math.max(0, Math.min(implicitWidth, flag.room))
                        visible: flag.room > 12
                        elide: Text.ElideRight
                        text: flag.modelData.n
                        color: Theme.inkDim
                        font.family: Theme.mono
                        font.pixelSize: 9
                    }
                }
            }

            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: 1
                color: Theme.edge
            }

            HoverTint {}

            // Scrubbing. On the ruler only, and not over the lanes: a click on a
            // clip means "open this", and a surface where the same gesture does
            // two things depending on where it lands is a surface you stop
            // trusting. Drag included — a playhead you can only place, never
            // pull, is a slider with no handle.
            MouseArea {
                anchors.fill: parent
                cursorShape: Qt.PointingHandCursor
                preventStealing: true
                onPressed: (mouse) => {
                    // Scrubbing is working in the timeline: the caret leaves the
                    // code pane, and Space stops being a space.
                    root.forceActiveFocus();
                    root.scrubbed(mouse.x / root.pxPerSecond);
                }
                onPositionChanged: (mouse) => {
                    if (pressed)
                        root.scrubbed(mouse.x / root.pxPerSecond);
                }
            }
        }

        // Where a carried template would land.
        Item {
            visible: root.dropAt >= 0
            x: root.pad + root.dropAt * root.pxPerSecond
            y: flick.contentY
            width: 1
            height: flick.height
            z: 6

            Rectangle {
                anchors.fill: parent
                color: Theme.live
            }

            Rectangle {
                anchors { bottom: parent.top; bottomMargin: -18; horizontalCenter: parent.horizontalCenter }
                width: dropStamp.implicitWidth + 12
                height: 18
                radius: 3
                color: Theme.live

                Text {
                    id: dropStamp
                    anchors.centerIn: parent
                    text: root.dropAt.toFixed(1) + "s"
                    color: "#0b1018"
                    font.family: Theme.mono
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                }
            }
        }

        // ── The range ─────────────────────────────────────────────────────
        // Everything outside it, quietened. Not hidden and not greyed to
        // nothing: the rest of the scene is still there and you still have to
        // be able to read it — it is simply not what you are working on.
        Repeater {
            model: root.ranged ? [{ from: 0, to: root.markIn }, { from: root.markOut, to: root.scene.duration }] : []

            Rectangle {
                required property var modelData
                visible: modelData.to > modelData.from
                x: root.pad + modelData.from * root.pxPerSecond
                y: flick.contentY
                width: Math.max((modelData.to - modelData.from) * root.pxPerSecond, 0)
                height: flick.height
                z: 3
                color: Qt.rgba(0.02, 0.027, 0.039, 0.55)
            }
        }

        // The two edges of it, and their handles on the ruler.
        Repeater {
            model: root.ranged ? [{ at: root.markIn, tip: "in" }, { at: root.markOut, tip: "out" }] : []

            Item {
                required property var modelData
                x: root.pad + modelData.at * root.pxPerSecond
                y: flick.contentY
                width: 1
                height: flick.height
                z: 6

                Rectangle {
                    anchors.fill: parent
                    color: Theme.ok
                }

                Rectangle {
                    y: 6
                    x: parent.modelData.tip === "in" ? 0 : -13
                    width: 13
                    height: 13
                    color: Theme.ok
                    topLeftRadius: parent.modelData.tip === "in" ? 3 : 0
                    bottomLeftRadius: parent.modelData.tip === "in" ? 3 : 0
                    topRightRadius: parent.modelData.tip === "in" ? 0 : 3
                    bottomRightRadius: parent.modelData.tip === "in" ? 0 : 3

                    Text {
                        anchors.centerIn: parent
                        text: parent.parent.modelData.tip === "in" ? "I" : "O"
                        color: "#04170e"
                        font.family: Theme.mono
                        font.pixelSize: 9
                        font.weight: Font.DemiBold
                    }
                }
            }
        }

        // ── Where the scene's time joins ──────────────────────────────────
        // Every `wait()` in the code, drawn across every lane.
        //
        // It is the one place the language lets a change propagate: what is
        // before a wait has ended, what is after starts from it. So lengthening
        // an animation pushes what follows exactly when one of these lines sits
        // between them — the timeline does not invent a rule about rippling, it
        // shows the one the scene already has.
        //
        // The gap the wait leaves is drawn as well as the join: `wait(0.5)` is
        // half a second in which nothing is scheduled, and a bare line would say
        // it was instantaneous.
        //
        // The gap is painted OVER the lanes, and takes no clicks.
        //
        // Under them it could be twice as strong and cover nothing, which is why
        // it was there — but a clip drawn on top of a wait says the clip is in
        // front of it, and a clip is never in front of a wait: the wait is when
        // the clock stopped, and everything crossing it is crossing it. Over,
        // it has to be faint, and faint is all it needs to be now that the stamp
        // says what it is.
        //
        // A bare Rectangle takes no pointer at all — no MouseArea, no handler —
        // so the clip underneath still opens when you click through the band.
        // That is the whole trick: it is a drawing, not a surface.
        Repeater {
            model: root.scene.waits !== undefined ? root.scene.waits : []

            Rectangle {
                required property var modelData
                x: root.pad + modelData.at * root.pxPerSecond
                y: flick.contentY
                width: modelData.d * root.pxPerSecond
                height: flick.height
                z: 3
                // 0.325. It was 0.20 under the lanes and dropped to 0.16 when
                // it moved in front of them, on the guess that anything in
                // front had to be fainter. The guess was wrong twice over: this
                // far up it has to read as something LAID OVER the clips, and
                // under a third of red they are still perfectly legible.
                color: Qt.alpha(Theme.inkDim, 0.10)

                // The join, on the instant everything before it ended. Drawn
                // here, under every label: on the labels' own layer the line
                // of one gap ran through the writing of the gap before it.
                Rectangle {
                    width: 1
                    height: parent.height
                    color: Qt.alpha(Theme.inkDim, 0.45)
                }
            }
        }

        Repeater {
            model: root.scene.waits !== undefined ? root.scene.waits : []

            Item {
                id: join
                required property var modelData
                required property int index
                x: root.pad + modelData.at * root.pxPerSecond
                y: flick.contentY
                width: Math.max(modelData.d * root.pxPerSecond, 1)
                height: flick.height
                z: 4

                // Where it is written, so the line is a thing you can go to
                // rather than a mark you have to decode.
                // At the FOOT of the pane, not at its head: the head is the
                // ruler's and the space under the last lane is the only place a
                // label can sit without landing on a clip and becoming dark red
                // text on a green bar.
                //
                // And it is the gap's own value, so clicking it edits the line
                // that wrote it: `wait(0.3)` is one number in one call, which is
                // the smallest edit this timeline can make.
                Rectangle {
                    id: gapStamp
                    // From the gap's own start, like a clip from its first
                    // frame, and allowed to overhang its end: a gap half a
                    // second long is twelve pixels at the opening zoom and can
                    // hold no writing at all. Centred on the gap it read as a
                    // thing floating near it; pulled, it has to start where
                    // the time it stretches starts.
                    x: 0
                    y: join.height - height - 4 - root.stampRowOf[join.index] * (height + 3)
                    width: stampText.implicitWidth + 12
                    height: stampText.implicitHeight + 6
                    radius: 3
                    // Always on a ground of its own. The stamp sits at the foot
                    // of the pane, where a lane, the grid or a clip can pass
                    // behind it, and dark red on green is not a reading — a
                    // chip at 92% settles what it is written on. Not a backdrop
                    // blur: that is a ShaderEffectSource and a pass per stamp
                    // for the same answer.
                    color: editing || stampMouse.containsMouse
                           ? Qt.rgba(0.153, 0.086, 0.086, 0.94)
                           : Qt.alpha(Theme.sunk, 0.92)
                    border.width: 1
                    border.color: editing
                                  ? Qt.alpha(Theme.inkDim, 0.8)
                                  : Qt.alpha(Theme.inkDim, 0.22)
                    readonly property bool editing: root.editingWait === join.modelData.line

                    Text {
                        id: stampText
                        anchors.centerIn: parent
                        visible: !gapStamp.editing
                        text: "wait " + join.modelData.says.toFixed(1) + "s"
                        color: Theme.inkDim
                        font.family: Theme.mono
                        font.pixelSize: 10
                    }

                    TextInput {
                        id: stampEntry
                        anchors { fill: parent; leftMargin: 6; rightMargin: 6 }
                        verticalAlignment: TextInput.AlignVCenter
                        visible: gapStamp.editing
                        color: Theme.inkDim
                        font.family: Theme.mono
                        font.pixelSize: 10
                        selectByMouse: true

                        onAccepted: {
                            root.waitChanged(join.modelData.line, stampEntry.text.trim());
                            root.editingWait = -1;
                        }
                        Keys.onEscapePressed: root.editingWait = -1;
                        onActiveFocusChanged: if (!activeFocus && gapStamp.editing) root.editingWait = -1;
                    }

                    // The label is the gap's handle: click it to type the
                    // number, pull it sideways to stretch the gap itself. Not
                    // the band's edges — a handle laid over the lanes takes the
                    // pointer from the clips under it, and a gap usually starts
                    // exactly where a clip ends. Moving a gap's START is the
                    // same gesture on the gap BEFORE it.
                    MouseArea {
                        id: stampMouse
                        anchors.fill: parent
                        anchors.margins: -3
                        hoverEnabled: true
                        enabled: !gapStamp.editing
                        cursorShape: pressed && pulled ? Qt.SizeHorCursor : Qt.IBeamCursor
                        preventStealing: true

                        property real anchorX: 0
                        property bool pulled: false

                        // The label keeps the press even where a short pane
                        // lays it over a lane — handing it to the clip made the
                        // gaps unreachable in the default layout, where all
                        // three labels fall on one. The cost is small and
                        // local: a clip is not dragged from the fifty pixels
                        // its gap's label covers.
                        onPressed: (mouse) => {
                            anchorX = mapToItem(flick.contentItem, mouse.x, 0).x;
                            pulled = false;
                        }

                        onPositionChanged: (mouse) => {
                            if (!pressed)
                                return;
                            const px = mapToItem(flick.contentItem, mouse.x, 0).x - anchorX;
                            if (!pulled && Math.abs(px) < Application.styleHints.startDragDistance)
                                return;
                            pulled = true;
                            const ends = join.modelData.at + join.modelData.d;
                            root.dropAt = ends + root.travel(ends, px, (mouse.modifiers & Qt.ShiftModifier) === 0, true);
                        }

                        onCanceled: { pulled = false; root.dropAt = -1; }

                        onReleased: {
                            const at = root.dropAt;
                            root.dropAt = -1;
                            if (!pulled) {
                                root.editingWait = join.modelData.line;
                                // The number alone, not the sentence: what you
                                // are editing is the argument in the call.
                                stampEntry.text = join.modelData.says.toFixed(2);
                                stampEntry.forceActiveFocus();
                                stampEntry.selectAll();
                            } else if (at >= 0) {
                                root.waitDragged(join.modelData.line, at);
                            }
                            pulled = false;
                        }
                    }
                }

            }
        }

        // Drawn over every lane AND over the ruler: the playhead is the most
        // urgent thing on screen and never hides behind anything.
        Item {
            x: root.pad + root.playhead * root.pxPerSecond
            y: flick.contentY
            width: 1
            height: flick.height
            z: 6

            Rectangle {
                anchors.fill: parent
                color: Theme.bad
            }

            // The grab handle, which is also what makes the line findable when it
            // sits over a bright clip.
            Canvas {
                width: 11; height: 7
                x: -5
                onPaint: {
                    const ctx = getContext("2d");
                    ctx.reset();
                    ctx.fillStyle = Theme.bad;
                    ctx.beginPath();
                    ctx.moveTo(0, 0);
                    ctx.lineTo(width, 0);
                    ctx.lineTo(width / 2, height);
                    ctx.closePath();
                    ctx.fill();
                }
            }
        }
    }

    // The cursor of the gesture, for as long as it lasts. A handle is sixteen
    // pixels wide and the edge it pulls is magnetised: the pointer runs ahead
    // of it, leaves the handle, and the double arrow fell back to a plain arrow
    // in the middle of a stretch. Takes no button, so it takes nothing from the
    // area that holds the press — it only says what the hand is doing.
    MouseArea {
        anchors.fill: parent
        z: 100
        visible: root.heldLane >= 0
        acceptedButtons: Qt.NoButton
        cursorShape: root.heldIn !== root.heldOut ? Qt.SizeHorCursor : Qt.ClosedHandCursor
    }
}
