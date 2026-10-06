// The scene's source, and everything the editor knows about it.
//
// The buffer is the scene: gestures on the timeline rewrite it, and it reaches
// the filesystem when you save. What makes this an editor rather than a text box
// is the language server behind it — diagnostics, hovers, completion,
// signatures, definitions, references and rename all come from LSP, and each one
// is a few lines here because the protocol does the thinking.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root

    property alias text: editor.text

    // What an agent turn changed, as `{kind, text}` rows in file order —
    // "same", "add" or "del". Empty when nothing is pending.
    //
    // The diff is shown HERE and not in the agent pane on purpose: what an edit
    // did to a scene is a fact about this file, and reading it anywhere else
    // means holding two places in your head at once. The buffer carries the
    // merged view while it is pending — the old lines and the new ones — so the
    // text on screen is briefly not valid Python. That is why the analyser is
    // told to hold: see `diffPending`.
    property var diffRows: []

    // The lines a hand on the timeline is about to change, lit before the
    // release writes them: `{ line, from, to, text, note, refused }`, lines
    // from 1. `from`–`to` is the part of the line that changes; `text`, when
    // it is not empty, is the whole line as it will read, drawn over the one
    // in the buffer — which is never touched; `note` is said after the line:
    // a statement that will be written under it, or why the gesture is refused.
    property var aimed: []
    onAimedChanged: if (aimed.length > 0) reveal(aimed[0].line)

    // Scrolled only as far as it takes: a pane that jumps at every hover is a
    // pane you stop reading.
    function reveal(line) {
        const flick = view.contentItem as Flickable;
        const top = editor.topPadding + (line - 1) * gutter.lineHeight;
        if (top < flick.contentY)
            flick.contentY = Math.max(0, top - gutter.lineHeight);
        else if (top + gutter.lineHeight > flick.contentY + view.height)
            flick.contentY = top + 2 * gutter.lineHeight - view.height;
    }
    readonly property bool diffPending: diffRows.length > 0
    property string name: "untitled.py"
    // Whether the buffer differs from what is on disk. Shown by the pane's tab,
    // which is the only place left that can show it now that the pane has no
    // strip of its own.
    property bool modified: false

    signal saveRequested()

    // The line the caret is on, always — unlike `writingLine`, which is the
    // line being typed into and only while the analyser is held back. The
    // timeline reads it to light the bar the line makes.
    readonly property int caretLine: root.locationAt(editor.cursorPosition).line

    // Play the scene from the moment this line makes. Raised here rather than
    // bound to a window Shortcut for the reason `executeRequested` is: this is
    // where the key is actually pressed, and a Shortcut is matched by the
    // platform's handler, which a synthetic event never reaches.
    signal playFromCaret()

    // Run the scene. Handled here as well as by the window's Shortcut, because
    // this is where the key is actually pressed — and because a Qt Shortcut is
    // matched by the platform's key handler, so a synthetic event never reaches
    // it and the whole path would be untestable.
    signal executeRequested()

    // The buffer's document, offered once it exists. The panel does not know
    // what a syntax highlighter is or that a C++ shell exists — it says "here is
    // the document" and the shell decides what to do about it.
    // `signature` : le document est une bulle, pas le buffer. Les deux sont
    // du Python, mais un paramètre déclaré ne s'écrit que dans une signature.
    signal documentReady(var document, bool signature)

    // The document the buffer is painted through, kept so the shell can hand it
    // the analyser's tokens when they arrive.
    property var document: null

    // Whether this file can be written at all. A file outside the project is
    // shown but never saved — following a definition into a library is reading,
    // not editing, and the pane says so rather than swallowing the ⌘S.
    readonly property bool readOnly: root.path.length > 0 && !Shell.writable(root.path)

    // True while a file is being swapped in. Every edit the pane reports during
    // that moment is the swap itself, not something a person typed.
    property bool loading: false

    // A file has been swapped in, and this is what it holds.
    signal opened(string where, string body)

    // ── What the language server found ────────────────────────────────────
    // Raw LSP diagnostics: { range: { start/end: { line, character } },
    // severity, message, source }. Kept in the protocol's shape rather than
    // translated, so that adding a field never means touching a converter.
    property var diagnostics: []

    // What the RUN said — the warnings `execSource` collects, and the failure
    // when a scene does not run at all. Kept in a list of its own because the
    // analyser publishes a WHOLE list on every pause in typing: anything written
    // into `diagnostics` beside it is erased a second later, which is how the
    // run's warnings were drawn and then quietly dropped before anyone read one.
    property var runFlaws: []

    // ── Not while you are still writing it ────────────────────────────────
    // A half-typed line is not a mistake, and being told it is one is noise you
    // learn to ignore — which is how a real error later goes unread.
    //
    // The analyser already waits: pyright backs off 250 ms from the last thing
    // you did and re-arms that on every keystroke, so it never runs mid-word.
    // What it cannot know is WHERE your hands are. It answers about the whole
    // file, and the answer arrives the moment you pause — including about the
    // line you are in the middle of.
    //
    // So the pane holds back only that line, and only while you are typing:
    // everything else in the file is reported as it always was, and the line you
    // are on joins them once you have been still for `settleDelay`.
    readonly property int settleDelay: 600
    property bool settling: false
    property int writingLine: -1

    function noteEdit() {
        root.settling = true;
        root.writingLine = root.locationAt(editor.cursorPosition).line;
        settle.restart();
    }

    Timer {
        id: settle
        interval: root.settleDelay
        onTriggered: {
            root.settling = false;
            root.writingLine = -1;
        }
    }

    // What is actually shown: everything, minus what is being written.
    readonly property var shownDiagnostics: {
        const all = root.diagnostics.concat(root.runFlaws);
        if (!root.settling || root.writingLine < 0)
            return all;
        return all.filter((d) => d.range.start.line !== root.writingLine);
    }

    // One size for everything that shows code or sits beside it. VS Code's
    // hovers and lists are drawn at the editor's own size, and the difference
    // shows: a signature a step smaller than the line it explains reads as a
    // footnote rather than as the answer.
    readonly property int codeSize: editor.font.pixelSize

    // Where the caret is, for whoever is told what the author is looking at.
    readonly property int cursorLine: editor.currentLine

    // The buffer's file on disk. The language server reasons about paths, so a
    // pane with no path simply has no intelligence — everything below degrades
    // to a plain editor rather than breaking.
    property string path: ""

    // ── Where you have been ───────────────────────────────────────────────
    // Following a definition into another file is only useful if coming back is
    // free. Two stacks, the browser's model, because it is the one everybody
    // already has in their fingers — and ⌘← / ⌘→ are the keys they press.
    property var back: []
    property var forward: []

    // Opening a file the pane was not showing. The buffer is told to the server
    // as it opens, because a file nobody has opened has no diagnostics and
    // answers no questions about itself.
    // Put text in the buffer that did NOT come from a person: an agent's edit,
    // or the file being put back after one. Goes through the same gate as
    // `load` — `ready` off — so it is not counted as a modification and does
    // not wake the analyser on a buffer that may be holding both sides of a
    // diff.
    function showAgentEdit(body) {
        editor.ready = false;
        root.replaceWhole(body);
        editor.pristine = body;
        root.modified = false;
        editor.ready = true;
        // The server is told only about text that is really the file. While a
        // diff is pending the buffer is a merged view, and telling pyright about
        // it would answer with errors about lines nobody wrote.
        if (!root.diffPending && root.path.length > 0)
            Lsp.changeDocument(root.path, body);
    }

    function load(where, line, character) {
        if (where !== root.path) {
            const body = Shell.readTextFile(where);

            // The PATH is set before the text, and the shell is told to hold
            // its sync while both move.
            //
            // Assigning the text first fires the change signal while `path`
            // still names the file being left — so the shell dutifully told the
            // server that scene.py now contained Rectangle.py, and coming back
            // told it the opposite. One jump and back left the analyser holding
            // two files' contents under each other's names, which is why the
            // return landed on sixty diagnostics that were not there before.
            root.loading = true;
            editor.ready = false;
            root.path = where;
            editor.text = body;
            editor.pristine = body;
            root.name = where.split("/").pop();
            root.modified = false;
            root.diagnostics = [];
            editor.ready = true;
            root.loading = false;

            // The one true statement about this file, made once and by hand.
            Lsp.openDocument(where, body);
            root.opened(where, body);
        }
        if (line !== undefined) {
            editor.cursorPosition = root.offsetOf(line, character !== undefined ? character : 0);
            // The line asked for, shown a third of the way down rather than at
            // the very bottom edge where a jump usually lands it.
            (view.contentItem as Flickable).contentY =
                Math.max(0, editor.cursorRectangle.y - view.height / 3);
        }
        // Only a pane you can see takes the caret. Following a definition is a
        // request to type; the scene loaded at startup, into a pane that is not
        // even in the dock yet, is not — and taking the keyboard there is how
        // Space stopped playing.
        if (root.visible)
            editor.forceActiveFocus();
    }

    // A jump is a load that remembers what it left, and forgets the way
    // forward — same as clicking a link after going back.
    function jump(where, line, character) {
        if (root.path.length > 0)
            root.back = root.back.concat([{ path: root.path, offset: editor.cursorPosition }]);
        root.forward = [];
        root.load(where, line, character);
    }

    function goBack() {
        if (root.back.length === 0)
            return;
        const mark = root.back[root.back.length - 1];
        root.back = root.back.slice(0, -1);
        root.forward = root.forward.concat([{ path: root.path, offset: editor.cursorPosition }]);
        root.load(mark.path);
        editor.cursorPosition = Math.min(mark.offset, editor.text.length);
    }

    function goForward() {
        if (root.forward.length === 0)
            return;
        const mark = root.forward[root.forward.length - 1];
        root.forward = root.forward.slice(0, -1);
        root.back = root.back.concat([{ path: root.path, offset: editor.cursorPosition }]);
        root.load(mark.path);
        editor.cursorPosition = Math.min(mark.offset, editor.text.length);
    }

    // A list from the server arrives as a JS-array-LIKE object, not a JS array:
    // Array.isArray() is false for it, which silently turned every reply into
    // "not a list" and made go-to-definition do nothing at all. Length is the
    // honest test on this side of the bridge.
    function listed(reply) {
        if (reply === undefined || reply === null)
            return [];
        if (typeof reply === "string")
            return [reply];
        return reply.length !== undefined ? reply : [reply];
    }

    // A definition reply is one location, a list of them, or a link with the
    // target range spelled differently. All three name a file and a line.
    function follow(reply) {
        const first = root.listed(reply)[0];
        if (!first)
            return;
        const where = first.uri !== undefined ? first.uri : first.targetUri;
        const range = first.range !== undefined ? first.range : first.targetSelectionRange;
        if (where === undefined || range === undefined)
            return;
        root.jump(where.replace("file://", ""), range.start.line, range.start.character);
    }

    // ── Renaming, everywhere at once ──────────────────────────────────────
    // The server answers with a WorkspaceEdit: every file that mentions the
    // name, and where in it. Most of those files are not open — a rename that
    // only fixed the visible buffer would leave the project broken, so the
    // edits go to disk.
    //
    // Edits are applied from the END of each file backwards, because applying
    // one from the top moves every offset below it.
    function applyEdit(edit) {
        if (!edit)
            return 0;

        // Two spellings of the same thing, both legal.
        let byFile = ({});
        if (edit.changes !== undefined) {
            for (const uri in edit.changes)
                byFile[uri.replace("file://", "")] = root.listed(edit.changes[uri]);
        }
        for (const change of root.listed(edit.documentChanges)) {
            if (change.textDocument === undefined)
                continue;
            byFile[change.textDocument.uri.replace("file://", "")] = root.listed(change.edits);
        }

        let touched = 0;
        for (const where in byFile) {
            const open = where === root.path;
            let body = open ? editor.text : Shell.readTextFile(where);
            if (body.length === 0 && !open)
                continue;

            let edits = [];
            for (const one of byFile[where])
                edits.push(one);
            edits.sort(function (a, b) {
                return b.range.start.line - a.range.start.line
                    || b.range.start.character - a.range.start.character;
            });

            const lines = body.split("\n");
            for (const one of edits) {
                const line = lines[one.range.start.line];
                if (line === undefined)
                    continue;
                // Single-line edits only: renaming a symbol never spans lines,
                // and pretending to handle what cannot happen hides the day it
                // does behind a silently wrong buffer.
                if (one.range.end.line !== one.range.start.line)
                    continue;
                lines[one.range.start.line] = line.substring(0, one.range.start.character)
                                            + one.newText
                                            + line.substring(one.range.end.character);
            }

            const next = lines.join("\n");
            if (open) {
                root.replaceWhole(next);
            } else if (!Shell.writeTextFile(where, next)) {
                continue;
            }
            ++touched;
        }
        return touched;
    }

    // A line/character pair is where the protocol counts; a character offset is
    // where a TextArea counts. One walk of the buffer converts between them.
    function offsetOf(line, character) {
        const lines = editor.text.split("\n");
        let offset = 0;
        for (let i = 0; i < line && i < lines.length; ++i)
            offset += lines[i].length + 1;
        // A line past the last one is the end of the text, not one character
        // beyond it: a file that does not end in a newline has no "start of the
        // next line", and a squiggle or a caret sent there made Qt warn on every
        // repaint (QTextCursor::setPosition: Position out of range).
        return Math.min(offset + Math.min(character, line < lines.length ? lines[line].length : 0), editor.text.length);
    }

    // The other direction: where the mouse is, told in the protocol's terms.
    // Renommer un élément depuis ailleurs dans la fenêtre — un double-clic sur
    // son clip, son nom sur sa fiche. Le curseur se pose là où la ligne le
    // déclare et le renommage du volet prend la suite : une seule boîte, un seul
    // chemin par le serveur de langage, et tous les fichiers qui s'en servent.
    function renameAt(line, name) {
        const rows = editor.text.split("\n");
        if (line < 1 || line > rows.length)
            return false;
        const column = rows[line - 1].indexOf(name);
        if (column < 0)
            return false;
        let offset = 0;
        for (let i = 0; i < line - 1; i++)
            offset += rows[i].length + 1;
        root.takeFocus();
        editor.cursorPosition = offset + column;
        renaming.begin();
        return true;
    }

    // The same rename, given its answer up front: no box, no caret moved, the
    // Inspector's field already asked. Every occurrence, every file, as ever.
    function renameTo(line, name, wanted, then) {
        const rows = editor.text.split("\n");
        if (line < 1 || line > rows.length || wanted.length === 0 || wanted === name)
            return false;
        const column = rows[line - 1].indexOf(name);
        if (column < 0)
            return false;
        const at = { line: line - 1, character: column };
        Lsp.rename(root.path, at.line, at.character, wanted, function (edit) {
            const touched = root.applyEdit(edit);
            notice.say(touched === 0
                       ? "nothing to rename"
                       : "renamed in " + touched + (touched === 1 ? " file" : " files"));
            if (touched > 0 && root.path.length > 0)
                Lsp.changeDocument(root.path, editor.text);
            if (then !== undefined)
                then(touched);
        });
        return true;
    }

    // The whole buffer, as ONE thing to undo: only the span that differs is
    // replaced, through the document, so a rename, an agent's turn or a file
    // put back are each a single ⌘Z — and the caret stays put. Assigning
    // `editor.text` would wipe the undo stack instead.
    function replaceWhole(next) {
        const cur = editor.text;
        if (cur === next)
            return true;
        if (cur.length === 0) {
            editor.text = next;
            return true;
        }
        const most = Math.min(cur.length, next.length);
        let head = 0;
        while (head < most && cur.charCodeAt(head) === next.charCodeAt(head))
            ++head;
        let tail = 0;
        while (tail < most - head
               && cur.charCodeAt(cur.length - 1 - tail) === next.charCodeAt(next.length - 1 - tail))
            ++tail;
        return root.replaceRange(head, cur.length - tail, next.substring(head, next.length - tail));
    }

    // The editor's own undo, for a ⌘Z pressed from another pane.
    readonly property bool editorHasFocus: editor.activeFocus
    function undo() { editor.undo(); }

    function locationAt(offset) {
        const before = editor.text.substring(0, offset).split("\n");
        return { line: before.length - 1, character: before[before.length - 1].length };
    }

    // A hover reply is markdown, or a plain string, or a list of either — three
    // shapes the protocol allows and every server picks from differently. What
    // the pane wants is text, so all three collapse to one here, and the code
    // fences go: the bubble is monospaced already, and ``` on its own line is
    // noise the reader has to look past.
    function readable(reply) {
        if (!reply || !reply.contents)
            return { code: "", prose: "" };
        const parts = root.listed(reply.contents);
        let out = [];
        for (const part of parts)
            out.push(typeof part === "string" ? part : (part.value !== undefined ? part.value : ""));
        const whole = out.join("\n");

        // The fenced block is the SIGNATURE and everything else is the
        // docstring. Kept apart because they are read differently: one is code
        // and gets coloured like code, the other is a sentence.
        let code = "";
        let prose = whole;
        const fenced = /```[a-z]*\n([\s\S]*?)```/.exec(whole);
        if (fenced !== null) {
            code = fenced[1].trim();
            prose = whole.replace(fenced[0], "");
        }

        return { code: code, prose: root.unmarked(prose) };
    }

    // Markdown, undone. A docstring arrives escaped for a renderer we do not
    // have, and the escapes show through as themselves: `&nbsp;` in the middle
    // of an example, `\[` around a list, `&lt;` where someone wrote `<`. Reading
    // those is worse than reading no documentation at all.
    function unmarked(text) {
        return text
            .replace(/```[a-z]*\n?/g, "")
            .replace(/&nbsp;/g, " ")
            .replace(/&lt;/g, "<")
            .replace(/&gt;/g, ">")
            .replace(/&amp;/g, "&")
            .replace(/\\([\[\]()*_#`~-])/g, "$1")
            .replace(/^\s*-{3,}\s*$/gm, "")
            .replace(/\n{3,}/g, "\n\n")
            .trim();
    }

    // The word being typed, which is both what the list filters on and what an
    // accepted completion replaces. Anything a Python identifier can hold.
    function wordStart(from) {
        let at = from === undefined ? editor.cursorPosition : from;
        while (at > 0 && /[A-Za-z0-9_]/.test(editor.text.charAt(at - 1)))
            --at;
        return at;
    }

    // The protocol's kinds, as the one letter that fits beside a name. Only the
    // ones Python actually produces are named; the rest fall back to a dot,
    // which says "something" without pretending to know what.
    function kindMark(kind) {
        const marks = {
            2: "m", 3: "f", 4: "f", 5: "p", 6: "v", 7: "C", 8: "I",
            9: "M", 10: "p", 14: "k", 21: "c", 22: "S"
        };
        return marks[kind] !== undefined ? marks[kind] : "·";
    }

    function kindColor(kind) {
        if (kind === 7 || kind === 8 || kind === 22) return Theme.ai;      // types
        if (kind === 2 || kind === 3 || kind === 4) return Theme.ok;       // callables
        if (kind === 14) return Theme.live;                               // keywords
        return Theme.inkDim;
    }

    function severityColor(severity) {
        if (severity === 1) return Theme.bad;
        if (severity === 2) return Theme.flaw;
        return Theme.ai;
    }

    // ── Which file this is ────────────────────────────────────────────────
    // Under the tabs rather than in them: a tab is a place in the dock, and the
    // dock's tabs are named after what they DO. Following a definition lands you
    // in another file, and the pane has to say which one without renaming the
    // place you are in.
    Rectangle {
        id: filebar
        anchors { left: parent.left; right: parent.right; top: parent.top }
        height: 20
        color: Theme.codeSkin.ground

        Text {
            anchors {
                left: parent.left; leftMargin: 10
                right: state.left; rightMargin: 8
                verticalCenter: parent.verticalCenter
            }
            // Relative to the project when it is inside it: the full path of a
            // file three folders down is mostly the same prefix as every other.
            text: root.path.indexOf(Shell.projectRoot() + "/") === 0
                  ? root.path.substring(Shell.projectRoot().length + 1)
                  : root.path
            color: Theme.codeSkin.line
            font.family: Theme.mono
            font.pixelSize: root.codeSize - 2
            elide: Text.ElideLeft
        }

        Text {
            id: state
            anchors { right: parent.right; rightMargin: 10; verticalCenter: parent.verticalCenter }
            text: root.readOnly ? "read-only" : (root.modified ? "•" : "")
            color: root.readOnly ? Theme.warn : Theme.codeSkin.ink
            font.family: Theme.mono
            font.pixelSize: root.codeSize - 2
        }

        Rectangle {
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            height: 1
            color: Theme.edgeSoft
        }
    }

    // The sunken surface is the whole editing area, not just the lines that
    // happen to be typed — a TextArea's own background stops at the last line,
    // which left the bottom of the panel a different colour and its corners
    // square. Drawn once here, it carries the panel's bottom corners too.
    Rectangle {
        anchors {
            left: parent.left; right: parent.right
            top: filebar.bottom; bottom: parent.bottom
        }
        color: Theme.codeSkin.ground
        bottomLeftRadius: Theme.radiusInner
        bottomRightRadius: Theme.radiusInner
    }

    // ── The gutter ────────────────────────────────────────────────────────
    // Line numbers are not decoration in this editor: a traceback from the
    // compiled scene points at a line, and a gesture on the timeline rewrites
    // one. Without numbers, neither can be pointed at out loud.
    //
    // It scrolls by following the view rather than living inside it, because a
    // gutter that scrolls sideways with the text stops being a gutter the moment
    // a line is longer than the pane.
    Rectangle {
        id: gutter
        anchors {
            left: parent.left
            top: filebar.bottom; bottom: parent.bottom
        }
        // As wide as the widest number it will ever draw, and no wider. A fixed
        // 44 px was two characters of air on a sixteen-line scene and too tight
        // the day a file passes a thousand lines — measured from the font rather
        // than guessed, so it holds at any size.
        width: digits.width + 18
        color: Theme.codeSkin.ground
        clip: true

        TextMetrics {
            id: digits
            font: editor.font
            text: "0".repeat(Math.max(String(editor.lineCount).length, 2))
        }

        readonly property real lineHeight: editor.lineCount > 0
                                           ? editor.contentHeight / editor.lineCount : 16

        Column {
            // A ScrollView's contentItem IS the Flickable it scrolls with; the
            // cast is what lets the binding — and qmllint — see contentY.
            y: editor.topPadding - (view.contentItem as Flickable).contentY

            Repeater {
                model: editor.lineCount

                Text {
                    id: number
                    required property int index
                    width: gutter.width - 10
                    height: gutter.lineHeight
                    horizontalAlignment: Text.AlignRight
                    verticalAlignment: Text.AlignVCenter
                    // A touched line says so in the margin as well as behind the
                    // text: a diff read at a glance is read down the gutter.
                    readonly property string mark: number.index < root.diffRows.length
                                                   ? root.diffRows[number.index].kind : "same"
                    text: number.mark === "add" ? "+" : number.mark === "del" ? "−" : number.index + 1
                    color: number.mark === "add" ? Theme.ok
                           : number.mark === "del" ? Theme.bad
                           : number.index === editor.currentLine ? Theme.codeSkin.ink : Theme.codeSkin.line
                    font.family: Theme.mono
                    font.pixelSize: root.codeSize - 1
                }
            }
        }

        // The same news as the squiggle, at the one place you can see the whole
        // file from: a file with an error two screens down looks clean without
        // this, and you only find out when you run it.
        Repeater {
            model: root.shownDiagnostics

            Rectangle {
                id: mark
                required property var modelData
                x: 4
                y: editor.topPadding - (view.contentItem as Flickable).contentY
                   + mark.modelData.range.start.line * gutter.lineHeight
                   + (gutter.lineHeight - height) / 2
                width: 5
                height: 5
                radius: 2.5
                color: root.severityColor(mark.modelData.severity)
            }
        }

        Rectangle {
            anchors { right: parent.right; top: parent.top; bottom: parent.bottom }
            width: 1
            color: Theme.edgeSoft
        }
    }

    // ── The bubble ────────────────────────────────────────────────────────
    // A child of the panel rather than of the text, so that a signature found on
    // the last visible line is not clipped away by the scroll view — it is
    // allowed to cover the code, which is what every editor does and what makes
    // it readable.
    Rectangle {
        id: tip
        visible: false
        z: 10
        // Where the word is, in the pane's coordinates. What follows is bound to
        // it rather than assigned in show(): the bubble's height comes from a
        // Column that lays out on the NEXT tick, so a placement computed inside
        // show() is computed against the size of the bubble before it — measured,
        // 16 px, which reads as "it fits under the line" every time and then hangs
        // the text off the bottom of the pane.
        property real atX: 0
        property real atY: 0

        readonly property real wanted: bubble.implicitHeight + 16
        readonly property real roomBelow: root.height - 8 - (tip.atY + 4)
        readonly property real roomAbove: tip.atY - gutter.lineHeight - 12
        // Under the line when the whole bubble fits there — that is where the eye
        // already is — and on the roomier side when it does not.
        readonly property bool under: tip.roomBelow >= Math.min(tip.wanted, root.height * 0.5)
                                      || tip.roomBelow >= tip.roomAbove

        width: Math.min(Math.max(signature.implicitWidth, body.implicitWidth) + 18, root.width - 24)
        // Half the pane at most. A docstring is as long as its author felt
        // like, and an uncapped bubble grew past the pane, flipped itself
        // above the line because it no longer fitted below, and then hung off
        // the top with the first paragraph — the part you wanted — cut away.
        //
        // And never taller than the side it sits on: what does not fit scrolls
        // INSIDE the bubble, where there is a scrollbar to say so, rather than
        // being cut off by the edge of the pane, where nothing does.
        height: Math.min(tip.wanted, root.height * 0.5,
                         Math.max(tip.under ? tip.roomBelow : tip.roomAbove, 40))
        // Kept inside the pane on both axes: a bubble half off the right edge is
        // worse than one that does not line up with the word. Four pixels from
        // the line, near enough to walk the pointer into — leaving the word is
        // what closes the bubble, so a wider gap is a bubble that shuts on the
        // way to it.
        x: Math.max(8, Math.min(tip.atX, root.width - tip.width - 8))
        y: tip.under ? tip.atY + 4
                     : Math.max(8, tip.atY - gutter.lineHeight - tip.height - 4)
        // The bubble belongs to the CODE, not to the chrome: VS Code paints its
        // hovers on their own surface, a step up from the editor's ground, and a
        // panel-blue box over a black buffer reads as a different application.
        color: Theme.codeSkin.hover
        radius: Theme.radiusSmall
        border.width: 1
        border.color: Theme.codeSkin.edge

        // The top of the line this bubble is about, in the text's coordinates.
        // It is what says the pointer is still "there" — see the move handler.
        property real forY: -1

        function show(what, cx, cy) {
            if (what.code.length === 0 && what.prose.length === 0) {
                tip.visible = false;
                return;
            }
            signature.text = what.code;
            body.text = what.prose;
            tip.forY = cy - gutter.lineHeight;
            const at = editor.mapToItem(root, cx, cy);
            tip.atX = at.x;
            tip.atY = at.y;
            scroll.contentY = 0;
            tip.visible = true;
        }

        function hide() { tip.visible = false; }

        // And what does not fit scrolls, rather than being cut off with no way
        // to see the rest.
        Flickable {
            id: scroll
            anchors.fill: parent
            anchors.margins: 8
            contentWidth: width
            contentHeight: bubble.implicitHeight
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            ScrollBar.vertical: ScrollBar {
                policy: scroll.contentHeight > scroll.height ? ScrollBar.AlwaysOn
                                                             : ScrollBar.AlwaysOff
            }

            Column {
                id: bubble
                width: scroll.width
                spacing: signature.text.length > 0 && body.text.length > 0 ? 7 : 0

                // A TextEdit rather than a Text, for one reason: it owns a document,
                // and a document is what a syntax highlighter attaches to. The
                // signature is code, so it is painted by the same rules and the same
                // palette as the buffer behind it.
                TextEdit {
                    id: signature
                    width: bubble.width
                    visible: text.length > 0
                    readOnly: true
                    selectByMouse: false
                    color: Theme.codeSkin.ink
                    font.family: Theme.mono
                    font.pixelSize: root.codeSize
                    wrapMode: TextEdit.NoWrap
                    textFormat: TextEdit.PlainText

                    Component.onCompleted: root.documentReady(signature.textDocument, true)

                    Connections {
                        target: Theme
                        function onCodeThemeChanged() { root.documentReady(signature.textDocument, true); }
                    }
                }

                Rectangle {
                    width: bubble.width
                    height: 1
                    visible: signature.text.length > 0 && body.text.length > 0
                    color: Theme.edgeSoft
                }

                Text {
                    id: body
                    width: bubble.width
                    visible: text.length > 0
                    color: Theme.codeSkin.ink
                    font.family: Theme.ui
                    font.pixelSize: root.codeSize
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                }
            }
        }
    }

    // A whole statement, put in on its own line above the caret's.
    //
    // Above rather than at the caret: a dropped file lands while you are in the
    // middle of a line as often as not, and splitting `Square(sid` in half is a
    // worse answer than a line you can move.
    // ── Monter, descendre, effacer un mot ─────────────────────────────────
    // Trois gestes d'éditeur, écrits ici parce que c'est ici qu'est le tampon.
    // Tous passent par `replaceRange`, donc chacun est UNE entrée d'annulation
    // et le coloriseur, le serveur de langage et la scène les voient comme une
    // frappe de plus.

    // La ligne et sa voisine échangent leur place. Le curseur suit la ligne,
    // pas le numéro : c'est la ligne qu'on déplace, on veut continuer à taper
    // dedans.
    function moveLine(delta) {
        const text = editor.text;
        const lines = text.split("\n");
        const at = root.locationAt(editor.cursorPosition).line;
        const to = at + delta;
        if (to < 0 || to >= lines.length)
            return false;

        const column = editor.cursorPosition - root.offsetOf(at, 0);
        const first = Math.min(at, to);
        const start = root.offsetOf(first, 0);
        const both = [lines[first], lines[first + 1]];
        const swapped = both[1] + "\n" + both[0];
        if (!root.replaceRange(start, start + both[0].length + 1 + both[1].length, swapped))
            return false;
        editor.cursorPosition = root.offsetOf(to, 0) + Math.min(column, lines[at].length);
        return true;
    }

    // Le mot à droite. `⌥⌫` fait déjà celui de gauche — c'est macOS qui le
    // donne — et rien ne faisait celui-ci.
    function deleteWordRight() {
        const text = editor.text;
        let end = editor.cursorPosition;
        while (end < text.length && /\s/.test(text[end]) && text[end] !== "\n")
            ++end;
        if (end < text.length && /[A-Za-z0-9_]/.test(text[end]))
            while (end < text.length && /[A-Za-z0-9_]/.test(text[end]))
                ++end;
        else if (end < text.length && text[end] !== "\n")
            ++end;                                  // un signe seul se mange seul
        else if (end < text.length)
            ++end;                                  // sinon la fin de ligne
        return end > editor.cursorPosition
               && root.replaceRange(editor.cursorPosition, end, "");
    }

    function redo() {
        editor.redo();
    }

    function insertLine(statement) {
        // Nobody has placed the caret yet — position 0 is where it starts — so
        // "add this to my scene" means the end, not above the shebang. Once the
        // caret has been somewhere, that somewhere is the answer.
        if (editor.cursorPosition === 0) {
            const tail = editor.text.endsWith("\n") ? "" : "\n";
            editor.insert(editor.text.length, tail + statement + "\n");
            editor.cursorPosition = editor.text.length - 1;
            editor.forceActiveFocus();
            return;
        }

        const at = editor.text.lastIndexOf("\n", Math.max(0, editor.cursorPosition - 1)) + 1;
        editor.insert(at, statement + "\n");
        editor.cursorPosition = at + statement.length;
        editor.forceActiveFocus();
    }

    // A statement placed under a line the gesture chose, rather than under the
    // caret. Trimming a shape writes `square.hide(start=…)`, and WHERE that
    // lands decides what it means: `start` is counted from the element's cursor,
    // and the cursor is only what it was on the line the editor measured.
    //
    // Through `replaceRange` so the insertion is one entry in the same undo
    // history as typing — and it takes the indentation of the line it follows,
    // because a statement written flush left inside a function is a syntax
    // error rather than an edit.
    function insertAfterLine(line, statement) {
        const lines = editor.text.split("\n");
        if (line < 1 || line > lines.length)
            return false;

        let offset = 0;
        for (let i = 0; i < line; ++i)
            offset += lines[i].length + 1;

        const indent = /^\s*/.exec(lines[line - 1])[0];
        // A file that does not end in a newline has no "after" its last line:
        // the offset lands one past the end, the edit was refused without a
        // word, and the last clip of a scene could not be given an end.
        if (offset > editor.text.length)
            return root.replaceRange(editor.text.length, editor.text.length, "\n" + indent + statement + "\n");
        return root.replaceRange(offset, offset, indent + statement + "\n");
    }

    // Several statements at once, as ONE edit: a template is a line that makes
    // the thing and a line that says when it appears, and two insertions would
    // be two ⌘Z. Blank line in front when there is not one already, because a
    // block that starts flush against the line above reads as part of it.
    function insertBlock(afterLine, statements) {
        const lines = editor.text.split("\n");
        if (afterLine < 0 || afterLine > lines.length)
            return false;

        let offset = 0;
        for (let i = 0; i < afterLine; ++i)
            offset += lines[i].length + 1;

        const indent = afterLine > 0 ? /^\s*/.exec(lines[afterLine - 1])[0] : "";
        // A blank line on whichever side does not already have one, so the block
        // reads as its own paragraph rather than as the tail of the statement
        // above it or the head of the one below.
        const above = afterLine > 0 && lines[afterLine - 1].trim().length > 0;
        const below = afterLine < lines.length && lines[afterLine].trim().length > 0;
        const body = statements.map((one) => indent + one).join("\n");
        return root.replaceRange(
            offset, offset, (above ? "\n" : "") + body + "\n" + (below ? "\n" : ""));
    }

    // An import goes with the other imports — under the last one, or at the top
    // under a shebang. A file's imports are a block, and one adrift in the
    // middle of a scene is the kind of tidiness a tool owes.
    function insertImport(statement) {
        const lines = editor.text.split("\n");
        let at = 0;
        for (let i = 0; i < lines.length; ++i)
            if (/^\s*(import|from)\s/.test(lines[i]))
                at = i + 1;
        if (at === 0 && lines.length > 0 && lines[0].indexOf("#!") === 0)
            at = 1;

        let offset = 0;
        for (let i = 0; i < at; ++i)
            offset += lines[i].length + 1;

        const caret = editor.cursorPosition;
        editor.insert(offset, statement + "\n");
        editor.cursorPosition = caret >= offset ? caret + statement.length + 1 : caret;
    }

    // Apply an edit the way a person would have typed it.
    //
    // Through the document — remove, then insert — rather than by assigning the
    // whole text. Qt's undo stack records edits and ignores assignments, so a
    // gesture that replaced the buffer left ⌘Z with nothing to take back. This
    // way a drag and a keystroke share one history, which is the only way a
    // gesture and the code can be undone in the order they happened.
    function replaceRange(from, to, text) {
        if (from < 0 || to < from || to > editor.length)
            return false;

        const caret = editor.cursorPosition;
        // Through the shell, on the document itself: `remove` then `insert` from
        // here are two entries in the undo stack, and one ⌘Z left `side=` with
        // nothing after it.
        if (!Shell.replaceRange(editor.textDocument, from, to, text))
            return false;

        // The caret stays where it was, shifted by what the edit changed in
        // front of it: a gesture must not move the place you were typing.
        const delta = text.length - (to - from);
        editor.cursorPosition = caret > to ? caret + delta : caret;
        return true;
    }

    // Take the keyboard.
    //
    // `load()` asks for focus too, but a file opened from the menu is loaded
    // before the pane is brought to the front, and a request made while the pane
    // is behind another tab is a request nobody receives. Asked again by the
    // shell once the tab is up.
    function takeFocus() { editor.forceActiveFocus(); }

    // Whether the keys of the keyboard are currently letters.
    //
    // A text editor owns Space, the arrows, Home and End — they are how you
    // write — and a video editor owns exactly the same five for its transport.
    // Both are right, so the answer is WHO HAS THE CARET, and this is how the
    // rest of the chrome asks.
    readonly property bool typing: editor.activeFocus

    // Say something for a moment. The panel's one channel for news that has no
    // other home: a save refused, a rename that touched files you cannot see.
    function say(what) { notice.say(what); spoke(what, null); }

    // The same strip, with something to do about it. A refusal that only says
    // no leaves the person to go and make the edit by hand; when there IS an
    // edit the gesture may make, the sentence is the button. It stays a little
    // longer than a plain notice and goes on its own like one: an offer that
    // waits for an answer is a dialog, and this is a drag that missed.
    function offer(what, act) { notice.offer(what, act); spoke(what, act); }

    // Whatever the strip was just given, for a panel that asked for the edit
    // while this pane is behind another tab: the strip alone is then said to
    // nobody. `act` is the offer's action, or null.
    signal spoke(string what, var act)

    // Something happened that you cannot see, said briefly and then gone.
    // A rename rewrites files nobody is looking at; a permanent strip for that
    // one sentence would cost a line of the pane forever.
    Rectangle {
        id: notice
        visible: false
        z: 14
        anchors {
            right: parent.right; rightMargin: 12
            top: parent.top; topMargin: finding.visible ? 44 : 10
        }
        width: word.implicitWidth + 18
        height: 22
        radius: Theme.radiusSmall
        color: Theme.panel
        border.width: 1
        border.color: Theme.edge

        // What clicking it does, or null — the strip is only a button while
        // there is something on the other end of it.
        property var act: null

        function say(what) {
            notice.act = null;
            word.text = what;
            // A refusal is not good news, and green would say it was.
            word.color = /read-only|could not|nothing/.test(what) ? Theme.warn : Theme.ok;
            notice.visible = true;
            fade.interval = 3000;
            fade.restart();
        }

        function offer(what, action) {
            notice.act = action;
            word.text = what;
            word.color = Theme.live;
            notice.visible = true;
            fade.interval = 7000;
            fade.restart();
        }

        Text {
            id: word
            anchors.centerIn: parent
            font.family: Theme.mono
            font.pixelSize: root.codeSize - 2
        }

        HoverTint { visible: notice.act !== null }

        MouseArea {
            anchors.fill: parent
            enabled: notice.act !== null
            hoverEnabled: enabled
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                const act = notice.act;
                notice.visible = false;
                notice.act = null;
                act();
            }
        }

        Timer {
            id: fade
            interval: 3000
            onTriggered: {
                notice.visible = false;
                notice.act = null;
            }
        }
    }

    // ── Finding text ──────────────────────────────────────────────────────
    // A strip over the top of the pane, not a pane of its own: what you are
    // looking for is in the buffer, and a search that pushes the buffer down
    // moves the thing you are reading while you read it.
    //
    // Plain text, ignoring case. No regular expressions and no whole-word
    // switch: ⌘F is how you get to a line you already know is there, and every
    // switch beside the field is a state to be in by accident next time.
    function openFind() { finding.open(); }

    // ⌘H : la même bande, la deuxième ligne montrée, et le curseur dedans quand
    // il y a déjà quelque chose à chercher.
    function openReplace() {
        finding.replacing = true;
        finding.open();
        if (query.text.length > 0)
            into.forceActiveFocus();
    }

    // Where the strip stands, as the strip itself prints it. A selection cannot
    // be read from outside the pane, so without this a scripted run has no way
    // to tell a search that landed from one that quietly found nothing.
    readonly property string found: finding.visible
                                    ? (finding.at + 1) + "/" + finding.hits.length : ""

    Rectangle {
        id: finding
        visible: false
        z: 15
        anchors { right: parent.right; rightMargin: 12; top: parent.top; topMargin: 10 }
        width: 320
        // Deux lignes quand on remplace, une quand on cherche : la deuxième
        // n'existe que si on a demandé de quoi la remplir.
        height: finding.replacing ? 56 : 28
        radius: Theme.radiusSmall
        color: Theme.panel
        border.width: 1
        border.color: Theme.edge

        // Where every match starts, in buffer offsets, and which one is shown.
        // -1 means "not moved yet": the first step lands on the match after the
        // caret rather than at the top of the file, because you searched from
        // where you were standing.
        property var hits: []
        property int at: -1
        // The buffer these offsets were counted in. Attaching the syntax
        // highlighter and re-colouring a block both raise `onTextChanged`
        // WITHOUT a character moving, and a recount on one of those blanked the
        // counter to "0/3" the instant after a search had landed on a match.
        property string counted: ""
        // Where the caret stood when the search opened. Stepping from the LIVE
        // caret instead walked forward with every letter typed — the caret is
        // moved by each landing — so typing "Circle" pushed you past the first
        // Circle in the file. A search starts where you were standing, and
        // stays anchored there until you ask for the next one.
        property int anchor: 0
        // Chercher, ou chercher POUR remplacer. Le même parcours de résultats,
        // la même bande ; une ligne de plus.
        property bool replacing: false

        Item {
            id: firstRow
            anchors { left: parent.left; right: parent.right; top: parent.top }
            height: 28
        }

        function open() {
            finding.anchor = editor.selectionStart;
            if (editor.selectedText.length > 0 && editor.selectedText.indexOf("\n") < 0)
                query.text = editor.selectedText;
            finding.visible = true;
            finding.recount();
            query.selectAll();
            query.forceActiveFocus();
        }

        function shut() {
            finding.visible = false;
            finding.replacing = false;
            editor.forceActiveFocus();
        }

        // Celui-ci, puis le suivant. `recount` d'abord : les positions d'après
        // ont bougé de ce que le remplacement a changé en longueur.
        function replaceOne() {
            if (query.text.length === 0 || finding.hits.length === 0)
                return;
            if (finding.at < 0) {
                finding.step(1);
                return;
            }
            const from = finding.hits[finding.at];
            if (!root.replaceRange(from, from + query.text.length, into.text))
                return;
            finding.recount();
            finding.step(1);
        }

        // Tous, de la fin vers le début : remplacer d'abord le dernier laisse
        // les positions des précédents valables.
        function replaceAll() {
            if (query.text.length === 0 || finding.hits.length === 0)
                return;
            const places = finding.hits.slice().sort(function (a, b) { return b - a; });
            for (const from of places)
                root.replaceRange(from, from + query.text.length, into.text);
            const many = places.length;
            finding.recount();
            root.say(many + (many === 1 ? " replaced" : " replaced"));
        }

        function recount() {
            const needle = query.text.toLowerCase();
            let out = [];
            if (needle.length > 0) {
                const hay = editor.text.toLowerCase();
                let i = hay.indexOf(needle);
                while (i >= 0) {
                    out.push(i);
                    i = hay.indexOf(needle, i + 1);
                }
            }
            finding.hits = out;
            // Where we already are, if the match under the selection survived
            // the count. Blanking it instead would reset "2/2" to "0/2" on
            // every keystroke and on every re-run that rewrites the buffer,
            // while the selection is still sitting on a match — and -1 is what
            // `indexOf` gives back when it genuinely is not one of them.
            finding.at = out.indexOf(editor.selectionStart);
            finding.counted = editor.text;
        }

        // Put the current match on screen. WHICH one is current is `at`, or the
        // first one at or after the anchor when nothing has been chosen yet.
        function show() {
            if (finding.hits.length === 0)
                return;
            if (finding.at < 0) {
                let k = 0;
                while (k < finding.hits.length && finding.hits[k] < finding.anchor)
                    ++k;
                finding.at = k % finding.hits.length;
            }
            const from = finding.hits[finding.at];
            editor.select(from, from + query.text.length);
            (view.contentItem as Flickable).contentY =
                Math.max(0, editor.cursorRectangle.y - view.height / 3);
        }

        // One match on, or one back. Separate from `show` on purpose: typing a
        // letter SHOWS where you are, it does not walk. Stepping on every
        // keystroke walked forward once per letter — narrowing "C" to "Circle"
        // keeps landing on the same match, `recount` recognised it, and each
        // letter then advanced past it.
        function step(by) {
            if (finding.hits.length === 0)
                return;
            if (finding.at >= 0)
                finding.at = (finding.at + by + finding.hits.length) % finding.hits.length;
            finding.show();
        }

        TextField {
            id: query
            anchors {
                left: parent.left; leftMargin: 8
                right: tally.left; rightMargin: 6
                verticalCenter: firstRow.verticalCenter
            }
            height: parent.height - 6
            placeholderText: "find"
            color: Theme.ink
            font.family: Theme.mono
            font.pixelSize: root.codeSize
            background: null
            onTextChanged: {
                finding.recount();
                finding.show();
            }
            // Enter walks forward, ⇧⏎ back — the two keys every editor on this
            // machine already answers to, so there is nothing new to learn.
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    finding.step(event.modifiers & Qt.ShiftModifier ? -1 : 1);
                    event.accepted = true;
                } else if (event.key === Qt.Key_Escape) {
                    finding.shut();
                    event.accepted = true;
                }
            }
        }

        // La deuxième ligne. ⏎ remplace celui-ci et passe au suivant, ⇧⏎ les
        // remplace tous — les deux gestes que fait n'importe quel éditeur, et
        // rien à cliquer pour les obtenir.
        TextField {
            id: into
            visible: finding.replacing
            anchors {
                left: parent.left; leftMargin: 8
                right: parent.right; rightMargin: 8
                top: firstRow.bottom
            }
            height: 24
            placeholderText: "replace with"
            color: Theme.ink
            font.family: Theme.mono
            font.pixelSize: root.codeSize
            background: Rectangle {
                anchors { fill: parent; topMargin: 2; bottomMargin: 2 }
                color: "transparent"
                border.width: 1
                border.color: into.activeFocus ? Theme.live : Theme.edgeSoft
                radius: Theme.radiusSmall
            }
            Keys.onPressed: (event) => {
                if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    if (event.modifiers & Qt.ShiftModifier)
                        finding.replaceAll();
                    else
                        finding.replaceOne();
                    event.accepted = true;
                } else if (event.key === Qt.Key_Escape) {
                    finding.shut();
                    event.accepted = true;
                }
            }
        }

        Text {
            id: tally
            anchors { right: prev.left; rightMargin: 6; verticalCenter: firstRow.verticalCenter }
            text: query.text.length === 0
                  ? ""
                  : (finding.hits.length === 0
                     ? "none"
                     : (finding.at + 1) + "/" + finding.hits.length)
            color: finding.hits.length === 0 && query.text.length > 0 ? Theme.warn : Theme.inkFaint
            font.family: Theme.mono
            font.pixelSize: root.codeSize - 2
        }

        // The direction is decided where the arrow is placed, not inside it:
        // under `ComponentBehavior: Bound` an inline component cannot see the
        // ids around it, and a signal is the way out that stays honest.
        component Step: Text {
            id: step
            signal stepped()

            width: 16
            color: arrow.containsMouse ? Theme.ink : Theme.inkFaint
            font.family: Theme.mono
            font.pixelSize: 12
            horizontalAlignment: Text.AlignHCenter

            MouseArea {
                id: arrow
                anchors.fill: parent
                anchors.margins: -3
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: step.stepped()
            }
        }

        Step {
            id: prev
            anchors { right: next.left; verticalCenter: parent.verticalCenter }
            text: "\u2039"
            onStepped: finding.step(-1)
        }

        Step {
            id: next
            anchors { right: shutIt.left; rightMargin: 2; verticalCenter: parent.verticalCenter }
            text: "\u203a"
            onStepped: finding.step(1)
        }

        CloseButton {
            id: shutIt
            anchors { right: parent.right; rightMargin: 4; verticalCenter: parent.verticalCenter }
            onTriggered: finding.shut()
        }
    }

    // ── The new name ──────────────────────────────────────────────────────
    // A field over the word rather than a dialog in the middle of the screen:
    // what you are renaming is what you are looking at, and a modal would cover
    // it. F2 opens it with the old name selected, exactly as pressing it in any
    // other editor does.
    Rectangle {
        id: renaming
        visible: false
        z: 13
        width: 220
        height: 26
        color: Theme.panel
        radius: Theme.radiusSmall
        border.width: 1
        border.color: Theme.live

        function begin() {
            const from = root.wordStart();
            let to = editor.cursorPosition;
            while (to < editor.text.length && /[A-Za-z0-9_]/.test(editor.text.charAt(to)))
                ++to;
            if (to === from)
                return;

            const at = editor.mapToItem(root, editor.positionToRectangle(from).x, editor.cursorRectangle.y);
            renaming.x = Math.max(8, Math.min(at.x - 6, root.width - renaming.width - 8));
            renaming.y = Math.max(4, at.y - 4);
            field.text = editor.text.substring(from, to);
            renaming.visible = true;
            field.selectAll();
            field.forceActiveFocus();
        }

        function commit() {
            const at = root.locationAt(editor.cursorPosition);
            const wanted = field.text;
            renaming.visible = false;
            editor.forceActiveFocus();
            if (wanted.length === 0)
                return;
            Lsp.rename(root.path, at.line, at.character, wanted, function (edit) {
                const touched = root.applyEdit(edit);
                notice.say(touched === 0
                           ? "nothing to rename"
                           : "renamed in " + touched + (touched === 1 ? " file" : " files"));
                if (touched > 0 && root.path.length > 0)
                    Lsp.changeDocument(root.path, editor.text);
            });
        }

        TextField {
            id: field
            anchors.fill: parent
            anchors.margins: 3
            color: Theme.ink
            font.family: Theme.mono
            font.pixelSize: root.codeSize
            background: null
            onAccepted: renaming.commit()
            Keys.onEscapePressed: {
                renaming.visible = false;
                editor.forceActiveFocus();
            }
        }
    }

    // ── Everywhere a name is used ─────────────────────────────────────────
    // A list, not a jump: the point of asking is to see how many places there
    // are and what they look like before going anywhere. Each row carries the
    // line it found, because a path and a number alone tell you nothing.
    Rectangle {
        id: uses
        visible: false
        z: 12
        anchors { right: parent.right; rightMargin: 10; top: parent.top; topMargin: 10 }
        width: Math.min(420, root.width - 80)
        height: Math.min(found.count * 34 + 30, root.height - 60)
        color: Theme.codeSkin.hover
        radius: Theme.radiusSmall
        border.width: 1
        border.color: Theme.codeSkin.edge

        property var rows: []

        function offer(reply) {
            const items = root.listed(reply);
            // Reading a file once and slicing every hit out of it: a symbol
            // used forty times in one module is forty rows but one read.
            let cache = ({});
            let out = [];
            for (const item of items) {
                const where = item.uri.replace("file://", "");
                if (cache[where] === undefined)
                    cache[where] = (where === root.path ? editor.text : Shell.readTextFile(where)).split("\n");
                out.push({
                    path: where,
                    name: where.split("/").pop(),
                    line: item.range.start.line,
                    character: item.range.start.character,
                    body: (cache[where][item.range.start.line] !== undefined
                           ? cache[where][item.range.start.line] : "").trim()
                });
            }
            uses.rows = out;
            uses.visible = out.length > 0;
        }

        Text {
            id: count
            anchors { left: parent.left; leftMargin: 10; top: parent.top; topMargin: 8 }
            text: uses.rows.length + (uses.rows.length === 1 ? " use" : " uses")
            color: Theme.inkDim
            font.family: Theme.ui
            font.pixelSize: root.codeSize - 2
        }

        Text {
            anchors { right: usesShut.left; rightMargin: 6; top: parent.top; topMargin: 8 }
            text: "esc"
            color: Theme.inkFaint
            font.family: Theme.mono
            font.pixelSize: root.codeSize - 2
        }

        CloseButton {
            id: usesShut
            anchors { right: parent.right; rightMargin: 6; top: parent.top; topMargin: 4 }
            onTriggered: uses.visible = false
        }

        ListView {
            id: found
            anchors { fill: parent; topMargin: 24; margins: 1 }
            model: uses.rows
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            delegate: Rectangle {
                id: use
                required property var modelData
                width: found.width
                height: 34
                color: hit.containsMouse ? Theme.rail : "transparent"

                Text {
                    id: place
                    anchors { left: parent.left; leftMargin: 10; top: parent.top; topMargin: 4 }
                    text: use.modelData.name + ":" + (use.modelData.line + 1)
                    color: Theme.inkFaint
                    font.family: Theme.mono
                    font.pixelSize: root.codeSize - 2
                }

                Text {
                    anchors {
                        left: parent.left; leftMargin: 10; right: parent.right; rightMargin: 10
                        top: place.bottom; topMargin: 1
                    }
                    text: use.modelData.body
                    color: Theme.ink
                    font.family: Theme.mono
                    font.pixelSize: root.codeSize
                    elide: Text.ElideRight
                }

                MouseArea {
                    id: hit
                    anchors.fill: parent
                    hoverEnabled: true
                    onClicked: {
                        uses.visible = false;
                        root.jump(use.modelData.path, use.modelData.line, use.modelData.character);
                    }
                }
            }
        }
    }

    // ── The call you are inside ───────────────────────────────────────────
    // Not a hover: it follows the caret, and what it emphasises changes with
    // every comma. Which argument you are on is the whole information — a
    // signature with no active parameter marked is just documentation.
    Rectangle {
        id: hint
        visible: false
        z: 11

        // The line it was asked about. A signature is only true of the call it
        // describes, and nothing was closing it when the caret left: typing `)`
        // hid it, moving away did not, so it sat over the code until the next
        // `(` replaced it.
        property int forLine: -1
        width: Math.min(shape.implicitWidth + 18, root.width - 24)
        height: shape.implicitHeight + 12
        color: Theme.codeSkin.hover
        radius: Theme.radiusSmall
        border.width: 1
        border.color: Theme.codeSkin.edge

        function offer(reply) {
            if (!reply || !reply.signatures || reply.signatures.length === 0) {
                hint.visible = false;
                return;
            }
            const chosen = reply.signatures[reply.activeSignature !== undefined ? reply.activeSignature : 0];
            if (chosen === undefined) {
                hint.visible = false;
                return;
            }
            shape.text = hint.emphasised(chosen, reply.activeParameter);
            hint.forLine = editor.currentLine;
            const at = editor.mapToItem(root, editor.cursorRectangle.x, editor.cursorRectangle.y);
            hint.x = Math.max(8, Math.min(at.x - 20, root.width - hint.width - 8));
            // Above the caret, always: below is where the completion list goes,
            // and the two of them are often up at the same time.
            hint.y = Math.max(4, at.y - hint.height - 4);
            hint.visible = true;
        }

        // A parameter's label is either the text itself or a pair of offsets
        // into the signature — both are legal, and pyright sends offsets.
        function emphasised(signature, active) {
            const whole = signature.label;
            const index = signature.activeParameter !== undefined ? signature.activeParameter : active;
            const params = signature.parameters;
            if (!params || index === undefined || index === null || params[index] === undefined)
                return hint.plain(whole);

            const label = params[index].label;
            let from = -1;
            let to = -1;
            if (typeof label === "string") {
                from = whole.indexOf(label);
                to = from + label.length;
            } else if (label !== undefined && label.length === 2) {
                // A pair of offsets into the signature. Tested by length rather
                // than by Array.isArray, which is false for anything that came
                // across the bridge.
                from = label[0];
                to = label[1];
            }
            if (from < 0)
                return hint.plain(whole);

            return hint.plain(whole.substring(0, from))
                 + "<font color=\"" + Theme.live + "\"><b>" + hint.plain(whole.substring(from, to)) + "</b></font>"
                 + hint.plain(whole.substring(to));
        }

        // Styled text, so a default value holding < or & would otherwise eat
        // the rest of the signature.
        function plain(text) {
            return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        Text {
            id: shape
            anchors.fill: parent
            anchors.margins: 6
            color: Theme.codeSkin.ink
            font.family: Theme.mono
            font.pixelSize: root.codeSize
            textFormat: Text.StyledText
            wrapMode: Text.Wrap
        }
    }

    // ── What you could type next ──────────────────────────────────────────
    // The server is asked once per pause in typing, and the list is narrowed
    // locally on every keystroke after that. Asking again per character would
    // put a round trip between the key and the letter appearing, which is the
    // one thing an editor may never do.
    Rectangle {
        id: suggestions
        visible: false
        z: 11
        width: 340
        height: Math.min(list.count, 9) * 20 + 2
        color: Theme.codeSkin.hover
        radius: Theme.radiusSmall
        border.width: 1
        border.color: Theme.codeSkin.edge

        property var all: []
        property var shown: []

        function offer(items) {
            suggestions.all = items !== undefined && items !== null ? items : [];
            suggestions.refine();
        }

        function refine() {
            const prefix = editor.text.substring(root.wordStart(), editor.cursorPosition).toLowerCase();
            let out = [];
            for (const item of suggestions.all) {
                const label = (item.filterText !== undefined ? item.filterText : item.label).toLowerCase();
                if (prefix.length === 0 ? !label.startsWith("_") : label.startsWith(prefix))
                    out.push(item);
                // A module's namespace runs to thousands of names; past a
                // hundred nobody is reading, they are typing another letter.
                if (out.length >= 100)
                    break;
            }
            suggestions.shown = out;
            list.currentIndex = 0;
            suggestions.visible = out.length > 0;
            if (suggestions.visible)
                suggestions.place();
        }

        function place() {
            const at = editor.mapToItem(root, editor.positionToRectangle(root.wordStart()).x,
                                        editor.cursorRectangle.y + editor.cursorRectangle.height);
            suggestions.x = Math.max(8, Math.min(at.x, root.width - suggestions.width - 8));
            // Below the caret unless that would fall out of the pane, in which
            // case above it — never half-drawn at the bottom edge.
            suggestions.y = at.y + suggestions.height + 4 > root.height
                            ? at.y - suggestions.height - editor.cursorRectangle.height - 4
                            : at.y + 2;
        }

        function accept() {
            const item = suggestions.shown[list.currentIndex];
            if (item === undefined)
                return;
            // A snippet's placeholders are dropped rather than played out: the
            // pane has no tab-through-fields yet, and `Square(${1:side})` left
            // in the buffer is worse than no completion at all.
            let insert = item.insertText !== undefined ? item.insertText : item.label;
            if (item.insertTextFormat === 2)
                insert = insert.replace(/\$\{\d+:([^}]*)\}/g, "$1").replace(/\$\d+/g, "");
            const from = root.wordStart();
            editor.remove(from, editor.cursorPosition);
            editor.insert(from, insert);

            // « Auto-import » n'était qu'une étiquette : le serveur joint la
            // ligne d'import à écrire (`additionalTextEdits`) et personne ne
            // l'écrivait — on acceptait un nom que le fichier n'avait pas, et
            // la ligne devenait rouge. Appliquée APRÈS le mot : l'import est
            // au-dessus du curseur, donc ses positions ne bougent pas.
            if (item.additionalTextEdits !== undefined && item.additionalTextEdits.length > 0)
                root.applyEdit({ changes: { ["file://" + root.path]: item.additionalTextEdits } });

            suggestions.visible = false;
        }

        ListView {
            id: list
            anchors.fill: parent
            anchors.margins: 1
            model: suggestions.shown
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                width: list.width
                height: 20
                color: row.index === list.currentIndex ? Theme.rail : "transparent"

                // Le nom porte sa propre couleur : c'est la même information que
                // la lettre à gauche, sans la colonne qu'elle coûtait — et une
                // couleur se lit sans être déchiffrée.
                Text {
                    id: label
                    anchors { left: parent.left; leftMargin: 9; verticalCenter: parent.verticalCenter }
                    text: row.modelData.label
                    color: root.kindColor(row.modelData.kind)
                    font.family: Theme.mono
                    font.pixelSize: root.codeSize
                }

                // The signature, when there is room for it. Greyed, because it
                // is what you read second — after finding the name you meant.
                Text {
                    anchors {
                        left: label.right; leftMargin: 8
                        right: parent.right; rightMargin: 7
                        verticalCenter: parent.verticalCenter
                    }
                    text: row.modelData.detail !== undefined ? row.modelData.detail : ""
                    color: Theme.inkFaint
                    font.family: Theme.mono
                    font.pixelSize: root.codeSize - 2
                    elide: Text.ElideRight
                    horizontalAlignment: Text.AlignRight
                }

                HoverTint {}

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        list.currentIndex = row.index;
                        suggestions.accept();
                    }
                }
            }
        }
    }

    // Room to scroll PAST the end — a whole viewport of it, so the last line can
    // be brought to the top of the pane.
    //
    // The line you are writing is almost never the one you want at the bottom
    // edge of the screen: you want it where your eyes already are, with room to
    // think below it. Every editor worth the name does this; VS Code calls it
    // scrollBeyondLastLine and has it on.
    //
    // It is the FLICKABLE that is given the room, not the text item. Padding the
    // TextArea by a viewport's height is the obvious way and it breaks the
    // rendering outright — everything past the first line stops being drawn.
    // A margin on the thing that scrolls adds the same space and touches neither
    // the text nor the buffer, so the file on disk still ends where the code
    // ends.
    Binding {
        target: view.contentItem
        property: "bottomMargin"
        value: Math.max(root.height - gutter.lineHeight, 0)
        when: view.contentItem !== null
    }

    ScrollView {
        id: view
        anchors {
            left: gutter.right; right: parent.right
            top: filebar.bottom; bottom: parent.bottom
        }
        clip: true

        // The bubble is placed once, in panel coordinates, and does not scroll
        // with the line it explains — so a scroll leaves it pointing at
        // whatever slid under it. Dropped rather than followed: that is what
        // the editors this is modelled on do.
        Connections {
            target: view.contentItem
            function onContentYChanged() { probe.dismiss(); }
        }

        TextArea {
            id: editor
            color: Theme.codeSkin.ink
            font.family: Theme.mono
            font.pixelSize: 12
            selectByMouse: true
            background: null
            // The gap between the numbers and the first character. Wider than
            // the obvious 8: a number and a letter that nearly touch read as one
            // word, and every editor leaves a hand's breadth there.
            leftPadding: 14
            // Half a pane past the end of the longest line: its last characters
            // are read with air after them, and what a gesture says after a
            // line has somewhere to be seen. Padding, unlike the room under
            // the text: sideways it breaks nothing, and a press out there
            // still lands on the end of its line.
            rightPadding: view.width / 2
            topPadding: 6
            // Code is not prose: a wrapped line lies about where the line ends,
            // and every editor a person has used before this one scrolls instead.
            wrapMode: TextEdit.NoWrap
            // Clicking under the last line is still clicking in the file. The
            // room to scroll past the end is the Flickable's margin, and a
            // TextArea only as tall as its text leaves every press down there
            // to the Flickable, which has nothing to do with it. Stretched over
            // the margin, the press reaches the text and lands on the nearest
            // character — the end of the last line.
            height: implicitHeight + (view.contentItem as Flickable).bottomMargin
            selectionColor: Qt.alpha(Theme.ai, 0.35)
            selectedTextColor: Theme.ink
            persistentSelection: true

            // Which line the caret is on, counted once per move rather than
            // measured from pixels: the highlight and the gutter must agree even
            // while the view is scrolling.
            readonly property int currentLine: text.substring(0, cursorPosition).split("\n").length - 1

            // What the agent changed, behind the glyphs like the caret band and
            // for the same reason. One rectangle per touched line, in the
            // buffer's own coordinates, so it scrolls with the text for free.
            Repeater {
                model: root.diffRows

                Rectangle {
                    id: touched
                    required property int index
                    required property var modelData
                    z: -1
                    x: 0
                    y: editor.topPadding + touched.index * gutter.lineHeight
                    width: editor.width
                    height: gutter.lineHeight
                    visible: touched.modelData.kind !== "same"
                    // Tinted rather than solid: a full-strength green under
                    // monospaced text is a line you cannot read, and the point
                    // of the colour is to let you read it.
                    color: touched.modelData.kind === "add"
                           ? Qt.rgba(0.31, 0.75, 0.53, 0.18)
                           : Qt.rgba(0.88, 0.38, 0.36, 0.18)
                }
            }

            // What a hand on the timeline would change: the line, and on it
            // the part that changes. Behind the glyphs, like the rows above.
            Repeater {
                model: root.aimed

                Rectangle {
                    id: lit
                    required property var modelData
                    readonly property rect head: editor.positionToRectangle(root.offsetOf(modelData.line - 1, modelData.from))
                    readonly property rect tail: editor.positionToRectangle(root.offsetOf(modelData.line - 1, modelData.to))
                    z: -1
                    y: editor.topPadding + (modelData.line - 1) * gutter.lineHeight
                    width: editor.width
                    height: gutter.lineHeight
                    color: Qt.alpha(modelData.refused ? Theme.bad : Theme.live, 0.13)

                    Rectangle {
                        visible: lit.modelData.to > lit.modelData.from && lit.modelData.text.length === 0
                        x: lit.head.x
                        width: lit.tail.x - lit.head.x
                        height: parent.height
                        radius: 2
                        color: Qt.alpha(Theme.live, 0.30)
                    }
                }
            }

            // And over them, once the clip is held: the line as the release
            // will write it, the value following the hand, and what is said
            // beside a line — the statement going under it, or the refusal.
            Repeater {
                model: root.aimed

                Item {
                    id: ghost
                    required property var modelData
                    readonly property string reads: modelData.text
                    readonly property rect end: editor.positionToRectangle(root.offsetOf(modelData.line - 1, 1e6))
                    z: 1
                    y: editor.topPadding + (modelData.line - 1) * gutter.lineHeight
                    width: editor.width
                    height: gutter.lineHeight

                    Rectangle {
                        visible: ghost.reads.length > 0
                        anchors.fill: parent
                        color: Theme.codeSkin.ground

                        Rectangle {
                            anchors.fill: parent
                            color: Qt.alpha(Theme.live, 0.13)
                        }

                        Row {
                            x: editor.leftPadding
                            height: parent.height

                            Text {
                                height: parent.height
                                verticalAlignment: Text.AlignVCenter
                                text: ghost.reads.slice(0, ghost.modelData.from)
                                color: Theme.codeSkin.ink
                                font: editor.font
                            }
                            Text {
                                height: parent.height
                                verticalAlignment: Text.AlignVCenter
                                text: ghost.reads.slice(ghost.modelData.from, ghost.modelData.to)
                                color: Theme.live
                                font: editor.font
                            }
                            Text {
                                height: parent.height
                                verticalAlignment: Text.AlignVCenter
                                text: ghost.reads.slice(ghost.modelData.to)
                                color: Theme.codeSkin.ink
                                font: editor.font
                            }
                        }
                    }

                    Text {
                        visible: ghost.modelData.note.length > 0
                        x: ghost.end.x + 18
                        height: parent.height
                        verticalAlignment: Text.AlignVCenter
                        text: (ghost.modelData.refused ? "" : "↳ ") + ghost.modelData.note
                        color: ghost.modelData.refused ? Theme.bad : Theme.live
                        font: editor.font
                    }
                }
            }

            // The band under the caret, drawn behind the text (z < 0) so it
            // never touches the glyphs.
            Rectangle {
                z: -1
                x: 0
                y: editor.cursorRectangle.y
                width: editor.width
                height: editor.cursorRectangle.height
                color: Theme.codeSkin.band
                visible: editor.activeFocus
            }

            // The line under the pointer, faintly, whether or not the pane has
            // the keyboard: the window answers the hand everywhere, and a line
            // is what a click here will land on. Not past the last line — the
            // empty space below the text belongs to no line.
            Rectangle {
                readonly property rect at: editor.positionToRectangle(editor.positionAt(probe.mouseX, probe.mouseY))
                z: -1
                x: 0
                y: at.y
                width: editor.width
                height: at.height
                color: Theme.hover
                visible: probe.containsMouse && probe.mouseY <= editor.topPadding + editor.contentHeight
            }

            // Only a human's edit dirties the buffer: assigning the initial text
            // fires onTextChanged too, and counting that as a modification made
            // the pane open claiming an edit nobody had made.
            //
            // What the buffer looked like when nobody had touched it. `ready`
            // alone was not enough: attaching the syntax highlighter marks the
            // document changed, and QSyntaxHighlighter runs its first pass on a
            // later tick — after the flag was set — so the panel opened claiming
            // an edit nobody had made. Comparing the text catches that, because
            // colouring changes the formatting and never a character.
            property bool ready: false
            // Not `baseline`: that is one of Item's anchor lines and it is FINAL,
            // so the panel refused to load at all.
            property string pristine: ""

            Component.onCompleted: {
                pristine = text;
                root.document = editor.textDocument;
                root.documentReady(editor.textDocument, false);
                ready = true;
            }

            // Changing theme has to reach the text that is already painted, and
            // the palette lives outside this panel — so the panel offers its
            // document again and the shell repaints it.
            Connections {
                target: Theme
                function onCodeThemeChanged() { root.documentReady(editor.textDocument, false); }
            }

            // Arrowing away, or clicking elsewhere, is the same statement as
            // moving the mouse away: the bubble is about somewhere you no
            // longer are.
            onCursorPositionChanged: {
                probe.dismiss();
                if (hint.visible && editor.currentLine !== hint.forLine)
                    hint.visible = false;
            }

            onTextChanged: {
                // A hover describes the word it was asked about, and typing has
                // just moved that word. Every editor drops it on the first
                // keystroke rather than leaving stale prose over live code.
                probe.dismiss();

                if (finding.visible && editor.text !== finding.counted)
                    finding.recount();

                if (!ready || text === pristine)
                    return;
                root.modified = true;

                // The author has written something of their own, so the agent's
                // turn stops being one thing to undo: a ⌘Z that swallowed both
                // would take work nobody asked it to take. The key goes back to
                // being the editor's own undo from here.
                Agent.disarm();

                // Narrowing happens now, on the letter just typed; asking the
                // server happens after the pause. The list therefore never
                // shows a name that no longer matches what is on screen.
                if (suggestions.visible)
                    suggestions.refine();
                const just = editor.text.charAt(editor.cursorPosition - 1);
                if (root.path.length > 0 && /[A-Za-z0-9_.]/.test(just))
                    ask.restart();
                else
                    suggestions.visible = false;

                // Opening a call asks what it takes; a comma asks again,
                // because the answer is which argument you are now on. Closing
                // it ends the question.
                if (root.path.length === 0)
                    return;
                if (just === "(" || just === ",")
                    askSignature.restart();
                else if (just === ")")
                    hint.visible = false;
            }

            Timer {
                id: askSignature
                interval: 160
                onTriggered: {
                    const at = root.locationAt(editor.cursorPosition);
                    Lsp.signatureHelp(root.path, at.line, at.character, function (reply) { hint.offer(reply); });
                }
            }

            // The pause after which the buffer is worth an opinion. It also
            // gives Main's handler time to push the edit to the server: asking
            // about text the server has not been told about answers about the
            // text before it.
            Timer {
                id: ask
                interval: 160
                onTriggered: {
                    const at = root.locationAt(editor.cursorPosition);
                    Lsp.completion(root.path, at.line, at.character, function (reply) {
                        // Either a bare list or { isIncomplete, items } — both
                        // shapes are legal and pyright uses the second.
                        suggestions.offer(reply && reply.items !== undefined ? reply.items : reply);
                    });
                }
            }

            // A press the text did not take is still a press in the file.
            //
            // The band under the last line belongs to the control — see the
            // height above — but which path a press travels down there is not
            // the same for a synthesised event and a real pointer: the Flickable
            // filters the real one for a drag first, and a press nobody claims
            // is simply dropped. A handler sees what is left. It answers only
            // BELOW the text, so clicking, dragging a selection and
            // double-clicking a word on a line are untouched.
            TapHandler {
                acceptedButtons: Qt.LeftButton
                onTapped: (point) => {
                    if (point.position.y <= editor.topPadding + editor.contentHeight)
                        return;
                    editor.forceActiveFocus();
                    editor.cursorPosition = editor.length;
                }
            }

            // ── Hovering a symbol ─────────────────────────────────────────
            // Declared BEFORE the squiggles so they sit above it: over a
            // squiggle the message wins, everywhere else the type wins. Asking
            // the server on every mouse move would be a request per pixel, so
            // the pointer has to come to rest first.
            MouseArea {
                id: probe
                anchors.fill: parent
                // Unset, not the arrow: this area only watches — a MouseArea
                // claims the arrow from birth, and over the text that hid the
                // text caret. What is under the pointer says what it is.
                cursorShape: undefined
                // Clicks are taken only to be handed straight back: ⌘-click
                // follows a definition, and a press with no modifier is
                // refused, which passes it up to the text where it belongs.
                acceptedButtons: Qt.LeftButton
                hoverEnabled: true

                onPressed: (mouse) => {
                    if ((mouse.modifiers & Qt.ControlModifier) && root.path.length > 0) {
                        const at = root.locationAt(editor.positionAt(mouse.x, mouse.y));
                        Lsp.definition(root.path, at.line, at.character, function (reply) { root.follow(reply); });
                        return;
                    }

                    mouse.accepted = false;
                }

                property real lastX: 0
                property real lastY: 0

                // Every reply the server sends answers a question about a
                // POSITION, and the pointer has usually moved on by the time it
                // lands. Without a token the late answer painted a bubble for a
                // word the mouse had already left — and nothing was left to
                // hide it, so it stayed until the next hover. Bumping this on
                // every move, exit and dismissal makes a stale reply arrive
                // holding the wrong number, and drop itself.
                property int token: 0

                // Where the word the bubble is about starts. A line holds several:
                // `position` and `cornerRadius` sit on one, and the rule below kept
                // the first one's answer while the pointer walked onto the second.
                property int forWord: -1

                function dismiss() {
                    probe.token++;
                    dwell.stop();
                    tip.forY = -1;
                    probe.forWord = -1;
                    tip.hide();
                }

                onPositionChanged: (mouse) => {
                    // An open bubble survives the pointer MOVING. It used to die
                    // on the first pixel of travel — including a pixel along the
                    // very word it was describing — because any move that was not
                    // already inside the bubble dismissed it. You could not read
                    // what you had asked for without holding your hand still.
                    //
                    // It closes when you have left BOTH the line it is about and
                    // the bubble itself; anywhere on that line, in the bubble, or
                    // in the few pixels between them, it stays. VS Code lets you
                    // walk onto a hover to read it, and this is the same rule with
                    // the line included.
                    if (tip.visible) {
                        if (mouse.y >= tip.forY && mouse.y <= tip.forY + gutter.lineHeight
                            && root.wordStart(editor.positionAt(mouse.x, mouse.y)) === probe.forWord)
                            return;
                        const at = editor.mapToItem(root, mouse.x, mouse.y);
                        if (at.x >= tip.x - 4 && at.x <= tip.x + tip.width + 4
                            && at.y >= tip.y - 6 && at.y <= tip.y + tip.height + 4)
                            return;
                    }
                    probe.lastX = mouse.x;
                    probe.lastY = mouse.y;
                    probe.dismiss();
                    dwell.restart();
                }

                onExited: probe.dismiss()

                Timer {
                    id: dwell
                    interval: 400
                    onTriggered: {
                        if (root.path.length === 0)
                            return;
                        const offset = editor.positionAt(probe.lastX, probe.lastY);
                        probe.forWord = root.wordStart(offset);
                        const at = root.locationAt(offset);
                        const anchor = editor.positionToRectangle(offset);
                        const mine = ++probe.token;
                        Lsp.hover(root.path, at.line, at.character, function (reply) {
                            if (mine !== probe.token)
                                return;
                            tip.show(root.readable(reply), anchor.x, anchor.y + anchor.height);
                        });
                    }
                }
            }

            // ── The squiggles ─────────────────────────────────────────────
            // Children of the TextArea rather than of the ScrollView, so they
            // scroll with the text for free — the same reason the current-line
            // band lives here. Under the glyphs would hide them, so they sit at
            // the default z and are drawn as a thin wave along the baseline.
            Repeater {
                model: root.shownDiagnostics

                Item {
                    id: squiggle
                    required property var modelData

                    // A diagnostic that spans lines is underlined on its first
                    // line only: a wave running down the left margin of three
                    // lines says nothing the first line did not already say.
                    readonly property int startLine: squiggle.modelData.range.start.line
                    readonly property rect head: editor.positionToRectangle(
                        root.offsetOf(squiggle.startLine, squiggle.modelData.range.start.character))
                    readonly property rect tail: editor.positionToRectangle(
                        squiggle.modelData.range.end.line === squiggle.startLine
                        ? root.offsetOf(squiggle.startLine, squiggle.modelData.range.end.character)
                        : root.offsetOf(squiggle.startLine + 1, 0) - 1)

                    x: squiggle.head.x
                    y: squiggle.head.y
                    // An empty range still has to be visible, or a diagnostic
                    // pointing at a missing character marks nothing at all.
                    width: Math.max(squiggle.tail.x - squiggle.head.x, 6)
                    height: squiggle.head.height

                    Canvas {
                        id: wave
                        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                        height: 3

                        onPaint: {
                            const ctx = getContext("2d");
                            ctx.reset();
                            ctx.strokeStyle = root.severityColor(squiggle.modelData.severity);
                            ctx.lineWidth = 1;
                            ctx.beginPath();
                            // Period of four pixels: shorter reads as a dotted
                            // line at this font size, longer as a scribble.
                            for (let x = 0; x <= width; ++x)
                                ctx.lineTo(x, 1.5 + Math.sin(x * Math.PI / 2) * 1.2);
                            ctx.stroke();
                        }

                        onWidthChanged: wave.requestPaint()
                    }

                    // Reading the message must not cost the caret its place, so
                    // the strip hovers and never takes a click.
                    MouseArea {
                        anchors.fill: parent
                        acceptedButtons: Qt.NoButton
                        hoverEnabled: true
                        cursorShape: undefined // the text's caret, not an arrow over a word
                        ToolTip.visible: containsMouse
                        ToolTip.delay: 350
                        ToolTip.text: squiggle.modelData.message
                    }
                }
            }

            Keys.onPressed: (event) => {
                // While the list is up it owns the keys it needs and nothing
                // else — the arrows, the two ways of accepting, and escape.
                // Everything else falls through and keeps typing, which is what
                // narrows the list.
                // Les flèches NUES, pas celles qui portent un modificateur :
                // ⌘↓ déplace la ligne, et une liste qui l'avalait rendait le
                // geste impossible tant qu'elle était ouverte — sans qu'on
                // comprenne pourquoi, puisqu'elle se referme au premier clic.
                if (suggestions.visible && (event.modifiers & (Qt.ControlModifier | Qt.MetaModifier | Qt.AltModifier)) === 0) {
                    if (event.key === Qt.Key_Down) {
                        list.incrementCurrentIndex();
                        event.accepted = true;
                        return;
                    }
                    if (event.key === Qt.Key_Up) {
                        list.decrementCurrentIndex();
                        event.accepted = true;
                        return;
                    }
                    if (event.key === Qt.Key_Return || event.key === Qt.Key_Enter || event.key === Qt.Key_Tab) {
                        suggestions.accept();
                        event.accepted = true;
                        return;
                    }
                    if (event.key === Qt.Key_Escape) {
                        suggestions.visible = false;
                        event.accepted = true;
                        return;
                    }
                }

                if (event.key === Qt.Key_Escape && uses.visible) {
                    uses.visible = false;
                    event.accepted = true;
                    return;
                }

                if (event.key === Qt.Key_Escape && finding.visible) {
                    finding.shut();
                    event.accepted = true;
                    return;
                }

                // Each of these is ASKED of Keymap rather than spelled out here,
                // so the keyboard board and this handler cannot drift apart:
                // rebinding writes one string and both follow it.
                if (root.path.length > 0) {
                    const at = root.locationAt(editor.cursorPosition);

                    if (Keymap.matches(event, "definition")) {
                        Lsp.definition(root.path, at.line, at.character, function (reply) { root.follow(reply); });
                        event.accepted = true;
                        return;
                    }
                    if (Keymap.matches(event, "references")) {
                        Lsp.references(root.path, at.line, at.character, function (reply) { uses.offer(reply); });
                        event.accepted = true;
                        return;
                    }
                    if (Keymap.matches(event, "rename")) {
                        renaming.begin();
                        event.accepted = true;
                        return;
                    }
                    if (Keymap.matches(event, "complete")) {
                        ask.restart();
                        event.accepted = true;
                        return;
                    }
                    if (Keymap.matches(event, "save")) {
                        root.saveRequested();
                        event.accepted = true;
                        return;
                    }
                    if (Keymap.matches(event, "execute")) {
                        root.executeRequested();
                        event.accepted = true;
                        return;
                    }
                    if (Keymap.matches(event, "playFromCaret")) {
                        root.playFromCaret();
                        event.accepted = true;
                        return;
                    }
                }
                // ⌘ arrives as ControlModifier and ⌃ as MetaModifier: Qt swaps
                // the two on macOS so that a shortcut written once lands on the
                // key a Mac user expects. So ⌘← is ControlModifier here, and
                // ⌃Space below is MetaModifier — reading them the other way
                // round silently binds nothing.
                if (Keymap.matches(event, "find")) {
                    finding.open();
                    event.accepted = true;
                    return;
                }
                if (Keymap.matches(event, "replace")) {
                    root.openReplace();
                    event.accepted = true;
                    return;
                }

                // Ici, et pas dans un `Shortcut` de la coquille : un TextEdit
                // réclame ces touches par ShortcutOverride avant qu'un raccourci
                // ne tire. ⌘↑ et ⌘↓ sont le début et la fin du document pour
                // macOS, et c'est ça qui répondait — la ligne ne bougeait pas.
                if (Keymap.matches(event, "moveUp")) {
                    root.moveLine(-1);
                    event.accepted = true;
                    return;
                }
                if (Keymap.matches(event, "moveDown")) {
                    root.moveLine(1);
                    event.accepted = true;
                    return;
                }
                if (Keymap.matches(event, "deleteWord")) {
                    root.deleteWordRight();
                    event.accepted = true;
                    return;
                }
                if (Keymap.matches(event, "redo")) {
                    root.redo();
                    event.accepted = true;
                    return;
                }
                if (Keymap.matches(event, "back")) {
                    root.goBack();
                    event.accepted = true;
                    return;
                }
                if (Keymap.matches(event, "forward")) {
                    root.goForward();
                    event.accepted = true;
                    return;
                }

                // Tab is four spaces, because the buffer is Python and a stray
                // tab character is a syntax error waiting for the next editor to
                // open the file.
                if (event.key === Qt.Key_Tab) {
                    editor.insert(editor.cursorPosition, "    ");
                    event.accepted = true;
                }
            }
        }
    }
}
