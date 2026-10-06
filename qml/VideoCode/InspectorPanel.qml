// The clip you clicked, as rows in the dock.
//
// The shape is the one Palmier Pro and Final Cut share: a title strip, then
// sections — a name, then a group — and inside each, one row per
// value, its label on the left and its value in a field on the right. Nothing
// travels and nothing is drawn against a ruler: what a clip DOES over time is
// the flying card's business (a double-click); what it IS, and what its line
// says, is this panel's.
//
// Three sections. The line's own arguments, as written; the metadata calls the
// line adds (position, scale…), one row per field, with what can still be
// added; and what the element is worth at the playhead — the stopwatch: a
// value typed there writes the animation that reaches it at that moment, and
// is refused while a line is already setting it.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root

    property var element: null
    property string buffer: ""
    property real playhead: 0
    // The folder the scene lives in: a picked file is written relative to it.
    property string baseDir: ""

    // ── What a type is called to a person ─────────────────────────────────
    readonly property var kindNames: ({
        "int": "number", "float": "number", "number": "number",
        "uint": "number ≥ 0", "ufloat": "number ≥ 0", "unumber": "number ≥ 0",
        "int8": "0–255", "uint8": "0–255",
        "wint": "units", "wfloat": "units", "wnumber": "units",
        "wuint": "units ≥ 0", "wufloat": "units ≥ 0", "wunumber": "units ≥ 0",
        "sec": "seconds", "frame": "frames", "degree": "degrees", "percent": "%",
        "index": "index", "url": "path", "point": "x, y", "v2": "x, y",
        "rgba": "color", "paint": "paint", "easing": "easing",
        "str": "text", "bool": "on/off", "attrName": "attribute"
    })
    function kindLabel(kind) {
        const inner = String(kind).match(/^maybe\[(.*)\]$/);
        if (inner !== null)
            return kindLabel(inner[1]) + " · optional";
        if (/^list\[/.test(kind))
            return "list";
        return kindNames[kind] !== undefined ? kindNames[kind] : kind;
    }

    // The values a closed type allows, for a menu; [] when it is open.
    function choicesFor(kind) {
        const bare = String(kind).replace(/^maybe\[(.*)\]$/, "$1");
        if (bare === "bool")
            return ["True", "False"];
        if (bare === "easing" && typeof Shell.easingCurves === "function")
            return Object.keys(Shell.easingCurves());
        if (typeof Shell.enumValues !== "function")
            return [];
        const found = Shell.enumValues(bare);
        return found.length > 0 ? found : Shell.enumValues(bare.charAt(0).toUpperCase() + bare.slice(1));
    }
    // Every name the buffer assigns — RATIO, square, marius — offered while a
    // field is typed in: a value here is Python, and its names are the file's.
    readonly property var namesInBuffer: {
        const seen = {};
        const out = [];
        const re = /^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=[^=]/gm;
        let m;
        while ((m = re.exec(root.buffer)) !== null)
            if (!seen[m[1]]) { seen[m[1]] = true; out.push(m[1]); }
        return out;
    }

    // What a type promises about a number — the same table as context.py —
    // so a field refuses a value the run would underline.
    readonly property var bounds: ({
        "uint8": [0, 255], "int8": [-128, 127], "percent": [0, 100],
        "uint": [0, null], "ufloat": [0, null], "unumber": [0, null],
        "wuint": [0, null], "wufloat": [0, null], "wunumber": [0, null],
        "sec": [0, null], "frame": [0, null]
    })
    // Why a value cannot be written, or "". An expression is judged by what
    // the scene makes of it; a name the scene does not know is left alone.
    function problem(kind, text) {
        const bare = String(kind).replace(/^maybe\[(.*)\]$/, "$1");
        const span = bounds[bare];
        if (span === undefined)
            return "";
        let value = Number(String(text).trim());
        if (isNaN(value) && typeof Shell.evalText === "function")
            value = Number(Shell.evalText(String(text)));
        if (isNaN(value))
            return "";
        if ((span[0] !== null && value < span[0]) || (span[1] !== null && value > span[1]))
            return span[1] !== null ? span[0] + "–" + span[1] : "≥ " + span[0];
        return "";
    }
    // The nearest value the type allows, for one it refuses.
    function nearest(kind, text) {
        const span = bounds[String(kind).replace(/^maybe\[(.*)\]$/, "$1")];
        let value = Number(String(text).trim());
        if (isNaN(value))
            value = Number(Shell.evalText(String(text)));
        return String(span[0] !== null && value < span[0] ? span[0] : span[1]);
    }

    function isPathKind(name, kind) {
        return kind === "url" || (kind === "str" && /path|file|url|src/i.test(name));
    }

    signal argumentWritten(var element, string call, string name, string value)
    signal metadataAdded(var element, string write)
    signal metadataWritten(var element, string call, string name, int at, string value)
    signal keyed(var element, string key, string value, int frame)
    signal jumpRequested(var element)
    signal renamed(var element, string name)
    signal says(string sentence)

    // The same two entry points as the card, so the shell talks to both alike.
    function open(what, where) { element = what; }

    // What became of an edit asked for here, when it was not what was typed:
    // `1 * RATIO` kept, a line of another file. `act`, when given, is the edit
    // that IS allowed instead, and the sentence is its button.
    function tell(what, act) { notice.show(what, act); }

    // The name just given, so the element is found again under it once the
    // scene has run: matched by index AND name, a renamed one would be lost.
    property string renamedTo: ""
    function follow(name) { renamedTo = name; }

    function rebind(elements) {
        if (element === null || element.index === undefined)
            return;
        const named = (one) => one.n === element.n || (renamedTo.length > 0 && one.n === renamedTo);
        for (const one of elements) {
            if (one.index === element.index && named(one)) {
                element = one;
                renamedTo = "";
                return;
            }
            for (const member of (one.members !== undefined ? one.members : [])) {
                if (member.index === element.index && member.n === element.n) {
                    element = member;
                    return;
                }
            }
        }
        element = null;
    }

    // ── What the line says ────────────────────────────────────────────────
    readonly property string cls: element !== null && element.cls !== undefined ? element.cls : ""
    readonly property string kind: element !== null && element.kind !== undefined ? element.kind : ""
    readonly property color hue: Theme.kind[kind] !== undefined ? Theme.kind[kind] : Theme.inkDim
    readonly property var arguments: cls.length > 0 ? Shell.inputParams(cls) : []
    readonly property bool writable: element !== null
                                     && element.line !== undefined && element.line > 0
                                     && cls.length > 0
                                     && Shell.callsOnLine(buffer, element.line).indexOf(cls) >= 0

    function written(name) {
        return root.writable ? Shell.readArgument(buffer, element.line, cls, name) : "";
    }
    function argOf(call, name) {
        return root.writable ? Shell.readArgument(buffer, element.line, call, name) : "";
    }
    function positionalOf(call, index) {
        return root.writable ? Shell.readPositional(buffer, element.line, call, index) : "";
    }
    // An enum typed by its short name is written in full: `WHITE` → `Color.WHITE`.
    function fullValue(param, text) {
        const typed = String(text).trim();
        const closed = typeof Shell.enumValues === "function" ? Shell.enumValues(param.kind) : [];
        for (const one of closed)
            if (one === typed || one.substring(one.lastIndexOf(".") + 1) === typed)
                return one;
        return typed;
    }
    function readable(value) {
        const rgba = String(value).match(/^\((\d+), *(\d+), *(\d+)(?:, *(\d+))?\)$/);
        if (rgba === null)
            return String(value);
        const hex = (n) => ("0" + Number(n).toString(16)).slice(-2);
        return "#" + hex(rgba[1]) + hex(rgba[2]) + hex(rgba[3])
                   + (rgba[4] !== undefined && Number(rgba[4]) !== 255 ? hex(rgba[4]) : "");
    }

    // ── What it is worth now ──────────────────────────────────────────────
    readonly property var meta: {
        if (root.element === null || root.element.index === undefined || typeof Shell.stateAt !== "function")
            return ({});
        return Shell.stateAt(root.element.index, Math.round(root.playhead * 30));
    }

    readonly property var argRows: root.arguments.map((one, i) => {
        // Named on the line, or given by position — `Video("clip.mov")`.
        const named = root.written(one.name);
        const asWritten = named.length > 0 ? named : root.positionalOf(root.cls, i);
        const live = root.meta["Args:" + one.name];
        const shown = asWritten.length > 0 ? asWritten : one.value;
        const now = live !== undefined ? root.readable(live) : "";
        const isColor = /color|paint|rgba/i.test(one.kind);
        // A named colour is asked of the scene itself: `BLUE_C` evaluates to
        // its tuple, which reads back as hex.
        let hex = now.startsWith("#") ? now : (/^"?#[0-9a-fA-F]{6}/.test(shown) ? shown.replace(/"/g, "") : "");
        if (isColor && hex.length === 0 && typeof Shell.evalText === "function") {
            const said = root.readable(Shell.evalText(shown));
            if (said.startsWith("#"))
                hex = said;
        }
        return { label: one.name, param: one, value: shown, isDefault: asWritten.length === 0,
                 now: now !== shown && !isColor ? now : "", kind: one.kind,
                 swatch: isColor && hex.length > 0 ? hex.substring(0, 7) : "",
                 choices: root.choicesFor(one.kind), isPath: root.isPathKind(one.name, one.kind) };
    })

    // The transform every element has, written on its line or not: position,
    // scale, rotation, opacity, align — Palmier's Transform panel, one row per
    // field. A row the line does not write shows the default, grey; typing in
    // it adds the call.
    readonly property var transforms: [
        { call: "position", fields: ["x", "y"], defaults: { x: "0", y: "0" } },
        { call: "scale", fields: ["factor"], defaults: { factor: "1" } },
        { call: "rotation", fields: ["degree"], defaults: { degree: "0" } },
        { call: "opacity", fields: ["o"], defaults: { o: "255" } },
        { call: "align", fields: ["x", "y"], defaults: { x: "0.5", y: "0.5" } }
    ]
    readonly property var metaRows: {
        if (root.element === null || root.cls.length === 0)
            return [];
        const on = root.writable ? Shell.callsOnLine(root.buffer, root.element.line) : [];
        let out = [];
        for (const t of root.transforms) {
            const params = Shell.inputParams(root.cls + "." + t.call);
            if (params.length === 0)
                continue;
            const written = on.indexOf(t.call) >= 0;
            t.fields.forEach((name) => {
                const i = params.findIndex((p) => p.name === name);
                if (i < 0)
                    return;
                const named = written ? root.argOf(t.call, name) : "";
                const given = named.length > 0 ? named : (written ? root.positionalOf(t.call, i) : "");
                out.push({ label: t.fields.length > 1 ? t.call + " · " + name : t.call,
                           call: t.call, name: name, at: i, param: params[i],
                           value: given.length > 0 ? given : t.defaults[name],
                           absent: !written || given.length === 0, spec: t });
            });
        }
        return out;
    }

    // The call a row adds when its line has none yet: the typed value in its
    // field, the defaults in the others — `position(x=3, y=0)`.
    function writeFor(spec, name, text) {
        const parts = spec.fields.map((f) => (spec.fields.length > 1 ? f + "=" : "") + (f === name ? text : spec.defaults[f]));
        return spec.call + "(" + parts.join(", ") + ")";
    }

    readonly property var nowRows: {
        const order = [
            ["Position X", "Position:x"], ["Position Y", "Position:y"],
            ["Scale X", "Scale:x"], ["Scale Y", "Scale:y"],
            ["Rotation", "Rotation"], ["Opacity", "Opacity"],
            ["Align X", "Align:x"], ["Align Y", "Align:y"]
        ];
        let out = [];
        for (const [label, key] of order)
            if (root.meta[key] !== undefined)
                out.push({ label: label, key: key, value: Number(root.meta[key]).toFixed(2) });
        return out;
    }

    // A value wears the colours the code pane gives it: a number, a string, a
    // NAME in capitals, a variable — so the Inspector and the buffer read alike.
    function painted(value) {
        const tok = Theme.code;
        const esc = (t) => t.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        const span = (t, c) => "<span style=\"color:" + c + "\">" + esc(t) + "</span>";
        let out = "";
        const re = /("[^"]*"|'[^']*'|\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_.]*|\s+|.)/g;
        let m;
        while ((m = re.exec(String(value))) !== null) {
            const t = m[0];
            if (/^["']/.test(t))
                out += span(t, tok.string);
            else if (/^\d/.test(t))
                out += span(t, tok.number);
            else if (/^[A-Za-z_]/.test(t))
                // A name is code: it wears the code pane's colour on a faint
                // pill, so it never reads as prose.
                out += "<span style=\"color:" + (/^[A-Z0-9_.]+$/.test(t.split(".").pop()) ? tok.caps : tok.variable)
                       + ";background-color:" + Theme.edge + "\">&nbsp;" + esc(t) + "&nbsp;</span>";
            else
                out += span(t, Theme.inkDim);
        }
        return out;
    }

    onElementChanged: if (element === null) notice.hide()

    // The code pane's notice, said again where the edit was asked for. Over the
    // bottom of the rows rather than in a row of its own, so nothing moves
    // under the pointer; it goes on its own, and sooner when it is only news.
    Rectangle {
        id: notice
        visible: false
        z: 5
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom; margins: 12 }
        height: said.implicitHeight + 14
        radius: 8
        color: Theme.panel
        border.width: 1
        border.color: act !== null ? Theme.live : Theme.edge

        property var act: null

        function show(what, action) {
            act = action !== undefined ? action : null;
            said.text = what;
            said.color = act !== null ? Theme.live : /added$/.test(what) ? Theme.ok : Theme.warn;
            visible = true;
            fade.interval = act !== null ? 7000 : 4000;
            fade.restart();
        }
        function hide() {
            visible = false;
            act = null;
        }

        Text {
            id: said
            anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 10 }
            wrapMode: Text.Wrap
            font.family: Theme.mono
            font.pixelSize: 11
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: notice.act !== null ? Qt.PointingHandCursor : Qt.ArrowCursor
            onClicked: {
                const act = notice.act;
                notice.hide();
                if (act !== null)
                    act();
            }
        }

        Timer {
            id: fade
            onTriggered: notice.hide()
        }
    }

    Text {
        anchors.centerIn: parent
        visible: root.element === null
        text: "click a clip"
        color: Theme.inkFaint
        font.family: Theme.ui
        font.pixelSize: 12
    }

    // ── One row: a label, a value — a field only when the pointer is on it ──
    component FieldRow: Item {
        id: row
        property string label: ""
        property string value: ""
        // Grey when the value is only the default the class would use anyway.
        property bool faint: false
        // What the playhead reads, when an effect has moved it off the line.
        property string now: ""
        property bool editable: true
        property bool last: false
        // The type the line expects, shown while the pointer is on the row.
        property string kind: ""
        // A colour's own colour, as a swatch that opens the picker; "" for none.
        property string swatch: ""
        // A closed type's values: the field becomes a menu.
        property var choices: []
        // A file: a button beside the value opens the system chooser.
        property bool isPath: false
        signal committed(string text)
        function beginEdit() { field.forceActiveFocus(); field.selectAll(); }

        width: parent !== null ? parent.width : 0
        height: 34

        // A MouseArea, not a TapHandler: under the slot's floor a handler never
        // sees the press (AgentPanel.qml says why). Pressing puts the caret in
        // the field with the value selected, ready to be overwritten.
        MouseArea {
            id: over
            anchors.fill: parent
            // Above the field: a press that reaches the TextInput first is lost
            // on its way through the Flickable; taken here, it lands.
            z: 2
            hoverEnabled: true
            // The cursor is this area's to give, being the topmost thing on the
            // row: a hand where a click edits, the caret once the field is
            // being typed in. A HoverHandler under it used to ask for the hand
            // and lose to the arrow every MouseArea claims from birth.
            cursorShape: !row.editable ? Qt.ArrowCursor : field.activeFocus ? Qt.IBeamCursor : Qt.PointingHandCursor
            onPressed: (mouse) => {
                if (!row.editable) { mouse.accepted = false; return; }
                if (row.isPath && mouse.x >= browse.x - 4 && mouse.x <= browse.x + browse.width + 4) {
                    const picked = typeof Shell.pickFile === "function" ? Shell.pickFile(root.baseDir) : "";
                    if (picked.length > 0) {
                        const rel = root.baseDir.length > 0 && picked.startsWith(root.baseDir + "/")
                                    ? picked.substring(root.baseDir.length + 1) : picked;
                        row.committed("\"" + rel + "\"");
                    }
                    return;
                }
                if (row.choices.length > 0) {
                    menu.open();
                    return;
                }
                row.beginEdit();
            }
            readonly property bool hovered: containsMouse
        }

        // Driven by the area above rather than a HoverTint of its own: a
        // MouseArea that takes hover keeps it from the siblings under it.
        Rectangle {
            anchors.fill: parent
            color: over.containsMouse ? Theme.hover : "transparent"
        }

        Text {
            id: labelText
            anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
            width: Math.min(implicitWidth, Math.max(40, parent.width - box.width - nowText.width - 36))
            text: row.label
            color: Theme.ink
            font.family: Theme.ui
            font.pixelSize: 12
            elide: Text.ElideRight
        }

        Text {
            anchors { left: labelText.right; leftMargin: 8; verticalCenter: parent.verticalCenter }
            visible: over.containsMouse && row.kind.length > 0
            text: root.kindLabel(row.kind)
            color: Theme.inkFaint
            font.family: Theme.mono
            font.pixelSize: 10
        }

        // "…", the way a Mac asks for a file.
        Rectangle {
            id: browse
            anchors { right: box.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
            visible: row.isPath && row.editable
            width: 24; height: 20; radius: 5
            color: Theme.rail
            border.width: 1
            border.color: Theme.edge
            Text { anchors.centerIn: parent; text: "…"; color: Theme.inkDim; font.pixelSize: 12 }
        }

        // A closed type's menu, under the field.
        Popup {
            id: menu
            x: box.x + box.width - width
            y: box.y + box.height + 4
            width: Math.max(box.width, 140)
            padding: 4
            background: Rectangle { color: Theme.panel; radius: 8; border.width: 1; border.color: Theme.edge }
            contentItem: Column {
                Repeater {
                    model: row.choices
                    Rectangle {
                        required property string modelData
                        width: menu.width - 8
                        height: 26
                        radius: 5
                        color: pick.containsMouse ? Qt.alpha(Theme.live, 0.15) : "transparent"
                        Text {
                            anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                            text: parent.modelData.split(".").pop()
                            color: parent.modelData === row.value || parent.modelData.split(".").pop() === row.value ? Theme.live : Theme.ink
                            font.family: Theme.mono
                            font.pixelSize: 11
                        }
                        MouseArea {
                            id: pick
                            anchors.fill: parent
                            hoverEnabled: true
                            onClicked: { row.committed(parent.modelData); menu.close(); }
                        }
                    }
                }
            }
        }

        // The colour, as a button: the system picker opens on it, and what is
        // chosen is written as rgba("#rrggbb"), which the scene reads back.
        Rectangle {
            id: dab
            anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
            visible: row.swatch.length > 0
            z: 3
            width: 16; height: 16; radius: 5
            color: row.swatch.length > 0 ? row.swatch : "transparent"
            border.width: 1
            border.color: dabHover.hovered ? Theme.live : Qt.rgba(1, 1, 1, 0.35)
            HoverHandler { id: dabHover; cursorShape: Qt.PointingHandCursor }
            MouseArea {
                anchors.fill: parent
                anchors.margins: -4
                onPressed: {
                    if (typeof Shell.pickColor !== "function")
                        return;
                    const hex = Shell.pickColor(row.swatch);
                    if (hex.length > 0)
                        row.committed("rgba(\"" + hex + "\")");
                }
            }
        }

        Text {
            id: nowText
            anchors { right: box.left; rightMargin: 8; verticalCenter: parent.verticalCenter }
            visible: row.now.length > 0
            width: visible ? implicitWidth : 0
            text: row.now
            color: Theme.inkFaint
            font.family: Theme.mono
            font.pixelSize: 10
        }

        // The value reads as text; the field around it only shows itself when
        // the pointer is there, the way a Settings row keeps its calm.
        Rectangle {
            id: box
            anchors { right: parent.right; rightMargin: row.swatch.length > 0 ? 32 : 10; verticalCenter: parent.verticalCenter }
            width: Math.min(150, Math.max(64, row.width * 0.42))
            height: 24
            radius: 6
            readonly property bool lit: row.editable && (over.hovered || field.activeFocus)
            color: lit ? Theme.sunk : "transparent"
            border.width: 1
            border.color: field.activeFocus ? Theme.live : lit ? Theme.edge : "transparent"

            // The coloured reading, under a field that only shows its own text
            // while it is being written in.
            Text {
                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                verticalAlignment: Text.AlignVCenter
                horizontalAlignment: Text.AlignRight
                visible: !field.activeFocus
                opacity: row.faint ? 0.6 : 1
                // Rich text cannot elide: a long value — a path — is drawn plain,
                // its head cut, since the end is the part that names the file.
                readonly property bool overflows: row.value.length > 20
                textFormat: overflows ? Text.PlainText : Text.RichText
                text: overflows ? row.value
                           : root.painted(row.value)
                             + (row.kind === "percent" ? "<span style=\"color:" + Theme.inkFaint + "\">%</span>" : "")
                             + (row.choices.length > 0 ? "<span style=\"color:" + Theme.inkFaint + "\"> ▾</span>" : "")
                color: /^["']/.test(row.value) ? Theme.code.string : Theme.ink
                font.family: Theme.mono
                font.pixelSize: 11
                elide: Text.ElideLeft
            }

            TextInput {
                id: field
                z: 1
                anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                verticalAlignment: TextInput.AlignVCenter
                horizontalAlignment: TextInput.AlignRight
                text: row.value
                color: activeFocus ? Theme.ink : "transparent"
                font.family: Theme.mono
                font.pixelSize: 11
                selectByMouse: true
                readOnly: !row.editable
                clip: true
                // A value past what the type allows is written as the nearest
                // one it does, and the bound is said: refusing left the field
                // red and the hand to do the arithmetic.
                // Said after the write, which has its own sentence to say:
                // the bound is the one worth reading.
                onAccepted: {
                    const why = root.problem(row.kind, text);
                    if (why.length > 0)
                        text = root.nearest(row.kind, text);
                    if (text !== row.value)
                        row.committed(text);
                    if (why.length > 0)
                        root.tell(row.label + " is " + why + " — set to " + text, null);
                    focus = false;
                }
                // Left without Enter: back to what the file says — unless what
                // was typed is out of bounds, which is fixed the same as on Enter.
                onActiveFocusChanged: {
                    if (activeFocus)
                        return;
                    if (root.problem(row.kind, text).length > 0)
                        accepted();
                    text = Qt.binding(() => row.value);
                }

                // The word under the caret, and the file's names that start with it.
                readonly property string word: {
                    const head = text.substring(0, cursorPosition);
                    const m = head.match(/[A-Za-z_][A-Za-z0-9_]*$/);
                    return m !== null ? m[0] : "";
                }
                readonly property var matches: word.length > 0 && row.choices.length === 0
                    ? root.namesInBuffer.filter((n) => n !== word && n.toLowerCase().startsWith(word.toLowerCase())).slice(0, 8)
                    : []
                function take(name) {
                    const at = cursorPosition;
                    const before = text.substring(0, at - word.length);
                    text = before + name + text.substring(at);
                    cursorPosition = before.length + name.length;
                }
            }
        }

        Popup {
            id: hints
            visible: field.activeFocus && field.matches.length > 0
            closePolicy: Popup.NoAutoClose
            x: box.x + box.width - width
            y: box.y + box.height + 4
            width: Math.max(box.width, 140)
            padding: 4
            background: Rectangle { color: Theme.panel; radius: 8; border.width: 1; border.color: Theme.edge }
            contentItem: Column {
                Repeater {
                    model: field.matches
                    Rectangle {
                        required property string modelData
                        width: hints.width - 8
                        height: 24
                        radius: 5
                        color: hintHover.containsMouse ? Qt.alpha(Theme.live, 0.15) : "transparent"
                        Text {
                            anchors { left: parent.left; leftMargin: 8; verticalCenter: parent.verticalCenter }
                            text: parent.modelData
                            color: /^[A-Z0-9_]+$/.test(parent.modelData) ? Theme.code.caps : Theme.code.variable
                            font.family: Theme.mono
                            font.pixelSize: 11
                        }
                        MouseArea {
                            id: hintHover
                            anchors.fill: parent
                            hoverEnabled: true
                            onPressed: { field.take(parent.modelData); field.forceActiveFocus(); }
                        }
                    }
                }
            }
        }

        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom; leftMargin: 14 }
            height: 1
            visible: !row.last
            color: Theme.edgeSoft
        }
    }

    // ── A section: a small title, then its rows in one rounded group ──────
    component Section: Column {
        id: section
        property string title: ""
        property string aside: ""
        default property alias rows: body.data
        width: parent !== null ? parent.width : 0
        spacing: 6
        topPadding: 14

        Item {
            width: parent.width
            height: 16

            Text {
                anchors { left: parent.left; leftMargin: 22; verticalCenter: parent.verticalCenter }
                text: section.title
                color: Theme.inkDim
                font.family: Theme.ui
                font.pixelSize: 11
                font.weight: Font.DemiBold
            }

            Row {
                anchors { right: parent.right; rightMargin: 22; verticalCenter: parent.verticalCenter }
                spacing: 8
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: section.aside
                    color: Theme.inkFaint
                    font.family: Theme.mono
                    font.pixelSize: 10
                }
            }
        }

        Rectangle {
            x: 12
            width: parent.width - 24
            height: body.height
            radius: 10
            color: Theme.rail
            border.width: 1
            border.color: Theme.edgeSoft
            clip: true

            Column {
                id: body
                width: parent.width
            }
        }
    }

    // A bare Flickable, as the timeline has: inside a Controls ScrollView the
    // rows never received a press under the slot's floor.
    Flickable {
        anchors.fill: parent
        visible: root.element !== null
        clip: true
        contentWidth: width
        contentHeight: sheet.height
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar {}

        Column {
            id: sheet
            width: root.width
            bottomPadding: 16

            // ── The header card: what it is ───────────────────────────────
            Item {
                width: parent.width
                height: 76

                Rectangle {
                    x: 12; y: 12
                    width: parent.width - 24
                    height: 56
                    radius: 10
                    color: Theme.rail
                    border.width: 1
                    border.color: Theme.edgeSoft

                    Rectangle {
                        id: dot
                        anchors { left: parent.left; leftMargin: 14; verticalCenter: parent.verticalCenter }
                        width: 26; height: 26; radius: 7
                        color: Qt.alpha(root.hue, 0.25)
                        border.width: 1
                        border.color: Qt.alpha(root.hue, 0.6)
                        Rectangle { anchors.centerIn: parent; width: 10; height: 10; radius: 3; color: root.hue }
                    }

                    // The name is a field: Enter renames it everywhere, here.
                    Rectangle {
                        id: nameText
                        anchors { left: dot.right; leftMargin: 6; top: parent.top; topMargin: 7 }
                        width: Math.min(nameField.implicitWidth + 16, parent.width - 130)
                        height: 22
                        radius: 5
                        readonly property bool lit: nameOver.hovered || nameField.activeFocus
                        color: lit ? Theme.sunk : "transparent"
                        border.width: 1
                        border.color: nameField.activeFocus ? Theme.live : lit ? Theme.edge : "transparent"
                        HoverHandler { cursorShape: Qt.IBeamCursor }
                        MouseArea {
                            id: nameOver
                            anchors.fill: parent
                            z: 2
                            hoverEnabled: true
                            onPressed: { nameField.forceActiveFocus(); nameField.selectAll(); }
                            readonly property bool hovered: containsMouse
                        }

                        TextInput {
                            id: nameField
                            z: 1
                            anchors { fill: parent; leftMargin: 4; rightMargin: 4 }
                            verticalAlignment: TextInput.AlignVCenter
                            text: root.element !== null && root.element.n !== undefined ? root.element.n : ""
                            color: Theme.ink
                            font.family: Theme.ui
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            selectByMouse: true
                            clip: true
                            validator: RegularExpressionValidator { regularExpression: /[A-Za-z_][A-Za-z0-9_]*/ }
                            onAccepted: {
                                if (root.element !== null && text !== root.element.n)
                                    root.renamed(root.element, text);
                                focus = false;
                            }
                            onActiveFocusChanged: if (!activeFocus) text = Qt.binding(() => root.element !== null && root.element.n !== undefined ? root.element.n : "")
                        }
                    }

                    Text {
                        anchors { left: dot.right; leftMargin: 10; top: nameText.bottom; topMargin: 1 }
                        text: root.cls + (root.element !== null && root.element.d > 0 ? "  ·  " + root.element.d.toFixed(1) + "s" : "")
                        color: Theme.inkFaint
                        font.family: Theme.ui
                        font.pixelSize: 11
                    }

                    Text {
                        anchors { right: parent.right; rightMargin: 14; verticalCenter: parent.verticalCenter }
                        text: root.element !== null && root.element.line > 0 ? "line " + root.element.line + "  ›" : ""
                        color: jump.hovered ? Theme.live : Theme.inkDim
                        font.family: Theme.ui
                        font.pixelSize: 11
                        MouseArea {
                            id: jump
                            anchors.fill: parent
                            anchors.margins: -6
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.jumpRequested(root.element)
                            readonly property bool hovered: containsMouse
                        }
                    }
                }
            }

            Section {
                title: "Arguments"
                aside: root.writable ? "" : "read only"

                Repeater {
                    model: root.argRows
                    FieldRow {
                        required property var modelData
                        required property int index
                        last: index === root.argRows.length - 1
                        label: modelData.label
                        value: modelData.value
                        faint: modelData.isDefault
                        now: modelData.now
                        kind: modelData.kind
                        swatch: modelData.swatch
                        choices: modelData.choices
                        isPath: modelData.isPath
                        editable: root.writable
                        onCommitted: (text) => root.argumentWritten(root.element, root.cls, modelData.label,
                                                                    root.fullValue(modelData.param, text))
                    }
                }
            }

            Section {
                title: "Transform"
                visible: root.metaRows.length > 0

                Repeater {
                    model: root.metaRows
                    FieldRow {
                        required property var modelData
                        required property int index
                        last: index === root.metaRows.length - 1
                        label: modelData.label
                        value: modelData.value
                        kind: modelData.param.kind
                        faint: modelData.absent
                        choices: root.choicesFor(modelData.param.kind)
                        onCommitted: (text) => {
                            if (modelData.absent)
                                root.metadataAdded(root.element, root.writeFor(modelData.spec, modelData.name, text));
                            else
                                root.metadataWritten(root.element, modelData.call, modelData.name,
                                                     modelData.at, root.fullValue(modelData.param, text));
                        }
                    }
                }

            }

            Section {
                title: "At the playhead"
                aside: root.playhead.toFixed(2) + "s"
                visible: root.nowRows.length > 0

                Repeater {
                    model: root.nowRows
                    FieldRow {
                        required property var modelData
                        required property int index
                        last: index === root.nowRows.length - 1
                        label: modelData.label
                        value: modelData.value
                        kind: modelData.key === "Opacity" ? "uint8" : "float"
                        faint: true
                        onCommitted: (text) => root.keyed(root.element, modelData.key, text.trim(), Math.round(root.playhead * 30))
                    }
                }
            }
        }
    }
}
