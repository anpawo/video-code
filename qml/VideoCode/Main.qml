// The editor shell.
//
// One dock, described by a TREE: a node is either a slot holding tabs or a split
// holding more nodes. There are no named layouts — two fixed arrangements to
// choose between answered a question nobody asked ("which of my two moods is
// this?") while refusing the one they did ("put the code where I want it").
//
// Every gesture is one edit to that tree:
//   · drop a tab on a slot's strip or middle  → the slot gains a tab
//   · drop it near a slot's edge              → the slot becomes a split of two
//   · drop it outside the window              → it leaves in a window of its own
//   · close the last tab of a slot            → the slot is pruned away
// The tree is then written to disk, so the arrangement outlives the process.
//
// All shared state lives here and the panels are views onto it, so moving a
// panel cannot lose your selection, your playhead or your unsaved buffer: the
// items themselves are created once, below, and only ever change parent.
pragma ComponentBehavior: Bound

import QtQml
import QtQuick
import QtQuick.Controls
import QtQuick.Window

ApplicationWindow {
    id: app

    // An editor opens filling the screen: every pane in this dock is sized as a
    // fraction of the window, so a small window makes all six of them useless at
    // once. The width/height below are only what a restored window falls back to.
    width: 1440
    height: 900
    // Shown maximized, or not shown at all.
    //
    // Said with `visibility` alone: setting `visible` beside it is a conflict Qt
    // warns about and resolves in an order nobody should have to know — and here
    // the losing side would be a window appearing when it was asked not to.
    //
    // It is asked not to because macOS has no public way to choose which Space a
    // window opens on (only private CoreGraphics calls), so a window opened by a
    // check lands on whatever desktop its author happens to be working on. The
    // fix is not to place it better. It is to not open one.
    visibility: Shell.headless ? ApplicationWindow.Hidden : ApplicationWindow.Maximized
    // The window is named after the arrangement you are in, not after the
    // program: which of them you are looking at is the one thing a title bar can
    // tell you that the window itself does not already show.
    title: templateLabel(template)
    color: Theme.ground

    // ── Shared state ──────────────────────────────────────────────────────
    // Nothing, until the buffer has been executed. There used to be a stand-in
    // scene here — five invented clips with names like `interview.mp4` — and it
    // was the right thing while the chrome was being built against no model at
    // all. It is the wrong thing now: the timeline is a picture OF THE CODE, and
    // a picture of something else is worse than no picture, because it is read
    // as an answer. The empty state says what to press instead.
    readonly property var emptyScene: ({ fps: 30, duration: 0, elements: [], waits: [], markers: [] })

    property int selectedIndex: -1
    property real playhead: 0
    property bool playing: false

    // The speaker follows `playing`: every way of starting or stopping — the
    // space bar, ⌘⏎, the end of the range, `tell play` — goes through here.
    onPlayingChanged: {
        if (!Shell.hasAudio)
            return;
        if (playing)
            Shell.audioPlay(playhead);
        else
            Shell.audioPause();
    }

    // The one way the playhead is moved by hand. The speaker is told too, so
    // Home, End, ±1 frame and a click on the ruler stay in step while playing.
    function seekTo(seconds) {
        playhead = Math.max(0, Math.min(seconds, shownScene.duration));
        if (Shell.hasAudio)
            Shell.audioSeek(playhead);
    }

    // ── What a gesture snaps to ───────────────────────────────────────────
    // The moments a drop or a trim should prefer over the arithmetic mean of
    // wherever your hand stopped: where clips start and end, where the scene
    // waits, where the playhead is, where the range is marked.
    //
    // Tenths are the fallback, not the rule. Snapping only to a grid makes an
    // editor that cannot line two things up exactly — which is the one thing
    // you use the timeline for.
    readonly property var snapPoints: {
        const out = [0];
        for (const one of shownScene.elements) {
            out.push(one.l);
            out.push(one.l + one.d);
        }
        for (const gap of (shownScene.waits !== undefined ? shownScene.waits : [])) {
            out.push(gap.at);
            out.push(gap.at + gap.d);
        }
        // A marker is a moment the author named on purpose.
        for (const mark of (shownScene.markers !== undefined ? shownScene.markers : []))
            out.push(mark.at);
        out.push(playhead);
        if (markIn >= 0) out.push(markIn);
        if (markOut >= 0) out.push(markOut);
        return out;
    }

    // `exact` is ⌘ held: no snapping at all, the moment under the pointer.
    function snapTime(seconds, exact) {
        if (exact)
            return Math.round(seconds * 100) / 100;

        // Eight pixels' worth of forgiveness, in seconds — the same distance on
        // screen whatever the zoom, which is what makes it feel like the same
        // magnet at every scale.
        const reach = 8 / Math.max(timeline.pxPerSecond, 1);
        let best = -1;
        let near = reach;
        for (const one of snapPoints) {
            const d = Math.abs(one - seconds);
            if (d < near) {
                near = d;
                best = one;
            }
        }
        if (best >= 0)
            return Math.round(best * 100) / 100;
        return Math.round(seconds * 10) / 10;
    }

    // ── The range ─────────────────────────────────────────────────────────
    // Two moments, in seconds, or -1 for "not set". They are a VIEW of the
    // scene, not part of it: nothing in the code says which part of a scene you
    // are working on this afternoon, and writing it there would be writing a
    // preference into a program.
    //
    // What they change is what Space means. Play with a range set plays the
    // range and stops at its end — the loop you cut against — and everything
    // outside it is dimmed on the timeline so you can see what you are ignoring.
    property real markIn: -1
    property real markOut: -1

    readonly property bool ranged: markIn >= 0 && markOut > markIn

    function setMarkIn() {
        markIn = playhead;
        // An out point before the in point is not a range, it is a mistake with
        // a number in it. The one you just placed is the one that stands.
        if (markOut >= 0 && markOut <= markIn)
            markOut = -1;
        source.say("in at " + playhead.toFixed(2) + "s");
    }

    function setMarkOut() {
        markOut = playhead;
        if (markIn >= 0 && markIn >= markOut)
            markIn = -1;
        source.say("out at " + playhead.toFixed(2) + "s");
    }

    function clearMarks() {
        markIn = -1;
        markOut = -1;
        source.say("the whole scene again");
    }

    // ── The moments the scene named ───────────────────────────────────────
    // A `timestamp()` is a place the author decided was worth coming back to,
    // so it is somewhere to jump to as well as something to look at. Half a
    // frame of slack, because a playhead the last jump parked exactly ON a
    // marker would otherwise count it as the next one and never leave it.
    //
    // It says the name it landed on: on a crowded ruler the name beside a flag
    // is elided, and a jump that moves the playhead silently is a jump you have
    // to work out for yourself.
    function jumpToMarker(direction) {
        const slack = 0.5 / (execFps > 0 ? execFps : 30);
        let best = null;
        for (const mark of (shownScene.markers !== undefined ? shownScene.markers : [])) {
            const ahead = (mark.at - playhead) * direction;
            if (ahead > slack && (best === null || ahead < (best.at - playhead) * direction))
                best = mark;
        }
        if (best === null) {
            source.say(direction > 0 ? "no marker after this one" : "no marker before this one");
            return;
        }
        // Placing the playhead stops play, the way scrubbing to it does.
        playing = false;
        seekTo(best.at);
        source.say(best.n);
    }

    readonly property var selectedElement:
        selectedIndex >= 0 && selectedIndex < shownScene.elements.length
        ? shownScene.elements[selectedIndex]
        : null

    // Something is always selected once the scene has something: an empty
    // Inspector was a panel that answered nothing, asked on 19 Sept. So when the
    // selection is gone — Escape, a first run, a re-run that dropped the element
    // — it lands on the top lane as the timeline draws it, and Escape now means
    // "back to the first", not "nothing". Filled quietly: only a click brings
    // the Inspector's tab forward. Called later, not at once: the lanes' order
    // is itself re-derived from the scene that just changed.
    function holdSelection() {
        const lanes = timeline.lanesOrder;
        if (selectedElement !== null || lanes.length === 0)
            return;
        selectedIndex = lanes[0];
        inspector.open(selectedElement, Qt.rect(0, 0, 0, 0));
    }
    onSelectedElementChanged: Qt.callLater(holdSelection)

    // ── The dock ──────────────────────────────────────────────────────────
    // Panels are created once, below, and never move house: a slot is told which
    // keys it holds and reparents those items into itself. Everything about the
    // arrangement is therefore this tree, and a gesture is one edit to it.
    readonly property var panelItems: ({
        "media": media,
        "library": library,
        "preview": preview,
        "timeline": timeline,
        "agent": agent,
        "inspector": inspector,
        "code": source
    })

    // The code tab carries the file it is showing, and only while it is the tab
    // you are looking at: a slot that holds Code behind Agent has no room to
    // spell out a filename for a pane nobody can see, and the name would then be
    // stale advice rather than a label. The dot is the unsaved mark — until now
    // the pane knew it was modified and had nowhere to say so.
    readonly property var panelTitles: ({
        "media": "Media",
        "library": "Library",
        "preview": "Preview",
        "timeline": "Timeline",
        "agent": "Agent",
        "inspector": "Inspector",
        "code": "Code"
    })

    // Whether the Code pane is the CURRENT tab of whichever slot holds it.
    property bool codeShown: false

    function currentKeys(node, out) {
        if (node.t === "s") {
            if (node.keys.length > 0)
                out.push(node.keys[Math.max(0, Math.min(node.current, node.keys.length - 1))]);
            return out;
        }
        for (const child of (node.nodes || []))
            currentKeys(child, out);
        return out;
    }

    function refreshCodeShown() {
        let shown = currentKeys(tree, []);
        for (const one of floats)
            if (one.keys.length > 0)
                shown.push(one.keys[Math.max(0, Math.min(one.current, one.keys.length - 1))]);
        codeShown = shown.indexOf("code") >= 0;
    }

    readonly property var panelKeys: ["media", "library", "preview", "timeline", "agent", "inspector", "code"]

    property var tree: defaultTree()

    // Panels that live in a window of their own: {id, keys, current, x, y, w, h}.
    property var floats: []

    // Set while a tab is in flight, so the slot under the cursor can show where
    // it would land.
    property string hoverSlot: ""
    property string hoverZone: ""

    // id → the Item drawing that node, filled by the tree as it renders. It is
    // what turns a cursor position into "which slot is that", and what lets the
    // saved layout record the sizes the user dragged the handles to.

    property int nextId: 1

    function makeId() {
        return "n" + (nextId++);
    }

    // ── Measuring the arrangement ─────────────────────────────────────────
    // Two readings of the same number, for the two moments you want it.
    //
    // `measuring` blanks every pane and writes the share of the window it takes:
    // the panes stop being what they contain and become what they measure, which
    // is the only way to compare them at a glance. It lasts until the next click,
    // because it is a question, not a mode you work in.
    //
    // `tip` is the same figure during a drag, next to the pointer, for the panes
    // the drag is moving. Deciding a size while it is still under your hand beats
    // dragging, letting go, looking, and dragging again.
    property bool measuring: false
    property var tip: null

    // The area the panes divide between them, handed to every slot so a share is
    // a share of the same thing wherever it is read.
    readonly property Item dockArea: dockArea

    // A tenth of a percent, with a comma — the same reading the panes give, so a
    // splitter and the pane it moves never disagree about what they measure.
    function sharePercent(part, whole) {
        return whole > 0 ? (part / whole * 100).toFixed(1).replace(".", ",") + "%" : "—";
    }

    function showTip(x, y, text) { tip = { x: x, y: y, text: text }; }
    function hideTip() { tip = null; }

    // The arrangement a first launch opens in. Video Coding, because this is an
    // application for writing videos in Python before it is anything else, and
    // the window ought to open on the thing you came to do.
    property string template: "code"

    // How the bin draws itself: "grid" or "list". It belongs to the arrangement
    // rather than to the application, because it answers the same question the
    // arrangement does — what are you doing right now. Writing the scene by hand
    // wants filenames in a column; cutting wants pictures.
    property string mediaDisplay: "grid"

    // Media the user has added this session. The scene's own assets come from
    // the compiled buffer and are not ours to edit; these sit beside them until
    // the day adding a file writes an input into the source, which is the same
    // door a timeline drag will use.
    property var addedAssets: []

    function kindOfFile(path) {
        const extension = path.split(".").pop().toLowerCase();
        if (["mp4", "mov", "mkv", "webm", "avi"].indexOf(extension) >= 0)
            return "video";
        if (["wav", "mp3", "aac", "flac", "m4a", "ogg"].indexOf(extension) >= 0)
            return "sound";
        if (["png", "jpg", "jpeg", "svg", "gif", "webp"].indexOf(extension) >= 0)
            return "image";
        return "";
    }

    function addMedia() {
        const chosen = Shell.pickMedia();
        if (!chosen || chosen.length === 0)
            return;

        const next = addedAssets.slice();
        for (let i = 0; i < chosen.length; i++) {
            const kind = kindOfFile(chosen[i]);
            // A file the engine has no input class for is not quietly filed
            // under a hue that would lie about what it is.
            if (kind === "")
                continue;
            next.push({ n: chosen[i].split("/").pop(), kind: kind, path: chosen[i] });
        }
        addedAssets = next;
    }

    // Trees the user has bent out of shape, keyed by template.
    property var layouts: ({})

    // Built-in arrangements the user has REPLACED, keyed by template. Where
    // `layouts` remembers a bend that Reset UI throws away, this is the new
    // shape itself — what Reset UI goes back TO.
    property var defaults: ({})

    // Arrangements the user has named and kept: [{ name, tree, floats, options }].
    // The three built-in templates are shapes to start from; these are the ones
    // that turned out to be worth keeping, and they sit in the same menus, under
    // keys of the form "user:<name>".
    property var saved: []

    function savedIndex(name) {
        for (let i = 0; i < saved.length; i++)
            if (saved[i].name === name)
                return i;
        return -1;
    }

    // A built-in arrangement, replaced by yours.
    //
    // Save display… under the name of one of the four — "Video Coding", say —
    // and it is that arrangement you are rewriting, not a fifth one beside it
    // with a confusing name. It holds for good: Reset UI then puts back YOUR
    // Video Coding, because the one it ships with stopped being the answer the
    // moment you said otherwise.
    function templateKeyNamed(name) {
        const wanted = name.trim().toLowerCase();
        for (const one of Layouts.templates)
            if (one.label.toLowerCase() === wanted)
                return one.key;
        return "";
    }

    // Saving over a name replaces it: two displays called the same thing is a
    // list you cannot read.
    function saveDisplay(name) {
        const snapshot = copy(tree);

        const builtIn = templateKeyNamed(name);
        if (builtIn.length > 0) {
            const nextDefaults = copy(defaults);
            nextDefaults[builtIn] = {
                tree: snapshot,
                floats: copy(floats),
                options: { mediaDisplay: mediaDisplay }
            };
            defaults = nextDefaults;

            // The template's own edits are dropped: they were bends of the old
            // shape, and the shape has changed.
            const trimmed = copy(layouts);
            delete trimmed[builtIn];
            layouts = trimmed;

            template = builtIn;
            saveLayout();
            Shell.setDockTemplates(menuTemplates());
            return;
        }

        const entry = {
            name: name,
            tree: snapshot,
            floats: copy(floats),
            options: { mediaDisplay: mediaDisplay }
        };

        const next = copy(saved);
        const at = savedIndex(name);
        if (at >= 0)
            next[at] = entry;
        else
            next.push(entry);

        saved = next;
        template = "user:" + name;
        saveLayout();
        Shell.setDockTemplates(menuTemplates());
        Shell.setDockDisplays(menuDisplays());
    }

    // Keep what is on screen as what this display IS.
    //
    // Save display… already does it — type the name of the arrangement you are
    // in and it rewrites that one rather than making a fifth with a confusing
    // name — but that asks you to know the rule and to type the name exactly.
    // This is the same act with the name filled in: whatever you are in, built-in
    // or your own, is now shaped like this, and Reset UI puts back THIS.
    function updateDefault() {
        if (template.length === 0)
            return;

        // Through `app`, not by bare name: the Save display… dialog is `id:
        // saveDisplay`, and an id wins over a function of the same name.
        if (template.indexOf("user:") === 0)
            app.saveDisplay(template.substring(5));
        else
            app.saveDisplay(templateLabel(template));

        source.say("updated " + templateLabel(template));
    }

    function loadDisplay(name) {
        const at = savedIndex(name);
        if (at < 0)
            return;

        // What you are leaving is kept the way switching template keeps it, so
        // loading a display never costs you the one you were in.
        const kept = copy(layouts);
        const snapshot = copy(tree);
        kept[template] = { tree: snapshot, floats: copy(floats), options: { mediaDisplay: mediaDisplay } };
        layouts = kept;

        const entry = saved[at];
        restoring = true;
        template = "user:" + name;
        tree = copy(entry.tree);
        floats = copy(entry.floats || []);
        mediaDisplay = entry.options && entry.options.mediaDisplay === "list" ? "list" : "grid";
        restoring = false;

        saveLayout();
        Shell.setDockTemplates(menuTemplates());
    }

    // The bin opens as a details list where its pane is short — sharing a row
    // with the timeline leaves no height for thumbnails, and a squashed picture
    // of a file is worth less than its name. Everywhere else it opens as a grid.
    function templateLabel(key) { return Layouts.label(key); }
    function buildOptions(key) {
        const mine = defaults[key];
        return mine && mine.options ? copy(mine.options) : Layouts.options(key);
    }
    function buildTemplate(key) {
        // Yours if you have saved one under that name, otherwise the one it
        // ships with.
        const mine = defaults[key];
        return mine && mine.tree ? copy(mine.tree) : Layouts.tree(key);
    }

    function buildFloats(key) {
        const mine = defaults[key];
        return mine && mine.floats ? copy(mine.floats) : [];
    }

    function defaultTree() {
        return buildTemplate(template);
    }

    // Switching keeps what you did to the template you are leaving, floating
    // panels included: they belong to an arrangement as much as the panes do.
    function useTemplate(key) {
        if (key === template)
            return;

        if (key.indexOf("user:") === 0) {
            loadDisplay(key.substring(5));
            return;
        }

        const kept = copy(layouts);
        const snapshot = copy(tree);
        kept[template] = {
            tree: snapshot,
            floats: copy(floats),
            options: { mediaDisplay: mediaDisplay }
        };

        const saved = kept[key];
        const options = saved && saved.options ? saved.options : buildOptions(key);
        layouts = kept;
        template = key;
        restoring = true;
        tree = saved && saved.tree ? saved.tree : buildTemplate(key);
        floats = saved && saved.floats ? saved.floats : buildFloats(key);
        mediaDisplay = options.mediaDisplay === "list" ? "list" : "grid";
        restoring = false;

        saveLayout();
        Shell.setDockTemplates(menuTemplates());
    }

    // The tree is replaced, never edited in place: a binding on `tree` does not
    // hear about a push() three levels down inside it.
    function copy(value) {
        return JSON.parse(JSON.stringify(value));
    }

    function eachNode(node, fn, parent, index) {
        fn(node, parent, index);
        if (node.t === "x")
            for (let i = 0; i < node.nodes.length; i++)
                eachNode(node.nodes[i], fn, node, i);
    }

    function findNode(root, id) {
        let found = null;
        eachNode(root, (node, parent, index) => {
            if (node.id === id)
                found = { node: node, parent: parent, index: index };
        });
        return found;
    }

    function slotOf(id) {
        const hit = findNode(tree, id);
        if (hit && hit.node.t === "s")
            return hit.node;
        for (let i = 0; i < floats.length; i++)
            if (floats[i].id === id)
                return floats[i];
        return null;
    }

    // Which panels are on screen at all — the rest are what the ⋯ menu offers to
    // bring back.
    function shownKeys() {
        const shown = [];
        eachNode(tree, (node) => {
            if (node.t === "s")
                for (let i = 0; i < node.keys.length; i++)
                    shown.push(node.keys[i]);
        });
        for (let i = 0; i < floats.length; i++)
            shown.push(...floats[i].keys);
        return shown;
    }

    // ── Editing the tree ──────────────────────────────────────────────────
    function pickTab(id, index) {
        const hit = findNode(tree, id);
        if (hit) {
            const next = copy(tree);
            // Read the panes as they STAND before replacing the tree.
            //
            // A dragged handle moves the items, not the model: the fractions in
            // the tree are still the ones it was rendered from. Every other edit
            // captures them first; picking a tab did not, so replacing the tree
            // re-rendered it from stale numbers and every pane you had resized
            // sprang back — which looked like switching tabs had a side effect.
            findNode(next, id).node.current = index;
            tree = next;
            saveLayout();
            return;
        }
        const nextFloats = copy(floats);
        for (let i = 0; i < nextFloats.length; i++)
            if (nextFloats[i].id === id)
                nextFloats[i].current = index;
        floats = nextFloats;
    }

    // An empty slot is not kept: a hole you cannot see is a hole you cannot fill
    // back in. What was closed comes back from the ⋯ menu, which is the list of
    // everything, not from a gap left in the dock.
    function prune(node) {
        // A gap is a node that draws nothing. It is kept for the same reason a
        // slot is: someone put it there on purpose.
        if (node.t === "g")
            return node.size > 0.02 ? node : null;

        if (node.t === "s")
            return node.keys.length > 0 ? node : null;

        const kept = [];
        for (let i = 0; i < node.nodes.length; i++) {
            const child = prune(node.nodes[i]);
            if (child)
                kept.push(child);
        }
        if (kept.length === 0)
            return null;

        // Space with nothing beside it is not space, it is a hole where a window
        // used to be — so a branch that has become all gaps goes with them.
        let onlyGaps = true;
        for (let i = 0; i < kept.length; i++)
            if (kept[i].t !== "g")
                onlyGaps = false;
        if (onlyGaps)
            return null;

        if (kept.length === 1) {
            // A split of one is not a split; it takes its parent's place and the
            // room that came with it.
            kept[0].size = node.size;
            return kept[0];
        }

        let total = 0;
        for (let i = 0; i < kept.length; i++)
            total += kept[i].size;
        for (let i = 0; i < kept.length; i++)
            kept[i].size = kept[i].size / total;

        node.nodes = kept;
        return node;
    }

    function settle(next) {
        const pruned = prune(next);
        // The dock is never nothing: an empty one is a slot waiting to be filled,
        // which is also the only thing you can drop a tab back onto.
        tree = pruned !== null
               ? pruned
               : { t: "s", id: makeId(), keys: [], current: 0, size: 1 };
    }

    function detach(next, nextFloats, key) {
        eachNode(next, (node) => {
            if (node.t !== "s")
                return;
            const at = node.keys.indexOf(key);
            if (at < 0)
                return;
            node.keys.splice(at, 1);
            node.current = Math.max(0, Math.min(node.current, node.keys.length - 1));
        });
        for (let i = 0; i < nextFloats.length; i++) {
            const at = nextFloats[i].keys.indexOf(key);
            if (at < 0)
                continue;
            nextFloats[i].keys.splice(at, 1);
            nextFloats[i].current = Math.max(0, Math.min(nextFloats[i].current, nextFloats[i].keys.length - 1));
        }
    }

    function dockTab(key, targetId, zone) {
        const next = copy(tree);
        const nextFloats = copy(floats).filter((one) => one.keys.length > 0 || one.keys.indexOf(key) >= 0);
        detach(next, nextFloats, key);

        // The dock's own edge: the arrangement that exists becomes one side of a
        // new split, and the tab becomes the other. Everything keeps its shape
        // and gives up a share of the window — which is what makes it read as
        // room being MADE rather than a pane being taken over.
        if (targetId === app.wholeDock) {
            const across = zone === "left" || zone === "right";
            const kept = prune(next);
            const leaf = { t: "s", id: makeId(), keys: [key], current: 0, size: 0.28 };
            if (kept === null) {
                leaf.size = 1;
                tree = leaf;
            } else {
                kept.size = 0.72;
                tree = {
                    t: "x", id: makeId(), dir: across ? "h" : "v", size: 1,
                    nodes: zone === "left" || zone === "top" ? [leaf, kept] : [kept, leaf]
                };
            }
            floats = nextFloats.filter((one) => one.keys.length > 0);
            return;
        }

        const hit = findNode(next, targetId);
        if (!hit) {
            // The slot it was aimed at is gone (it held only this tab). Put it
            // back where it came from rather than losing it.
            settle(next);
            floats = nextFloats.filter((one) => one.keys.length > 0);
            return;
        }

        if (zone === "center" || hit.node.t !== "s") {
            hit.node.keys.push(key);
            hit.node.current = hit.node.keys.length - 1;
        } else {
            const leaf = { t: "s", id: makeId(), keys: [key], current: 0, size: 0.5 };
            const kept = copy(hit.node);
            kept.size = 0.5;
            const split = {
                t: "x",
                id: makeId(),
                dir: zone === "left" || zone === "right" ? "h" : "v",
                size: hit.node.size,
                nodes: zone === "left" || zone === "top" ? [leaf, kept] : [kept, leaf]
            };
            if (hit.parent)
                hit.parent.nodes[hit.index] = split;
            else
                return settleRoot(split, nextFloats);
        }

        settle(next);
        floats = nextFloats.filter((one) => one.keys.length > 0);
    }

    function settleRoot(node, nextFloats) {
        settle(node);
        floats = nextFloats.filter((one) => one.keys.length > 0);
    }

    function closeTab(id, key) {
        const next = copy(tree);
        const nextFloats = copy(floats);
        detach(next, nextFloats, key);
        settle(next);
        floats = nextFloats.filter((one) => one.keys.length > 0);
        saveLayout();
    }

    // Bringing a panel back puts it where you last had the dock's attention —
    // the slot whose menu you opened — because that is the one you are looking at.
    function openPanel(key, whereId) {
        const target = slotOf(whereId) ? whereId : firstSlotId();
        // dockTab has already saved, and from the model: saving again here would
        // re-read panes that were replaced a moment ago and have no geometry yet.
        dockTab(key, target, "center");
    }

    function firstSlotId() {
        let first = "";
        eachNode(tree, (node) => {
            if (first === "" && node.t === "s")
                first = node.id;
        });
        return first;
    }

    // ── Space ─────────────────────────────────────────────────────────────
    // A SplitView shares out ALL of its room among its children, so a pane can
    // only ever shrink by growing a neighbour: there is no way to say "smaller,
    // and leave the rest empty". A gap is that neighbour — a node that takes a
    // share of the tree and draws nothing, so the window's own background shows
    // through and the splitter between them resizes the pane against the void.
    // True when the pane already has something on that side to give room to.
    // Where it has not, the dock offers a grip instead: an edge you can pull in
    // even though nothing is waiting to take the space.
    function hasNeighbour(id, side) {
        const hit = findNode(tree, id);
        if (!hit || !hit.parent)
            return false;
        if (hit.parent.dir !== (side === "left" || side === "right" ? "h" : "v"))
            return false;
        return side === "right" || side === "bottom"
               ? hit.index < hit.parent.nodes.length - 1
               : hit.index > 0;
    }

    // Pulling that grip. The first pixel of the drag builds the void the pane is
    // about to shrink into; every pixel after it just moves the boundary between
    // the two, which is the same arithmetic a splitter does.
    // Committed once, on release, never during the drag.
    //
    // Resizing rearranges the tree — a pane with nothing beside it has to be
    // wrapped in a split with a void — and rearranging destroys and rebuilds the
    // panes below that point, including the very grip under the pointer. Doing
    // it per pixel therefore cancelled the gesture on its first pixel. The drag
    // draws its own preview instead, and the model hears about it exactly once.
    function commitResize(slotId, side, deltaPixels) {
        if (Math.abs(deltaPixels) < 2)
            return;

        const horizontal = side === "left" || side === "right";
        const extent = app.paneExtent(slotId, horizontal);
        if (extent <= 0)
            return;
        const next = copy(tree);
        // Everything the user has dragged elsewhere, read while the panes still
        // stand as they are.
        let hit = findNode(next, slotId);
        if (!hit)
            return;

        const aligned = hit.parent && hit.parent.dir === (horizontal ? "h" : "v");
        // A whole share, in pixels: the pane's own length divided by the share it
        // holds — or, when it is about to become nearly all of a new split, the
        // pane's length itself.
        const total = aligned ? extent / Math.max(hit.node.size, 0.001) : extent;

        if (!aligned) {
            const gap = { t: "g", id: makeId(), size: 0.001 };
            const kept = copy(hit.node);
            kept.size = 0.999;
            const split = {
                t: "x",
                id: makeId(),
                dir: horizontal ? "h" : "v",
                size: hit.node.size,
                nodes: side === "left" || side === "top" ? [gap, kept] : [kept, gap]
            };
            if (hit.parent) {
                hit.parent.nodes[hit.index] = split;
                hit = findNode(next, slotId);
            } else {
                settle(split);
                commitResize(slotId, side, deltaPixels);
                return;
            }
        }

        const siblings = hit.parent.nodes;
        const after = side === "right" || side === "bottom";
        let neighbour = after ? hit.index + 1 : hit.index - 1;

        if (neighbour < 0 || neighbour >= siblings.length) {
            siblings.splice(after ? siblings.length : 0, 0,
                            { t: "g", id: makeId(), size: 0.001 });
            hit = findNode(next, slotId);
            neighbour = after ? hit.index + 1 : hit.index - 1;
        }

        const mine = siblings[hit.index];
        const theirs = siblings[neighbour];

        let delta = deltaPixels / total;
        if (!after)
            delta = -delta;
        delta = Math.max(-mine.size + 0.06, Math.min(delta, theirs.size - 0.001));

        mine.size += delta;
        theirs.size -= delta;

        settle(next);
        saveLayout();
    }

    // Where a pane is on the desktop, from the PLAN — the canvas computed it,
    // and asking an item would be asking the same question twice.
    function paneCentre(slotId) {
        const rect = dockArea.rectOf(slotId);
        if (!rect)
            return Qt.point(240, 240);
        return dockArea.mapToGlobal(rect.x + rect.w / 2, rect.y + rect.h / 2);
    }

    function paneExtent(slotId, horizontal) {
        const rect = dockArea.rectOf(slotId);
        if (!rect)
            return 0;
        return horizontal ? rect.w : rect.h;
    }

    // Moving a boundary. Written into the model on every move — the canvas keeps
    // its panes across a change, so there is no longer a grip that destroys
    // itself under the pointer. It used to be committed on release only, for
    // exactly that reason.
    function dragHandle(splitId, index, deltaPixels) {
        const rect = dockArea.splitRect(splitId);
        if (!rect || Math.abs(deltaPixels) < 0.4)
            return;

        const total = rect.dir === "h" ? rect.w : rect.h;
        if (total <= 0)
            return;

        const next = copy(tree);
        const hit = findNode(next, splitId);
        if (!hit || hit.node.t !== "x" || index + 1 >= hit.node.nodes.length)
            return;

        const mine = hit.node.nodes[index];
        const theirs = hit.node.nodes[index + 1];
        // Neither side below a usable width, and neither eating the other: a
        // pane you cannot see is a pane you cannot get back.
        const floor = (rect.dir === "h" ? 140 : 90) / total;
        let delta = deltaPixels / total;
        delta = Math.max(-mine.size + floor, Math.min(delta, theirs.size - floor));
        if (Math.abs(delta) < 0.0001)
            return;

        mine.size += delta;
        theirs.size -= delta;
        tree = next;
        saveLayout();
    }

    // What the two sides of a handle hold, as the figures shown while it moves.
    function shareAt(splitId, index) {
        const hit = findNode(tree, splitId);
        if (!hit || hit.node.t !== "x" || index + 1 >= hit.node.nodes.length)
            return "";
        return Math.round(hit.node.nodes[index].size * 100) + "%   "
             + Math.round(hit.node.nodes[index + 1].size * 100) + "%";
    }

    function hasSpaceBeside(slotId) {
        const hit = findNode(tree, slotId);
        if (!hit || !hit.parent)
            return false;
        for (let i = 0; i < hit.parent.nodes.length; i++)
            if (hit.parent.nodes[i].t === "g")
                return true;
        return false;
    }

    // ── Turning a cursor into a place ─────────────────────────────────────
    // Positions travel in GLOBAL coordinates: a drop may land in another window,
    // and a scene position means nothing over there. They are brought into the
    // canvas once, here, and compared against the PLAN — the rectangles the dock
    // laid the panes out with, rather than the items it laid out.
    function zoneIn(rect, lx, ly) {
        if (lx < rect.x || ly < rect.y || lx > rect.x + rect.w || ly > rect.y + rect.h)
            return "";

        const fx = (lx - rect.x) / rect.w;
        const fy = (ly - rect.y) / rect.h;

        // The shape of the zones is Qt's, because it is the one every docking
        // window on this machine has already taught: the middle two thirds in
        // both directions add a tab, and the ring around it splits — thirds left
        // and right, halves top and bottom of what is left.
        //
        //        +--------------+          +------------+
        //        |              |          |LLLL TT RRRR|
        //        |   CCCCCCCC   |   the    |LLLL TT RRRR|
        //        |   CCCCCCCC   |   ring:  |LLLL BB RRRR|
        //        |              |          |LLLL BB RRRR|
        //        +--------------+          +------------+
        if (fx > 1 / 6 && fx < 5 / 6 && fy > 1 / 6 && fy < 5 / 6)
            return "center";
        if (fx < 1 / 3)
            return "left";
        if (fx > 2 / 3)
            return "right";
        return fy < 0.5 ? "top" : "bottom";
    }

    // ── The dock's own edge ───────────────────────────────────────────────
    // A band along the outside of the whole dock, where a drop means "a new area
    // across the entire window" rather than "split the pane under the pointer".
    // Without it a tab could only ever divide the pane it landed on: to put the
    // timeline along the bottom of a window whose bottom is a corner of one
    // pane, there was nothing to aim at.
    readonly property real dockBand: 26

    // The name a drop uses for "not a pane — the dock itself". No slot can ever
    // be called this: ids are made by `makeId`.
    readonly property string wholeDock: "__dock__"

    function rootZoneAt(lx, ly) {
        if (lx < 0 || ly < 0 || lx > dockArea.width || ly > dockArea.height)
            return "";

        const band = Math.min(dockBand, Math.min(dockArea.width, dockArea.height) / 8);
        const edges = [
            { zone: "left", d: lx },
            { zone: "right", d: dockArea.width - lx },
            { zone: "top", d: ly },
            { zone: "bottom", d: dockArea.height - ly }
        ];
        let closest = edges[0];
        for (let i = 1; i < edges.length; i++)
            if (edges[i].d < closest.d)
                closest = edges[i];
        return closest.d < band ? closest.zone : "";
    }

    function resolve(x, y) {
        const at = dockArea.mapFromGlobal(x, y);
        // The committed arrangement, not the preview: resolving against the
        // preview made each answer move the panes that produced it, and the
        // layout throbbed under the held tab instead of following the mouse.
        const panes = dockArea.hitPlan.panes;

        // A tab strip wins over everything, the dock's own edge included: a
        // strip that happens to run along the top of the window is still a row
        // of tabs, and dropping on one has never meant anything else.
        for (const one of panes) {
            if (one.kind !== "s")
                continue;
            if (at.x >= one.x && at.x <= one.x + one.w
                && at.y >= one.y && at.y < one.y + 28)
                return { id: one.id, zone: "center" };
        }

        // Then the outside of the dock — a new area spanning the window.
        const outer = rootZoneAt(at.x, at.y);
        if (outer !== "")
            return { id: app.wholeDock, zone: outer };

        for (const one of panes) {
            if (one.kind !== "s")
                continue;
            const zone = zoneIn(one, at.x, at.y);
            if (zone !== "")
                return { id: one.id, zone: zone };
        }
        return null;
    }

    // ── The hole that opens before you let go ─────────────────────────────
    //
    // What OBS does, and what makes its dock read as a room rather than as a
    // diagram: while a panel is in the air the layout ITSELF opens a gap for it,
    // so the arrangement you are about to get is the one on screen — not a
    // coloured rectangle drawn over the one you have.
    //
    // Qt calls it `insertGap`: a placeholder goes into the layout at the drop
    // position and everything re-lays out around it. This is the same idea in
    // the dock's own terms — a node of kind "p" spliced into a COPY of the tree,
    // which the canvas draws instead of the real one until the drag ends.
    // Nothing is committed: let go outside and the copy is thrown away.
    property var previewTree: null

    // True from the first move of a tab drag until it lands. The dock's own edge
    // is drawn while it is true, and the panes only slide while it is true.
    property bool tabInFlight: false

    function holeNode(size) {
        return { t: "p", id: "__hole__", size: size };
    }

    function buildPreview(targetId, zone) {
        // A drop that only adds a tab moves nothing: the strip is where it lands
        // and the pane keeps every pixel it has. The slot draws that one itself.
        if (zone === "" || zone === "center")
            return null;

        const across = zone === "left" || zone === "right";
        const first = zone === "left" || zone === "top";

        if (targetId === app.wholeDock) {
            const kept = copy(tree);
            kept.size = 0.72;
            return {
                t: "x", id: "__holesplit__", dir: across ? "h" : "v", size: 1,
                nodes: first ? [holeNode(0.28), kept] : [kept, holeNode(0.28)]
            };
        }

        const next = copy(tree);
        const hit = findNode(next, targetId);
        if (!hit)
            return null;

        const kept = copy(hit.node);
        kept.size = 0.5;
        const split = {
            t: "x", id: "__holesplit__", dir: across ? "h" : "v", size: hit.node.size,
            nodes: first ? [holeNode(0.5), kept] : [kept, holeNode(0.5)]
        };
        if (!hit.parent)
            return split;
        hit.parent.nodes[hit.index] = split;
        return next;
    }

    function dragOver(fromId, x, y) {
        tabInFlight = true;
        const target = resolve(x, y);
        const id = target ? target.id : "";
        const zone = target ? target.zone : "";
        if (id === hoverSlot && zone === hoverZone)
            return;

        hoverSlot = id;
        hoverZone = zone;
        previewTree = buildPreview(id, zone);
    }

    function drop(fromId, key, x, y) {
        hoverSlot = "";
        hoverZone = "";
        tabInFlight = false;
        previewTree = null;

        const target = resolve(x, y);
        if (target) {
            // Dropping a lone tab back onto its own slot changes nothing, and
            // must not tear it out and put it back.
            const from = slotOf(fromId);
            if (!(target.id === fromId && (target.zone === "center" || (from && from.keys.length === 1))))
                dockTab(key, target.id, target.zone);
        } else {
            floatTab(key, x, y);
        }
    }

    // ── Floating ──────────────────────────────────────────────────────────
    // The pop-out button in a slot's strip: the tab on top leaves for a window
    // of its own, landing over the pane it came from.
    function floatCurrent(slotId) {
        const here = slotOf(slotId);
        if (!here || here.keys.length === 0)
            return;
        const at = app.paneCentre(slotId);
        floatTab(here.keys[here.current], at.x, at.y);
    }

    function floatTab(key, x, y) {
        const next = copy(tree);
        const nextFloats = copy(floats);
        detach(next, nextFloats, key);
        nextFloats.push({
            id: makeId(),
            keys: [key],
            current: 0,
            // Dropped where you let go, not centred on the screen: the window
            // appears under your hand.
            x: Math.round(x - 160),
            y: Math.round(y - 14),
            w: 520,
            h: 360
        });
        settle(next);
        floats = nextFloats.filter((one) => one.keys.length > 0);
        saveLayout();
    }

    // ── Persistence ───────────────────────────────────────────────────────
    // Sizes are no longer read back off the panes. The model IS the size: a
    // handle writes fractions into the tree as it moves, and the canvas lays
    // the panes out from them. What used to be `captureSizes` existed because
    // the two could disagree — and it was itself the source of the drift it
    // was written to prevent.

    property bool restoring: false

    // fromModel: the tree in hand is already the truth — do not go and read the
    // panes for their sizes. After a structural change the new panes have not
    // been laid out yet, and reading them then wrote a layout of three equal
    // columns over the one the user had.
    function saveLayout() {
        if (restoring || !restored)
            return;
        // Moving a pane is an ATTEMPT, not a decision.
        //
        // The arrangement you are bending lives in memory for as long as the
        // window does — switch away and back and your bend is still there — and
        // it is never written here. What the file holds is what you decided:
        // the shape pinned with Update default, the displays saved under a
        // name, your keys, your colours, and which arrangement you were in.
        //
        // Otherwise every drag quietly became the new normal: you could not try
        // a wider timeline for ten minutes without owning it, and Reset was the
        // only way back to a shape you never meant to leave.
        Shell.saveLayout(JSON.stringify({
            version: 3,
            template: template,
            defaults: defaults,
            saved: saved,
            codeTheme: Theme.codeTheme,
            codeThemePicked: codeThemePicked,
            keymap: Keymap.bindings,
            safeMargins: safeMargins
        }));
    }

    // What a restart forgets, and why it is not a bug.
    //
    // Where the panes ARE does not survive closing the app unless you said it
    // should: Update default pins the shape of an arrangement, Save display
    // keeps one under a name. Everything else — the pane you widened while
    // reading something, the tab you dragged across to compare two things — is
    // an attempt, and the window it was made in is as long as it lasts.

    // A layout read from disk is data from another run: it may name panels this
    // build no longer has, or have been written by a version that arranged them
    // differently. Anything unrecognised is dropped rather than trusted.
    function sanitise(node) {
        if (node.t === "g")
            return { t: "g", id: node.id, size: node.size > 0 ? node.size : 0.2 };

        if (node.t === "s") {
            node.keys = (node.keys || []).filter((key) => panelKeys.indexOf(key) >= 0);
            node.current = Math.max(0, Math.min(node.current || 0, node.keys.length - 1));
            return node.keys.length > 0 ? node : null;
        }
        if (node.t !== "x")
            return null;

        const kept = [];
        for (let i = 0; i < (node.nodes || []).length; i++) {
            const child = sanitise(node.nodes[i]);
            if (child)
                kept.push(child);
        }
        if (kept.length === 0)
            return null;

        let allGaps = true;
        for (let i = 0; i < kept.length; i++)
            if (kept[i].t !== "g")
                allGaps = false;
        if (allGaps)
            return null;

        if (kept.length === 1) {
            kept[0].size = node.size;
            return kept[0];
        }
        node.nodes = kept;
        return node;
    }

    // Ids read from a file must not collide with ids minted this run.
    function highestId(node) {
        let highest = 0;
        eachNode(node, (one) => {
            const number = parseInt(String(one.id).replace("n", ""), 10);
            if (!isNaN(number) && number > highest)
                highest = number;
        });
        return highest;
    }

    // Whether the file on disk has been read yet. NOTHING is written before it
    // has.
    //
    // A start that failed half-way — a bridge this binary does not have, a
    // scene that would not run — leaves the window on the shape it ships with
    // and the restore never reached. The first pane moved after that saved THAT
    // over the arrangement you had built, and the loss looked like the dock
    // forgetting rather than like a start that never finished. A save is only
    // ever an edit to something that was read.
    property bool restored: false

    function restoreLayout() {
        // Set on every path out of here, the failures included: a file that is
        // absent or unreadable is not a reason to stop saving — it is the reason
        // there was nothing to read.
        restored = true;

        const stored = Shell.loadLayout();
        if (!stored)
            return;

        try {
            const parsed = JSON.parse(stored);

            restoring = true;
            // A file may name an arrangement this build has dropped; the one a
            // first launch opens in is the safe landing.
            const named = parsed.template || "";
            let known = named.indexOf("user:") === 0;
            for (let i = 0; i < Layouts.templates.length; i++)
                if (Layouts.templates[i].key === named)
                    known = true;
            template = known ? named : Layouts.templates[0].key;

            // Not part of an arrangement: which colours you read code in
            // survives every template switch and every Reset UI.
            codeThemePicked = parsed.codeThemePicked === true;
            if (codeThemePicked && Theme.codeThemes[parsed.codeTheme] !== undefined)
                Theme.codeTheme = parsed.codeTheme;
            Keymap.restore(parsed.keymap);
            safeMargins = parsed.safeMargins === true;

            // The trees that DO come from disk are data from another run: they
            // may name panels this build no longer has. Anything unrecognised is
            // dropped rather than trusted — an arrangement is not worth a window
            // that will not open.
            defaults = keptArrangements(parsed.defaults || ({}));
            saved = (parsed.saved || [])
                .filter((one) => one && one.name && one.tree)
                .map((one) => ({
                    name: one.name,
                    tree: sanitise(one.tree),
                    floats: one.floats || [],
                    options: one.options || ({})
                }))
                .filter((one) => one.tree);

            // No arrangement is read back: the window opens on what you DECIDED
            // it should open on. A named display opens as it was named; a
            // built-in one opens on the shape you pinned with Update default, or
            // on the shape it ships with. Whatever you bent last session was an
            // attempt, and attempts do not outlive the window that made them.
            const mine = template.indexOf("user:") === 0 ? savedIndex(template.substring(5)) : -1;
            if (mine >= 0) {
                const kept = saved[mine];
                tree = copy(kept.tree);
                floats = copy(kept.floats || []);
                mediaDisplay = kept.options && kept.options.mediaDisplay === "list" ? "list" : "grid";
            } else {
                tree = buildTemplate(template);
                floats = buildFloats(template);
                mediaDisplay = buildOptions(template).mediaDisplay === "list" ? "list" : "grid";
            }
            layouts = ({});
            nextId = highestId(tree) + 1;
            restoring = false;
        } catch (error) {
            console.warn("[dock] ignoring an unreadable saved layout:", error);
            restoring = false;
        }
    }

    // The pinned arrangements, with anything this build cannot draw taken out.
    function keptArrangements(stored) {
        let out = ({});
        for (const key in stored) {
            const one = stored[key];
            if (!one || !one.tree)
                continue;
            const shape = sanitise(copy(one.tree));
            if (!shape)
                continue;
            out[key] = { tree: shape, floats: one.floats || [], options: one.options || ({}) };
        }
        return out;
    }

    // ── The menu bar's half of the dock ───────────────────────────────────
    // The bar is Qt Widgets and knows nothing about the tree, so the chrome
    // restates the panel list whenever the dock changes.
    function menuPanels() {
        const shown = shownKeys();
        const panels = [];
        for (let i = 0; i < panelKeys.length; i++)
            panels.push({
                key: panelKeys[i],
                label: panelTitles[panelKeys[i]],
                shown: shown.indexOf(panelKeys[i]) >= 0
            });
        return panels;
    }

    function menuTemplates() {
        const entries = [];
        for (let i = 0; i < Layouts.templates.length; i++)
            entries.push({
                key: Layouts.templates[i].key,
                label: Layouts.templates[i].label,
                current: Layouts.templates[i].key === template
            });
        return entries;
    }

    // The legend: what the TIMELINE paints, in the order it should be read —
    // what a thing is, what is happening now, and the marks on it. Nothing else
    // belongs here: the agent's blue and the status strip's gold and red are
    // never on a clip, and a legend for the timeline that lists them sends the
    // reader looking for colours that are not there. Panels read the hues
    // straight from Theme, so a row only has to say what it means.
    function guideColors() {
        return [
            // Read from the simplest thing the engine can make towards the
            // richest: a shape it draws itself, then a still, then a still with
            // time in it, then time with a picture AND sound. Each line adds one
            // thing to the one above.
            { section: "Inputs — what a scene is made of" },
            { label: "polygon", meaning: "a shape the engine draws" },
            { label: "image", meaning: "a still — png, svg" },
            { label: "sound", meaning: "audio on its own" },
            { label: "video", meaning: "a picture with its sound, as one clip" },
            { label: "subs", meaning: "text derived from a track, so it borrows the neutral" },

            { section: "Now" },
            { label: "live", meaning: "the playhead, and whatever is about to happen" },

            { section: "Marks" },
            { label: "ok", meaning: "the in and out marks of a range" }
        ];
    }

    // The overrides from last time, kept only if this build still has the
    // label and the value is a colour: a hand-edited file is not a reason for a
    // window full of "Unable to assign" warnings.
    function restoreColors() {
        let kept = {};
        try {
            const parsed = JSON.parse(Shell.loadColors() || "{}");
            for (const label in parsed)
                if (Theme.shipped[label] !== undefined && /^#[0-9a-fA-F]{8}$/.test(parsed[label]))
                    kept[label] = parsed[label].toLowerCase();
        } catch (e) {
        }
        Theme.overrides = kept;
    }

    function menuDisplays() {
        const entries = [];
        for (let i = 0; i < saved.length; i++)
            entries.push({ name: saved[i].name });
        return entries;
    }

    onTreeChanged: { Shell.setDockPanels(menuPanels()); refreshCodeShown(); }
    onFloatsChanged: { Shell.setDockPanels(menuPanels()); refreshCodeShown(); }

    // Ticking a panel that is already open closes it, exactly as its × does:
    // the menu is a view of the same state, not a second way to reach it.
    function togglePanel(key) {
        if (shownKeys().indexOf(key) >= 0)
            closeTab(firstSlotId(), key);
        else
            openPanel(key, firstSlotId());
    }

    Connections {
        target: Shell
        function onDockPanelToggled(key) { app.togglePanel(key); }
        function onDockResetRequested() { confirmReset.ask(); }
        function onDockTemplateChosen(key) { app.useTemplate(key); }
        function onDockDisplayChosen(name) { app.loadDisplay(name); }
        function onDockSaveRequested() { saveDisplay.ask(); }
        function onDockDefaultRequested() { app.updateDefault(); }
        function onDockMeasureRequested() { app.measuring = true; }
        // Opening a scene is one call: the pane loads it, the analyser is told
        // about it, and the window's idea of "the scene" moves with it.
        function onSceneOpened(path) { app.openScene(path); }
        function onExportRequested() { app.beginExport(); }
        function onExportProgress(done, total) { exporting.advance(done, total); }
        function onExportFinished(ok, message) {
            exporting.settle(ok, message);
            source.say(ok ? "exported " + message : message);
        }

        function onMediaDropped(path) {
            const kind = app.kindOfFile(path);
            if (kind === "")
                return;
            app.addedAssets = app.addedAssets.concat([{ n: path.split("/").pop(), kind: kind, path: path }]);
            app.insertMedia(path, kind);
        }

        // A folder changes what the analyser considers the project, and a
        // server's root is fixed at initialize — so this is a new process.
        function onFolderOpened(folder, path) {
            Lsp.restart(folder);
            // The agent is told the same thing for the same reason: what it may
            // read and write is the project, and the project just changed.
            Agent.setRoot(folder);
            app.openScene(path);
        }

        function onSettingsRequested() { settings.visible = true; }
        function onCodeThemeChosen(key) { app.useCodeTheme(key); }
        function onShortcutsRequested() { shortcuts.visible = true; }
        function onColorsRequested() { colors.visible = true; }
    }

    // The code pane's palette. Kept with the dock's options rather than with the
    // arrangement: which colours you read code in is about you, not about which
    // template you happen to be in.
    // Whether the palette on screen is a CHOICE or just the default of the day.
    // Without it, a default that changes cannot reach anyone who has ever saved
    // a layout: the old default was written to disk and would look like a
    // decision nobody made.
    property bool codeThemePicked: false

    // The preview's safe margins. Kept in the dock file with the keys and the
    // code theme: whether you work with guides on is a habit, not an attempt.
    property bool safeMargins: false

    function toggleSafeMargins() {
        safeMargins = !safeMargins;
        saveLayout();
    }

    function openScene(path) {
        scenePath = path;
        // The one file `Agent.revert()` can put back. Told here rather than at
        // startup, because it changes every time a scene is opened.
        Agent.watch(path);
        source.load(path);
        sentText = source.text;
        // Opening a file IS an execute. The rule that the timeline only moves on
        // ⌘R is about edits — it stops the picture flickering under your typing
        // — and it was never meant to leave a freshly opened scene represented
        // by nothing.
        executeScene();
        // The pane may be behind another tab — opening a file and not showing
        // it is the kind of silence this dock is built to avoid.
        showPanel("code");
        Qt.callLater(source.takeFocus);
    }

    function showPanel(key) {
        const slot = slotHolding(key);
        if (slot === -1) {
            openPanel(key, firstSlotId());
            return;
        }
        const next = copy(tree);
        const hit = findNode(next, slot);
        if (hit) {
            hit.node.current = Math.max(0, hit.node.keys.indexOf(key));
            tree = next;
            saveLayout();
        }
    }

    function slotHolding(key, node) {
        const here = node !== undefined ? node : tree;
        if (here.t === "s")
            return here.keys.indexOf(key) >= 0 ? here.id : -1;
        for (const child of (here.nodes || [])) {
            const found = slotHolding(key, child);
            if (found !== -1)
                return found;
        }
        return -1;
    }

    function useCodeTheme(key) {
        Theme.codeTheme = key;
        codeThemePicked = true;
        Shell.setCodeThemes(menuCodeThemes());
        saveLayout();
    }

    function menuCodeThemes() {
        let out = [];
        for (const key in Theme.codeThemes)
            out.push({ key: key, label: Theme.codeThemes[key].label, current: key === Theme.codeTheme });
        return out;
    }

    // Reset UI puts the CURRENT template back to how it ships and forgets your
    // version of it. The other templates are untouched: resetting the one you
    // are looking at should not cost you the two you are not.
    function resetLayout() {
        // A saved display resets to what was saved under its name; a built-in
        // one resets to how it ships — or to the shape you saved OVER it, which
        // is then the one it ships with as far as this dock is concerned.
        if (template.indexOf("user:") === 0) {
            const name = template.substring(5);
            template = "";
            loadDisplay(name);
            return;
        }

        const kept = copy(layouts);
        delete kept[template];
        layouts = kept;
        floats = buildFloats(template);
        tree = buildTemplate(template);
        mediaDisplay = buildOptions(template).mediaDisplay;
        saveLayout();
    }

    // ── The language server ───────────────────────────────────────────────
    // Started with the window rather than with the pane: it takes a moment to
    // index a project, and nothing is gained by making that wait visible.
    property string scenePath: ""

    Connections {
        target: Lsp

        function onReady(capabilities) {
            // One line, and a count rather than the roll-call: twenty-one
            // provider names wrapped over three terminal lines every launch,
            // and the only thing anyone reads there is whether it came up.
            console.log("[lsp] ready —", capabilities.length, "providers");
            if (source.path.length > 0) {
                Lsp.openDocument(source.path, source.text);
                colouring.restart();
            }
        }

        function onFailed(why) {
            console.warn("[lsp]", why);
        }

        // Diagnostics arrive for every file the server has looked at, not only
        // the one on screen — following a definition into videocode/ makes it
        // check that module too. Only the pane's current file is drawn.
        // What each name IS, from the analyser. Asked for once the file settles
        // rather than on every keystroke: it costs a walk of the whole file, and
        // the lexical colouring underneath is already correct while you type.
        function onTokens(path, spans) {
            if (path === source.path && source.document !== null)
                Shell.applySemanticTokens(source.document, spans);
        }

        function onDiagnostics(path, items) {
            if (path !== source.path)
                return;
            // Not printed. The analyser answers on every pause in typing, so
            // this wrote a line per keystroke-and-a-half into the terminal the
            // window was launched from — hundreds of them in a session, none of
            // which anyone reads. What it had to say is already on screen: the
            // squiggle, the gutter mark, and the count in the status strip.
            source.diagnostics = items;
        }
    }

    // Launched from a terminal, the shell came up on screen while the TERMINAL
    // stayed the frontmost application. macOS gives the menu bar, the ⌘ keys and
    // the cursor to whoever is frontmost, so ⌘1..4 did nothing (every Shortcut
    // here is a Qt.WindowShortcut, which needs `active`) and no MouseArea could
    // turn the pointer into a splitter arrow — the window looked focused all the
    // same, because Qt's requestActivate() only makes it key. It stayed that way
    // until something else raised the app: switching a Space, or the Dock
    // changing display.
    //
    // On the first swapped frame rather than on completion: the application can
    // only be raised once it has a window on screen to raise.
    property bool raised: false

    onFrameSwapped: {
        if (raised || Shell.headless)
            return;
        raised = true;
        // The application first, the window second. Reversed, makeKeyWindow
        // runs while the process is still in the background, where AppKit
        // ignores it, and the activation that follows picks the key window and
        // the first responder on its own — which is how the menu bar came up
        // right while ⌘1..4 stayed dead: a native menu item has no target, so
        // Cocoa looks for one up the responder chain from the focused view.
        Shell.bringToFront();
        requestActivate();
    }

    Component.onCompleted: {
        // The scene is a file on disk before it is anything else: a language
        // server reasons about files, and so does every jump to a definition.
        scenePath = Shell.scenePath();
        effectNames = Shell.effects();
        // Asked for only if this binary has it. The chrome is QML read from
        // disk and reloads on save; the shell behind it does not, so a window
        // started from a binary built before a bridge existed meets a call that
        // is not there — and an exception here stops the WHOLE of this block,
        // which is the line that loads the scene. One missing panel is a
        // nuisance; an editor that opens empty looks broken.
        templateNames = Shell.templates !== undefined ? Shell.templates() : [];

        // Asked once, at the top: the setting is a preference about the whole
        // window, and re-reading it per animation would be a system call in the
        // middle of every fade.
        Theme.reducedMotion = Shell.reducedMotion();

        Lsp.start(Shell.projectRoot());
        Agent.setRoot(Shell.projectRoot());
        if (scenePath.length > 0) {
            Agent.watch(scenePath);
            source.load(scenePath);
            sentText = source.text;
            // Nothing takes the caret here. The five transport keys and the
            // editor's five are the same five, and whoever holds the caret wins
            // them — so handing it to the pane at launch made Space write a
            // space in a window whose first gesture is almost always to play.
            // The pane takes it when you click in it, open a file, or follow a
            // definition, which are the moments you meant to type.
            //
            // One tick later, so the window is on screen before a
            // scene that takes 200 ms to run gets to hold it there.
            Qt.callLater(app.executeScene);
        }

        restoreLayout();
        restoreColors();

        // Filled in the order the menus are meant to READ in, left to right.
        // Qt's Cocoa bridge inserts a menu into the bar when it first gets
        // contents, not when it was declared — so the order these calls run in
        // is the order the titles end up in.
        Shell.setCodeThemes(menuCodeThemes());
        Shell.setDockPanels(menuPanels());
        Shell.setDockTemplates(menuTemplates());
        Shell.setDockDisplays(menuDisplays());
    }

    // ── The ⋯ menu ────────────────────────────────────────────────────────
    property string menuSlot: ""

    function openMenu(id, x, y) {
        menuSlot = id;

        const shown = shownKeys();
        const entries = [];
        for (let i = 0; i < panelKeys.length; i++) {
            const key = panelKeys[i];
            entries.push({
                kind: "check",
                on: shown.indexOf(key) >= 0,
                label: panelTitles[key],
                act: "toggle",
                key: key
            });
        }

        const here = slotOf(id);
        const currentKey = here && here.keys.length > 0 ? here.keys[here.current] : "";

        // What a panel can be asked, asked of the panel you are looking at. Only
        // the bin has anything to say so far, and the submenu exists so the next
        // panel with an opinion has somewhere to put it.
        if (currentKey === "media") {
            entries.push({ kind: "rule" });
            entries.push({
                kind: "sub",
                label: "Display",
                sub: [
                    { kind: "check", on: mediaDisplay === "grid", label: "Grid",
                      act: "media-display", value: "grid" },
                    { kind: "check", on: mediaDisplay === "list", label: "Details",
                      act: "media-display", value: "list" }
                ]
            });
        }

        if (currentKey !== "") {
            entries.push({ kind: "rule" });
            entries.push({
                kind: "item",
                label: "Float " + panelTitles[currentKey],
                act: "float",
                key: currentKey
            });
        }

        if (hasSpaceBeside(id)) {
            entries.push({ kind: "rule" });
            entries.push({ kind: "item", label: "Remove space", act: "remove-space" });
        }

        entries.push({ kind: "rule" });
        entries.push({ kind: "item", label: "Save display…", act: "save-display" });

        const displays = [];
        for (let i = 0; i < saved.length; i++)
            displays.push({
                kind: "check",
                on: template === "user:" + saved[i].name,
                label: saved[i].name,
                act: "load-display",
                value: saved[i].name
            });
        if (displays.length === 0)
            displays.push({ kind: "item", label: "Nothing saved yet", act: "" });
        entries.push({ kind: "sub", label: "Load display", sub: displays });

        entries.push({ kind: "item", label: "Reset UI", act: "reset", key: "" });

        menu.entries = entries;
        const local = menu.mapFromGlobal(x, y);
        menu.popup(local.x, local.y);
    }

    function runMenu(entry) {
        if (!entry)
            return;

        if (entry.act === "") {
            return;
        } else if (entry.act === "reset") {
            // Never straight through: this one throws away work.
            confirmReset.ask();
        } else if (entry.act === "remove-space") {
            removeSpace(menuSlot);
        } else if (entry.act === "save-display") {
            saveDisplay.ask();
        } else if (entry.act === "load-display") {
            loadDisplay(entry.value);
        } else if (entry.act === "media-display") {
            mediaDisplay = entry.value;
            saveLayout();
        } else if (entry.act === "float") {
            const at = app.paneCentre(menuSlot);
            floatTab(entry.key, at.x, at.y);
        } else if (shownKeys().indexOf(entry.key) >= 0) {
            closeTab(menuSlot, entry.key);
        } else {
            openPanel(entry.key, menuSlot);
        }
    }

    // ── No title bar of our own ───────────────────────────────────────────
    // The window already has one, drawn by the system, and a second strip under
    // it was spending 36 px of every screen on a brand nobody needs to be told
    // twice. What it also carried — the scene's name — was a promise the editor
    // does not keep: a scene need not come from a .py file at all, since the
    // buffer IS the scene and an empty one is a legitimate way to start. The
    // name belongs where the buffer is, on the Code panel's own bar, which shows
    // it beside whether it is compiled and whether it differs from the last save.

    // ── Dock ──────────────────────────────────────────────────────────────
    DockCanvas {
        id: dockArea
        anchors {
            left: parent.left; right: parent.right
            top: parent.top; bottom: status.top
            margins: Theme.gap
        }
        // The preview while a tab is in the air, the real tree otherwise. The
        // panes are the same items either way — the canvas keeps a row per node
        // id and only moves it — so the hole opening is a re-layout of things
        // that already exist, which is exactly what makes it animate.
        // Truthiness, not `!== null`: an uninitialised property is `undefined`,
        // which is not null — so at startup this handed the canvas `undefined`
        // and the dock came up empty and STAYED empty, because the binding then
        // depended on a property nothing was going to change.
        node: app.previewTree ? app.previewTree : app.tree
        // What the pointer is resolved against, which must not be what the
        // pointer just changed — see `hitPlan`.
        hitNode: app.tree
        dock: app
    }

    // The dock's own edge, shown while a tab is in the air: a band you cannot
    // see is a band nobody finds, and "drop here for a row across the window" is
    // not a thing you guess. Where it would LAND is not drawn here — the hole
    // that opens in the layout says that better than any rectangle could.
    Item {
      anchors.fill: dockArea
      z: 199

      Repeater {
        model: app.tabInFlight ? ["left", "right", "top", "bottom"] : []

        Rectangle {
            required property var modelData
            readonly property bool across: modelData === "left" || modelData === "right"
            x: modelData === "right" ? parent.width - app.dockBand : 0
            y: modelData === "bottom" ? parent.height - app.dockBand : 0
            width: across ? app.dockBand : parent.width
            height: across ? parent.height : app.dockBand
            color: "transparent"
            border.width: 1
            border.color: app.hoverZone === modelData && app.hoverSlot === app.wholeDock
                          ? Theme.live : Qt.alpha(Theme.live, 0.22)
            radius: Theme.radiusInner

            Behavior on border.color { ColorAnimation { duration: Theme.motion(120) } }
        }
      }
    }

    StatusStrip {
        id: status
        anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
        inputCount: app.shownScene.elements.length
        compileMs: 84
        frameMs: 11.4
        execState: app.execState
        execStale: app.execStale
        execMs: app.execMs
    }

    ExportPanel {
        id: exporting
        anchors.fill: parent
        z: 322
        onCancelled: Shell.cancelExport()
    }

    SettingsPanel {
        id: settings
        anchors.fill: parent
        z: 320
        mediaDisplay: app.mediaDisplay
        onCodeThemePicked: (key) => app.useCodeTheme(key)
        onMediaDisplayPicked: (key) => { app.mediaDisplay = key; app.saveLayout(); }
        onResetRequested: confirmReset.ask()
    }

    // ── Dropping a file on the window ─────────────────────────────────────
    // A file dragged from the Finder becomes a LINE OF CODE at the caret, and a
    // row in the bin. Anything else would be a lie about where a scene lives:
    // there is no hidden project model behind this editor, only the buffer, so
    // "adding" a video has to be a statement you can read and delete.
    //
    // This is an insertion, not a rewrite — the councils refused rewriting an
    // existing call, and this touches nothing that was already written.
    DropArea {
        anchors.fill: parent
        z: 400
        keys: ["text/uri-list"]

        onDropped: (drop) => {
            let added = [];
            for (const url of drop.urls) {
                const path = url.toString().replace("file://", "");
                const kind = app.kindOfFile(path);
                if (kind === "")
                    continue;
                added.push({ n: path.split("/").pop(), kind: kind, path: path });
                app.insertMedia(path, kind);
            }
            if (added.length === 0)
                return;
            app.addedAssets = app.addedAssets.concat(added);
            drop.accept();
        }

        Rectangle {
            anchors.fill: parent
            visible: parent.containsDrag
            color: Qt.alpha(Theme.live, 0.06)
            border.width: 2
            border.color: Theme.live
        }
    }

    // The statement a dropped file becomes. Named after the file so the line
    // reads as a sentence, and inserted on its own line above the caret's —
    // never in the middle of whatever you were typing.
    function insertMedia(path, kind) {
        const cls = kind === "video" ? "Video" : (kind === "image" ? "Image" : "Sound");
        source.insertLine(app.nameFromFile('"' + path + '"')
                          + " = " + cls + '("' + app.projectRelative(path) + '")');
        showPanel("code");
    }

    // A Python name out of a file name: what is between the last slash and the
    // first dot, with anything that cannot be in a name taken out. `interview =
    // Video("interview.mp4")` is what a person writes; `video2` is what a tool
    // writes.
    function nameFromFile(lead) {
        const quoted = /^["'](.*)["']$/.exec(lead.trim());
        if (quoted === null)
            return "";
        const base = quoted[1].split("/").pop().split(".")[0].replace(/[^A-Za-z0-9_]/g, "_");
        return /^[A-Za-z_]/.test(base) ? base : "clip" + base;
    }

    // The clip you opened, in the middle of the window.
    ElementCard {
        id: elementCard
        anchors.fill: parent
        z: 310
        effectNames: app.effectNames
        playhead: app.playhead
        onEffectRequested: (element, effect, options) => app.applyEffect(element, effect, options)
        onMemberOpened: (member, where) => elementCard.open(member, where)
        // Reading the source is the card's own business — `Shell` is in scope
        // everywhere. Writing goes through the shell so the scene re-runs, which
        // is what makes the gesture visible.
        onArgumentWritten: (element, call, name, value) => app.writeArgument(element, call, name, value)
        onMetadataAdded: (element, write) => app.addMetadata(element, write)
        onMetadataWritten: (element, call, name, at, value) => app.writeMetadata(element, call, name, at, value)
        buffer: source.text
        onJumpRequested: (element) => app.revealLine(element.line)
        onRenameRequested: (element) => app.renameElement(element)
        // An effect row answers for the call that wrote it: the ✕ deletes that
        // call, a drag rewrites its `start` or `duration`, a click goes to it.
        onEffectRemoved: (fx) => app.removeCall(fx.line, fx.call, fx.file)
        onEffectWritten: (fx, name, value) => {
            // No name means the card would not do the arithmetic: the argument
            // is written as an expression, and rewriting `RATIO * 0.5` as `0.6`
            // would answer a drag by deleting a decision.
            if (name.length === 0)
                source.say(fx.call + " is written as an expression — edit the line itself");
            else
                app.writeOn(fx.line, fx.call, name, value, fx.file,
                            elementCard.element !== null ? elementCard.element.cls : "");
        }
        onEffectJumped: (fx) => app.revealLine(fx.line)
        onSays: (sentence) => source.say(sentence)
        onEffectToggled: (line, off, file) => app.toggleLine(line, off, file)
    }

    // What is being carried, under the pointer. Small and out of the way: the
    // thing you are aiming at is the timeline, and a big label over it would
    // hide the moment you are trying to pick.
    Rectangle {
        visible: app.carried !== null
        z: 340
        x: (app.carried !== null ? app.carried.x : 0) + 14
        y: (app.carried !== null ? app.carried.y : 0) + 14
        width: ghost.implicitWidth + 16
        height: 22
        radius: 4
        color: Theme.live
        opacity: 0.92

        Text {
            id: ghost
            anchors.centerIn: parent
            text: app.carried !== null ? app.carried.template.name : ""
            color: "#0b1018"
            font.family: Theme.mono
            font.pixelSize: 11
            font.weight: Font.DemiBold
        }
    }

    ShortcutsPanel {
        id: shortcuts
        anchors.fill: parent
        z: 320
        docks: app.panelKeys.map((key) => ({ id: key, label: app.panelTitles[key] }))
    }

    ColorsPanel {
        id: colors
        anchors.fill: parent
        z: 320
        rows: app.guideColors()
        onChanged: Shell.saveColors(JSON.stringify(Theme.overrides))
    }

    // The click that ends the measuring. Over every pane so nothing else can
    // take it — the panes are showing numbers rather than working, and a click
    // that landed on one of them would have to mean two things at once.
    MouseArea {
        anchors.fill: parent
        z: 330
        visible: app.measuring
        acceptedButtons: Qt.AllButtons
        onPressed: app.measuring = false
    }

    // The figure under your hand while a pane is being resized. Drawn at the
    // window's level rather than inside the pane: a label that belongs to a
    // splitter is on the boundary of two panes, and inside either one it would be
    // clipped away by the very edge you are dragging.
    Rectangle {
        id: tipBox
        z: 340
        visible: app.tip !== null
        width: tipText.implicitWidth + 14
        height: tipText.implicitHeight + 8
        // Ahead of the pointer, and pulled back inside the window at the edges —
        // the reading you want is the one you get while dragging TOWARDS an edge.
        x: app.tip !== null ? Math.max(4, Math.min(app.tip.x + 14, app.width - width - 4)) : 0
        y: app.tip !== null ? Math.max(4, Math.min(app.tip.y + 16, app.height - height - 4)) : 0
        color: Theme.rail
        radius: Theme.radiusSmall
        border.width: 1
        border.color: Theme.live

        Text {
            id: tipText
            anchors.centerIn: parent
            text: app.tip !== null ? app.tip.text : ""
            color: Theme.ink
            font.family: Theme.mono
            font.pixelSize: 11
        }
    }

    // Re-asked after the typing stops. The tokens are positions in a file that
    // is still being edited, so asking mid-word would paint yesterday's answer
    // onto today's text.
    // The buffer as the server last saw it.
    property string sentText: ""

    // ── Making the file ───────────────────────────────────────────────────
    // The editor could write a scene and never make anything of it: rendering
    // meant leaving for a terminal. It is the same binary either way — the
    // child is the command the author would have typed — so what comes out of
    // the menu is what comes out of the command line, and the pane reads the
    // renderer's own count rather than inventing one.
    //
    // What is rendered is the BUFFER, not the file on disk: the picture in the
    // preview is the buffer's, and an export that quietly rendered the last
    // saved version would hand back a video of something you cannot see.
    function beginExport() {
        if (source.path.length === 0) {
            source.say("nothing is open to export");
            return;
        }

        const suggested = source.path.replace(/\.py$/, "") + ".mp4";
        const chosen = Shell.pickExport(suggested);
        if (chosen.length === 0)
            return;

        // The marks are a range someone set on purpose, so an export honours
        // them the way play does. Nothing marked is the whole scene.
        const first = ranged ? markIn : -1;
        const last = ranged ? markOut : -1;
        if (!Shell.startExport(source.path, source.text, chosen, first, last)) {
            source.say("an export is already running");
            return;
        }
        exporting.begin(chosen, first, last);
    }

    // ── Executing the scene ───────────────────────────────────────────────
    // Only ⌘R runs it, and that is not a performance decision.
    //
    // A scene is arbitrary Python whose constructors open files. Running it on
    // a pause in typing means running unfinished text ten to thirty times a
    // minute, and the compile gate does not save you: `wait(1)` mid-keystroke is
    // `wait(11)` — syntactically perfect, semantically another film, executed
    // for real. You can debounce a question; you cannot debounce a side effect.
    //
    // The cost of the choice is that the picture is behind the buffer, and the
    // whole of `execState` exists so that is visible rather than assumed.
    property string execText: ""
    property string execState: "none"   // none · fresh · stale · failed
    property real execMs: 0
    property int execInputs: 0
    property int execFrames: 0
    property int execFps: 30

    // Bumped by every successful run. The preview draws frame N of a scene, and
    // "frame 12" means a different picture once the buffer has been executed
    // again — without this the pane would keep showing the old scene at the new
    // playhead, which is the one lie a preview must not tell.
    property int execRevision: 0

    readonly property bool execStale: execState !== "none" && source.text !== execText

    // ── The scene the timeline draws ──────────────────────────────────────
    // Built from what the last ⌘R actually made, in the shape the timeline
    // already speaks. Empty until a run has happened, and the panel falls back
    // to the stand-in scene so the dock still has something to lay out.
    //
    // Elements are grouped by their CALL SITE: one `Text("GRADIENT")` is eight
    // Polygon inputs from one line, and eight bars for one word is not a
    // timeline, it is a leak of the engine's internals. A row with members is a
    // group; clicking it opens them.
    property var liveScene: null

    readonly property var shownScene: liveScene !== null ? liveScene : emptyScene

    // ── The caret is a playhead ───────────────────────────────────────────
    // The model already knows which line made each element and which line
    // wrote each of its statements, so the line the caret is on can be looked
    // up in it. The bar it makes lights, and one key plays from the moment
    // that line makes rather than from wherever the playhead was left.
    //
    // Nothing is written. This is the reading half of the link between the
    // code and the time — a wrong guess costs a highlight, which is why it can
    // be live while the writing half waits for a gesture.
    //
    // A statement wins over a declaration: the caret on `square.moveBy(...)`
    // means that move, not the square. Lines from another file are skipped for
    // the same reason a gesture refuses them — the number is not this
    // document's.
    readonly property var caretMakes: {
        const nothing = ({ index: -1, at: -1, n: "" });
        const line = source.caretLine + 1; // the model counts lines from one
        if (line <= 0)
            return nothing;

        const rows = shownScene.elements;
        for (let i = 0; i < rows.length; i++) {
            const row = rows[i];
            if (!app.fromOpenFile(row.file))
                continue;
            for (const fx of row.effects)
                if (fx.line === line)
                    return { index: i, at: fx.l, n: row.n + "." + fx.n };
            if (row.line === line)
                return { index: i, at: row.l, n: row.n };
        }
        // A `timestamp()` line makes a marker, not a bar: nothing to light,
        // but a moment to play from — the one the flag on the ruler points at.
        for (const m of shownScene.markers)
            if (m.line === line && app.fromOpenFile(m.file))
                return { index: -1, at: m.at, n: "timestamp " + m.n };
        // Any other line — a comment, a wait(), a blank, an import — still has
        // a moment: where the scene's clock stands when that line runs. That
        // is the latest thing written above it: an element's cursor once its
        // statement is done, a wait's start, a marker's flag.
        const fps = shownScene.fps !== undefined ? shownScene.fps : 30;
        let clock = 0;
        for (const row of rows) {
            if (!app.fromOpenFile(row.file))
                continue;
            for (const point of row.points || [])
                if (point.line <= line && app.fromOpenFile(point.file) && point.cursor !== undefined)
                    clock = Math.max(clock, point.cursor / fps);
        }
        // A wait above the caret has passed; the caret ON the wait plays it.
        for (const w of shownScene.waits)
            if (w.line !== undefined && w.line <= line)
                clock = Math.max(clock, w.line < line ? w.at + w.d : w.at);
        for (const m of shownScene.markers)
            if (m.line <= line && app.fromOpenFile(m.file))
                clock = Math.max(clock, m.at);
        return { index: -1, at: Math.min(clock, shownScene.duration), n: "line " + line };
    }

    function playFromCaret() {
        const made = app.caretMakes;
        if (made.at < 0) {
            source.say("nothing this line makes is on the timeline");
            return;
        }
        app.seekTo(made.at);
        app.playing = true;
        source.say(made.n + " — playing from " + made.at.toFixed(1) + "s");
    }

    // The bin holds what the SCENE loads, plus what has been dropped this
    // session. Same rule as the timeline: it comes from the code, or it is not
    // there. `Video`, `Image` and `Sound` are the inputs that read a file; a
    // Rectangle is not media however it is drawn.
    readonly property var sceneAssets: {
        const out = [];
        const seen = ({});
        for (const one of shownScene.elements) {
            if (one.kind !== "video" && one.kind !== "image" && one.kind !== "sound")
                continue;
            if (seen[one.n] === true)
                continue;
            seen[one.n] = true;
            // Where the file IS, read off the call that loaded it. Without it a
            // clip already in the scene could be shown in the bin and not
            // dragged out of it — and "the bin" would mean two different things
            // depending on which row you had your hand on.
            const path = one.line > 0
                       ? Shell.readPositional(source.text, one.line, one.cls, 0) : "";
            out.push({ n: one.n, kind: one.kind, lead: path, line: one.line });
        }
        return out;
    }

    function kindOf(cls) {
        if (cls === "Video") return "video";
        if (cls === "Image") return "image";
        if (cls === "Sound") return "sound";
        // `Text` is drawn by the engine, so it is a polygon like any other
        // shape. The palette's `subs` hue means text DERIVED from a track —
        // a transcription — and giving it to a title would say the wrong thing
        // in the one place the colour is supposed to be the explanation.
        return "polygon";
    }

    // The name the author gave it, read off the line that made it: `square =
    // Square(...)` is called `square` everywhere else in their file, so calling
    // it "Square" here would be the tool renaming their work.
    function labelFor(element) {
        const lines = source.text.split("\n");
        const line = element.line >= 1 && element.line <= lines.length
                   ? lines[element.line - 1] : "";
        const named = /^\s*([A-Za-z_]\w*)\s*=/.exec(line);
        return named !== null ? named[1] : element.kind;
    }

    // A part of a folded row, numbered. They all come from one line, so they all
    // carry the same name — and eight rows called `title` name nothing. The
    // ordinal is the letter's place in the word, which is the only thing that
    // tells them apart.
    function partOf(element, ordinal) {
        return {
            n: element.n + " " + ordinal,
            kind: element.kind,
            l: element.l,
            d: element.d,
            line: element.line,
            file: element.file,
            index: element.index,
            cls: element.cls,
            points: element.points,
            effects: element.effects,
            members: []
        };
    }

    // `flaws` is what the run said about the scene it just made — the warnings
    // `execSource` collects. They are joined in HERE, once, so that the timeline
    // and the effect tree each read a fault off the row they already draw
    // instead of holding a second list and matching line numbers against it.
    function buildLiveScene(model, flaws) {
        const fps = model.fps;
        const said = flaws !== undefined ? flaws : [];
        // Where the scene's time joins. A `wait()` is the only place the
        // language lets a change push what follows, so the timeline draws them
        // rather than inventing a rule of its own about what ripples.
        // A gap is exactly the frames it was written as. It reaches the end of
        // the scene on its own when nothing follows — no special case here —
        // because the scene is now as long as the video it makes.
        const waits = (model.waits || []).map((w) => ({
            at: w.start / fps,
            d: w.frames / fps,
            says: w.frames / fps,
            line: w.line
        }));
        // The moments the scene named with `timestamp()`. Flags on the ruler,
        // and stops for the marker keys.
        const markers = (model.markers || []).map((m) => ({
            at: m.frame / fps,
            n: m.name,
            line: m.line !== undefined ? m.line : 0,
            file: m.file !== undefined ? m.file : ""
        }));
        let rows = [];
        let byLine = ({});

        for (const element of model.elements) {
            // Joined on the element's INDEX, not on its line: a warning names
            // the input it is about, and one line can carry several elements.
            const mine = said.filter((w) => w.input === element.index);
            const one = {
                n: labelFor(element),
                kind: kindOf(element.kind),
                l: element.first / fps,
                d: (element.last - element.first + 1) / fps,
                line: element.line,
                // Which file that line is in. A gesture writes by line number
                // into the open document, so without this an element built by
                // an imported module is edited as if its line were this file's.
                file: element.file,
                // The class the scene actually named — `Square`, `Video` — kept
                // beside the media kind it is drawn as. A gesture writes to the
                // CALL, and the call is spelled with this.
                cls: element.kind,
                index: element.index,
                // Empty on a clean element, which is how the timeline knows
                // whether to stripe the bar at all.
                flaws: mine,
                // The lines that already say something about this element, and
                // the cursor each one leaves behind. What a gesture needs to
                // write a NEW statement — see trimElement.
                points: element.points !== undefined ? element.points : [],
                // Named by what the SCENE says, not by what the renderer
                // calls it: a row that reads `scaleTo` is talking about the
                // line you wrote, and a row that reads `Scale` is talking
                // about a shader you never asked about. `kinds` keeps the
                // shaders behind it, for the tooltip.
                effects: element.effects.map((fx) => ({
                    n: fx.call !== undefined && fx.call.length > 0 ? fx.call : fx.name,
                    l: fx.start / fps,
                    d: (fx.end - fx.start + 1) / fps,
                    call: fx.call !== undefined ? fx.call : "",
                    line: fx.line !== undefined ? fx.line : 0,
                    file: fx.file !== undefined ? fx.file : "",
                    // The message that landed on THIS call, or "". The timeline
                    // says which element; this says which line of it.
                    flaw: app.flawOn(mine, fx.line !== undefined ? fx.line : 0),
                    kinds: fx.kinds !== undefined ? fx.kinds : [fx.name]
                })),
                members: []
            };

            // Same line, same gesture: fold it in rather than adding a row.
            const key = element.file + ":" + element.line;
            if (element.line > 0 && byLine[key] !== undefined) {
                const parent = rows[byLine[key]];
                // The row IS the first part, so it joins the list the first
                // time a second one shows up — otherwise a word of eight
                // letters reports seven.
                if (parent.members.length === 0)
                    parent.members.push(partOf(parent, 1));
                parent.members.push(partOf(one, parent.members.length + 1));
                parent.flaws = parent.flaws.concat(one.flaws);
                parent.l = Math.min(parent.l, one.l);
                parent.d = Math.max(parent.d, one.l + one.d - parent.l);
                continue;
            }
            byLine[key] = rows.length;
            rows.push(one);
        }

        return { fps: fps, duration: model.frames / fps, elements: rows, waits: waits, markers: markers };
    }

    // The message a warning left on one source line, or "".
    function flawOn(said, line) {
        for (const w of said)
            if (w.sourceLine === line)
                return w.message;
        return "";
    }

    // Every effect the library exposes, asked for once.
    property var effectNames: []

    // And everything it can build: shapes, media, templates.
    property var templateNames: []

    // The two catalogues as one list, which is what the Library panel shows.
    //
    // They are different in kind — a template IS an element, an effect happens
    // TO one — and the panel says so by where a thing can be dropped, not by
    // making you look in two places for "what can I add".
    readonly property var placeable: {
        const out = [];
        for (const template of templateNames)
            out.push(template);
        for (const effect of effectNames)
            out.push({
                name: effect.name,
                group: "effect",
                module: effect.module,
                form: effect.form,
                // An effect drops on a clip whichever folder it came from, so a
                // preset of yours stays in the EFFECTS group — and says where it
                // lives instead, since it cannot have its own heading.
                says: effect.module.indexOf("templates.") === 0 ? "yours — templates/" : "",
                params: effect.params,
                required: []
            });
        return out;
    }

    // What is being carried across the window right now — {template, values,
    // x, y} — or null. The ghost under the pointer is drawn from it, and so is
    // the timeline's mark of where it would land.
    property var carried: null

    function carryTemplate(template, values, x, y) {
        carried = { template: template, values: values, x: x, y: y };
        timeline.dropAt = timeline.timeAtWindow(x, y);
        // An effect needs a clip under it; a template needs only a moment. Both
        // are shown while the thing is in the air, because a drop you cannot aim
        // is a drop you undo.
        const over = template.group === "effect" ? timeline.elementAtWindow(x, y) : null;
        timeline.hoverLane = over === null ? -1 : timeline.scene.elements.indexOf(over);
    }

    // ── A file, from the bin onto the timeline ────────────────────────────
    // The same gesture as a template, with the file as the call's first
    // argument. Which class it is comes from the KIND the bin already knows —
    // a bin that can show you a sound and then write `Video(...)` about it is a
    // bin that has stopped being about your files.
    function carryAsset(asset, x, y) {
        carried = { template: { name: app.classOf(asset.kind), group: "media" }, values: ({}), x: x, y: y };
        timeline.dropAt = timeline.timeAtWindow(x, y);
        timeline.hoverLane = -1;
    }

    function classOf(kind) {
        if (kind === "video") return "Video";
        if (kind === "sound") return "Sound";
        if (kind === "image") return "Image";
        return "Video";
    }

    function dropAsset(asset, x, y) {
        const at = timeline.timeAtWindow(x, y);
        carried = null;
        timeline.dropAt = -1;
        timeline.hoverLane = -1;

        if (at < 0) {
            source.say("drop it on the timeline, at the moment it should appear");
            return;
        }

        // What the call needs to name the file. A row that came from the bin
        // carries a path; a row that came from the scene carries the very text
        // the existing call uses, quotes and all.
        const lead = asset.lead !== undefined && asset.lead.length > 0
                   ? asset.lead
                   : '"' + app.projectRelative(asset.path !== undefined ? asset.path : "") + '"';
        if (lead === '""') {
            source.say("that row has no file behind it");
            return;
        }

        placeTemplate({ name: app.classOf(asset.kind), module: "", params: [], required: [] },
                      ({}), app.snapTime(at, false),
                      { lead: lead, name: app.nameFromFile(lead) });
    }

    // Relative to the project when it is inside it: an absolute path is a scene
    // that only renders on this machine.
    function projectRelative(path) {
        const root = Shell.projectRoot() + "/";
        return path.indexOf(root) === 0 ? path.substring(root.length) : path;
    }

    function dropTemplate(template, values, x, y) {
        const at = timeline.timeAtWindow(x, y);
        const over = timeline.elementAtWindow(x, y);
        carried = null;
        timeline.dropAt = -1;
        timeline.hoverLane = -1;

        if (template.group === "effect") {
            if (over === null || at < 0) {
                source.say("an effect goes on a clip — drop it on one");
                return;
            }
            app.applyEffect(over, template, { values: values, at: app.snapTime(at, false) });
            return;
        }

        if (at < 0) {
            // Dropped on nothing. Better than dropping it at the caret: a
            // template that lands wherever the cursor happens to be is a line
            // you did not place.
            source.say("drop it on the timeline, at the moment it should appear");
            return;
        }
        placeTemplate(template, values, app.snapTime(at, false));
    }

    // Applying an effect is an INSERTED statement, never a rewritten one.
    //
    // `square.apply(fadeIn())` on its own line says exactly what happened, can
    // be read, moved and deleted, and leaves every call you wrote untouched.
    // Editing an existing call — adding an argument, changing a duration — is
    // the thing three councils refused, because it needs to be right about code
    // it did not write.
    // A gesture writes to the line that made the element.
    //
    // Not a line appended at the end: the timeline is a VIEW of the source, so
    // moving something in the view has to be the same edit a person would have
    // typed. `Shell.setArgument` finds the call by line and name and replaces
    // that value's characters — the rest of the file, comments and spacing
    // included, is what it was.
    //
    // The scene is re-run straight after, because a gesture whose result you
    // have to ask for with ⌘R is not a gesture.
    // A line belongs to a file, and an element does not have to come from the
    // open one: `from titles import banner` makes one whose line is a line of
    // titles.py. Every gesture here addresses the pane's own document by line
    // number, so applied to such an element it rewrites whatever the scene
    // happens to say at that number — a different call, or nothing at all.
    // Refusing is not enough on its own: a gesture that declines in silence
    // looks exactly like one that failed, so the file that owns the line is
    // named out loud.
    function fromOpenFile(file) {
        return file === undefined || file.length === 0
            || source.path.length === 0 || file === source.path;
    }

    function foreignLine(file) {
        return app.fromOpenFile(file) ? "" : String(file).split("/").pop() + " wrote that line — open it to change it there";
    }

    function ownsLine(file) {
        const foreign = app.foreignLine(file);
        if (foreign.length > 0)
            source.say(foreign);
        return foreign.length === 0;
    }

    function writeArgument(element, call, name, value) {
        if (element === null || element.line === undefined)
            return false;
        return app.writeOn(element.line, call, name, value, element.file, element.cls);
    }

    // The same edit, addressed by line rather than by element: an effect knows
    // the call that wrote it and nothing else about the element it animates.
    //
    // The edit is a range applied to the pane's own document, so the gesture is
    // in the same undo history as typing — see SourcePanel.replaceRange.
    // A refusal, and the edit that IS allowed instead.
    //
    // `wait(PAUSE_DELAY)` cannot be dragged to 0.5 — that would keep the timing
    // and throw away the decision the name stands for. But the constant's own
    // line can be changed, and that is what the person meant every time they
    // aimed at a value they had given a name. So the sentence becomes a button:
    // it says what will change and how many places read it, and it goes on its
    // own if it is not taken. Said, never done quietly — changing one number
    // that thirty lines share is not a thing to do behind someone's back.
    function offerConstant(line, call, key, value) {
        const offer = Shell.constantOffer(source.text, line, call, key, value);
        if (!offer.ok)
            return false;

        source.offer(
            offer.name + " → " + value + ", read on " + offer.uses
            + (offer.uses === 1 ? " line" : " lines") + " · click to change it",
            () => {
                if (!source.replaceRange(offer.start, offer.end, offer.text))
                    return;
                app.executeScene();
                source.say(offer.name + " is now " + value);
            }
        );
        return true;
    }

    // `owner`, the element's class when it is known, lets the shell find a
    // value the line gives by position: `Text("Merci")` says `text` with no name.
    function writeOn(line, call, name, value, file, owner) {
        return app.carryOut(app.planOn(line, call, name, value, file, owner));
    }

    // An edit decided without being made: `{ ok, line, start, end, text }` for
    // a range of the buffer and what replaces it, `{ ok, line, insert }` for a
    // statement written under a line, `{ ok: false, message, offer }` for a
    // refusal — with the constant's own line to offer when a name stood in the
    // way. Decided apart from the write so that the timeline's tip can show
    // the very edit the release will make, before anything is written.
    function planOn(line, call, name, value, file, owner) {
        if (line === undefined || line <= 0 || call === undefined || call.length === 0)
            return { ok: false, message: "" };
        const foreign = app.foreignLine(file);
        if (foreign.length > 0)
            return { ok: false, message: foreign };

        const span = Shell.argumentSpan(source.text, line, call, name, value, owner !== undefined ? owner : "");
        if (!span.ok)
            // Where and what, not just that: "could not write start" names
            // nothing anyone can go and look at.
            return {
                ok: false, offer: { line: line, call: call, key: name, value: value },
                message: span.message.length > 0 ? span.message
                         : "could not write " + name + "=" + value + " on " + call + "(), line " + line
            };
        return { ok: true, line: line, start: span.start, end: span.end, text: span.text };
    }

    function carryOut(plan) {
        if (!plan.ok) {
            const offer = plan.offer;
            if (!(offer !== undefined && app.offerConstant(offer.line, offer.call, offer.key, offer.value))
                && plan.message.length > 0)
                source.say(plan.message);
            return false;
        }
        if (!(plan.insert !== undefined ? source.insertAfterLine(plan.line, plan.insert)
                                         : source.replaceRange(plan.start, plan.end, plan.text)))
            return false;
        app.executeScene();
        return true;
    }

    // Taking an effect off is deleting the call that put it on — the same edit
    // in reverse, and the reason `removeCallSpan` tells a link of a chain from a
    // statement of its own: `.rotateBy(180)` goes on its own, `square.fadeIn()`
    // takes its line with it. Refused rather than guessed when the call sits
    // inside something else, because a delete that lands on the wrong span is
    // the one gesture nobody forgives.
    function removeCall(line, call, file) {
        if (line === undefined || line <= 0 || call === undefined || call.length === 0)
            return false;
        if (!app.ownsLine(file))
            return false;

        const span = Shell.removeCallSpan(source.text, line, call);
        if (!span.ok) {
            source.say("could not remove " + call + " — line " + line);
            return false;
        }
        if (!source.replaceRange(span.start, span.end, span.text))
            return false;

        app.executeScene();
        source.say("removed " + call + " · ⌘Z to put it back");
        return true;
    }

    // ── Placing something new, at a moment ────────────────────────────────
    //
    // A template is not an effect: it does not act on an element, it IS one. So
    // the drop writes the line that makes it — and, when the moment asked for is
    // not the one the code has already reached, the two lines that say when it
    // appears.
    //
    // WHERE those lines go is the whole problem. A `wait()` is a barrier for
    // everything in the scene: an element created after one cannot start before
    // it, whatever it says. So the block goes before the first wait that has
    // already passed the moment wanted, and `start=` counts from the wait
    // before that. Written at the end of the file, a template could only ever
    // land after the last wait — which is to say, at the end of the video.
    function placeTemplate(template, values, seconds, options) {
        if (template === undefined || template === null)
            return;

        const fps = execFps > 0 ? execFps : 30;
        const target = Math.round(seconds * fps);

        let base = 0;
        let afterLine = source.text.split("\n").length;
        for (const gap of (liveScene.waits !== undefined ? liveScene.waits : [])) {
            const ends = Math.round((gap.at + gap.d) * fps);
            if (ends <= target) {
                base = ends;
                continue;
            }
            // The block belongs above this wait, and `insertBlock` writes after
            // a line, so it is told about the one before it.
            afterLine = Math.max(0, gap.line - 1);
            break;
        }

        // A name nothing else in the scene has. The class in lower case is what
        // a person writes nine times out of ten; the number only appears when it
        // has to.
        // Named after the FILE when there is one — `interview = Video("interview.mp4")`
        // is what a person writes, and `video2` is what a tool writes.
        const wanted = options && options.name ? options.name : "";
        const stem = wanted.length > 0
                   ? wanted
                   : template.name.charAt(0).toLowerCase() + template.name.slice(1);
        let name = stem;
        for (let n = 2; new RegExp("^\\s*" + name + "\\s*[.=]", "m").test(source.text); ++n)
            name = stem + n;

        // Only what was actually decided: a field left at the signature's own
        // default is not written. The day a default changes, every scene that
        // spelled it out keeps the old one without saying so.
        const args = [];
        for (const parameter of template.params) {
            const written = values[parameter.name];
            if (written === undefined)
                continue;
            const value = String(written).trim();
            if (value.length === 0 || value === parameter.value)
                continue;
            args.push(parameter.name + "=" + value);
        }

        // A file goes in the first slot, with no name in front of it — that is
        // how `Video("shot.mp4")` reads, and the editor writes what a person
        // would have typed.
        const lead = options && options.lead ? [options.lead] : [];
        const statements = [name + " = " + template.name + "(" + lead.concat(args).join(", ") + ")"];
        const moment = (target - base) / fps;
        if (moment > 0.001) {
            // Hidden, then shown: an input is on screen from the moment it
            // exists, and a template dropped at two seconds that flashes at zero
            // is not what anybody dragged.
            statements.push(name + ".hide()");
            statements.push(name + ".show(start=" + app.plain(moment) + ")");
        }

        // The block first, the import after it: an import is written at the top
        // of the file and moves every line under it by one, including the one
        // the block was measured against.
        if (!source.insertBlock(afterLine, statements))
            return;
        if (template.module.length > 0) {
            const line = "from " + template.module + " import " + template.name;
            if (source.text.indexOf(line) < 0)
                source.insertImport(line);
        }
        app.executeScene();
        source.say(name + " at " + (target / fps).toFixed(1) + "s");
    }

    // ── A clip in the hand, alone unless ⌘ pushes ─────────────────────────
    //
    // The scene is sequential: a clip that ends later starts every gap after
    // it later, and the whole film follows. That is what ⌘ asks for. Without
    // it the clip moves ALONE — the first gap that moved gives the time back,
    // so nothing after that gap is touched — and it stops where that gap has
    // nothing left.
    //
    // Measured on the run rather than worked out: whether a `hide` pushes
    // depends on where the scene's clock stood when its line ran, and a first
    // `.wait()` costs a frame more than it says. So the edit is written, the
    // gaps are read again, and what the first of them lost is written back.
    // The several writes are then folded into one, for one ⌘Z.
    function gesture(element, edge, value, push) {
        const before = source.text;
        const fps = execFps > 0 ? execFps : 30;
        const was = (liveScene.waits !== undefined ? liveScene.waits : [])
                    .map((gap) => ({ at: Math.round(gap.at * fps), frames: Math.round(gap.d * fps) }));
        const write = (to) => edge === "body" ? app.moveElement(element, to) : app.trimElement(element, edge, to);

        write(value);
        if (source.text === before || push)
            return app.asOneEdit(before);

        // More than the gap holds: as far as it goes, and no further. Asked
        // again rather than computed once — a `.wait()` counts whole frames.
        let owed = app.owedBy(was);
        for (let tries = 0; owed !== null && owed.left < 0 && tries < 3; ++tries) {
            value += owed.left / fps;
            const went = edge === "body" ? value : value - element.l - (edge === "out" ? element.d : 0);
            app.rewind(before);
            if (went < 0.02) {
                app.executeScene();
                source.say("the wait() on line " + owed.line + " has no time left to give — ⌘ pushes what follows instead");
                return;
            }
            write(value);
            owed = source.text === before ? null : app.owedBy(was);
        }
        if (owed !== null) {
            const span = owed.left < 0 ? { ok: false }
                       : Shell.positionalSpan(source.text, owed.line, "wait", 0, app.plain(Math.ceil(owed.left / fps * 100 - 1e-6) / 100));
            if (!span.ok) {
                app.rewind(before);
                app.executeScene();
                source.say("the wait() on line " + owed.line + " cannot give that time back — ⌘ pushes what follows instead");
                return;
            }
            source.replaceRange(span.start, span.end, span.text);
            app.executeScene();
        }
        app.asOneEdit(before);
    }

    // The first gap a write moved, and the frames it would have left once it
    // has given the move back. Null when no gap moved: nothing was pushed.
    function owedBy(was) {
        const fps = execFps > 0 ? execFps : 30;
        const now = liveScene.waits !== undefined ? liveScene.waits : [];
        if (now.length !== was.length)
            return null;
        for (let i = 0; i < now.length; ++i) {
            const moved = Math.round(now[i].at * fps) - was[i].at;
            if (moved !== 0)
                return { line: now[i].line, left: was[i].frames - moved };
        }
        return null;
    }

    // The gap that follows a line, or null. The waits are in the film's order.
    function gapAfter(line) {
        const found = (liveScene.waits !== undefined ? liveScene.waits : []).find((gap) => gap.line > line);
        return found !== undefined ? found : null;
    }

    // The gap a clip would push by ending later, and the slack it has before
    // it does: a gap starts when the LAST thing before it has ended, so a clip
    // that ends early can go that far without moving anything. Null when no
    // gap follows, or when the clip's end is not its clock's to move — a left
    // edge whose `hide` is told the old moment again.
    function gapBehind(element, edge, line) {
        const gap = app.gapAfter(line);
        const points = element.points !== undefined ? element.points : [];
        if (gap === null || (edge === "in" && points.some((point) => point.call === "hide")))
            return null;
        // Where the element's own clock stands: the end of the last thing it does.
        const clock = element.effects.reduce((most, fx) => Math.max(most, fx.l + fx.d), 0);
        return { gap: gap, slack: Math.max(0, gap.at - clock) };
    }

    // How far a clip can be taken later on its own: its slack, then what the
    // gap behind it holds. A right edge is not held back here — whether a
    // `hide` pushes at all is the run's to say, see gesture.
    function roomAfter(element, edge) {
        if (edge === "out")
            return Infinity;
        const plan = app.planGesture(element, edge, edge === "body" ? 0.1 : element.l + 0.1);
        const behind = plan.ok ? app.gapBehind(element, edge, plan.line) : null;
        if (behind === null)
            return Infinity;
        return behind.slack + (app.gapSpan(behind.gap).ok ? behind.gap.d : 0);
    }

    // Where a gap's number is written, if it is a number: a name is not the
    // gesture's to change. Asked with another value than the one it holds —
    // the same one is no edit, and is answered as a refusal.
    function gapSpan(gap) {
        return Shell.positionalSpan(source.text, gap.line, "wait", 0, app.plain(gap.d + 1));
    }

    // ── The stopwatch ─────────────────────────────────────────────────────
    // A value typed at the playhead writes the animation that reaches it THERE:
    // `box.moveTo(x=3, at=2.1)` lands on the playhead's frame. `at=` and not
    // `start=`, because the moment is the film's and not the element's clock —
    // measured, such a line moves no clock, so nothing written after it shifts.
    readonly property var keyVerbs: ({
        "Position:x": "moveTo(x=", "Position:y": "moveTo(y=",
        "Scale:x": "scaleTo(x=", "Scale:y": "scaleTo(y=",
        "Rotation": "rotateTo(", "Opacity": "fadeTo(",
        "Align:x": "alignTo(x=", "Align:y": "alignTo(y="
    })

    function keyAt(element, key, value, frame) {
        const fps = execFps > 0 ? execFps : 30;
        const what = key.replace(":", " ").toLowerCase();
        const at = (frame / fps).toFixed(2) + "s";
        if (app.keyVerbs[key] === undefined || isNaN(Number(value)))
            return false;
        if (!app.fromOpenFile(element.file)) {
            source.say(app.foreignLine(element.file));
            return false;
        }
        const declaration = source.text.split("\n")[element.line - 1];
        if (declaration === undefined || !new RegExp("^\\s*" + element.n + "\\s*=").test(declaration)) {
            source.say("give it a name first — " + element.cls + "(...) on its own cannot be told to change");
            return false;
        }
        const born = Math.round(element.l * fps);
        if (frame <= born) {
            source.say("at its first frame a value is where " + element.n + " starts — type it in Transform");
            return false;
        }

        // Twelve frames, the verbs' own length — or as many as the channel
        // has free: on a frame a line already sets, the value is that line's
        // to say, and right after one the animation starts where it ends.
        let from = Math.max(born, frame - 11);
        for (const fx of element.effects) {
            if (fx.kinds.indexOf(key) < 0)
                continue;
            const first = Math.round(fx.l * fps), last = first + Math.round(fx.d * fps) - 1;
            if (first <= frame && frame <= last) {
                source.say(fx.n + "() on line " + fx.line + " is setting " + what + " at " + at + " — the value there is that line's to say");
                return false;
            }
            if (last < frame)
                from = Math.max(from, last + 1);
        }
        const frames = frame - from + 1;
        const duration = frames === 12 ? "" : ", duration=" + app.plain(Math.ceil(frames / fps * 100 - 1e-6) / 100);
        const statement = element.n + "." + app.keyVerbs[key] + value + ", at=" + app.plain(from / fps) + duration + ")";

        // Under the last line of its own that has not gone past the start, and
        // under every wait() that begins before the end: a wait starts when the
        // last thing written above it has ended, so one left below would be
        // pushed.
        const point = app.pointFor(element, from);
        let line = point !== null ? point.line : element.line;
        const gaps = liveScene.waits !== undefined ? liveScene.waits : [];
        for (const gap of gaps)
            if (Math.round(gap.at * fps) <= frame && gap.line > line)
                line = gap.line;

        // The run is the judge: the film keeps its length and its waits, and
        // no two lines end up claiming the same frames.
        const before = source.text;
        const shape = () => JSON.stringify([execFrames, gaps.length].concat(
            (liveScene.waits !== undefined ? liveScene.waits : []).map((gap) => [Math.round(gap.at * fps), Math.round(gap.d * fps)])));
        const was = shape(), flaws = source.runFlaws.length;
        if (!source.insertAfterLine(line, statement))
            return false;
        app.executeScene();
        const failed = execState === "failed", clash = source.runFlaws.length > flaws, moved = shape() !== was;
        if (failed || clash || moved) {
            const why = failed ? element.n + " is not free to be told that at " + at
                      : clash ? "another line already sets " + what + " over those frames"
                      : "it would push a wait() that follows";
            app.rewind(before);
            app.executeScene();
            source.say(why + " — nothing written");
            return false;
        }
        source.say(what + " reaches " + value + " at " + at + " — line " + (line + 1) + " added");
        return true;
    }

    function rewind(to) {
        for (let guard = 0; source.text !== to && guard < 4; ++guard)
            source.undo();
    }

    // What a gesture wrote in several steps, as one entry of the undo stack:
    // taken back, then written again as the single range that differs.
    function asOneEdit(before) {
        const after = source.text;
        if (after === before)
            return;
        app.rewind(before);
        const now = source.text;
        let head = 0;
        while (head < now.length && head < after.length && now[head] === after[head])
            ++head;
        let tail = 0;
        while (tail < now.length - head && tail < after.length - head
               && now[now.length - 1 - tail] === after[after.length - 1 - tail])
            ++tail;
        source.replaceRange(head, now.length - tail, after.slice(head, after.length - tail));
    }

    // ── Trimming: where a clip stops ──────────────────────────────────────
    //
    // One meaning for every kind, because the timeline only ever draws one
    // thing: when the element is ON SCREEN. Pulling the right edge in says "stop
    // showing it here", and the only line that says that is `hide`.
    //
    // A video's `startFrame`/`endFrame` are NOT that, which is worth writing
    // down: they choose which frames of the file get loaded, and a clip whose
    // media runs out keeps its place in the scene either way — a `Video` cut to
    // thirty frames inside a three-second scene is still reported as lasting
    // three seconds. Writing `endFrame` from this gesture would have moved
    // nothing on the timeline. The frame range stays where it belongs, on the
    // card, beside the rest of the call.
    function trimElement(element, edge, seconds) {
        if (element === null || element.line === undefined || element.line <= 0)
            return;
        if (edge === "out") {
            hideAt(element, seconds);
            return;
        }

        // The left edge is a move whose END stays put. An end the film gives —
        // nothing hides the element — did not follow the clock and needs
        // nothing; a `hide(start=…)` counts from the clock that just moved, so
        // it is told the old moment again. Asked of the scene as it is AFTER
        // the move, because only a run knows where that line's cursor now is.
        const end = element.l + element.d;
        const now = app.shiftClock(element, seconds - element.l, app.planGesture(element, edge, seconds));
        if (now === null)
            return;
        const fps = execFps > 0 ? execFps : 30;
        if (now.points.some((point) => point.call === "hide") && Math.abs(now.l + now.d - end) * fps > 0.5) {
            // A hide that could not be rewritten has said why; that stands.
            const before = source.text;
            hideAt(now, end);
            if (source.text === before)
                return;
        }
        source.say(now.n + " now starts at " + now.l.toFixed(1) + "s");
    }

    // ── Moving: when a clip starts ────────────────────────────────────────
    //
    // A clip starts where its element's own clock stood when the first thing
    // that takes time was written, and the word that moves that clock is
    // `.wait()`. So a drag writes one — or changes the one already there — in
    // front of that call: `title.wait(0.5).fadeIn()`. Everything the element
    // does afterwards counts from the same clock and follows on its own, which
    // is what makes it a move and not a retiming of one effect.
    //
    // A video does not follow its clock: its frames play from where the scene
    // stood when the line made it. Waiting would delay its entrance over a
    // picture that kept running — a slip, shown as a move — so the body of a
    // media clip refuses, while its left edge, which MEANS that, does not.
    function moveElement(element, by) {
        const now = app.shiftClock(element, by, app.planGesture(element, "body", by));
        if (now !== null)
            source.say(now.n + " now starts at " + now.l.toFixed(1) + "s");
    }

    // What a clip gesture would write — the one decision behind the release
    // (trimElement, moveElement) and the lines lit beforehand (aimCode).
    // `value` is what the timeline hands over: the moment for an edge, the
    // distance for the body.
    function planGesture(element, edge, value) {
        if (element === null || element.line === undefined || element.line <= 0)
            return { ok: false, message: "" };
        if (edge === "out")
            return app.planHide(element, value);
        if (edge === "in")
            return app.planClock(element, value - element.l);
        if (element.kind === "video" || element.kind === "sound")
            return {
                ok: false,
                message: element.n + " plays from where line " + element.line
                         + " stands in the scene — nothing to move but that line, or the wait() above it"
            };
        return app.planClock(element, value);
    }

    // What a hand on a clip lights in the code pane: the line the release will
    // write — as it will read, once the clip is held — or the refusal, while
    // the button is still down. Asked of `planGesture`, so it shows the edit
    // the release makes, and the buffer is never touched. Alone, the gap that
    // gives the time back is lit too: that line changes with it. Two things
    // only a run can know are not in it: a `.wait()` the scene ignores (taken
    // back on release, see shiftClock) and the `hide` a moved left edge is
    // told again (trimElement).
    function aimCode(aim) {
        if (aim === null) {
            source.aimed = [];
            return;
        }
        // Hovered, nothing is pulled yet: planned a tenth further, which is the
        // line a drag would touch, and any refusal a drag would meet.
        const nudged = aim.edge === "body" ? 0.1 : aim.at + 0.1;
        const plan = app.planGesture(aim.element, aim.edge, aim.held ? aim.value : nudged);
        if (!plan.ok) {
            const named = plan.offer !== undefined
                          ? Shell.constantOffer(source.text, plan.offer.line, plan.offer.call, plan.offer.key, plan.offer.value)
                          : { ok: false };
            source.aimed = [{
                line: plan.offer !== undefined ? plan.offer.line : aim.element.line, from: 0, to: 0, text: "", refused: true,
                note: named.ok ? named.name + " is a name — let go and its own line is offered: " + named.name + " → " + plan.offer.value
                    : plan.message.length > 0 ? plan.message : "nothing to write"
            }];
            return;
        }

        const rows = [];
        if (plan.insert === undefined) {
            const head = source.text.slice(0, plan.start).split("\n");
            const from = head[head.length - 1].length;
            const reads = source.text.split("\n")[head.length - 1];
            rows.push({
                line: head.length, from: from, to: from + (aim.held ? plan.text.length : plan.end - plan.start),
                text: aim.held ? reads.slice(0, from) + plan.text + reads.slice(from + plan.end - plan.start) : "",
                note: "", refused: false
            });
        } else {
            // A statement of its own: said beside the line it goes under.
            rows.push({ line: plan.line, from: 0, to: 0, text: "", note: aim.held ? plan.insert : "", refused: false });
        }

        // Lit only when it WILL change: past the slack the clip has before it
        // is the last thing to end, and not for a left edge whose end a hide
        // keeps in place.
        const behind = aim.push || aim.edge === "out" ? null : app.gapBehind(aim.element, aim.edge, plan.line);
        const went = !aim.held ? 0.05 : aim.edge === "body" ? aim.value : aim.value - aim.element.l;
        if (behind !== null && went > behind.slack) {
            const gap = behind.gap;
            const span = app.gapSpan(gap);
            const column = span.ok ? source.text.slice(0, span.start).split("\n").pop().length : 0;
            rows.push({
                line: gap.line, from: column, to: span.ok ? column + span.end - span.start : 0, text: "", refused: !span.ok,
                note: span.ok ? "" : "a name cannot give the time back — ⌘ pushes what follows"
            });
        }
        source.aimed = rows;
    }

    // The write, then what the run made of it. A `wait()` or a `waitFor()`
    // between the element and its first effect sets the clock AFTER the
    // `.wait()` did: the clip stays where it was, and the line has gained a word
    // that does nothing. That word is taken back — code the editor wrote and
    // the scene ignores is the one thing worse than a refusal. Answers the
    // element as the new run has it, or null.
    function shiftClock(element, by, plan) {
        if (!app.carryOut(plan) || execState !== "fresh")
            return null;

        // Most of the way is a move: `.wait()` counts whole frames, and a fade
        // is seen a frame after it starts, so the last frame is not promised.
        const now = liveScene.elements.find((one) => one.index === element.index);
        if (now !== undefined && (now.l - element.l) / by > 0.5)
            return now;

        source.undo();
        app.executeScene();
        source.say("could not move " + element.n + " — a wait() above it sets its clock later than that");
        return null;
    }

    function planClock(element, by) {
        const foreign = app.foreignLine(element.file);
        if (foreign.length > 0)
            return { ok: false, message: foreign };
        const fps = execFps > 0 ? execFps : 30;
        const mine = element.effects.filter((fx) => fx.line > 0 && app.fromOpenFile(fx.file));

        // Placed by a drop: `hide()`, then `show(start=…)`. The show already
        // says when, in a number — that number moves.
        for (const fx of mine) {
            const written = fx.call === "show" ? parseFloat(Shell.readArgument(source.text, fx.line, "show", "start")) : NaN;
            if (isNaN(written))
                continue;
            if (written + by < 0)
                return { ok: false, message: "that is before " + element.n + " reaches this line" };
            return app.planOn(fx.line, "show", "start", app.plain(written + by), fx.file);
        }

        // The first thing that takes TIME. `.opacity(0)` and `.position()` are
        // written on a frame and stay on it; a wait in front of them would
        // leave the element standing there, opaque, for as long as it waits.
        const timed = mine.filter((fx) => fx.d * fps > 1.5).sort((a, b) => a.l - b.l);
        if (timed.length === 0)
            return { ok: false, message: "nothing says when " + element.n + " starts — it is there from its first line. Give it a fadeIn() and drag that" };

        // `apply(popIn())` is a call the scene cannot name; the link is `apply`.
        const line = timed[0].line;
        const calls = timed.filter((fx) => fx.line === line).map((fx) => fx.call.length > 0 ? fx.call : "apply");
        const span = Shell.waitLinkSpan(source.text, line, calls, by);
        if (!span.ok) {
            // `.wait(PAUSE)`: the name stays, and its own line is offered —
            // worth what it is worth now, plus the drag.
            const named = Shell.constantOffer(source.text, line, "wait", 0, "0");
            const next = named.ok ? parseFloat(source.text.slice(named.start, named.end)) + by : -1;
            return {
                ok: false, offer: next > 0 ? { line: line, call: "wait", key: 0, value: app.plain(next) } : undefined,
                message: span.message.length > 0 ? span.message : "could not move " + element.n + " — nothing on line " + line + " to wait in front of"
            };
        }
        return { ok: true, line: line, start: span.start, end: span.end, text: span.text };
    }

    // Where a statement about this element has to go if it is to happen at a
    // given frame, and what its `start=` must then say.
    //
    // `start` is seconds after the element's OWN cursor, and the cursor is
    // nowhere in the buffer — it is what the lines above have left it at. So the
    // scene reports, per element, every line that already touched it and where
    // its cursor stood afterwards; a new statement goes under the last of those
    // that has not gone past the moment asked for, and counts from there.
    //
    // `null` when the moment is behind every line that could carry it, which is
    // a refusal: writing a negative `start` would schedule something before the
    // line that schedules it.
    function pointFor(element, target) {
        const fps = execFps > 0 ? execFps : 30;
        const points = element !== null && element.points !== undefined ? element.points : [];
        if (points.length === 0)
            return null;

        // Only the lines this document actually holds: a point from an
        // imported module is a place no edit here can go.
        const mine = points.filter(point => app.fromOpenFile(point.file));
        if (mine.length === 0)
            return null;

        let chosen = mine[0];
        for (const point of mine)
            if (point.cursor <= target)
                chosen = point;

        const start = (target - chosen.cursor) / fps;
        return start < 0 ? null : { line: chosen.line, call: chosen.call, start: start, file: chosen.file };
    }

    // Ending an element: `square.hide(start=…)`, written where it means what it says.
    //
    // `start` is seconds after the ELEMENT's own cursor, and the cursor is
    // nowhere in the buffer — it is what the lines above have left it at. So the
    // scene reports, per element, every line that already touched it and where
    // its cursor stood afterwards; the statement goes under the last of those
    // that has not already gone past the moment asked for, and counts from
    // there. Put at the end of the file instead, it could only ever push the
    // shape's end later, never earlier.
    // `0.7`, not `0.70`: the editor writes what a person would have typed.
    function plain(value) {
        return String(Math.round(value * 100) / 100);
    }

    function hideAt(element, seconds) {
        const fps = execFps > 0 ? execFps : 30;
        if (app.carryOut(app.planHide(element, seconds)))
            source.say(element.n + " now ends at " + (Math.round(seconds * fps) / fps).toFixed(1) + "s");
    }

    function planHide(element, seconds) {
        const foreign = app.foreignLine(element.file);
        if (foreign.length > 0)
            return { ok: false, message: foreign };

        const fps = execFps > 0 ? execFps : 30;
        const target = Math.round(seconds * fps);
        const points = element.points !== undefined ? element.points : [];
        if (points.length === 0)
            return { ok: false, message: "nothing in the scene says when " + element.n + " happens" };

        // One end, not a queue of them: an element already told to hide is told
        // a different moment.
        for (const written of points) {
            if (written.call !== "hide")
                continue;
            const moment = (target - written.cursor) / fps;
            if (moment < 0)
                return { ok: false, message: "that is before " + element.n + " reaches this line" };
            return app.planOn(written.line, "hide", "start", app.plain(moment), written.file);
        }

        const where = app.pointFor(element, target);
        if (where === null)
            return { ok: false, message: "that is before " + element.n + " is finished moving" };

        // The name has to be a name. An element built inline — `Square(...)`
        // with nothing on the left of an `=` — is called after its class here,
        // and `Square.hide()` is a statement about the class.
        const lines = source.text.split("\n");
        const declaration = element.line <= lines.length ? lines[element.line - 1] : "";
        if (!new RegExp("^\\s*" + element.n + "\\s*=").test(declaration))
            return { ok: false, message: "give it a name first — " + element.cls + "(...) on its own cannot be told to hide" };

        return { ok: true, line: where.line, insert: element.n + ".hide(start=" + app.plain(where.start) + ")" };
    }

    // ── A gap, typed or pulled ────────────────────────────────────────────
    function writeWait(line, value) {
        if (isNaN(value) || value < 0) {
            source.say("a gap is a number of seconds");
            return false;
        }

        const span = Shell.positionalSpan(source.text, line, "wait", 0, app.plain(value));
        if (!span.ok) {
            if (!app.offerConstant(line, "wait", 0, app.plain(value)))
                source.say(span.message.length > 0 ? span.message
                           : "could not write wait(" + app.plain(value) + ") on line " + line);
            return false;
        }

        source.replaceRange(span.start, span.end, span.text);
        app.executeScene();
        return true;
    }

    // A gap's label, pulled: the gap ends where it was let go.
    //
    // Only its length is its own. Where a gap STARTS is wherever the work
    // before it ended, and nothing writes that down — so moving a start is
    // this same gesture on the gap before it, which is the one line that can
    // give the time back.
    function dragWait(line, seconds) {
        const waits = liveScene.waits !== undefined ? liveScene.waits : [];
        const mine = waits.find((one) => one.line === line);
        if (mine === undefined)
            return;

        const kept = Math.max(0, seconds - mine.at);
        if (kept < 0.02) {
            source.say("a gap of no time is a line to delete, not a gap to pull");
            return;
        }
        if (app.writeWait(line, kept))
            source.say("wait(" + app.plain(kept) + ") on line " + line);
    }

    // ── Off, without being gone ───────────────────────────────────────────
    // A commented-out line is how a person turns something off in a scene, and
    // it is the only way that survives being read back: the statement is still
    // there, in order, with its arguments, and the scene runs without it.
    //
    // Which is also why the card can still show it. It is not in the timeline —
    // nothing ran — so it is found by reading the buffer, not the scene.
    // A value the line does not carry yet — `.opacity(255)` at the end of the
    // chain, at its factory setting. Written rather than asked about: the card
    // shows it the moment the scene re-runs, and typing over it is the same
    // gesture as changing any other argument.
    function addMetadata(element, write) {
        if (element === null || element.line === undefined || !app.ownsLine(element.file))
            return;

        const lines = source.text.split("\n");
        if (element.line < 1 || element.line > lines.length)
            return;

        let offset = 0;
        for (let i = 0; i < element.line - 1; i++)
            offset += lines[i].length + 1;

        // At the end of what the line says, never after a trailing comment: the
        // call would land inside it and the scene would stop running.
        const text = lines[element.line - 1];
        const code = text.replace(/\s+#.*$/, "");
        // A regex, not trimEnd(): that is ES2019, and Qt's JS engine does not
        // have it — the call threw and nothing was ever added.
        const next = code.replace(/\s+$/, "") + "." + write + text.slice(code.length);
        if (!source.replaceRange(offset, offset + text.length, next))
            return;
        app.executeScene();
        source.say(write.split("(")[0] + " added");
    }

    // A value set on the line is rewritten where the line writes it. `.opacity(0)`
    // names nothing, and an `o=` added beside it would give `o` twice — so what
    // stands without a name is replaced in place. What the line does not write
    // yet is added by name, which is valid wherever it lands.
    function writeMetadata(element, call, name, at, value) {
        if (element === null || element.line === undefined)
            return false;
        const line = element.line;
        if (Shell.readArgument(source.text, line, call, name).length > 0
            || Shell.readPositional(source.text, line, call, at).length === 0)
            return app.writeOn(line, call, name, value, element.file, element.cls);
        if (!app.ownsLine(element.file))
            return false;

        const span = Shell.positionalSpan(source.text, line, call, at, value);
        if (!span.ok) {
            if (!app.offerConstant(line, call, at, value))
                source.say(span.message.length > 0 ? span.message : "could not write " + name);
            return false;
        }
        if (!source.replaceRange(span.start, span.end, span.text))
            return false;

        app.executeScene();
        return true;
    }

    function toggleLine(line, off, file) {
        if (!app.ownsLine(file))
            return;

        const lines = source.text.split("\n");
        if (line < 1 || line > lines.length)
            return;

        let offset = 0;
        for (let i = 0; i < line - 1; i++)
            offset += lines[i].length + 1;

        const text = lines[line - 1];
        const parts = /^(\s*)(#\s?)?(.*)$/.exec(text);
        const next = off ? parts[1] + "# " + parts[3] : parts[1] + parts[3];
        if (next === text)
            return;

        if (!source.replaceRange(offset, offset + text.length, next))
            return;
        app.executeScene();
        source.say(off ? "off — the line is still there" : "back on");
    }

    // Going to a line: the pane comes up, the caret lands on it, and the card
    // gets out of the way. Claimed with `callLater` because the pane may have
    // been behind another tab when the line was asked for.
    // Un nom vit dans le code, donc le renommer est le renommage du volet de
    // code — celui du serveur de langage, qui atteint tous les fichiers qui s'en
    // servent. Un élément dont les lignes sont dans un autre document est refusé
    // pour la raison qui refuse déjà tous les gestes sur lui : le numéro de ligne
    // n'est pas celui de ce document.
    function renameElement(one, wanted) {
        if (one === null || one === undefined || !fromOpenFile(one.file)) {
            source.say("those lines are in another file");
            return;
        }
        // Named already — from the Inspector's field — the rename happens
        // where you are; otherwise the box opens in the code.
        if (wanted !== undefined) {
            // Renamed, the Inspector follows the element under its new name and
            // the scene runs again — nothing should move, and the timeline says
            // the new name.
            const ok = source.renameTo(one.line, one.n, wanted, (touched) => {
                if (touched > 0) {
                    inspector.follow(wanted);
                    app.executeScene();
                }
            });
            if (!ok)
                source.say("no name to rename on line " + one.line);
            return;
        }
        showPanel("code");
        if (!source.renameAt(one.line, one.n))
            source.say("no name to rename on line " + one.line);
    }

    function revealLine(line) {
        if (line === undefined || line <= 0 || source.path.length === 0)
            return;
        source.load(source.path, line - 1, 0);
        showPanel("code");
        Qt.callLater(source.takeFocus);
        elementCard.close();
    }

    function readArgument(element, call, name) {
        if (element === null || element.line === undefined || element.line <= 0)
            return "";
        // Silently, unlike a gesture: reading is what the card does on its own
        // while you look at it, and a line of another file read as if it were
        // this one shows a value belonging to neither.
        if (!app.fromOpenFile(element.file))
            return "";
        return Shell.readArgument(source.text, element.line, call, name);
    }

    // An effect is not part of `from videocode import *` — `flash` lives in
    // videocode.template.effect.other.flash — so writing the call alone would
    // hand you a scene that does not run. A core transformation needs none:
    // `square.scaleTo(...)` is a method on the element, and importing the
    // function behind it would be an import nothing in the scene uses.
    function needsImport(effect) {
        if (effect.form === "method" || effect.module.length === 0)
            return;
        const line = "from " + effect.module + " import " + effect.name;
        if (source.text.indexOf(line) < 0)
            source.insertImport(line);
    }

    function applyEffect(element, effect, options) {
        if (element === null || element.n === undefined)
            return;
        if (!app.ownsLine(element.file))
            return;

        // The import first, if it is missing. Effects are not part of
        // `from videocode import *` — `flash` lives in
        // videocode.template.effect.other.flash — so writing the call alone
        // would hand you a scene that does not run.
        //
        // A core transformation needs none: `square.scaleTo(...)` is a method on
        // the element, and importing the function behind it would be an import
        // nothing in the scene uses.

        // Only what you actually decided.
        //
        // A field left at the signature's own default is not written: the call
        // would say the same thing at twice the length, and the day a default
        // changes, every scene that spelled it out keeps the old one without
        // saying so. What you typed is written exactly as you typed it — the
        // field IS the argument.
        const args = [];
        const chosen = options && options.values ? options.values : ({});
        for (const parameter of effect.params) {
            const written = chosen[parameter.name];
            if (written === undefined)
                continue;
            const value = String(written).trim();
            if (value.length === 0 || value === parameter.value)
                continue;
            args.push(parameter.name + "=" + value);
        }

        // WHEN it happens, and WHERE that has to be written.
        //
        // The moment comes in counted from the start of the scene, because that
        // is the only thing both surfaces that can drop an effect agree on — the
        // card measures from the element's left edge, the timeline from zero.
        // `start=` is then seconds after the element's own cursor on the line
        // the statement lands on, which is not the same number and is why the
        // shell places the line rather than dropping it under the caret.
        const fps = execFps > 0 ? execFps : 30;
        const at = options && options.at !== undefined ? options.at : -1;
        let where = null;
        if (at >= 0) {
            where = app.pointFor(element, Math.round(at * fps));
            if (where === null) {
                source.say("that is before " + element.n + " is ready for it");
                return;
            }
            if (where.start > 0.001)
                args.push("start=" + app.plain(where.start));
        }

        // Three ways of saying the same thing, and the effect itself decides
        // which: a method on the element, a generator handed the element and
        // splatted into `apply`, or a factory `apply` calls for you.
        const call = effect.name + "(" + args.join(", ") + ")";
        let statement;
        if (effect.form === "method")
            statement = element.n + "." + call;
        else if (effect.form === "generator")
            statement = element.n + ".apply(*" + effect.name + "("
                      + [element.n].concat(args).join(", ") + "))";
        else
            statement = element.n + ".apply(" + call + ")";

        // Under the line that leaves the cursor where the drop asked for, or —
        // when nothing said when — under the caret, which is where you were
        // looking.
        //
        // The statement goes in BEFORE the import. An import is written at the
        // top of the file, so adding it first moves every line under it by one
        // — including the one this statement was measured against, which put a
        // `flash` between a comment and the line it was written about.
        if (where !== null) {
            if (!source.insertAfterLine(where.line, statement))
                return;
            app.needsImport(effect);
            app.executeScene();
            source.say(effect.name + " at " + at.toFixed(1) + "s");
            return;
        }

        source.insertLine(statement);
        app.needsImport(effect);
        source.say("added " + effect.name + " — ⌘R to see it");
    }

    // `announce` is what separates a run you ASKED for from one the window did
    // on its own. The notice in the code pane is a receipt for a gesture — ⌘R,
    // a save — and a receipt for something nobody did is noise: the status strip
    // already carries the last run's time, permanently, at the bottom of the
    // window. A failure speaks either way; a scene that did not run is news
    // whoever started it.
    function executeScene(announce) {
        if (source.path.length === 0)
            return;

        const answer = Shell.executeScene(source.text, source.path);
        execMs = answer.ms !== undefined ? answer.ms : 0;

        if (answer.ok) {
            execText = source.text;
            execState = "fresh";
            // Two lines writing the same channel over the same frames is not an
            // error — the scene runs — but swapping them gives a different
            // video, and that is worth seeing where the line is rather than on
            // a stderr the editor never reads. Severity 2 = warning.
            const flaws = JSON.parse(answer.warnings || "[]");
            source.runFlaws = flaws.map(function (w) {
                return {
                    range: { start: { line: w.line, character: 0 },
                             end:   { line: w.line, character: 200 } },
                    severity: w.severity !== undefined ? w.severity : 2,
                    source: "execute",
                    message: w.message
                };
            });
            liveScene = buildLiveScene(JSON.parse(answer.scene), flaws);
            // Anything looking at the scene has to be looking at THIS one.
            elementCard.rebind(liveScene.elements);
            inspector.rebind(liveScene.elements);
            execInputs = parseInt(answer.inputs);
            execFrames = parseInt(answer.frames);
            execFps = answer.fps !== undefined ? parseInt(answer.fps) : execFps;
            execRevision += 1;
            if (announce)
                source.say("ran in " + execMs.toFixed(0) + " ms · " + execInputs + " inputs");
            return;
        }

        // The last good scene stays: an emptied timeline after a typo is the
        // worst possible answer. The failure is shown where every other one is.
        execState = "failed";
        const line = parseInt(answer.line);
        const column = parseInt(answer.column);
        source.runFlaws = [{
            range: {
                start: { line: line, character: column },
                end: { line: line, character: column + 200 }
            },
            severity: 1,
            source: "execute",
            message: answer.message
        }];
        source.say(answer.message.slice(0, 60));
    }

    // What the author is looking at, in front of every question. The child
    // edits the FILE and sees nothing else: "move this left" names a selection
    // it was never shown, and the warnings the last run painted in the gutter
    // never reached it. A few lines, not the buffer — it can Read the file and
    // it can run --inspect for the whole timeline; what it cannot do is look
    // at the screen. Lines count from one, the way the file does.
    function agentBrief() {
        const lines = ["<editor>"];
        lines.push("file: " + source.path + " · caret on line " + (source.cursorLine + 1));

        const one = selectedElement;
        if (one === null)
            lines.push("selected: nothing");
        else {
            const effects = one.effects.map((fx) =>
                fx.n + " (line " + fx.line + ", " + fx.l.toFixed(2) + "–" + (fx.l + fx.d).toFixed(2) + " s)");
            lines.push("selected: " + one.cls + " at line " + one.line
                       + (effects.length > 0 ? " — " + effects.join(", ") : ""));
            // An element built by an imported module is animated by lines this
            // document does not have, and every gesture on it is refused for
            // that reason. Said here so the refusal is not a mystery, and so
            // "move this left" is edited in the file that actually says it.
            if (!fromOpenFile(one.file))
                lines.push("  — those lines are in " + one.file + ", not the open file: "
                           + "the editor refuses gestures on them, so the edit belongs in that file");
        }

        lines.push("playhead: " + playhead.toFixed(2) + " s of " + shownScene.duration.toFixed(2) + " s"
                   + (ranged ? " · range " + markIn.toFixed(2) + "–" + markOut.toFixed(2) + " s" : ""));

        if (execState === "none")
            lines.push("last run: none yet");
        else {
            const flaws = source.runFlaws;
            lines.push("last run: " + (execState === "failed" ? "failed"
                                       : flaws.length === 0 ? "ok, no warnings"
                                       : "ok, " + flaws.length + " warning" + (flaws.length > 1 ? "s" : "")));
            for (const flaw of flaws.slice(0, 5))
                lines.push("  line " + (flaw.range.start.line + 1) + ": " + flaw.message);
            if (flaws.length > 5)
                lines.push("  … " + (flaws.length - 5) + " more");
        }

        // Two ways the picture can be behind the text, said only when they hold.
        if (source.modified)
            lines.push("unsaved: the buffer is ahead of the file on disk — the author reads the buffer, "
                       + "you edit the file, and the line numbers above are the buffer's");
        if (execStale)
            lines.push("stale: the scene has been edited since it last ran — "
                       + "the selection and warnings above describe that run");

        lines.push("</editor>");
        return lines.join("\n") + "\n\n";
    }

    // control() — what `video-code tell <verb>` reaches, from the Agent pane
    // or from any terminal. One object in, one out, `ok` always set. The verbs
    // are the things the author does with the keyboard; an agent gets the same
    // and nothing more, and every answer carries the state it changed so the
    // caller need not ask twice. Edits are NOT here on purpose: the file is the
    // scene, and an agent edits the file.
    function control(req) {
        const verb = req.do;
        const brief = (e) => e === null || e === undefined ? null : ({
            index: shownScene.elements.indexOf(e),
            name: e.n, cls: e.cls, line: e.line, file: e.file,
            from: e.l, to: e.l + e.d,
            effects: e.effects.map((fx) => ({ name: fx.n, line: fx.line, from: fx.l, to: fx.l + fx.d }))
        });
        const state = () => ({
            ok: true,
            file: source.path,
            caret: source.cursorLine + 1,
            modified: source.modified,
            playhead: playhead,
            duration: shownScene.duration,
            playing: playing,
            range: ranged ? { from: markIn, to: markOut } : null,
            selected: brief(selectedElement),
            run: {
                state: execState,
                stale: execStale,
                warnings: source.runFlaws.map((f) => ({ line: f.range.start.line + 1, message: f.message }))
            },
            markers: shownScene.markers.map((m) => ({ name: m.n, at: m.at, line: m.line })),
            sound: Shell.hasAudio ? "ready" : (Shell.audioWhy.length > 0 ? Shell.audioWhy : "none"),
            elements: shownScene.elements.length,
            // Said, so a screenshot's rectangles are not read as the scene's.
            guides: safeMargins,
            frame: { width: Shell.frameWidth, height: Shell.frameHeight }
        });

        switch (verb) {
        case "state":
            return state();
        case "brief":
            return { ok: true, text: agentBrief() };
        case "caret":
            // What the caret's line makes, and the moment ⌘⏎ would play from.
            return { ok: true, line: source.cursorLine + 1, makes: caretMakes.n, at: caretMakes.at, index: caretMakes.index };
        case "elements":
            return { ok: true, elements: shownScene.elements.map(brief) };
        case "seek": {
            let at = req.at;
            if (typeof at === "string") {
                const hit = shownScene.markers.find((m) => m.n === at);
                if (hit === undefined)
                    return { ok: false, error: "no marker named " + at + " — markers: " + shownScene.markers.map((m) => m.n).join(", ") };
                at = hit.at;
            }
            if (typeof at !== "number" || isNaN(at))
                return { ok: false, error: "seek wants at=<seconds> or at=<marker name>" };
            playing = false;
            seekTo(at);
            return { ok: true, playhead: playhead };
        }
        case "play":
            if (!playing)
                togglePlay();
            return { ok: true, playing: playing, playhead: playhead };
        case "pause":
            if (playing)
                togglePlay();
            return { ok: true, playing: playing, playhead: playhead };
        case "select": {
            let idx = -1;
            if (req.index !== undefined)
                idx = Number(req.index);
            else if (req.line !== undefined)
                idx = shownScene.elements.findIndex((e) => e.line === Number(req.line) && fromOpenFile(e.file));
            else if (req.name !== undefined)
                idx = shownScene.elements.findIndex((e) => e.n === req.name);
            if (idx < 0 || idx >= shownScene.elements.length)
                return { ok: false, error: "nothing to select — give index=, line= or name=" };
            selectedIndex = idx;
            return { ok: true, selected: brief(shownScene.elements[idx]) };
        }
        case "run":
            executeScene(true);
            return state();

        // ── verify ────────────────────────────────────────────────────────
        // Run the scene, and answer with everything needed to judge what it
        // made — the state AND a picture of it — in ONE reply.
        //
        // This is the verb the whole `tell` channel exists for. An agent that
        // writes a scene can already run it and read `state`, but "it ran" is
        // not "it is right": the warnings say what the engine noticed, the
        // markers say where the scene thinks its moments are, and only the
        // sheet says what it LOOKS like. Three calls the agent had to know to
        // chain, and would not; one call it cannot get wrong.
        //
        // The sheet samples the scene's own `timestamp()` moments when it named
        // any — the frames the author said were the ones that matter — and
        // falls back to an even spread when it named none.
        case "verify": {
            executeScene(true);
            const tiles = req.sheet !== undefined ? Math.max(2, Number(req.sheet)) : 8;
            const out = req.out ? String(req.out)
                                : "/tmp/videocode-verify-" + Date.now() + ".png";
            // The MIDDLE of each named section, not the instant the name sits on.
            //
            // A timestamp() marks where a section BEGINS, so the frame at that
            // exact instant is the last frame of the section before it: the tile
            // labelled "the camera" showed the bar chart that the camera section
            // was about to replace. Named moments are still what decides where
            // to look — they are the author saying which stretches matter — but
            // what a stretch LOOKS like is in the middle of it.
            //
            // The last one runs to the end of the scene, which is its section.
            const marks = shownScene.markers;
            let named = [];
            for (let i = 0; i < marks.length; ++i) {
                const ends = i + 1 < marks.length ? marks[i + 1].at : shownScene.duration;
                named.push(((marks[i].at + ends) / 2).toFixed(2));
            }

            let answer = state();
            const drawn = Shell.renderSheet(source.path, source.text, out, tiles,
                                            named.length > 1 ? named.join(",") : "");
            answer.sheet = drawn.ok === true ? out : null;
            if (drawn.ok !== true)
                answer.sheetError = drawn.error;
            answer.sheetAt = named.length > 1 ? named.map(Number) : [];
            return answer;
        }
        case "open":
            if (!req.file)
                return { ok: false, error: "open wants file=<scene.py>" };
            openScene(req.file);
            return state();
        case "reveal":
            revealLine(Number(req.line));
            return { ok: true, caret: source.cursorLine + 1 };
        case "show":
            showPanel(String(req.panel));
            return { ok: true };
        case "say":
            source.say(String(req.text));
            return { ok: true };
        case "export": {
            if (source.path.length === 0)
                return { ok: false, error: "nothing is open to export" };
            const out = req.out ? String(req.out) : source.path.replace(/\.py$/, "") + ".mp4";
            const first = req.from !== undefined ? Number(req.from) : (ranged ? markIn : -1);
            const last = req.to !== undefined ? Number(req.to) : (ranged ? markOut : -1);
            if (!Shell.startExport(source.path, source.text, out, first, last))
                return { ok: false, error: "an export is already running" };
            exporting.begin(out, first, last);
            return { ok: true, out: out };
        }
        default:
            return { ok: false, error: "unknown verb " + verb + " — state, brief, caret, elements, audio, mute, seek, play, pause, select, run, verify, open, reveal, show, say, export, key, click, panel, screenshot, quit" };
        }
    }

    // What an agent turn does to the buffer, and the two keys that settle it.
    //
    // The scene is NOT run when the turn lands. The author sees the colours,
    // and running it is what accepting MEANS — which is why ⌘R does both and
    // why nothing moves in the preview until they press it.
    Connections {
        target: Shell
        function onAudioChanged() {
            if (!Shell.hasAudio && Shell.audioWhy.length > 0)
                source.say(Shell.audioWhy);
        }
    }

    Connections {
        target: Agent

        function onChanged() {
            const rows = Agent.diff();
            // The merged view: what was there in red, what replaces it in green.
            // Briefly not valid Python, so the analyser is told to hold — a
            // buffer holding both sides of an edit would light up in errors that
            // describe nothing the author did.
            let merged = "";
            for (let i = 0; i < rows.length; i++)
                merged += (i > 0 ? "\n" : "") + rows[i].text;

            source.diffRows = rows;
            source.showAgentEdit(merged);
        }
    }

    // Take the turn: drop the old lines, keep the new ones, and run. The undo
    // stays armed — the reason to take an edit back is nearly always the
    // picture, and the picture is only there once it has run.
    function acceptAgentEdit() {
        const kept = Agent.accepted();
        Agent.accept();
        source.diffRows = [];
        source.showAgentEdit(kept);
        app.executeScene(true);
    }

    // Drop it, whether or not it was taken. Nothing is run: the file goes back
    // to what it was, and what was on screen was already that.
    function undoAgentEdit() {
        if (!Agent.revertable())
            return false;
        const back = Shell.readTextFile(source.path);
        Agent.revert();
        source.diffRows = [];
        source.showAgentEdit(Shell.readTextFile(source.path));
        if (app.execState !== "none")
            app.executeScene(false);
        return true;
    }

    // ── What answers a key, and when ──────────────────────────────────────
    // Two questions, and both have to be asked of every shortcut in the window.
    //
    // The first is old: a text editor owns Space and the arrows, so while the
    // caret is in the code pane the transport does not get them.
    //
    // The second is the keyboard board. It is a surface you go to in order to
    // PRESS keys and be told what they do, so every key struck there has to
    // stop there — otherwise Space plays the scene behind it, I marks in, and
    // the board describes a keyboard while a timeline you cannot see obeys it.
    // A `Shortcut` is answered by the window, not by whoever holds the focus,
    // so nothing short of standing them down does it.
    function keyFree(id) {
        return !shortcuts.visible && (!source.typing || Keymap.survivesTyping(id));
    }

    Shortcut {
        sequence: Keymap.sequence("execute")
        enabled: !shortcuts.visible
        onActivated: {
            if (Agent.pending)
                app.acceptAgentEdit();
            else
                app.executeScene(true);
        }
    }

    // ⌘F reaches the buffer from anywhere in the window: the pane answers it
    // itself while the caret is in it (a TextEdit claims the key through
    // ShortcutOverride before a Shortcut ever fires), and this is the same key
    // working from the timeline or the picture.
    Shortcut {
        sequence: Keymap.sequence("find")
        enabled: !shortcuts.visible && !source.typing
        onActivated: {
            app.showPanel("code");
            source.openFind();
        }
    }

    // ⌘H is ⌘F with the second line showing: the same band, the same walk
    // through the matches, plus what goes in their place.
    Shortcut {
        sequence: Keymap.sequence("replace")
        enabled: !shortcuts.visible && !source.typing
        onActivated: {
            app.showPanel("code");
            source.openReplace();
        }
    }

    // ⌘⏎ from anywhere, the way ⌘F is: the pane answers it while the caret is in
    // it, and this is the same key once focus is elsewhere — the agent's field
    // after a turn, where it did nothing at all.
    Shortcut {
        id: playKey
        sequence: Keymap.sequence("playFromCaret")
        enabled: !shortcuts.visible && !source.typing
        onActivated: app.playFromCaret()
    }

    // Refaire, monter, descendre, effacer un mot : le volet de code les prend
    // lui-même, dans son `Keys.onPressed`. Un `Shortcut` ici ne tirerait jamais
    // — un TextEdit qui a le curseur réclame la touche avant lui — et ⌘↑ est
    // le début du document pour macOS tant que personne ne la lui prend.

    // F5 : les deux choses que F5 veut dire ailleurs, ensemble. La scène est
    // rejouée d'abord — sans ça on lit une timeline qui décrit le texte d'avant
    // — puis la lecture part de ce que cette ligne fabrique.
    Shortcut {
        sequence: Keymap.sequence("runFrom")
        enabled: !shortcuts.visible
        onActivated: {
            app.executeScene();
            app.playFromCaret();
        }
    }

    // ⌘Z is the editor's own undo, except while an agent turn is still the last
    // thing that happened — then it takes the WHOLE turn back in one press,
    // which is the unit the turn was asked for in. `Agent.disarm()` hands the
    // key back the moment the author types anything of their own.
    Shortcut {
        // `sequences`, not `sequence`: undo is spelled more than one way on this
        // platform, and binding the single form takes only the first of them.
        sequences: [StandardKey.Undo]
        enabled: Agent.revertable && !shortcuts.visible
        onActivated: app.undoAgentEdit()
    }
    // ⌘Z from any other pane undoes the code: whatever wrote the file — the
    // Inspector, a gesture on the timeline, a rename — went through the
    // document, so the editor's stack holds it. A field being typed in keeps
    // its own undo. With the caret in the editor, the editor already answers.
    Shortcut {
        sequences: [StandardKey.Undo]
        enabled: !Agent.revertable && !shortcuts.visible && !source.editorHasFocus
        onActivated: {
            const it = activeFocusItem;
            if (it && typeof it.undo === "function" && it.canUndo)
                it.undo();
            else
                source.undo();
        }
    }
    // Redo the same way, on the key the board lists as well as the system's
    // own ⇧⌘Z: ⌘Y only answered with the caret in the code.
    Shortcut {
        sequences: [StandardKey.Redo, Keymap.sequence("redo")]
        enabled: !shortcuts.visible && !source.editorHasFocus
        onActivated: {
            const it = activeFocusItem;
            if (it && typeof it.redo === "function" && it.canRedo)
                it.redo();
            else
                source.redo();
        }
    }

    // Play, pause, or start over.
    //
    // The playhead parks at the end when a scene finishes, so the next Space
    // asked the clock to advance past the end and it stopped again on the same
    // frame: play appeared to do nothing at all. Pressing play on a finished
    // scene means "again" — every player on this machine agrees — so it rewinds
    // first. Pausing mid-scene still leaves the playhead where you stopped it.
    function togglePlay() {
        if (!playing) {
            // Where "again" starts. With a range set that is its in point, and
            // pressing play anywhere outside the range means you want the range
            // — you marked it a moment ago for exactly this.
            const from = ranged ? markIn : 0;
            const until = ranged ? markOut : shownScene.duration;
            // One frame of slack, because the last FRAME sits at `until - 1/fps`
            // and not at `until`. Testing against `until` alone left a playhead
            // parked on the last frame looking unfinished: play advanced one
            // tick, hit the end, and stopped again on the frame it started on.
            const spent = until - 1 / execFps + 1e-6;
            // `seekTo`, pas une affectation : le haut-parleur doit repartir de
            // là aussi. Posé à la main, le son restait garé à la fin, et le
            // premier battement d'horloge lisait SA position — celle de la fin —
            // et arrêtait la lecture sur l'image d'où elle venait de partir.
            if (playhead >= spent || playhead < from - 1e-6)
                seekTo(from);
        }
        playing = !playing;
    }

    // Playback advances the playhead one frame per tick, and the preview
    // renders whatever frame it lands on. A frame clock rather than a wall
    // clock: rendering happens on demand on this thread, so chasing real time
    // would mean claiming a frame rate the pane is not delivering.
    //
    // Unless there is sound. Then the speaker is the clock and the picture
    // follows it, skipping frames if the pane is slow: a dropped frame is not
    // heard, a dropped sample is. `Math.max` because the cursor does not move
    // on the very tick `play` was called — without it the head fell back to
    // where the sound started.
    Timer {
        id: clock
        interval: Math.max(1, Math.round(1000 / app.execFps))
        repeat: true
        running: app.playing && app.shownScene.duration > 0
        onTriggered: {
            const heard = Shell.hasAudio ? Shell.audioPosition() - Shell.audioLatency : -1;
            // Le son mène TANT QU'IL AVANCE. Quand il est fini — un mix plus
            // court que le film, ce qui arrive dès qu'un clip s'arrête avant la
            // dernière image — sa position cesse de bouger, et `max(tête, son)`
            // rendait la tête elle-même : la lecture restait allumée sur place,
            // sans jamais atteindre la fin ni s'arrêter, et rejouer ne faisait
            // rien puisqu'on n'était jamais arrivé au bout.
            const next = heard > app.playhead ? heard : app.playhead + 1 / app.execFps;
            const until = app.ranged ? app.markOut : app.shownScene.duration;
            if (next >= until) {
                app.playhead = until;
                app.playing = false;
            } else {
                app.playhead = next;
            }
        }
    }

    Timer {
        id: colouring
        interval: 400
        onTriggered: if (source.path.length > 0) Lsp.semanticTokens(source.path)
    }

    // A rebinding is a setting, so it is written where every other setting is.
    Connections {
        target: Keymap
        function onChanged() { app.saveLayout(); }
    }

    DockDialog {
        id: confirmReset
        anchors.fill: parent
        z: 300
        title: "Reset " + app.templateLabel(app.template) + "?"
        // What it lands on, said out loud. "How it ships" and "the shape you
        // pinned with Update default" are very different answers, and the one
        // you get depends on something you may have done weeks ago — so the
        // dialog reads the answer rather than describing the rule.
        message: (app.defaults[app.template] !== undefined
                  ? "It goes back to the shape you pinned with Update default, and the changes you have made since are forgotten. "
                  : "You have never pinned a default for this one, so it goes back to how it SHIPS — not to the shape you have been working in. ")
                 + "Save it under a name first if you want it back later."
        extraLabel: "Save it first…"
        acceptLabel: "Reset"
        destructive: true
        onAccepted: app.resetLayout()
        onExtraChosen: saveDisplay.ask()
    }

    DockDialog {
        id: saveDisplay
        anchors.fill: parent
        z: 300
        title: "Save this display"
        message: "It joins Load display, and comes back exactly as it is now — "
                 + "panes, sizes, floating windows and all."
        asksName: true
        placeholder: app.templateLabel(app.template) + " (mine)"
        acceptLabel: "Save"
        onAccepted: (name) => app.saveDisplay(name)
    }

    DockMenu {
        id: menu
        anchors.fill: parent
        z: 100
        onChosen: (entry) => app.runMenu(entry)
    }

    // ── Panels torn out of the dock ───────────────────────────────────────
    // A Repeater only makes Items and a window is not one, so the floating
    // panels are instantiated rather than repeated.
    Instantiator {
        model: app.floats

        delegate: Window {
            id: floater
            required property var modelData

            width: floater.modelData.w
            height: floater.modelData.h
            x: floater.modelData.x
            y: floater.modelData.y
            visible: true
            color: Theme.ground
            title: app.panelTitles[floater.modelData.keys[floater.modelData.current]] + " — video-code"

            Panel {
                anchors.fill: parent
                anchors.margins: Theme.gap
                slotId: floater.modelData.id
                keys: floater.modelData.keys
                current: floater.modelData.current
                titles: app.panelTitles
                items: app.panelItems
                dropZone: app.hoverSlot === floater.modelData.id ? app.hoverZone : ""

                onFloatRequested: {} // already a window of its own
                onTabPicked: (index) => app.pickTab(floater.modelData.id, index)
                onTabClosed: (key) => app.closeTab(floater.modelData.id, key)
                onMenuRequested: (x, y) => app.openMenu(floater.modelData.id, x, y)
                onTabDragMoved: (x, y) => app.dragOver(floater.modelData.id, x, y)
                onTabDropped: (key, x, y) => app.drop(floater.modelData.id, key, x, y)
            }

            // Closing the window puts the panel away, exactly as closing its tab
            // would: one panel, one meaning for "close".
            onClosing: {
                const keys = floater.modelData.keys.slice();
                for (let i = 0; i < keys.length; i++)
                    app.closeTab(floater.modelData.id, keys[i]);
            }
        }
    }

    // ── The panels themselves, created once and reparented by the slots ────
    // Keeping them out of the dock's own tree is what makes moving one free: the
    // buffer, the selection and the scroll positions all survive the trip.
    PreviewPanel {
        id: preview
        visible: false
        playhead: app.playhead
        playing: app.playing
        framerate: app.execFps
        revision: app.execRevision
        ready: app.execRevision > 0
        onTogglePlay: app.togglePlay()
        onSeek: (seconds) => app.seekTo(seconds)
        // The frame the scene is made in, so a 1080x1920 one is letterboxed as
        // one rather than drawn into a 16:9 box.
        frameWidth: Shell.frameWidth
        frameHeight: Shell.frameHeight
        guides: app.safeMargins
        onToggleGuides: app.toggleSafeMargins()
    }

    TimelinePanel {
        id: timeline
        visible: false
        scene: app.shownScene
        litIndex: app.caretMakes.index
        // Which bar is out of its lane, so the lane can be drawn hollow for
        // exactly as long as the flight and the card last.
        openedName: elementCard.element !== null && elementCard.element.n !== undefined
                    ? elementCard.element.n : ""
        onElementOpened: (element, where) => elementCard.open(element, where)
        onElementInspected: (element) => app.inspect(element)
        onRenameRequested: (element) => app.renameElement(element)
        // Scrubbing stops playback: the two are the same control, and a playhead
        // that keeps running away from where you put it is not a scrub.
        // A gap edited on the timeline is one number rewritten in the file: the
        // wait carries the line it was written on, and `wait(0.3)` writes its
        // seconds without a name, so the span comes from the positional writer.
        onTrimmed: (element, edge, seconds, push) => app.gesture(element, edge, seconds, push)
        onShifted: (element, seconds, push) => app.gesture(element, "body", seconds, push)
        roomFor: (element, edge) => app.roomAfter(element, edge)
        onAimChanged: app.aimCode(timeline.aim)
        onWaitChanged: (line, seconds) => app.writeWait(line, parseFloat(seconds))
        onWaitDragged: (line, seconds) => app.dragWait(line, seconds)

        onScrubbed: (seconds) => {
            app.playing = false;
            app.seekTo(seconds);
        }
        selectedIndex: app.selectedIndex
        playhead: app.playhead
        markIn: app.markIn
        markOut: app.markOut
        snapPoints: app.snapPoints
        onElementPicked: (index) => app.selectedIndex = index
        onLanesOrderChanged: Qt.callLater(app.holdSelection)
    }

    // The clip you clicked, as rows in the dock — the Inspector of Palmier Pro
    // and Final Cut: what it is, what its line says, what it is worth now.
    InspectorPanel {
        id: inspector
        visible: false
        playhead: app.playhead
        buffer: source.text
        baseDir: source.path.length > 0 ? source.path.substring(0, source.path.lastIndexOf("/")) : ""
        onArgumentWritten: (element, call, name, value) => app.fromInspector(() => app.writeArgument(element, call, name, value))
        onMetadataAdded: (element, write) => app.fromInspector(() => app.addMetadata(element, write))
        onMetadataWritten: (element, call, name, at, value) => app.fromInspector(() => app.writeMetadata(element, call, name, at, value))
        onKeyed: (element, key, value, frame) => app.fromInspector(() => app.keyAt(element, key, value, frame))
        onJumpRequested: (element) => app.revealLine(element.line)
        onRenamed: (element, name) => app.fromInspector(() => app.renameElement(element, name))
        onSays: (sentence) => source.say(sentence)
    }

    // An edit asked for in the Inspector answers in the Inspector. Every
    // refusal on the way — a name kept, a line of another file, the constant
    // offered instead — is said by the code pane, and with the Inspector in
    // front that pane is behind a tab: the field closed, nothing changed, and
    // nothing said why. What the pane says during the edit is said here too.
    property bool inspectorAsking: false
    function fromInspector(write) {
        app.inspectorAsking = true;
        try {
            write();
        } finally {
            app.inspectorAsking = false;
        }
    }
    Connections {
        target: source
        function onSpoke(what, act) {
            if (app.inspectorAsking)
                inspector.tell(what, act);
        }
    }

    // One click on a clip fills the Inspector and brings its tab forward —
    // beside the Agent when the layout has never held one.
    function inspect(element) {
        inspector.open(element, Qt.rect(0, 0, 0, 0));
        if (slotHolding("inspector") === -1) {
            const stage = slotHolding("preview");
            if (stage === -1) {
                openPanel("inspector", slotHolding("agent"));
            } else {
                // Beside the preview, five sevenths as wide: the proportion
                // asked for on 16 Sept.
                dockTab("inspector", stage, "right");
                const next = copy(tree);
                const hit = findNode(next, slotHolding("inspector"));
                if (hit && hit.parent && hit.parent.nodes.length === 2) {
                    hit.parent.nodes[1 - hit.index].size = 7 / 12;
                    hit.node.size = 5 / 12;
                    settle(next);
                }
            }
        }
        showPanel("inspector");
    }

    AgentPanel {
        id: agent
        visible: false
        onSent: (text) => Agent.ask(app.agentBrief() + text)
        // Until the turn is taken the buffer shows both sides, so the line to
        // go to is the one in that view.
        onRevealed: (line, column, shown) => source.jump(source.path, (source.diffRows.length > 0 ? shown : line) - 1, column - 1)
    }

    // The scene, edited here and understood by a language server of our own.
    //
    // This pane used to host the real VS Code, over `code serve-web` in a
    // WKWebView. It worked, and it cost 9 % CPU at rest for intelligence that
    // is not VS Code's to begin with: definitions, hovers, signatures,
    // completion, diagnostics, references and rename all come from LSP, which
    // pyright speaks standing alone. What was lost with it — the extension
    // marketplace — was never what this pane was for. See docs/ui/CODE-PANE.md.
    SourcePanel {
        id: source
        visible: false
        name: "scene"
        onDocumentReady: (document, signature) => Shell.highlightPython(document, Theme.code, signature)
        onExecuteRequested: app.executeScene(true)
        onPlayFromCaret: app.playFromCaret()

        onSaveRequested: {
            if (source.path.length === 0)
                return;
            if (source.readOnly) {
                source.say("read-only — outside the project");
                return;
            }
            if (!Shell.writeTextFile(source.path, source.text)) {
                source.say("could not write " + source.name);
                return;
            }
            source.modified = false;

            // Saving IS an execute, like opening one.
            //
            // ⌘R exists because the timeline must not flicker under your typing:
            // between two keystrokes a scene is half-written, and running it
            // thirty times a second would be thirty answers to a question you
            // have not finished asking. A save is the opposite — it is you saying
            // the edit is done — and a preview still showing what the file no
            // longer says is the one lie a preview must not tell.
            //
            // Nothing is rendered here that would not be rendered anyway: the
            // scene is re-run (single-digit milliseconds) and the pane redraws
            // the one frame the playhead is on.
            app.executeScene();
            source.say(app.execState === "fresh"
                       ? "saved · ran in " + app.execMs.toFixed(0) + " ms"
                       : "saved");
        }
        // Compared against what was last SENT, not merely non-empty: repainting
        // the buffer changes its formats, Qt reports that as a text change, and
        // taking it at face value made the pane tell the server about an edit
        // that had not happened — which came back as new tokens, which repainted
        // the buffer, for ever.
        // The spans belong to the file that just left. The highlighter keeps
        // them until told otherwise, and it holds LINE and COLUMN — so they
        // land on whatever text is now at those coordinates: opening eg.py
        // after scene.py painted `ocode ` teal, because scene.py had a class
        // at line 4 column 9. Cleared here, and asked for again.
        onOpened: (where, body) => {
            app.sentText = body;
            if (source.document !== null)
                Shell.applySemanticTokens(source.document, []);
            colouring.restart();
        }

        onTextChanged: {
            if (source.loading || source.path.length === 0 || source.text === app.sentText)
                return;
            app.sentText = source.text;
            // The server is told at once — completion, hovers and signatures all
            // answer about the text as it is now, and a stale document would
            // make them lie. What waits is the REPORTING of what it finds on the
            // line under your hands; see SourcePanel.shownDiagnostics.
            Lsp.changeDocument(source.path, source.text);
            source.noteEdit();
            colouring.restart();
        }
    }

    LibraryPanel {
        id: library
        visible: false
        catalogue: app.placeable
        onCarrying: (template, values, x, y) => app.carryTemplate(template, values, x, y)
        onDropped: (template, values, x, y) => app.dropTemplate(template, values, x, y)
        onReleased: app.carried = null
    }

    MediaPanel {
        id: media
        visible: false
        sceneAssets: app.sceneAssets
        scene: app.shownScene
        added: app.addedAssets
        display: app.mediaDisplay
        onAddRequested: app.addMedia()
        onAssetCarried: (asset, x, y) => app.carryAsset(asset, x, y)
        onAssetDropped: (asset, x, y) => app.dropAsset(asset, x, y)
        onCarryCancelled: app.carried = null
    }

    // ── Keys ──────────────────────────────────────────────────────────────
    // The transport keys the preview window already answers to, kept identical
    // so the two windows are not two different applications.
    // Read from Keymap rather than spelled here, so they appear on the keyboard
    // board and can be rebound like everything else. They were the one set of
    // keys the board could not see — which made its claim to be the whole truth
    // false by exactly five lines.
    // ── Transport, and the caret ──────────────────────────────────────────
    // All five are keys a text editor already owns. While the caret is in the
    // code pane they stay the editor's — Space writes a space, the arrows move
    // the caret — and the transport gets them back the moment you click on the
    // picture or the timeline.
    //
    // The alternative was a Shortcut that wins over the pane, and it is worse
    // than it sounds: `TextEdit` claims the key through ShortcutOverride, so the
    // shortcut never fires AND the space still lands in the buffer. Nothing
    // played, and the scene quietly went stale.
    Shortcut {
        sequence: Keymap.sequence("play")
        enabled: app.keyFree("play")
        onActivated: app.togglePlay()
    }
    Shortcut {
        sequence: Keymap.sequence("toStart")
        enabled: app.keyFree("toStart")
        onActivated: app.seekTo(0)
    }
    Shortcut {
        sequence: Keymap.sequence("toEnd")
        enabled: app.keyFree("toEnd")
        onActivated: app.seekTo(app.shownScene.duration)
    }
    Shortcut {
        sequence: Keymap.sequence("prevFrame")
        enabled: app.keyFree("prevFrame")
        onActivated: app.seekTo(app.playhead - 1 / preview.framerate)
    }
    Shortcut {
        sequence: Keymap.sequence("nextFrame")
        enabled: app.keyFree("nextFrame")
        onActivated: app.seekTo(app.playhead + 1 / preview.framerate)
    }
    Shortcut {
        sequence: Keymap.sequence("prevMarker")
        enabled: app.keyFree("prevMarker")
        onActivated: app.jumpToMarker(-1)
    }
    Shortcut {
        sequence: Keymap.sequence("nextMarker")
        enabled: app.keyFree("nextMarker")
        onActivated: app.jumpToMarker(1)
    }
    // The range. `I` and `O` are the two keys every editor on this machine
    // spells the same way, and the third gives the whole scene back.
    Shortcut {
        sequence: Keymap.sequence("markIn")
        enabled: app.keyFree("markIn")
        onActivated: app.setMarkIn()
    }
    Shortcut {
        sequence: Keymap.sequence("markOut")
        enabled: app.keyFree("markOut")
        onActivated: app.setMarkOut()
    }
    Shortcut {
        sequence: Keymap.sequence("clearMarks")
        enabled: app.keyFree("clearMarks")
        onActivated: app.clearMarks()
    }
    // ⇧Z: the whole scene in the pane, 100 % — Premiere's and Final Cut's key.
    Shortcut {
        sequence: Keymap.sequence("zoomFit")
        enabled: app.keyFree("zoomFit")
        onActivated: timeline.zoomToFit()
    }
    // ': Premiere's key for the Program Monitor's safe margins.
    Shortcut {
        sequence: Keymap.sequence("safeMargins")
        enabled: app.keyFree("safeMargins")
        onActivated: app.toggleSafeMargins()
    }
    Shortcut {
        sequence: "Escape"
        onActivated: {
            // Escape puts away what is on top before it touches the selection.
            if (confirmReset.visible)
                confirmReset.close();
            else if (saveDisplay.visible)
                saveDisplay.close();
            else if (menu.visible)
                menu.visible = false;
            // The overlays, before anything under them. Each one answers Escape
            // itself through `Keys.onEscapePressed`, which is enough until
            // something inside it takes the keyboard: the moment a hex field in
            // Colors is clicked, the panel's root no longer has focus and the
            // key never reaches it. This shortcut sees it whatever holds focus.
            //
            // It has to live in THIS ladder and not in a shortcut of its own:
            // two Shortcuts on one sequence in one window are an ambiguous
            // overload, and Qt fires neither.
            else if (exporting.visible)
                exporting.stop();
            else if (colors.visible)
                colors.visible = false;
            // La planche pendant qu'elle attend une touche : Escape annule
            // l'attente, pas la planche. C'est ce que son en-tête promet — « esc
            // to cancel » — et cette échelle-ci la fermait par-dessus, parce
            // qu'un raccourci de la coquille voit la touche avant le panneau.
            else if (shortcuts.visible && shortcuts.capturing.length > 0)
                shortcuts.stopCapturing();
            else if (shortcuts.visible)
                shortcuts.visible = false;
            else if (settings.visible)
                settings.visible = false;
            else if (app.measuring)
                app.measuring = false;
            else if (elementCard.element !== null)
                // The card answers Escape itself while it holds the keyboard —
                // its own ladder has more rungs than this one. But typing in a
                // parameter field leaves the focus inside the card and this
                // shortcut wins, and Escape has to mean the same thing either
                // way: put away what is on top.
                elementCard.dismiss();
            else
                app.selectedIndex = -1;
        }
    }
}
