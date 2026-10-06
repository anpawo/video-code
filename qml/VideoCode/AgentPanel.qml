// The conversation, in the right-hand column.
//
// It sits in the dock rather than in a drawer because talking to the agent is not
// an interruption of editing — it IS editing here: what it answers with is code,
// and the code is the scene. So it gets a permanent column, and what used to live
// on the right (Properties, Effects) moves to the element you click.
//
// Its steps come first, folded: a grey line per stretch of reasoning and per
// tool it ran, a tool's line opening on its arguments and its result. Then what
// it says, and the answer ends on the lines it changed, each a link to its place
// in the code pane.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root

    signal sent(string text)
    // A changed line was clicked: its line and column once the turn is taken,
    // and its line in the coloured view shown until then. All 1-based.
    signal revealed(int line, int column, int shown)

    // The conversation, as it happens. Built by appending to a plain list
    // rather than by a model class: a turn is a handful of entries, and what
    // the pane needs from them is exactly what a ListView reads off an array.
    property var log: []

    // The answer being written, as an index into `log`, or -1 between turns.
    // Every sentence of one turn lands in that entry, so a question gets one
    // block back however many times the agent speaks.
    property int turn: -1

    // What the running counter reads. It only moves while the agent works, so
    // a finished answer keeps the time it took.
    property double now: 0

    // Whether the newest line is kept in view. Unfolding a step is reading, not
    // talking: the page stays where it is.
    property bool follows: true

    function append(entry) {
        root.follows = true;
        const grown = root.log.slice();
        grown.push(entry);
        root.log = grown;
    }

    function edit(index, changes) {
        root.follows = true;
        const grown = root.log.slice();
        grown[index] = Object.assign({}, grown[index], changes);
        root.log = grown;
    }

    function say(text) {
        const line = { kind: "text", text: text };
        if (root.turn < 0)
            root.append({ who: "agent", body: [line], started: 0, ended: 0 });
        else
            root.edit(root.turn, { body: root.log[root.turn].body.concat([line]) });
    }

    function amend(turn, index, changes) {
        const body = root.log[turn].body.slice();
        body[index] = Object.assign({}, body[index], changes);
        root.edit(turn, { body: body });
    }

    function step(entry) {
        if (root.turn >= 0)
            root.edit(root.turn, { body: root.log[root.turn].body.concat([entry]) });
    }

    // The count arrives several times for one stretch of reasoning, growing:
    // one line per stretch, not one per count.
    function think(tokens, text) {
        if (root.turn < 0)
            return;
        const body = root.log[root.turn].body;
        const last = body.length > 0 ? body[body.length - 1] : null;
        if (last !== null && last.kind === "thinking")
            root.amend(root.turn, body.length - 1, { tokens: Math.max(last.tokens, tokens), text: text.length > 0 ? text : last.text });
        else
            root.step({ kind: "thinking", tokens: tokens, text: text, open: false });
    }

    function toolEnd(id, output, failed) {
        if (root.turn < 0)
            return;
        const at = root.log[root.turn].body.findIndex((b) => b.kind === "tool" && b.id === id);
        if (at >= 0)
            root.amend(root.turn, at, { output: output, state: failed ? "bad" : "ok" });
    }

    function toggle(turn, index) {
        root.amend(turn, index, { open: !root.log[turn].body[index].open });
        root.follows = false;
    }

    // The changes a turn left, from the rows of its diff, one per run of
    // changed lines: where the run is once taken (`line`, `column` — the first
    // character that differs from the line it replaces), where it is in the
    // coloured view (`shown`, the first green line, else the first red one),
    // and what it now reads.
    function changesOf(rows) {
        const out = [];
        let shown = 0, kept = 0;
        for (let i = 0; i < rows.length;) {
            if (rows[i].kind === "same") {
                ++shown; ++kept; ++i;
                continue;
            }
            const was = [], now = [];
            let first = -1, firstGreen = -1;
            for (; i < rows.length && rows[i].kind !== "same"; ++i) {
                ++shown;
                if (first < 0)
                    first = shown;
                if (rows[i].kind === "add") {
                    if (firstGreen < 0)
                        firstGreen = shown;
                    now.push(rows[i].text);
                } else {
                    was.push(rows[i].text);
                }
            }
            let column = 0;
            if (now.length > 0 && was.length > 0)
                while (column < now[0].length && now[0][column] === was[0][column])
                    ++column;
            out.push({ line: kept + 1, column: column + 1, shown: firstGreen > 0 ? firstGreen : first,
                       text: (now.length > 0 ? now[0] : was[0]).trim(), removed: now.length === 0 });
            kept += now.length;
        }
        return out;
    }

    // Written under the answer that made them, as links: "Done." says nothing
    // about where to look, and these are where to look.
    function noteChanges(changes) {
        if (changes.length === 0)
            return;
        let at = root.log.length - 1;
        while (at >= 0 && root.log[at].who !== "agent")
            --at;
        if (at < 0)
            return;
        const shorten = (text) => (text.length > 60 ? text.slice(0, 57) + "…" : text).replace(/`/g, "'");
        const lines = changes.map((c) => "- [" + c.line + ":" + c.column + "](line:" + c.line + ":" + c.column + ":" + c.shown + ") "
                                         + (c.removed ? "removed " : "") + "`" + shorten(c.text) + "`");
        root.edit(at, { body: root.log[at].body.concat([{ kind: "changes", text: lines.join("\n") }]) });
    }

    function reveal(link) {
        const parts = link.split(":");
        if (parts.length === 4 && parts[0] === "line")
            root.revealed(Number(parts[1]), Number(parts[2]), Number(parts[3]));
    }

    function finish() {
        if (root.turn < 0)
            return;
        root.edit(root.turn, { ended: Date.now() });
        root.turn = -1;
    }

    function elapsed(entry) {
        const until = entry.ended > 0 ? entry.ended : root.now;
        const s = Math.max(0, Math.round((until - entry.started) / 1000));
        return s < 60 ? s + "s" : Math.floor(s / 60) + "m " + (s % 60) + "s";
    }

    Timer {
        interval: 1000
        repeat: true
        running: Agent.busy
        onTriggered: root.now = Date.now()
    }

    // Everything the agent says arrives as a signal, in the order it happened.
    // The pane does not ask for anything — it only writes down what it is told.
    Connections {
        target: Agent

        function onSaid(text) { root.say(text); }

        function onThinking(tokens, text) { root.think(tokens, text); }

        function onToolStarted(id, name, summary, input) {
            root.step({ kind: "tool", id: id, name: name, summary: summary, input: input, output: "", state: "run", open: false });
        }

        function onToolEnded(id, name, output, failed) { root.toolEnd(id, output, failed); }

        function onTurnEnded(cost, error) {
            if (error.length > 0)
                root.say("— " + error);
            root.finish();
        }

        function onChanged() { root.noteChanges(root.changesOf(Agent.diff())); }

        function onFailed(why) {
            root.say(why);
            root.finish();
        }
    }

    ScrollView {
        id: scroll
        anchors { left: parent.left; right: parent.right; top: parent.top; bottom: composer.top }
        clip: true

        Column {
            width: root.width
            spacing: 20
            // The newest line is the one being read: keep the bottom in view.
            onHeightChanged: if (root.follows) scroll.contentItem.contentY = Math.max(0, height - scroll.height)
            topPadding: 12
            bottomPadding: 8
            leftPadding: 16
            rightPadding: 16

            Repeater {
                model: root.log

                // The question sits on the right in a soft pill; the answer is
                // bare text on the left, the way Palmier Pro draws its chat —
                // where each side is on the page says who spoke, so no badge
                // and no frame has to.
                Item {
                    id: msg
                    required property var modelData
                    required property int index
                    readonly property bool mine: msg.modelData.who === "me"
                    readonly property real avail: root.width - 32
                    width: avail
                    height: mine ? pill.height : answer.implicitHeight

                    Rectangle {
                        id: pill
                        visible: msg.mine
                        anchors.right: parent.right
                        width: Math.min(mineText.implicitWidth + 28, msg.avail - 48)
                        height: mineText.implicitHeight + 16
                        radius: 14
                        color: Qt.alpha(Theme.ink, 0.08)

                        Text {
                            id: mineText
                            x: 14
                            y: 8
                            width: parent.width - 28
                            text: msg.mine ? msg.modelData.body.map(b => b.text).join("\n") : ""
                            color: Theme.ink
                            font.family: Theme.ui
                            font.pixelSize: 12
                            lineHeight: 1.4
                            wrapMode: Text.WordWrap
                        }
                    }

                    Column {
                        id: answer
                        visible: !msg.mine
                        width: parent.width
                        // Steps sit close, like the lines of a list; words keep
                        // the air they had, as padding above them.
                        spacing: 4

                        Repeater {
                            model: msg.mine ? [] : msg.modelData.body

                            Column {
                                id: part
                                required property var modelData
                                required property int index
                                readonly property bool isTool: modelData.kind === "tool"
                                readonly property bool isStep: isTool || modelData.kind === "thinking"
                                // Reasoning the stream withheld has nothing to open on.
                                readonly property bool opens: isTool || (isStep && modelData.text.length > 0)
                                width: answer.width
                                spacing: 4

                                // The agent answers in Markdown.
                                Text {
                                    visible: !part.isStep
                                    width: parent.width
                                    topPadding: part.index > 0 ? 6 : 0
                                    text: part.isStep ? "" : part.modelData.text
                                    textFormat: Text.MarkdownText
                                    color: Theme.ink
                                    font.family: Theme.ui
                                    font.pixelSize: 12
                                    lineHeight: 1.4
                                    wrapMode: Text.WordWrap
                                    onLinkActivated: (link) => root.reveal(link)
                                    HoverHandler { cursorShape: parent.hoveredLink.length > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor }
                                }

                                Item {
                                    id: fold
                                    visible: part.isStep
                                    width: parent.width
                                    height: 16

                                    Text {
                                        id: chevron
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 12
                                        text: !part.opens ? "" : part.modelData.open ? "▾" : "▸"
                                        color: Theme.inkFaint
                                        font.family: Theme.ui
                                        font.pixelSize: 13
                                    }
                                    Text {
                                        id: name
                                        anchors { left: chevron.right; verticalCenter: parent.verticalCenter }
                                        text: part.isTool ? part.modelData.name
                                            : !part.isStep ? ""
                                            : (msg.modelData.ended === 0 && part.index === msg.modelData.body.length - 1 ? "Thinking" : "Thought")
                                              + (part.modelData.tokens > 0 ? " · " + part.modelData.tokens + " tokens" : "")
                                        color: Theme.inkDim
                                        font.family: Theme.ui
                                        font.pixelSize: 11
                                        font.italic: !part.isTool
                                    }
                                    Text {
                                        id: mark
                                        visible: part.isTool
                                        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                                        text: !part.isTool ? "" : part.modelData.state === "ok" ? "✓" : part.modelData.state === "bad" ? "✗" : "…"
                                        color: !part.isTool ? Theme.inkFaint : part.modelData.state === "ok" ? Theme.ok
                                             : part.modelData.state === "bad" ? Theme.bad : Theme.inkFaint
                                        font.family: Theme.ui
                                        font.pixelSize: 11
                                    }
                                    Text {
                                        visible: part.isTool
                                        anchors { left: name.right; leftMargin: 8; right: mark.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
                                        text: part.isTool && part.modelData.summary !== part.modelData.name ? part.modelData.summary.split("\n")[0] : ""
                                        // A path is told apart by its end, a command by its start.
                                        elide: text.startsWith("/") ? Text.ElideLeft : Text.ElideRight
                                        color: Theme.inkFaint
                                        font.family: Theme.mono
                                        font.pixelSize: 10
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        enabled: part.opens
                                        cursorShape: part.opens ? Qt.PointingHandCursor : undefined
                                        onClicked: root.toggle(msg.index, part.index)
                                    }
                                }

                                Rectangle {
                                    visible: part.opens && part.modelData.open
                                    x: 12
                                    width: parent.width - 12
                                    height: unfolded.implicitHeight + 16
                                    radius: 6
                                    color: Theme.sunk
                                    border.width: 1
                                    border.color: Theme.edgeSoft

                                    Column {
                                        id: unfolded
                                        x: 10
                                        y: 8
                                        width: parent.width - 20
                                        spacing: 8

                                        Text {
                                            width: parent.width
                                            text: !part.isStep ? "" : part.isTool ? part.modelData.input : part.modelData.text
                                            color: Theme.inkDim
                                            font.family: part.isTool ? Theme.mono : Theme.ui
                                            font.pixelSize: part.isTool ? 10 : 11
                                            font.italic: !part.isTool
                                            wrapMode: Text.WrapAnywhere
                                        }
                                        Rectangle {
                                            visible: result.visible
                                            width: parent.width
                                            height: 1
                                            color: Theme.edgeSoft
                                        }
                                        Text {
                                            id: result
                                            visible: part.isTool && part.modelData.state !== "run"
                                            width: parent.width
                                            text: !part.isTool ? "" : part.modelData.output.length > 0 ? part.modelData.output : "(nothing)"
                                            color: part.isTool && part.modelData.state === "bad" ? Theme.bad : Theme.inkDim
                                            font.family: Theme.mono
                                            font.pixelSize: 10
                                            wrapMode: Text.WrapAnywhere
                                        }
                                    }
                                }
                            }
                        }

                        // Three dots breathing in turn while it works; the time
                        // it took, faint, once it is done.
                        Row {
                            id: dots
                            visible: msg.modelData.started > 0 && msg.modelData.ended === 0
                            topPadding: 6
                            spacing: 5
                            property int phase: 0
                            Timer {
                                interval: 280
                                repeat: true
                                running: dots.visible && !Theme.reducedMotion
                                onTriggered: dots.phase = (dots.phase + 1) % 3
                            }
                            Repeater {
                                model: 3
                                Rectangle {
                                    required property int index
                                    width: 5; height: 5; radius: 2.5
                                    color: Theme.inkDim
                                    opacity: dots.phase === index ? 1 : 0.25
                                    Behavior on opacity { NumberAnimation { duration: 250 } }
                                }
                            }
                        }

                        Text {
                            visible: msg.modelData.ended > 0
                            topPadding: 6
                            text: msg.modelData.ended > 0 ? root.elapsed(msg.modelData) : ""
                            color: Theme.inkFaint
                            font.family: Theme.mono
                            font.pixelSize: 10
                        }
                    }
                }
            }
        }
    }

    // Clicking anywhere in the column means "I want to talk": the caret lands
    // in the field without aiming at the field.
    //
    // Over the content and declining the press it just saw — the same shape as
    // Panel.qml's `floor`, and for the same reason. A TapHandler here was tried
    // first and never fired over the empty transcript: the pane's own floor
    // takes the press, and the ScrollView's Flickable takes the grab, so no tap
    // is ever recognised. Declining the press instead leaves the scroll, the
    // links and the field itself working exactly as before.
    MouseArea {
        anchors.fill: parent
        z: 50
        acceptedButtons: Qt.LeftButton
        cursorShape: undefined // it hands the press back; the cursor is not its to say either
        onPressed: (mouse) => {
            input.forceActiveFocus();
            mouse.accepted = false;
        }
    }

    // No rule between what you read and what you write: one conversation, and
    // the field's own rounded edge already says "type here".
    Item {
        id: composer
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        height: 84

        Rectangle {
            id: box
            anchors.fill: parent
            anchors.margins: 10
            anchors.topMargin: 4
            radius: 20
            color: Theme.rail
            border.width: 1
            border.color: input.activeFocus ? Qt.alpha(Theme.live, 0.55) : Theme.edge

            TextField {
                id: input
                anchors { left: parent.left; right: parent.right; top: parent.top }
                height: 36
                leftPadding: 14
                rightPadding: 14
                topPadding: 10
                placeholderText: Agent.busy ? "Working…" : "Ask for an edit…"
                placeholderTextColor: Theme.inkFaint
                color: Theme.ink
                font.family: Theme.ui
                font.pixelSize: 12
                background: null
                enabled: !Agent.busy
                onAccepted: root.ask(text)
            }

            // After the field, so it hears the pointer before the field keeps
            // it; before the send button, which has its own.
            HoverTint {}

            // Send, as a round button; stop while it works.
            Rectangle {
                id: send
                anchors { right: parent.right; bottom: parent.bottom; margins: 7 }
                width: 24; height: 24; radius: 12
                readonly property bool canSend: !Agent.busy && input.text.length > 0
                color: Agent.busy ? Qt.alpha(Theme.ink, 0.12) : Theme.ai
                opacity: Agent.busy || canSend ? 1 : 0.45

                Text {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: Agent.busy ? 0 : -0.5
                    text: Agent.busy ? "■" : "↑"
                    color: Agent.busy ? Theme.ink : Theme.ground
                    font.family: Theme.ui
                    font.pixelSize: Agent.busy ? 9 : 13
                    font.weight: Font.Bold
                }

                HoverTint {}

                MouseArea {
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    onClicked: Agent.busy ? Agent.interrupt() : root.ask(input.text)
                }
            }
        }
    }

    function ask(text) {
        if (text.length === 0 || Agent.busy)
            return;
        root.append({ who: "me", body: [{ kind: "text", text: text }] });
        // The answer's block opens before a word of it: until a first step
        // arrives, its dots are what say the agent is working.
        root.now = Date.now();
        root.append({ who: "agent", body: [], started: root.now, ended: 0 });
        root.turn = root.log.length - 1;
        // The shell asks, not the pane: it prefixes what the author is
        // looking at, and only it knows.
        root.sent(text);
        input.text = "";
    }
}
