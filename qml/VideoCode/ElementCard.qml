// One element of the scene, opened.
//
// The CLIP travels — not a card shaped like it.
//
// The bar you clicked leaves its lane, grows, and comes to rest in the middle of
// the window; the card is built around it once it lands. That distinction is the
// whole point: a panel that merely starts at the clip's rectangle is a second
// object appearing over a first one that never moved, and the eye has two things
// to reconcile. Here there is one thing, and it went somewhere. Its lane stays
// exactly as it was, with a hollow where the bar used to be, so the timeline
// does not reflow and you can see where it will go back.
//
// What is inside a clip does not belong on the timeline. Rows that grow push
// everything below them down, and a map whose geometry changes when you look at
// something has stopped being a map. So the effects live here, under the clip
// they belong to, drawn against the CLIP's own length rather than the scene's:
// at timeline scale a two-second clip is a sliver and a 0.4 s fade is a sliver
// of a sliver, while here that fade is a fifth of what you are looking at.
//
// The ruler under the block is what makes the spans mean anything — without it
// they are proportions of nothing — and the same half-second and whole-second
// lines carry down through the effect rows, so a bar is read AGAINST the ruler
// instead of near it.
//
// A row made of several inputs from one line — `Text("GRADIENT")` is one per
// glyph — opens into its members instead, and each member opens into its own
// card. Same gesture, same question: what is really in there.
pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls

Item {
    id: root
    anchors.fill: parent
    visible: element !== null

    property var element: null
    // In the dock rather than over the window: no journey, no backdrop, no
    // effects timeline — what it is, what its line says, what it is worth now.
    property bool docked: false
    property var effectNames: []

    // Where the clip is on screen, so the card can start from it.
    property rect from: Qt.rect(0, 0, 0, 0)

    // The scene's text, so the card can read what the line actually says. Bound
    // rather than fetched: a gesture rewrites the buffer and every field on the
    // card has to agree with it on the next frame.
    property string buffer: ""

    signal closed()
    // One value, on the call that made this element. The shell writes it and
    // re-runs the scene; the card never edits the buffer itself.
    signal argumentWritten(var element, string call, string name, string value)
    signal jumpRequested(var element)
    signal renameRequested(var element)
    signal effectRequested(var element, var effect, var options)
    signal memberOpened(var member, rect where)
    // An applied effect, acted on through the call that wrote it.
    signal effectRemoved(var fx)
    signal effectWritten(var fx, string name, string value)
    signal effectJumped(var fx)
    // L'argument qu'on est en train de taper, et où sa pastille commence : la
    // fiche du type se pose sous elle, hors de la rangée qui défile — dedans,
    // elle partirait avec le défilement et ne serait pas cliquable (le + l'a
    // appris pour tout le monde).
    property var editing: null
    property real editingAt: 0

    // Ce que ce type accepte, quand la bibliothèque le ferme.
    readonly property var editingValues: {
        if (root.editing === null || root.editing.kind === undefined)
            return [];
        if (typeof Shell.enumValues !== "function")
            return [];
        return Shell.enumValues(root.editing.kind);
    }

    // Les couleurs du code, exactement — les mêmes règles que PythonHighlighter,
    // dans le même ordre (la dernière qui s'applique gagne) :
    //
    //   `"marius.mov"`         string        `None` `True` `False`  constant
    //   `6` `0.5`              number        `UVMapping` `Video`    type
    //   `TRANSPARENT` `BLUE_C` caps          `[]` et le reste       rien — l'encre
    //
    // Lu sur la VALEUR affichée et non sur le type déclaré : `endFrame` est
    // annoncé `maybe[frame]`, mais ce que la ligne dit est `None`, et `None` est
    // bleu dans l'éditeur. Une pastille qui l'aurait peint en vert de nombre
    // aurait dit autre chose que le code juste au-dessus.
    function valueHue(text) {
        const t = String(text).trim();
        const tokens = Theme.code;
        let hue = tokens.variable;
        if (/^_*[A-Z][A-Z0-9_]+$/.test(t))
            hue = tokens.caps;
        if (/^[A-Z][A-Za-z0-9_]*[a-z][A-Za-z0-9_]*(\.[A-Za-z_]\w*)*$/.test(t))
            hue = tokens.type;
        if (/^-?(0[xX][0-9a-fA-F]+|\d+\.?\d*([eE][+-]?\d+)?)$/.test(t))
            hue = tokens.number;
        if (/^(True|False|None)$/.test(t))
            hue = tokens.constant;
        if (/^(["']).*\1$/.test(t))
            hue = tokens.string;
        return hue;
    }

    // `UVMapping.STRETCH` s'affiche `STRETCH`, et s'écrit toujours en entier.
    //
    // Sur une pastille qui s'appelle déjà `uvMapping` et porte la teinte d'un
    // type, le préfixe ne disait rien et prenait la moitié de la place. Mais le
    // fichier est du Python, et `uvMapping=STRETCH` est un NameError : ce qu'on
    // tape, court ou long, est rallongé avant d'être écrit.
    function closedValues(param) {
        if (param === undefined || param.kind === undefined || typeof Shell.enumValues !== "function")
            return [];
        return Shell.enumValues(param.kind);
    }

    function shortValue(param, text) {
        const full = String(text).trim();
        if (root.closedValues(param).indexOf(full) < 0)
            return full;
        return full.substring(full.lastIndexOf(".") + 1);
    }

    function fullValue(param, text) {
        const typed = String(text).trim();
        for (const one of root.closedValues(param))
            if (one === typed || one.substring(one.lastIndexOf(".") + 1) === typed)
                return one;
        return typed;
    }

    // Est-ce que ce qui a été tapé EST une valeur pour cet argument.
    //
    // Strict là où la bibliothèque ferme le type : `uvMapping` accepte trois
    // mots et rien d'autre, et une faute de frappe y est une faute, pas une
    // idée. Ailleurs, non : `width` accepte `6` comme `1 * RATIO` comme
    // `carre.width`, et un champ qui refuserait les deux derniers refuserait le
    // langage. Ce qui ne va pas là, la ligne le dira — c'est son métier.
    function fits(param, value) {
        if (value.length === 0)
            return false;
        if (param === undefined || param.kind === undefined)
            return true;
        if (typeof Shell.enumValues !== "function")
            return true;
        const closed = Shell.enumValues(param.kind);
        return closed.length === 0 || closed.indexOf(root.fullValue(param, value)) >= 0;
    }

    // Le nom d'un effet que le moteur ne nomme pas. `.apply(popIn(...))` n'écrit
    // aucun nom d'appel dans le modèle — l'effet est un objet passé à `apply`,
    // pas un verbe sur l'élément — et la rangée n'avait donc qu'une durée à
    // montrer. La ligne, elle, le nomme : c'est le dernier appel qui n'est ni la
    // plomberie (`apply`) ni l'élément lui-même.
    function effectName(fx) {
        if (fx.n !== undefined && fx.n.length > 0)
            return fx.n;
        if (root.element === null || fx.line === undefined || fx.line <= 0)
            return "";
        const calls = Shell.callsOnLine(root.buffer, fx.line);
        for (let i = calls.length - 1; i >= 0; i--)
            if (calls[i] !== "apply" && calls[i] !== root.cls && calls[i] !== root.element.n)
                return calls[i];
        return calls.length > 0 ? calls[calls.length - 1] : "";
    }

    // Un réglage de plus sur la ligne de l'élément — `.opacity(255)` posé au
    // bout de la chaîne, à sa valeur d'usine, prêt à être tapé par-dessus.
    signal metadataAdded(var element, string write)
    signal metadataWritten(var element, string call, string name, int at, string value)

    // Off: the line is commented out rather than deleted. The card stops
    // showing it at that point — what is commented is not in the scene, and
    // the place to read it, or bring it back, is the code.
    signal effectToggled(int line, bool off, string file)
    // A gesture that cannot be made, in words. The card has no status line of
    // its own; the pane does, and a refusal nobody hears looks exactly like a
    // gesture that failed.
    signal says(string sentence)

    readonly property var members: element !== null && element.members !== undefined
                                   ? element.members : []
    readonly property var effects: element !== null && element.effects !== undefined
                                   ? element.effects : []
    // Read top-down as a timeline: the effect that starts first is the one at
    // the top. Ties on the start go to the SHORTER one, which puts an instant
    // `opacity` above the `fadeIn` that begins alongside it — the short bar
    // would otherwise be buried under a long one it does not belong inside.
    //
    // `slice()` because `sort` works in place and `effects` is a binding.
    readonly property var rows: {
        if (members.length > 0)
            return members;
        // Ce qui dure zéro image à l'ouverture n'est pas un effet : c'est la
        // valeur de départ, et elle se lit dans `default:` au-dessus. Elles
        // prenaient quatre rangées pour dire ce qu'une pastille dit — dont une
        // sans nom du tout, le `Hide` que le moteur écrit lui-même quand un
        // élément naît invisible, et que personne n'a jamais demandé à voir.
        const played = effects.filter(function (fx) {
            return !(fx.d <= root.oneFrame + 1e-6 && fx.l <= root.origin + 1e-6);
        }).sort(function (a, b) {
            return a.l !== b.l ? a.l - b.l : a.d - b.d;
        });
        return played;
    }

    // The clip's own extent, which is what the bars below are measured against.
    readonly property real span: element !== null && element.d > 0 ? element.d : 1

    // Où la tête de lecture est, pour que la carte puisse dire ce que l'élément
    // vaut LÀ. Les pastilles du dessus disent avec quoi il a été fabriqué ; ça,
    // c'est où il en est.
    property real playhead: 0

    // Les huit canaux, relus à l'image du curseur. Une carte ouverte sur une
    // scène qui n'a pas tourné en rend zéro, et la ligne disparaît.
    readonly property var meta: {
        if (root.element === null || root.element.index === undefined)
            return ({});
        // Le QML se relit du disque, le C++ non : une chrome plus récente que le
        // binaire qui la charge est l'état NORMAL entre deux compilations, et
        // une carte qui casse là-dessus emporte le clic qui l'ouvre. La ligne
        // disparaît, le reste de la fiche vit.
        if (typeof Shell.stateAt !== "function")
            return ({});
        return Shell.stateAt(root.element.index, Math.round(root.playhead * 30));
    }

    // Ce qui se lit, dans l'ordre où on le cherche, et seulement ce que la scène
    // a vraiment revendiqué : afficher « rotation 0 » sur un carré que personne
    // n'a tourné, c'est huit pastilles dont sept ne disent rien.
    readonly property var metaShown: {
        const order = [
            ["x", "Position:x"], ["y", "Position:y"],
            ["scaleX", "Scale:x"], ["scaleY", "Scale:y"],
            ["rotation", "Rotation"], ["opacity", "Opacity"],
            ["alignX", "Align:x"], ["alignY", "Align:y"]
        ];
        let out = [];
        for (const [label, key] of order)
            if (root.meta[key] !== undefined)
                out.push({ n: label, v: root.meta[key] });
        return out;
    }

    // Ce que l'élément vaut À SA PREMIÈRE IMAGE, et seulement là où ça diffère
    // du réglage d'usine. `position(x=0, y=0)` sur un élément qui est déjà à
    // zéro ne dit rien à personne ; `opacity 0` sur un élément qui va apparaître
    // dit tout de la ligne qui l'a écrit.
    //
    // Ça remplace les rangées de durée nulle — `position 0.0s`, `opacity 0.0s` —
    // qui prenaient chacune une ligne de timeline pour un instant qui ne dure
    // pas : une valeur n'est pas une animation, et se lit comme une valeur.
    // Un instant, pas une animation : une image ou moins, à l'ouverture de
    // l'élément. `.opacity(0)`, `.position(x=0, y=0)`, le `show` qui suit — le
    // moteur les porte comme des effets parce que tout est effet ici, mais ce
    // qu'ils disent est une VALEUR, et une valeur n'a pas de durée à montrer.
    readonly property real oneFrame: 1 / 30

    readonly property var instants: {
        return root.effects.filter(function (fx) {
            return fx.d <= root.oneFrame + 1e-6 && fx.l <= root.origin + 1e-6;
        });
    }

    function argOf(call, name) {
        if (root.element === null || !writable)
            return "";
        return Shell.readArgument(root.buffer, root.element.line, call, name);
    }

    function positionalOf(call, index) {
        if (root.element === null || !writable)
            return "";
        return Shell.readPositional(root.buffer, root.element.line, call, index);
    }

    // Ce que ces instants ÉCRIVENT, lu sur la ligne. Un `show` n'a pas
    // d'argument et n'en montre pas ; un `hide` que personne n'a tapé — celui
    // que le moteur pose lui-même sur un élément né invisible — n'a pas de nom
    // d'appel, et ne se montre pas non plus : il n'y a rien à y changer.
    readonly property var startShown: {
        let out = [];
        for (const fx of root.instants) {
            const call = fx.call !== undefined && fx.call.length > 0 ? fx.call : "";
            if (call.length === 0)
                continue;
            // Les champs sont ceux de la signature du setter, typés par elle :
            // `position` donne x et y, `blendMode` sa liste fermée. `offset` et
            // `at` disent QUAND, pas quoi, et restent l'affaire de la ligne.
            // L'index est pris avant ce tri : c'est la place qu'occupe entre les
            // parenthèses une valeur écrite sans nom — `.opacity(0)`.
            const fields = Shell.inputParams(root.cls + "." + call).map(function (p, i) {
                const named = root.argOf(call, p.name);
                return { name: p.name, kind: p.kind, value: p.value, at: i,
                         current: named.length > 0 ? named : root.positionalOf(call, i) };
            }).filter(function (p) { return p.name !== "offset" && p.name !== "at"; });
            out.push({ n: call, fields: fields });
        }
        return out;
    }

    // Ce qu'on peut encore poser sur la ligne : les quatre verbes qui écrivent
    // une valeur plutôt qu'une animation, moins ceux qui y sont déjà.
    readonly property var addable: {
        if (root.element === null || !root.writable)
            return [];
        const calls = [
            { name: "position", write: "position(x=0, y=0)" },
            { name: "scale", write: "scale(1)" },
            { name: "opacity", write: "opacity(255)" },
            { name: "align", write: "align(x=0.5, y=0.5)" }
        ];
        const already = Shell.callsOnLine(root.buffer, root.element.line);
        return calls.filter((one) => already.indexOf(one.name) < 0);
    }

    // Une couleur en chemin, écrite comme la ligne au-dessus l'écrit.
    //
    // Le moteur la porte en quadruplet, ce qui est juste et illisible à côté de
    // `fillColor RED`. Une couleur à mi-parcours n'a pas de nom — c'est le
    // propre d'un fondu — donc elle prend la seule autre écriture qu'une scène
    // accepte, et l'alpha ne s'écrit que lorsqu'il compte.
    function readable(value) {
        const rgba = String(value).match(/^\((\d+), *(\d+), *(\d+)(?:, *(\d+))?\)$/);
        if (rgba === null)
            return String(value);
        const hex = (n) => ("0" + Number(n).toString(16)).slice(-2);
        return "#" + hex(rgba[1]) + hex(rgba[2]) + hex(rgba[3])
                   + (rgba[4] !== undefined && Number(rgba[4]) !== 255 ? hex(rgba[4]) : "");
    }

    // Les MÊMES arguments que la ligne du dessus, à l'image du curseur.
    //
    // La plupart ne bougent jamais : un `side` que personne n'anime vaut à
    // toute heure ce que la ligne dit. Ceux qu'un verbe anime, en revanche —
    // un `fill()` écrit `Args:fillColor` image par image — n'ont nulle part
    // ailleurs où se lire, et la ligne du dessus continue d'afficher la couleur
    // de départ pendant que la forme en a changé.
    //
    // Même ordre, même largeur de mots : les deux lignes se lisent en colonnes,
    // ce qui rend la différence visible sans avoir à comparer deux textes.
    readonly property var argsNow: {
        let out = [];
        for (const one of root.arguments) {
            const live = root.meta["Args:" + one.name];
            // Rien d'animé sur ce nom : sa valeur à cette image EST celle qui
            // est écrite. La rangée reste complète, et ce qui a bougé se repère
            // parce que c'est la seule chose qui diffère de la ligne au-dessus.
            // Écrit → animé → par défaut. Un argument absent de la ligne n'est
            // pas un argument sans valeur : il a celle de la signature, et une
            // pastille qui ne montre qu'un nom ne dit rien de ce que l'élément
            // vaut à cette image.
            const asWritten = root.written(one.name);
            out.push({
                n: one.name,
                v: live !== undefined ? root.readable(live)
                                      : (asWritten.length > 0 ? asWritten : one.value)
            });
        }
        return out;
    }
    readonly property real origin: element !== null ? element.l : 0

    readonly property string kind: element !== null && element.kind !== undefined
                                   ? element.kind : "video"
    readonly property color hue: Theme.kind[kind] !== undefined ? Theme.kind[kind] : Theme.inkDim
    // The host's complement, shared by everything that animates it: one hue for
    // the thing, one for what happens to it.
    readonly property color fxHue: Theme.fxKind[kind] !== undefined ? Theme.fxKind[kind] : Theme.live

    readonly property var kindLabel: ({
        "video": "Video", "sound": "Sound", "image": "Image",
        "subs": "Subtitles", "polygon": "Polygon"
    })

    // 0 = still in its lane, 1 = landed in the middle. Everything the flight
    // touches is derived from it, so there is one clock for the whole gesture
    // rather than four animations that can disagree about where the bar is.
    property real travel: 0

    Behavior on travel {
        NumberAnimation { duration: Theme.motion(220); easing.type: Easing.OutCubic }
    }

    function open(what, where) {
        // Clicking a second clip while the first is on its way home: the return
        // trip's timer is still armed and would clear the element under the card
        // that has just opened.
        landing.stop();

        element = what;
        from = where;
        library = false;
        curving = null;
        if (docked) {
            travel = 1;
            return;
        }
        travel = 0;
        // One frame at zero before it is told to go: setting both in the same
        // tick means no journey to animate.
        launch.start();
    }

    // A gesture rewrote the scene, and the card is a VIEW of it: the bars have
    // to become the ones that came back, not the ones the card opened with.
    // Matched by the element's index rather than by its place in the list — a
    // deleted effect can change the order of neither, but a deleted element can.
    function rebind(elements) {
        if (element === null || element.index === undefined)
            return;

        for (const one of elements) {
            if (one.index === element.index && one.n === element.n) {
                element = one;
                return;
            }
            for (const member of (one.members !== undefined ? one.members : [])) {
                if (member.index === element.index && member.n === element.n) {
                    element = member;
                    return;
                }
            }
        }

        // Its element is gone from the scene — deleted, or renamed into
        // something else. A card describing nothing is worse than no card.
        close();
    }

    function close() {
        if (docked)
            return;
        // And the other way round, for a card shut inside the frame it opened on.
        launch.stop();

        root.closed();
        curving = null;
        travel = 0;
        // The element is kept until the bar is home — it is what the lane's
        // hollow and the flying bar are both drawn from.
        landing.start();
    }

    Timer {
        id: launch
        interval: 16
        onTriggered: root.travel = 1
    }

    Timer {
        id: landing
        interval: Theme.motion(230)
        onTriggered: root.element = null
    }

    // The effects library, summoned with E. Not a permanent neighbour of the
    // card: it is called for, used, dismissed — so it spends no layout on being
    // absent.
    property bool library: false

    // ── Placing an effect: choose it, set it up, then aim it ──────────────
    // The three are one gesture and they happen in that order for a reason. An
    // effect's DURATION is what you are about to drop — a 0.4 s fade is a fifth
    // of a two-second clip, a whole third of a 1.2 s one — so the parameters are
    // set first and the bar you drag is the size it will be. Choosing the moment
    // before the length would mean aiming at something whose shape you cannot
    // see yet, and correcting it afterwards by hand.
    property var picked: null
    // name → what will be written for it. Seeded from the signature's own
    // defaults, so an untouched field writes nothing at all.
    property var values: ({})

    property bool dragging: false
    // Where the drop would land, in seconds from the start of the ELEMENT, and
    // whether it is snapped there or sitting exactly under the pointer.
    property real dropAt: 0
    property bool exact: false

    // The tenth of a second is the trim resolution everywhere else in this
    // window — the timeline's own ruler is drawn in tenths — so a drop lands on
    // one unless you say otherwise.
    readonly property real snap: 0.1

    function pick(effect) {
        const seeded = ({});
        for (const parameter of effect.params)
            seeded[parameter.name] = parameter.value;
        values = seeded;
        picked = effect;
        dropAt = 0;
    }

    function unpick() {
        picked = null;
        dragging = false;
        // Back from the fields: the card answers keys again, which is what makes
        // Escape and E work straight after setting an effect up.
        forceActiveFocus();
    }

    // How long the effect being placed will last, read off its own fields: the
    // one number that decides the width of what you are dragging.
    readonly property real pickedDuration: {
        if (picked === null)
            return 0;
        const written = values["duration"];
        const seconds = written === undefined ? NaN : parseFloat(written);
        // No `duration` in the signature, or a value that is not a number yet
        // while it is being typed: a single frame, which is what an effect with
        // no length of its own covers.
        return isNaN(seconds) || seconds <= 0 ? 1 / 30 : seconds;
    }

    // Every field the effect takes that has no default. Until they are filled,
    // the call would not run, so the drop is refused rather than written.
    readonly property var missing: {
        if (picked === null)
            return [];
        const out = [];
        for (const parameter of picked.params) {
            const written = values[parameter.name];
            if (parameter.value.length === 0 && (written === undefined || written.trim().length === 0))
                out.push(parameter.name);
        }
        return out;
    }

    // ── The element's own line, as fields ─────────────────────────────────
    // What the call that made this element takes, straight from its signature —
    // `Square` answers side, fillColor, stroke…, `Video` answers startFrame,
    // endFrame, cuts. Nothing here knows what a video is; the class does.
    readonly property string cls: element !== null && element.cls !== undefined ? element.cls : ""
    // A template's are asked of the module it lives in — see Main.foldTemplates.
    readonly property var arguments: cls.length === 0 ? []
                                     : Shell.inputParams(element.signature !== undefined ? element.signature : cls)

    // Whether the line is one this card can safely write to. An element built in
    // a loop, or by a helper, has a line that says where it came from but not a
    // call anyone can rewrite — better to show the values and refuse the edit
    // than to write into the wrong place.
    readonly property bool writable: element !== null
                                     && element.line !== undefined && element.line > 0
                                     && cls.length > 0
                                     && Shell.callsOnLine(buffer, element.line).indexOf(cls) >= 0

    // `element` and not `writable`: the card is emptied by setting the element
    // to null, and a binding that calls this can re-run before `writable` has
    // caught up — which is the "Cannot read property 'line' of null" the console
    // showed on closing a card.
    function written(name) {
        if (root.element === null || !writable)
            return "";
        return Shell.readArgument(buffer, element.line, cls, name);
    }

    // A value written WITHOUT a name still belongs to the argument it fills:
    // `Video("marius.mov")` is the filepath, and a chip that shows nothing there
    // is a chip that misreads the call it is describing.
    function writtenAt(index) {
        if (root.element === null || !writable)
            return "";
        return Shell.readPositional(buffer, element.line, cls, index);
    }

    // ── What a call's `easing=` says, as a curve ──────────────────────────
    // The presets come from the library rather than from a list written here:
    // `Easing.Out` IS a `CubicBezier`, and a preset added there has to reach
    // the card without a second edit. Read once — the shell asks Python for
    // them, and the answer cannot change while a card is open.
    readonly property var presets: Shell.easingCurves()

    // The four control points behind what is WRITTEN, or an empty list when
    // that is not a curve at all. `Easing.Wiggle` is a function, `SNAPPY` is a
    // decision with a name on it, `pick(fast)` is neither — each is shown as
    // what it says and none of them is pulled about by a drag.
    function curveOf(text) {
        if (root.presets[text] !== undefined)
            return root.presets[text];
        const numbers = /^CubicBezier\s*\(([^()]*)\)$/.exec(text.trim());
        if (numbers === null)
            return [];
        const parts = numbers[1].split(",").map(Number);
        return parts.length === 4 && !parts.some(isNaN) ? parts : [];
    }

    // The name a curve is already known by, so picking `Out` writes
    // `Easing.Out` and not the four numbers behind it: the word is what the
    // person meant, and it stays readable when the preset itself is tuned.
    function nameOf(points) {
        for (const name in root.presets) {
            const preset = root.presets[name];
            if (preset.every((v, i) => Math.abs(v - points[i]) < 0.005))
                return name;
        }
        return "";
    }

    // Why a written easing cannot be pulled about, in the words `edit.py` uses
    // for the same refusal on a number: what is there is a decision, and a
    // gesture that overwrote it would keep the timing and lose the decision.
    // `Easing.Wiggle` is a function with no handles to show; `SNAPPY` is a name
    // the person gave a curve, and changing it is an edit to that line, not to
    // this one.
    function whyNotCurve(text) {
        if (/^Easing\.\w+$/.test(text))
            return text + " is a function, not a curve — edit the line itself";
        if (/^[A-Za-z_]\w*$/.test(text))
            return text + " is a name, not a curve — change " + text + " itself";
        return text + " is written as an expression — edit the line itself";
    }

    // What the signature would use when the line says nothing: `moveTo` eases
    // in and out, `slideIn` eases out, `flash` goes there and back. Taken from
    // the same catalogue the library panel shows, so the curve opens on the
    // easing that is really running.
    //
    // "" for a call the catalogue does not name, and that is the whole guard:
    // `square.opacity(0)` takes no easing, and a curve offered on it would have
    // written an argument that call cannot accept — a gesture that breaks the
    // scene it was supposed to tune. A call outside the catalogue that DOES
    // take one, `fadeIn` among them, gets its curve as soon as the line says
    // `easing=` itself; until then the editor does not guess.
    function defaultEasing(call) {
        for (const effect of root.effectNames) {
            if (effect.name !== call)
                continue;
            for (const parameter of effect.params)
                if (parameter.name === "easing" && parameter.value.length > 0)
                    return parameter.value;
        }
        return "";
    }

    // Which row's curve is open, and where on the card it was summoned from.
    // Card-level because the rows are inside a clipped ListView: a panel drawn
    // in the row would be cut off by the row above it.
    property var curving: null

    // Turn a pointer position into a moment on the element.
    function timeAt(globalX) {
        const at = bar.mapFromItem(null, globalX, 0);
        const seconds = Math.max(0, Math.min(root.span, at.x / Math.max(bar.width, 1) * root.span));
        return root.exact ? seconds : Math.round(seconds / root.snap) * root.snap;
    }

    Rectangle {
        anchors.fill: parent
        visible: !root.docked
        color: Qt.rgba(0.02, 0.027, 0.039, 0.88)
        opacity: root.travel

        MouseArea {
            anchors.fill: parent
            onClicked: root.close()
        }
    }

    Rectangle {
        id: card

        readonly property int pad: 18
        readonly property int wide: Math.min(1080, root.width - 48)
        readonly property int rowsTall: Math.max(root.rows.length * 42 + Math.max(root.rows.length - 1, 0) * 7, 28)
        // Ce que les pastilles ajoutent : celles qui sont ÉCRITES font grandir la
        // barre, les deux lectures se posent dessous. Sans ce compte, la fiche
        // gardait la hauteur d'une barre de 76 px et les effets tombaient hors
        // du cadre, qui est en `clip` — ils avaient disparu sans un mot.
        readonly property int fieldsTall: Math.max(0, bar.height - 76)
                                        + (argBlock.visible ? argBlock.height + 10 : 0)
                                        + (metaBlock.visible ? metaBlock.height + 8 : 0)
                                        + (liveRow.visible ? liveRow.height + 10 : 0)
                                        + (rule.visible ? 8 : 0)
                                        + (metaRow.visible ? metaRow.height + 7 : 0)
        readonly property int tall: Math.min(pad + 22 + 76 + 8 + 24 + 12 + rowsTall + fieldsTall + 34 + pad,
                                             root.height - 48)

        // The card does not travel — the bar does. It is at its final size and
        // place from the first frame, and simply arrives: everything in it has
        // nowhere to come from, and a box that grows behind a moving bar is a
        // second thing to watch.
        x: root.docked ? 0 : (root.width - wide) / 2
        y: root.docked ? 0 : Math.min(Math.max(24, root.height * 0.12), Math.max(24, root.height - tall - 24))
        width: root.docked ? root.width : wide
        height: root.docked ? root.height : tall

        // Behind the bar until the bar is nearly home. The delay is what makes
        // the eye follow one moving thing: the chrome shows up around a bar that
        // has already stopped.
        opacity: root.docked ? 1 : Math.max(0, (root.travel - 0.55) / 0.45)

        clip: true
        color: Theme.panel
        radius: root.docked ? 0 : Theme.radius
        border.width: root.docked ? 0 : 1
        border.color: Theme.edge

        MouseArea { anchors.fill: parent }

        // Cliquer ailleurs referme le champ ouvert. Il n'a pas de bouton
        // « fini » et n'en veut pas : on part en regardant autre chose, et ce
        // qui a été tapé se range tout seul — gardé s'il tient, remis comme
        // avant sinon.
        //
        // Au-dessus de tout, et seulement pendant qu'un champ est ouvert : la
        // barre, les rangées et la bibliothèque prennent chacune leurs propres
        // appuis, et une zone posée SOUS elles ne voyait jamais le clic. Elle
        // refuse l'appui qu'elle vient de voir, donc ce qu'on visait se produit
        // quand même — y compris re-viser le champ, qui reprend alors le focus.
        MouseArea {
            anchors.fill: parent
            z: 500
            visible: root.editing !== null
            acceptedButtons: Qt.AllButtons
            cursorShape: undefined // it hands the press back; the cursor is not its to say either
            onPressed: (mouse) => {
                root.forceActiveFocus();
                mouse.accepted = false;
            }
        }

        // ── What it is ────────────────────────────────────────────────────
        Text {
            anchors.centerIn: parent
            visible: root.docked && root.element === null
            text: "click a clip"
            color: Theme.inkFaint
            font.family: Theme.ui
            font.pixelSize: 12
        }

        Item {
            id: head
            anchors { left: parent.left; right: parent.right; top: parent.top }
            anchors.margins: card.pad
            height: root.docked ? 30 : 12

            Item { id: nameLine; width: 1; height: 12; y: 0 }
            Item { id: lineLine; width: 1; height: 12; y: root.docked ? 18 : 0 }

            // Its name, at the left end of the same row as the line it was
            // written on. On the clip it was a label ON the picture, fighting
            // the waveform under it; here it reads as what it is — the thing
            // this card is about — and the row already carries the other two
            // facts about it.
            Text {
                anchors { left: parent.left; verticalCenter: nameLine.verticalCenter }
                text: root.element !== null && root.element.n !== undefined ? root.element.n : ""
                color: Theme.ink
                font.family: Theme.ui
                font.pixelSize: 12
                font.weight: Font.DemiBold
                elide: Text.ElideRight
                width: Math.min(implicitWidth, root.docked ? head.width - 56 : head.width / 3)

                HoverHandler { cursorShape: Qt.PointingHandCursor }
                HoverTint {}

                TapHandler {
                    onTapped: if (root.element !== null) root.renameRequested(root.element)
                }
            }

            // What it is, in the middle of the card's own top bar rather than
            // in its left corner. The bar is the card's title, and the kind is
            // the title — everything else along it (where it was written, how
            // long it is, the way out) is a fact ABOUT it and belongs at the
            // ends. Left-aligned it read as one more of those.
            Row {
                anchors.centerIn: parent
                spacing: 8
                visible: !root.docked

                Rectangle {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 9; height: 9
                    radius: 2
                    color: root.hue
                }

                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.kindLabel[root.kind] !== undefined
                          ? root.kindLabel[root.kind].toUpperCase() : root.kind.toUpperCase()
                    color: Theme.inkFaint
                    font.family: Theme.ui
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                    font.letterSpacing: 1.1
                }
            }

            // Where it was written. The card is the one surface that can afford
            // to say it, and clicking it puts the caret there.
            Text {
                id: where
                anchors.right: root.docked ? undefined : dur.left
                anchors.rightMargin: 12
                anchors.left: root.docked ? parent.left : undefined
                anchors.verticalCenter: root.docked ? lineLine.verticalCenter : parent.verticalCenter
                text: root.element !== null && root.element.line > 0
                      ? "line " + root.element.line : ""
                color: jump.containsMouse ? Theme.live : Theme.inkFaint
                font.family: Theme.mono
                font.pixelSize: 11

                MouseArea {
                    id: jump
                    anchors.fill: parent
                    anchors.margins: -6
                    hoverEnabled: true
                    onClicked: root.jumpRequested(root.element)
                }
            }

            Text {
                id: dur
                anchors.right: root.docked ? parent.right : closer.left
                anchors.rightMargin: root.docked ? 0 : 10
                anchors.verticalCenter: nameLine.verticalCenter
                text: root.span.toFixed(1) + "s"
                color: Theme.inkDim
                font.family: Theme.mono
                font.pixelSize: 12
            }

            CloseButton {
                id: closer
                visible: !root.docked
                anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                onTriggered: root.dismiss()
            }
        }

        // ── The element itself, re-scaled to the whole width ──────────────
        // Shown only once the flight is over: until then this exact rectangle is
        // being drawn by the bar that is still on its way here, and two of them
        // would be one too many. The swap happens at rest, where nothing moves.
        Rectangle {
            id: bar
            visible: !root.docked && root.travel >= 1
            anchors {
                left: parent.left; right: parent.right
                leftMargin: card.pad; rightMargin: card.pad
                top: head.bottom; topMargin: 10
            }
            // Le clip, et rien d'autre : le nom est monté dans l'en-tête et les
            // arguments sont descendus dans leur propre cadre, donc la barre
            // n'a plus à loger que ce qu'elle montre — la forme d'onde.
            height: root.docked ? 0 : 76
            radius: 6
            color: root.hue
            border.width: 1
            border.color: Qt.rgba(1, 1, 1, 0.18)
            clip: true

            // Same problem as the timeline clips, one size up: the waveform runs
            // straight under the name, so the glyphs are stroked to keep their
            // weight against it.
            Row {
                anchors { fill: parent; topMargin: 10; bottomMargin: 10 }
                spacing: 1
                visible: root.kind === "video" || root.kind === "sound"
                opacity: 0.34

                Repeater {
                    model: Math.max(Math.round(root.span * 10), 1)

                    Rectangle {
                        required property int index
                        // Deterministic pseudo-waveform: it must not reshuffle
                        // every time the card is opened.
                        readonly property real v: 22 + 78 * Math.abs(
                            Math.sin(index * 0.7) * Math.cos(index * 0.21) * Math.sin(index * 0.05 + 1))
                        width: Math.max((bar.width - 20) / Math.max(Math.round(root.span * 10), 1) - 1, 1)
                        height: parent.height * v / 100
                        // Vers le haut seulement. Centré, un son se lit comme
                        // deux formes d'onde qui se regardent ; posé sur le
                        // sol, il se lit comme ce qu'il est — un niveau.
                        anchors.bottom: parent.bottom
                        radius: 1
                        color: "#dff3ee"
                    }
                }
            }

            // What the drop would cover, drawn ON the element while you aim it.
            // The width is the effect's own duration against the element's, so
            // the thing you are placing is the size it will be — a fade that
            // covers a third of the clip looks like a third before it exists.
            Rectangle {
                id: ghost
                visible: root.dragging
                x: bar.width * root.dropAt / root.span
                width: Math.max(bar.width * root.pickedDuration / root.span, 3)
                anchors { top: parent.top; bottom: parent.bottom }
                color: Qt.alpha(root.fxHue, 0.55)
                border.width: 1
                border.color: root.fxHue
                radius: 4
            }

            // The instant it lands on. Green when it is exactly under the
            // pointer, accent when it snapped — you can see WHICH you got
            // without being told, which is the only way a modifier key is ever
            // learned.
            Rectangle {
                visible: root.dragging
                x: bar.width * root.dropAt / root.span
                width: 2
                anchors { top: parent.top; bottom: parent.bottom }
                color: root.exact ? Theme.ok : Theme.live
                z: 2

                Rectangle {
                    y: 6
                    x: 6
                    width: stamp.implicitWidth + 12
                    height: stamp.implicitHeight + 6
                    radius: 3
                    color: root.exact ? Theme.ok : Theme.live

                    Text {
                        id: stamp
                        anchors.centerIn: parent
                        text: root.dropAt.toFixed(2) + "s → " + (root.dropAt + root.pickedDuration).toFixed(2) + "s"
                        color: root.exact ? "#04170e" : "#180c06"
                        font.family: Theme.mono
                        font.pixelSize: 11
                        font.weight: Font.DemiBold
                    }
                }
            }
        }

        // ── Ce que l'appel dit, avant que rien ne bouge ───────────────────
        // Sorti de la barre : ce qui est ÉCRIT n'est pas le clip, c'est la
        // recette du clip. Sur la barre, les pastilles couvraient la forme
        // d'onde et faisaient grandir un rectangle qui doit rester la taille
        // d'une durée. Ici elles ont un cadre, un titre, et la place de tenir
        // sur une ligne.
        Rectangle {
            id: argBlock
            anchors {
                left: bar.left; right: bar.right
                top: bar.bottom; topMargin: 10
            }
            height: 26 + argRow.height + 10
            visible: root.docked && argRow.visible
            radius: 6
            color: Theme.sunk
            border.width: 1
            border.color: Theme.edgeSoft

            Text {
                anchors { left: parent.left; leftMargin: 12; top: parent.top; topMargin: 8 }
                text: "arguments:"
                color: Theme.inkFaint
                font.family: Theme.mono
                font.pixelSize: 11
            }
        }

        // Ce que la ligne RÈGLE, par opposition à ce qu'elle PREND. Deux cadres
        // et pas un : un argument se retape, une metadata se pose ou s'enlève,
        // et les mêmes pastilles côte à côte laissaient croire à une seule
        // sorte de chose.
        Rectangle {
            id: metaBlock
            anchors {
                left: bar.left; right: bar.right
                top: argBlock.visible ? argBlock.bottom : bar.bottom; topMargin: 8
            }
            height: 26 + 40 + 10
            visible: startRow.visible
            radius: 6
            color: Theme.sunk
            border.width: 1
            border.color: Theme.edgeSoft

            Text {
                anchors { left: parent.left; leftMargin: 12; top: parent.top; topMargin: 8 }
                text: "metadata:"
                color: Theme.inkFaint
                font.family: Theme.mono
                font.pixelSize: 11
            }
        }

        // ── The element's own duration, laid out under it ─────────────────
        Item {
            id: scale
            visible: !root.docked
            anchors {
                left: bar.left; right: bar.right
                // Sous la DERNIÈRE rangée visible, quelle qu'elle soit. Accrochée
                // au seul metaRow, elle remontait sous la barre dès qu'il était
                // vide — et les valeurs courantes se retrouvaient dessinées
                // par-dessus la règle.
                top: metaRow.visible ? metaRow.bottom
                     : (liveRow.visible ? liveRow.bottom : bar.bottom)
                topMargin: 8
            }
            height: 24

            Rectangle {
                anchors { left: parent.left; right: parent.right; top: parent.top }
                height: 1
                color: Theme.edge
            }

            // A tick is a time and a class: the tenth is the trim resolution and
            // stays nearly silent, the half second is warm, the whole second is
            // the one you count in — and only whole seconds are ever labelled.
            readonly property var ticks: {
                const d = root.span;
                const every = d <= 8 ? 1 : (d <= 20 ? 2 : 5);
                const out = [];
                if (d <= 15) {
                    for (let n = 1; n * 0.1 < d; n++) {
                        if (n % 5 === 0)
                            continue;
                        out.push({ at: n * 0.1 / d, h: 4, c: Theme.edge, label: "" });
                    }
                }
                for (let h = 1; h * 0.5 < d; h++) {
                    if (h % 2 === 0)
                        continue;
                    out.push({ at: h * 0.5 / d, h: 8, c: "#88d9a94e", label: "" });
                }
                for (let t = 0; t <= d + 1e-6; t++)
                    out.push({ at: t / d, h: 12, c: "#cc4a86c5",
                               label: t % every === 0 ? t + "s" : "" });
                return out;
            }

            Repeater {
                model: scale.ticks

                Item {
                    required property var modelData
                    x: scale.width * modelData.at
                    y: 0
                    width: 1
                    height: scale.height

                    Rectangle {
                        id: stem
                        width: 1
                        height: parent.modelData.h
                        color: parent.modelData.c
                    }

                    Text {
                        anchors { top: stem.bottom; topMargin: 2; horizontalCenter: parent.horizontalCenter }
                        text: parent.modelData.label
                        color: Theme.inkFaint
                        font.family: Theme.mono
                        font.pixelSize: 10
                    }
                }
            }

            // The end of the element, named rather than counted: the last whole
            // second is not where a clip stops.
            Rectangle {
                x: scale.width - 1
                width: 1
                height: 12
                color: Theme.inkFaint

                Text {
                    anchors { top: parent.bottom; topMargin: 2; right: parent.right }
                    text: root.span.toFixed(1) + "s"
                    color: Theme.inkDim
                    font.family: Theme.mono
                    font.pixelSize: 10
                }
            }
        }

        // ── What animates it, on the element's own axis ───────────────────
        Item {
            id: applied
            visible: !root.docked
            // Jusqu'à la phrase du bas, pas jusqu'aux pastilles : celles-ci sont
            // remontées DANS la barre, donc au-dessus d'ici, et le bloc a eu une
            // hauteur négative — les effets ont disparu sans un mot.
            anchors {
                left: bar.left; right: bar.right
                top: scale.bottom; topMargin: 12
                bottom: hint.top; bottomMargin: 10
            }

            // The ruler's half-second and whole-second lines, carried down
            // behind the rows.
            Repeater {
                model: {
                    const out = [];
                    for (let h = 1; h * 0.5 < root.span; h++)
                        out.push({ at: h * 0.5 / root.span, c: h % 2 ? "#1fd9a94e" : "#334a86c5" });
                    return out;
                }

                Rectangle {
                    required property var modelData
                    x: applied.width * modelData.at
                    width: 1
                    height: applied.height
                    color: modelData.c
                }
            }

            Text {
                anchors { left: parent.left; top: parent.top; topMargin: 6 }
                visible: root.rows.length === 0
                text: "Nothing animates this element — press E for the library."
                color: Theme.inkFaint
                font.family: Theme.ui
                font.pixelSize: 12
            }

            ListView {
                anchors.fill: parent
                model: root.rows
                clip: true
                spacing: 7
                boundsBehavior: Flickable.StopAtBounds

                delegate: Item {
                    id: row
                    required property var modelData
                    width: ListView.view.width
                    height: 42

                    readonly property bool isMember: root.members.length > 0

                    // A row can be edited when it knows the call that wrote it
                    // and that call is still where it said it was. An effect
                    // that came out of a loop, or from a helper the scene
                    // imported, keeps its bar and loses its handles rather than
                    // writing to a line it only half understands.
                    readonly property bool editable: !isMember
                                                     && modelData.line !== undefined && modelData.line > 0
                                                     && modelData.call !== undefined && modelData.call.length > 0
                                                     && Shell.callsOnLine(root.buffer, modelData.line)
                                                             .indexOf(modelData.call) >= 0

                    // Written on a `Group(...)` line: one call, every member.
                    // Said out loud, because the ✕ on this row takes the effect
                    // off the others too.
                    readonly property bool shared: editable
                                                   && Shell.callsOnLine(root.buffer, modelData.line)
                                                           .indexOf("Group") >= 0

                    // What the drag is worth so far, in seconds, before it is
                    // written. The bar follows these; the source does not, until
                    // the mouse comes up.
                    property real heldStart: 0
                    property real heldSpan: 0

                    // Tenths, unless ⌘ says otherwise — the same rule as
                    // dropping an effect, and the same reason: the ruler above
                    // is drawn in tenths.
                    function snap(seconds, free) {
                        return free ? Math.round(seconds * 100) / 100 : Math.round(seconds * 10) / 10;
                    }

                    // A value the card is allowed to do arithmetic on. An
                    // argument written as `RATIO * 0.5` is a number to Python
                    // and an expression to us: it keeps its bar, and the drag
                    // that would have rewritten it says why it did not.
                    function written(name, fallback) {
                        const text = Shell.readArgument(root.buffer, modelData.line, modelData.call, name);
                        if (text.length === 0)
                            return fallback;
                        const value = Number(text);
                        return isNaN(value) ? NaN : value;
                    }

                    // ── The curve this effect runs on ────────────────
                    // What the line says, or what the signature would use when
                    // it says nothing: an effect opens on the easing that is
                    // really running, never on a default the card invented.
                    readonly property string easingText: {
                        if (!row.editable)
                            return "";
                        const said = Shell.readArgument(root.buffer, row.modelData.line,
                                                        row.modelData.call, "easing");
                        return said.length > 0 ? said : root.defaultEasing(row.modelData.call);
                    }

                    readonly property var easingPoints: root.curveOf(row.easingText)

                    readonly property bool curveOpen: root.curving !== null
                                                      && root.curving.line === row.modelData.line
                                                      && root.curving.call === row.modelData.call

                    function openCurve(from) {
                        if (row.easingPoints.length !== 4) {
                            root.says(root.whyNotCurve(row.easingText));
                            return;
                        }
                        if (row.curveOpen) {
                            root.curving = null;
                            return;
                        }
                        const at = from.mapToItem(card, 0, 0);
                        root.curving = {
                            line: row.modelData.line, call: row.modelData.call,
                            file: row.modelData.file, n: row.modelData.n,
                            points: row.easingPoints,
                            x: at.x, y: at.y, w: from.width, h: from.height
                        };
                    }

                    function commit(name, value) {
                        if (isNaN(value)) {
                            root.effectWritten(modelData, "", "");
                            return;
                        }

                        // A gesture that lands back on the default writes
                        // nothing rather than writing `start=0`: an argument
                        // that says what the signature already says is noise the
                        // next reader has to check.
                        const rounded = Math.round(value * 100) / 100;
                        const already = Shell.readArgument(root.buffer, modelData.line, modelData.call, name);
                        if (rounded === 0 && already.length === 0)
                            return;
                        root.effectWritten(modelData, name, rounded.toString());
                    }

                    // The ✕ and the line number live at the far right of the
                    // ROW, not on the bar: a 0.4 s fade inside a three-second
                    // clip is a sliver, and a button that shrinks with what it
                    // acts on is a button you cannot press.
                    Row {
                        id: handle
                        anchors { right: easeChip.left; rightMargin: 8
                                  verticalCenter: parent.verticalCenter }
                        spacing: 8
                        opacity: row.editable
                                 && (hover.hovered || bar.pressed || row.curveOpen) ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: Theme.motion(110) } }

                        Text {
                            anchors.verticalCenter: parent.verticalCenter
                            text: (row.shared ? "group · " : "") + "line " + row.modelData.line
                            color: Theme.inkFaint
                            font.family: Theme.mono
                            font.pixelSize: 10
                        }

                        // Off, not gone: the line stays in the scene, commented
                        // out, where you can read what it said and switch it
                        // back on. Deleting is the other button.
                        Rectangle {
                            width: 18; height: 18; radius: 9
                            anchors.verticalCenter: parent.verticalCenter
                            color: mute.containsMouse ? Qt.alpha(Theme.inkDim, 0.18) : "transparent"
                            border.width: 1
                            border.color: mute.containsMouse ? Theme.inkDim : Theme.inkFaint

                            Text {
                                anchors.centerIn: parent
                                text: "◦"
                                color: mute.containsMouse ? Theme.ink : Theme.inkDim
                                font.family: Theme.ui
                                font.pixelSize: 12
                            }

                            MouseArea {
                                id: mute
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.effectToggled(row.modelData.line, true, row.modelData.file)
                            }
                        }

                        Rectangle {
                            width: 18; height: 18; radius: 9
                            anchors.verticalCenter: parent.verticalCenter
                            color: cut.containsMouse ? "#33e05a4a" : "transparent"
                            border.width: 1
                            border.color: cut.containsMouse ? "#cce05a4a" : Theme.inkFaint

                            Text {
                                anchors.centerIn: parent
                                text: "✕"
                                color: cut.containsMouse ? "#ffe05a4a" : Theme.inkDim
                                font.family: Theme.ui
                                font.pixelSize: 10
                            }

                            MouseArea {
                                id: cut
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.effectRemoved(row.modelData)
                            }
                        }
                    }

                    HoverHandler { id: hover }

                    Rectangle {
                        id: span
                        x: row.width * Math.max(0, row.modelData.l - root.origin + row.heldStart) / root.span
                        width: Math.max(row.width * (row.modelData.d + row.heldSpan) / root.span, 3)
                        anchors { top: parent.top; bottom: parent.bottom; topMargin: 4; bottomMargin: 4 }
                        radius: 4
                        color: row.isMember
                               ? (Theme.kind[row.modelData.kind] !== undefined
                                  ? Theme.kind[row.modelData.kind] : root.hue)
                               : root.fxHue
                        clip: true

                        HoverTint {}

                        // What the run said about THIS call, or "". The timeline
                        // says which element is at fault; this says which of its
                        // lines earned it, which is the only place the two ever
                        // needed to be told apart.
                        readonly property string flaw: row.modelData.flaw !== undefined
                                                       ? row.modelData.flaw : ""

                        ToolTip.visible: hover.hovered && span.flaw.length > 0
                        ToolTip.delay: 250
                        ToolTip.text: span.flaw

                        Item {
                            id: fxHazard
                            anchors.fill: parent
                            clip: true
                            visible: span.flaw.length > 0

                            Repeater {
                                model: fxHazard.visible
                                       ? Math.ceil((fxHazard.width + fxHazard.height) / 12) : 0

                                Rectangle {
                                    required property int index
                                    width: 4
                                    height: fxHazard.height * 2
                                    x: index * 12 - fxHazard.height
                                    y: -fxHazard.height / 2
                                    rotation: -45
                                    color: Qt.alpha(Theme.flaw, 0.40)
                                }
                            }
                        }

                        Text {
                            id: fxMark
                            visible: span.flaw.length > 0
                            anchors {
                                left: parent.left; leftMargin: 9
                                verticalCenter: parent.verticalCenter
                            }
                            text: "\u26A0"
                            color: span.ink
                            font.pixelSize: 12
                            transformOrigin: Item.Center

                            SequentialAnimation on scale {
                                running: fxMark.visible
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

                        // Every complement on the wheel lands on the light, warm
                        // side, so dark ink beats white on an effect — and it
                        // separates what animates from what is animated, which
                        // carries light text on a saturated ground.
                        readonly property color ink: row.isMember ? "#eef3f9" : "#21160a"

                        // Wide enough to read it in: a 0.1 s effect on a
                        // four-second clip is three pixels of bar, and a name
                        // elided into nothing tells you only that something is
                        // there.
                        readonly property bool roomy: width > 96

                        Text {
                            anchors {
                                left: parent.left; leftMargin: fxMark.visible ? 26 : 11
                                right: length.left; rightMargin: 12
                                verticalCenter: parent.verticalCenter
                            }
                            visible: span.roomy
                            text: root.effectName(row.modelData)
                            color: span.ink
                            font.family: Theme.mono
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                            elide: Text.ElideRight
                        }

                        // Pushed to the far edge of the bar, so the number sits
                        // exactly where the effect ends — you read the duration
                        // and see it at the same time.
                        Text {
                            id: length
                            anchors { right: parent.right; rightMargin: 11; verticalCenter: parent.verticalCenter }
                            visible: span.roomy
                            text: (row.modelData.d + row.heldSpan).toFixed(1) + "s"
                            color: span.ink
                            opacity: 0.72
                            font.family: Theme.mono
                            font.pixelSize: 11
                        }

                        MouseArea {
                            anchors.fill: parent
                            enabled: row.isMember
                            onClicked: {
                                const at = row.mapToItem(null, span.x, 0);
                                root.memberOpened(row.modelData,
                                                  Qt.rect(at.x, at.y, span.width, row.height));
                            }
                        }
                    }

                    // Moving the bar writes `start=`, dragging its right edge
                    // writes `duration=`. Both as a DELTA on what the line
                    // already says: `start` is counted from the element's own
                    // cursor, and the card has no business working out where
                    // that cursor is — only how much further along the person
                    // just asked for.
                    MouseArea {
                        id: dragBar
                        enabled: row.editable
                        anchors.fill: span
                        hoverEnabled: true
                        cursorShape: onEdge || edging ? Qt.SizeHorCursor
                                   : (pressed ? Qt.ClosedHandCursor : Qt.PointingHandCursor)

                        property real anchorX: 0
                        property bool edging: false
                        property bool moved: false
                        readonly property bool onEdge: containsMouse && mouseX > width - 9

                        function seconds(dx) {
                            return dx * root.span / Math.max(row.width, 1);
                        }

                        // Measured against the ROW, never against itself. The
                        // bar is what the drag moves, so a delta taken in the
                        // bar's own coordinates shrinks by exactly as much as
                        // the bar travels — the two cancel, and a drag of half a
                        // second writes `start=0`.
                        onPressed: (mouse) => {
                            anchorX = mapToItem(row, mouse.x, 0).x;
                            // Read from the press itself. `onEdge` also asks
                            // whether the pointer is inside, and a press that
                            // arrives without a hover before it — every
                            // scripted one, and a tap — says it is not.
                            edging = mouse.x > width - 9;
                            moved = false;
                        }

                        onPositionChanged: (mouse) => {
                            if (!pressed)
                                return;
                            const now = mapToItem(row, mouse.x, 0).x;
                            const delta = row.snap(seconds(now - anchorX), (mouse.modifiers & Qt.ControlModifier) !== 0);
                            if (Math.abs(delta) > 0.001)
                                moved = true;
                            if (edging)
                                // A bar cannot be shortened past nothing: a
                                // `duration` of zero is a change with no time to
                                // happen in, which the scene draws as a jump.
                                row.heldSpan = Math.max(0.1 - row.modelData.d, delta);
                            else
                                // `start` is counted from the element's own
                                // cursor and cannot go behind it: an effect
                                // dragged to the left of where its element is
                                // ready is asking to happen before the line
                                // that schedules it.
                                row.heldStart = Math.max(-row.written("start", 0), delta);
                        }

                        onReleased: {
                            if (!moved) {
                                row.heldStart = 0;
                                row.heldSpan = 0;
                                // A press that went nowhere is a click, and a
                                // click on an effect asks to see the line that
                                // wrote it.
                                root.effectJumped(row.modelData);
                                return;
                            }
                            if (edging)
                                row.commit("duration", row.written("duration", row.modelData.d) + row.heldSpan);
                            else
                                row.commit("start", row.written("start", 0) + row.heldStart);
                            // Held only until the scene comes back saying where
                            // the bar really is — the source is the truth, and
                            // keeping the offset would draw the move twice.
                            row.heldStart = 0;
                            row.heldSpan = 0;
                        }
                    }

                    // What a bar too narrow to hold its name says, beside it.
                    Text {
                        anchors { left: span.right; leftMargin: 9; verticalCenter: span.verticalCenter }
                        visible: !span.roomy
                        text: root.effectName(row.modelData) + "  " + (row.modelData.d + row.heldSpan).toFixed(1) + "s"
                        color: row.isMember ? Theme.ink : root.fxHue
                        font.family: Theme.mono
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                    }

                    // The edge you can take hold of, shown only while the mouse
                    // is on it.
                    Rectangle {
                        x: span.x + span.width - 3
                        width: 2
                        anchors { top: span.top; bottom: span.bottom; topMargin: 5; bottomMargin: 5 }
                        radius: 1
                        color: span.ink
                        opacity: bar.onEdge || bar.edging ? 0.8 : 0
                        Behavior on opacity { NumberAnimation { duration: Theme.motion(90) } }
                    }

                    // The shape of the change this effect runs on, always in
                    // view rather than under the pointer: it is what the line
                    // SAYS, the same way the duration on the bar is, and a
                    // curve you have to go hunting for is one nobody corrects.
                    //
                    // Over the bar rather than beside it, on its own ground: an
                    // effect that covers its whole clip leaves no margin to put
                    // this in, and a control that disappears on the longest
                    // effects is missing exactly where easing matters most.
                    Item {
                        id: easeChip
                        anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                        width: row.easingText.length === 0 ? 0
                             : (row.easingPoints.length === 4
                                ? 24 : Math.min(saidEase.implicitWidth + 8, 92))
                        height: 24
                        visible: width > 0

                        Rectangle {
                            anchors.fill: parent
                            radius: 3
                            color: Theme.panel
                            opacity: 0.94
                        }

                        EasingCurve {
                            anchors.fill: parent
                            visible: row.easingPoints.length === 4
                            handles: row.easingPoints.length === 4
                                     ? row.easingPoints : [0, 0, 1, 1]
                            tint: row.curveOpen ? Theme.ink : root.fxHue
                        }

                        // Not a curve: the word the line uses, because that word
                        // is the whole reason this one cannot be pulled about.
                        Text {
                            id: saidEase
                            anchors.fill: parent
                            visible: row.easingPoints.length !== 4
                            verticalAlignment: Text.AlignVCenter
                            horizontalAlignment: Text.AlignHCenter
                            text: row.easingText.replace("Easing.", "")
                            color: Theme.inkFaint
                            font.family: Theme.mono
                            font.pixelSize: 10
                            elide: Text.ElideRight
                        }

                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: row.openCurve(easeChip)
                        }

                        HoverTint { radius: 3 }
                    }
                }
            }
        }

        // ── The line that made it, as values you can change ───────────────
        // The chips ARE the call: what the source says, in the order the
        // signature declares. A value that is not written shows its default,
        // dimmed — writing it adds it to the line; clearing it takes it back
        // out. Trimming a video is `endFrame` here, and nothing in this card
        // knows that is what trimming means.
        Flickable {
            id: argRow
            // DANS la barre, pas sous elle. Les valeurs sont celles de cet
            // élément-là ; posées dessous elles flottaient entre lui et le reste
            // de la fiche, et il fallait décider à qui elles appartenaient. Sur
            // sa propre barre, la question ne se pose plus.
            //
            // UNE ligne, jamais deux : un `Flow` qui reprend à la ligne fait
            // grandir la barre, et une barre qui grandit cesse de se lire comme
            // le clip qu'elle est. Ce qui dépasse est coupé à droite et se
            // ramène à la molette ou au doigt — pas d'ascenseur, il prendrait
            // plus de hauteur que ce qu'il sert à voir.
            anchors {
                left: argBlock.left; right: argBlock.right
                top: argBlock.top; topMargin: 26
                leftMargin: 12; rightMargin: 12
            }
            height: 40
            visible: root.docked && root.arguments.length > 0
            clip: true
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: argLine.width
            contentHeight: height

            // La molette verticale pousse la rangée horizontalement : elle n'a
            // qu'un axe, et c'est celui-là qu'on veut en tournant dessus.
            WheelHandler {
                onWheel: (event) => {
                    argRow.contentX = Math.max(0, Math.min(argRow.contentWidth - argRow.width,
                                                           argRow.contentX - event.angleDelta.y - event.angleDelta.x));
                }
            }

            Row {
            id: argLine
            spacing: 6

            Repeater {
                model: root.arguments

                Rectangle {
                    id: arg
                    required property var modelData
                    required property int index

                    readonly property string current: {
                        const named = root.written(arg.modelData.name);
                        return named.length > 0 ? named : root.writtenAt(arg.index);
                    }
                    readonly property bool set: current.length > 0

                    height: 40
                    width: Math.max(argName.implicitWidth, argValue.width + 4) + 18
                    radius: 4
                    readonly property color hue: root.valueHue(root.fullValue(arg.modelData, argEntry.text))
                    color: argEntry.activeFocus ? Qt.alpha(root.fxHue, 0.12) : Qt.alpha(arg.hue, 0.10)
                    border.width: 1
                    border.color: argEntry.activeFocus
                                  ? root.fxHue
                                  : Qt.alpha(arg.hue, arg.set ? 0.55 : 0.30)

                    // Le nom au-dessus, la valeur en dessous, un cheveu entre les
                    // deux. Côte à côte, une pastille large se lisait comme une
                    // phrase — `width 6 height None` — et il fallait chercher où
                    // finissait l'un et commençait l'autre. L'un sur l'autre,
                    // c'est une étiquette et sa valeur, comme partout ailleurs.
                    Text {
                        id: argName
                        anchors { left: parent.left; leftMargin: 8; top: parent.top; topMargin: 4 }
                        text: arg.modelData.name
                        color: Theme.code.argument
                        font.family: Theme.mono
                        font.pixelSize: 10
                    }

                    Rectangle {
                        id: hair
                        anchors { left: parent.left; right: parent.right; top: argName.bottom; topMargin: 3 }
                        height: 1
                        color: argEntry.activeFocus ? Qt.alpha(root.fxHue, 0.5) : Theme.edgeSoft
                    }

                    Item {
                        id: argValue
                        anchors { left: parent.left; leftMargin: 8; top: hair.bottom; topMargin: 3 }
                        width: Math.max(argEntry.implicitWidth + 4, 26)
                        height: 16

                        TextInput {
                            id: argEntry
                            anchors.fill: parent
                            verticalAlignment: TextInput.AlignVCenter
                            // What the source says, or the signature's default
                            // shown for what it is: a value nobody chose.
                            text: root.shortValue(arg.modelData, arg.set ? arg.current : arg.modelData.value)
                            // Écrite dans la couleur du code ; un défaut que personne
                            // n'a choisi garde la même teinte, plus pâle.
                            color: Qt.alpha(arg.hue, arg.set ? 1 : 0.6)
                            font.family: Theme.mono
                            font.pixelSize: 11
                            selectByMouse: true
                            selectionColor: Qt.alpha(root.fxHue, 0.4)
                            enabled: root.writable

                            // On Enter, not on every keystroke: a scene that
                            // re-runs on each character would run on `1.`, on
                            // `1.5` and on everything in between.
                            onAccepted: arg.commit()
                            onActiveFocusChanged: {
                                if (activeFocus) {
                                    root.editing = arg.modelData;
                                    root.editingAt = arg.mapToItem(card, 0, 0).x;
                                } else {
                                    arg.commit();
                                    // Par NOM, pas par identité : `arguments`
                                    // est une liaison qui refabrique ses objets
                                    // à chaque relecture, et l'objet qu'on avait
                                    // retenu n'est déjà plus le même — la fiche
                                    // restait ouverte sur un champ parti.
                                    if (root.editing !== null && root.editing.name === arg.modelData.name)
                                        root.editing = null;
                                }
                            }
                            Keys.onEscapePressed: {
                                argEntry.text = root.shortValue(arg.modelData, arg.set ? arg.current : arg.modelData.value);
                                root.forceActiveFocus();
                            }
                        }
                    }

                    // Ce qui était là avant qu'on tape — ce que la ligne écrit,
                    // ou le défaut de la signature quand elle n'écrit rien.
                    readonly property string before: root.shortValue(arg.modelData, arg.set ? arg.current : arg.modelData.value)

                    function commit() {
                        const value = argEntry.text.trim();
                        if (value === arg.before)
                            return;
                        // Rien qui tienne : le champ revient à ce qu'il disait.
                        // Une valeur qu'on abandonne ne doit pas rester à l'écran
                        // comme si elle comptait.
                        if (!root.writable || !root.fits(arg.modelData, value)
                            || (!arg.set && value === arg.modelData.value)) {
                            argEntry.text = arg.before;
                            return;
                        }
                        root.argumentWritten(root.element, root.cls, arg.modelData.name, root.fullValue(arg.modelData, value));
                    }

                    MouseArea {
                        anchors.fill: parent
                        enabled: !argEntry.activeFocus
                        cursorShape: root.writable ? Qt.IBeamCursor : Qt.ArrowCursor
                        onClicked: {
                            if (!root.writable)
                                return;
                            argEntry.forceActiveFocus();
                            argEntry.selectAll();
                        }
                    }

                    HoverTint { visible: root.writable }
                }
            }
            }
        }

        // ── Ce qu'il vaut au départ, et de quoi en ajouter ────────────────
        // Le + est HORS de la rangée qui défile : un bouton qui s'en va quand on
        // pousse la liste est un bouton qu'on ne peut pas viser — et dans le
        // Flickable il n'était même pas atteint par le clic.
        Rectangle {
            id: plusChip
            anchors {
                left: metaBlock.left; leftMargin: 12
                top: metaBlock.top; topMargin: 26 + (40 - 22) / 2
            }
            width: 22; height: 22
            radius: 4
            visible: startRow.visible && root.addable.length > 0
            color: plus.containsMouse || adder.visible ? Qt.alpha(root.fxHue, 0.14) : Theme.rail
            border.width: 1
            border.color: plus.containsMouse || adder.visible ? root.fxHue : Theme.edge
            z: 20

            Text {
                anchors.centerIn: parent
                text: "+"
                color: plus.containsMouse || adder.visible ? root.fxHue : Theme.inkDim
                font.family: Theme.ui
                font.pixelSize: 13
            }

            MouseArea {
                id: plus
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: adder.visible = !adder.visible
            }
        }

        Flickable {
            id: startRow
            anchors {
                left: plusChip.visible ? plusChip.right : metaBlock.left
                leftMargin: plusChip.visible ? 6 : 12
                right: metaBlock.right; rightMargin: 12
                top: metaBlock.top; topMargin: 26
            }
            height: 40
            visible: root.docked && (root.startShown.length > 0 || root.addable.length > 0)
            clip: true
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: startLine.width
            contentHeight: height

            WheelHandler {
                onWheel: (event) => {
                    startRow.contentX = Math.max(0, Math.min(startRow.contentWidth - startRow.width,
                                                             startRow.contentX - event.angleDelta.y - event.angleDelta.x));
                }
            }

            Row {
                id: startLine
                spacing: 6

                Repeater {
                    model: root.startShown

                    // Le même dessin qu'un argument : le nom, un cheveu, la
                    // valeur — et les couleurs du code. Le nom est un APPEL
                    // (`.opacity(0)`), donc il prend la teinte `call` ; la
                    // pastille prend celle de sa première valeur.
                    Rectangle {
                        id: start
                        required property var modelData
                        readonly property var fields: start.modelData.fields
                        readonly property color hue: start.fields.length > 0 && start.fields[0].current.length > 0
                                                     ? root.valueHue(start.fields[0].current) : Theme.code.variable

                        width: Math.max(startName.implicitWidth, startValues.width) + 18
                        height: 40
                        radius: 4
                        color: Qt.alpha(start.hue, 0.10)
                        border.width: 1
                        border.color: Qt.alpha(start.hue, 0.55)

                        Text {
                            id: startName
                            anchors { left: parent.left; leftMargin: 8; top: parent.top; topMargin: 4 }
                            text: start.modelData.n
                            color: Theme.code.call
                            font.family: Theme.mono
                            font.pixelSize: 10
                        }

                        Rectangle {
                            id: startHair
                            anchors { left: parent.left; right: parent.right; top: startName.bottom; topMargin: 3 }
                            height: 1
                            color: Theme.edgeSoft
                        }

                        Row {
                            id: startValues
                            anchors { left: parent.left; leftMargin: 8; top: startHair.bottom; topMargin: 3 }
                            spacing: 8

                            // Un `show()` n'a rien entre ses parenthèses, et un
                            // tiret le dit mieux qu'une case vide.
                            Text {
                                visible: start.fields.length === 0
                                height: 16
                                verticalAlignment: Text.AlignVCenter
                                text: "—"
                                color: Theme.inkFaint
                                font.family: Theme.mono
                                font.pixelSize: 11
                            }

                            Repeater {
                                model: start.fields

                                // Un champ d'argument, en plus petit : ce que la
                                // ligne écrit, ou le défaut en pâle. Entrée ou un
                                // clic ailleurs l'écrit ; ce qui ne tient pas revient.
                                Row {
                                    id: metaField
                                    required property var modelData
                                    readonly property string key: start.modelData.n + "." + metaField.modelData.name
                                    readonly property bool set: metaField.modelData.current.length > 0
                                    readonly property string before: root.shortValue(metaField.modelData, metaField.set ? metaField.modelData.current : metaField.modelData.value)
                                    readonly property color hue: root.valueHue(root.fullValue(metaField.modelData, fieldEntry.text))
                                    spacing: 4

                                    function commit() {
                                        const value = fieldEntry.text.trim();
                                        if (value === metaField.before)
                                            return;
                                        if (!root.writable || !root.fits(metaField.modelData, value)
                                            || (!metaField.set && value === metaField.modelData.value)) {
                                            fieldEntry.text = metaField.before;
                                            return;
                                        }
                                        root.metadataWritten(root.element, start.modelData.n, metaField.modelData.name,
                                                             metaField.modelData.at, root.fullValue(metaField.modelData, value));
                                    }

                                    // Seul, le nom répéterait l'appel : `opacity` n'a
                                    // qu'une valeur. À deux, il dit laquelle est `x`.
                                    Text {
                                        visible: start.fields.length > 1
                                        height: 16
                                        verticalAlignment: Text.AlignVCenter
                                        text: metaField.modelData.name
                                        color: Theme.code.argument
                                        font.family: Theme.mono
                                        font.pixelSize: 10
                                    }

                                    Item {
                                        width: Math.max(fieldEntry.implicitWidth + 4, 18)
                                        height: 16

                                        TextInput {
                                            id: fieldEntry
                                            anchors.fill: parent
                                            verticalAlignment: TextInput.AlignVCenter
                                            text: metaField.before
                                            color: Qt.alpha(metaField.hue, metaField.set ? 1 : 0.6)
                                            font.family: Theme.mono
                                            font.pixelSize: 11
                                            selectByMouse: true
                                            selectionColor: Qt.alpha(root.fxHue, 0.4)
                                            enabled: root.writable

                                            onAccepted: metaField.commit()
                                            onActiveFocusChanged: {
                                                if (activeFocus) {
                                                    root.editing = { name: metaField.key, kind: metaField.modelData.kind, value: metaField.modelData.value,
                                                                     call: start.modelData.n, param: metaField.modelData.name, at: metaField.modelData.at };
                                                    root.editingAt = metaField.mapToItem(card, 0, 0).x;
                                                } else {
                                                    metaField.commit();
                                                    if (root.editing !== null && root.editing.name === metaField.key)
                                                        root.editing = null;
                                                }
                                            }
                                            Keys.onEscapePressed: {
                                                fieldEntry.text = metaField.before;
                                                root.forceActiveFocus();
                                            }
                                        }

                                        MouseArea {
                                            anchors.fill: parent
                                            enabled: !fieldEntry.activeFocus
                                            cursorShape: root.writable ? Qt.IBeamCursor : Qt.ArrowCursor
                                            onClicked: {
                                                if (!root.writable)
                                                    return;
                                                fieldEntry.forceActiveFocus();
                                                fieldEntry.selectAll();
                                            }
                                        }

                                        HoverTint { visible: root.writable }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ── Ce que ce champ accepte ───────────────────────────────────────
        // Un nom, une valeur, et rien qui dise ce qu'une valeur peut ÊTRE. Le
        // type est écrit dans la signature ; quand il est fermé — `UVMapping`,
        // `Align` — c'est une liste, et une liste se choisit au lieu de se
        // retenir. Le reste garde son champ : c'est le cas normal.
        Rectangle {
            id: argSheet
            visible: root.editing !== null
            x: Math.min(Math.max(card.pad, root.editingAt), card.width - width - card.pad)
            anchors { top: root.editing !== null && root.editing.call !== undefined ? startRow.bottom : argRow.bottom; topMargin: 4 }
            width: Math.max(160, sheetKind.implicitWidth + 24)
            height: sheetBody.implicitHeight + 12
            radius: 4
            color: Theme.panel
            border.width: 1
            border.color: root.fxHue
            z: 40

            Column {
                id: sheetBody
                anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 6 }
                spacing: 2

                Text {
                    id: sheetKind
                    anchors { left: parent.left; leftMargin: 10 }
                    // Le type seul : le nom est écrit sur la pastille juste
                    // au-dessus, le répéter ici faisait lire deux fois la même
                    // chose avant d'arriver à ce qu'on venait chercher.
                    text: root.editing !== null
                          ? (root.editing.kind.length > 0 ? root.editing.kind : "any")
                          : ""
                    color: Theme.inkFaint
                    font.family: Theme.mono
                    font.pixelSize: 10
                }

                Repeater {
                    model: root.editingValues

                    Rectangle {
                        id: value
                        required property string modelData
                        width: sheetBody.width
                        height: 20
                        color: take.containsMouse ? Qt.alpha(root.fxHue, 0.14) : "transparent"

                        Text {
                            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                            text: root.shortValue(root.editing, value.modelData)
                            color: take.containsMouse ? Theme.ink : Theme.inkDim
                            font.family: Theme.mono
                            font.pixelSize: 11
                        }

                        MouseArea {
                            id: take
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                if (root.editing.call !== undefined)
                                    root.metadataWritten(root.element, root.editing.call, root.editing.param, root.editing.at, value.modelData);
                                else
                                    root.argumentWritten(root.element, root.cls, root.editing.name, value.modelData);
                                root.editing = null;
                            }
                        }
                    }
                }

            }
        }

        // La liste de ce qui manque, ouverte par le +. Hors du Flickable : une
        // liste qui défile avec la rangée qui l'a ouverte se promène toute seule.
        Rectangle {
            id: adder
            visible: false
            anchors { left: plusChip.left; top: plusChip.bottom; topMargin: 4 }
            width: 132
            height: addList.implicitHeight + 8
            radius: 4
            color: Theme.pop !== undefined ? Theme.pop : Theme.panel
            border.width: 1
            border.color: Theme.edge
            z: 30

            Column {
                id: addList
                anchors { left: parent.left; right: parent.right; top: parent.top; topMargin: 4 }

                Repeater {
                    model: root.addable

                    Rectangle {
                        id: choice
                        required property var modelData
                        width: parent.width
                        height: 22
                        color: pick.containsMouse ? Qt.alpha(root.fxHue, 0.14) : "transparent"

                        Text {
                            anchors { left: parent.left; leftMargin: 10; verticalCenter: parent.verticalCenter }
                            text: choice.modelData.name
                            color: pick.containsMouse ? Theme.ink : Theme.inkDim
                            font.family: Theme.mono
                            font.pixelSize: 11
                        }

                        MouseArea {
                            id: pick
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                adder.visible = false;
                                root.metadataAdded(root.element, choice.modelData.write);
                            }
                        }
                    }
                }
            }
        }

        // ── Les mêmes arguments, à l'image du curseur ─────────────────────
        // La rangée du dessus dit ce que la LIGNE écrit ; celle-ci ce que
        // l'élément en a fait à cette image-là. La plupart sont identiques —
        // personne n'anime `side` — et c'est voulu : ce qui a bougé est alors
        // la seule chose qui diffère entre les deux rangées, et se voit sans
        // qu'on ait à lire.
        Flickable {
            id: liveRow
            // Sous la barre, pas dedans. Le rectangle vert EST le clip : ce qui
            // y est écrit est ce qui le fabrique. Une lecture n'est pas le clip,
            // c'est ce qu'on en dit à un instant — la poser dessus mélangeait
            // les deux, et faisait grandir une barre qui doit rester la taille
            // d'un clip.
            anchors {
                left: bar.left; right: bar.right
                top: metaBlock.visible ? metaBlock.bottom
                     : (argBlock.visible ? argBlock.bottom : bar.bottom); topMargin: 10
            }
            height: 22
            visible: root.docked && root.argsNow.length > 0
            clip: true
            flickableDirection: Flickable.HorizontalFlick
            boundsBehavior: Flickable.StopAtBounds
            contentWidth: liveLine.width
            contentHeight: height

            WheelHandler {
                onWheel: (event) => {
                    liveRow.contentX = Math.max(0, Math.min(liveRow.contentWidth - liveRow.width,
                                                            liveRow.contentX - event.angleDelta.y - event.angleDelta.x));
                }
            }

            Row {
            id: liveLine
            spacing: 6

            Repeater {
                model: root.argsNow

                Rectangle {
                    id: live
                    required property var modelData
                    width: liveText.implicitWidth + 16
                    height: 22
                    radius: Theme.radiusSmall
                    color: Theme.sunk

                    Text {
                        id: liveText
                        anchors.centerIn: parent
                        text: live.modelData.n + " " + live.modelData.v
                        color: Theme.inkDim
                        font.family: Theme.mono
                        font.pixelSize: 11
                        elide: Text.ElideRight
                    }
                }
            }
            }
        }

        // Ce qui est ÉCRIT au-dessus, ce que la scène FAIT en dessous. Les deux
        // se lisent de la même façon et ne veulent pas dire la même chose ; une
        // ligne coûte moins qu'une légende et se voit de plus loin.
        Rectangle {
            id: rule
            anchors {
                left: bar.left; right: bar.right
                top: liveRow.bottom; topMargin: 7
            }
            height: 1
            visible: metaRow.visible && liveRow.visible
            color: Theme.edgeSoft
        }

        // ── Où il en est, à l'image du curseur ────────────────────────────
        // La ligne du dessus dit ce que l'APPEL prend — `side`, `fillColor` —
        // et ne dira jamais autre chose : ce sont les arguments écrits, ils ne
        // bougent pas. Celle-ci dit où l'élément EST, ce qu'aucun argument ne
        // porte parce que ce n'en est pas un : c'est ce que toutes les lignes
        // au-dessus lui ont fait à cette image-là.
        //
        // Relue, pas modifiable : écrire ici est l'autre moitié de B4, et un
        // champ qu'on peut taper sans qu'il écrive une ligne serait un champ
        // qui ment.
        Flow {
            id: metaRow
            anchors {
                left: bar.left; right: bar.right
                top: rule.visible ? rule.bottom : liveRow.bottom; topMargin: 7
            }
            spacing: 6
            visible: root.docked && root.metaShown.length > 0

            Text {
                height: 22
                verticalAlignment: Text.AlignVCenter
                text: "à " + root.playhead.toFixed(2) + "s"
                color: Theme.inkFaint
                font.family: Theme.mono
                font.pixelSize: 10
            }

            Repeater {
                model: root.metaShown

                Rectangle {
                    id: chip
                    required property var modelData
                    width: readout.implicitWidth + 16
                    height: 22
                    radius: Theme.radiusSmall
                    color: Theme.sunk

                    Text {
                        id: readout
                        anchors.centerIn: parent
                        text: chip.modelData.n + " "
                              + (Math.abs(chip.modelData.v) >= 100
                                 ? Math.round(chip.modelData.v)
                                 : chip.modelData.v.toFixed(2))
                        color: Theme.inkDim
                        font.family: Theme.mono
                        font.pixelSize: 11
                    }
                }
            }
        }

        // ── How to get out, and how to add one ────────────────────────────
        Item {
            id: hint
            visible: !root.docked
            anchors {
                left: bar.left; right: bar.right
                bottom: parent.bottom; bottomMargin: card.pad
            }
            height: 22

            Rectangle {
                anchors { left: parent.left; right: parent.right; top: parent.top }
                height: 1
                color: Theme.edge
            }

            Text {
                anchors { left: parent.left; bottom: parent.bottom }
                textFormat: Text.StyledText
                text: "<b>E</b> for the effects library · click outside or <b>Esc</b> to go back"
                color: Theme.inkFaint
                font.family: Theme.ui
                font.pixelSize: 11
            }
        }

        // ── The curve, big enough to pull ─────────────────────────────────
        // Beside the row rather than over it: the rows are the one thing on
        // this card you aim at, and a panel that covers the neighbours of what
        // you clicked is a panel you have to move before you can carry on.
        //
        // Nothing is written until the point is let go. The shape follows the
        // pointer the whole way, so what the release will write has already
        // been on screen for a second before it lands in the file.
        Rectangle {
            id: curvePanel

            readonly property int pad: 10

            visible: root.curving !== null
            z: 6
            width: 220
            height: curveHead.height + curve.height + presetRow.height + reads.height + pad * 2 + 18
            x: root.curving === null ? 0
               : Math.max(card.pad, Math.min(root.curving.x - width - 10,
                                             card.width - width - card.pad))
            y: root.curving === null ? 0
               : Math.max(card.pad, Math.min(root.curving.y + root.curving.h / 2 - height / 2,
                                             card.height - height - card.pad))
            radius: 6
            color: Theme.panel
            border.width: 1
            border.color: Theme.edge

            Item {
                id: curveHead
                anchors { left: parent.left; right: parent.right; top: parent.top
                          margins: curvePanel.pad }
                height: 14

                Text {
                    anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                    text: root.curving !== null ? root.curving.n : ""
                    color: Theme.inkDim
                    font.family: Theme.mono
                    font.pixelSize: 11
                }

                Text {
                    anchors { right: parent.right; verticalCenter: parent.verticalCenter }
                    text: "✕"
                    color: shut.containsMouse ? Theme.ink : Theme.inkFaint
                    font.family: Theme.ui
                    font.pixelSize: 10

                    MouseArea {
                        id: shut
                        anchors.fill: parent
                        anchors.margins: -6
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: root.curving = null
                    }
                }
            }

            EasingCurve {
                id: curve
                anchors { left: parent.left; right: parent.right; top: curveHead.bottom
                          leftMargin: curvePanel.pad; rightMargin: curvePanel.pad; topMargin: 8 }
                height: width
                interactive: true
                tint: root.fxHue
                onLetGo: curvePanel.write()
            }

            // A preset IS a curve, so choosing one moves the handles rather
            // than replacing the drawing with a word — and what gets written is
            // the word again, because `Easing.Out` is what the person meant and
            // it stays right if the preset itself is ever tuned.
            Flow {
                id: presetRow
                anchors { left: parent.left; right: parent.right; top: curve.bottom
                          leftMargin: curvePanel.pad; rightMargin: curvePanel.pad; topMargin: 8 }
                spacing: 4

                Repeater {
                    model: Object.keys(root.presets)

                    Rectangle {
                        required property string modelData

                        readonly property var points: root.presets[modelData]
                        readonly property bool current: root.nameOf(curve.handles) === modelData

                        width: presetName.implicitWidth + 12
                        height: 18
                        radius: 3
                        color: current ? Qt.alpha(root.fxHue, 0.18) : Theme.sunk
                        border.width: 1
                        border.color: current ? root.fxHue
                                     : (presetTap.containsMouse ? Theme.edge : Theme.edgeSoft)

                        Text {
                            id: presetName
                            anchors.centerIn: parent
                            text: parent.modelData.replace("Easing.", "")
                            color: parent.current ? Theme.ink : Theme.inkDim
                            font.family: Theme.mono
                            font.pixelSize: 10
                        }

                        MouseArea {
                            id: presetTap
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                curve.handles = parent.points.slice();
                                curvePanel.write();
                            }
                        }
                    }
                }
            }

            // The line the release will write, before it writes it.
            Text {
                id: reads
                anchors { left: parent.left; right: parent.right; top: presetRow.bottom
                          leftMargin: curvePanel.pad; rightMargin: curvePanel.pad; topMargin: 8 }
                text: "easing=" + curvePanel.value()
                color: Theme.inkFaint
                font.family: Theme.mono
                font.pixelSize: 10
                // Wrapped rather than elided: a line you are about to write
                // with three of its four numbers hidden is not a line you were
                // shown.
                wrapMode: Text.Wrap
            }

            function value() {
                const p = curve.handles;
                const named = root.nameOf(p);
                return named.length > 0
                     ? named
                     : "CubicBezier(" + p[0] + ", " + p[1] + ", " + p[2] + ", " + p[3] + ")";
            }

            function write() {
                if (root.curving !== null)
                    root.effectWritten(root.curving, "easing", curvePanel.value());
            }

            // The handles are the panel's own from the moment it opens: the
            // curve is dragged, which assigns them, and a binding back to the
            // row would have been broken by the first drag anyway.
            Connections {
                target: root
                function onCurvingChanged() {
                    if (root.curving !== null)
                        curve.handles = root.curving.points.slice();
                }
            }
        }
    }

    // ── The bar, on its way ───────────────────────────────────────────────
    // The clip you clicked, between its lane and the middle of the window.
    //
    // It is not a copy dressed as one: the lane it left is drawn hollow for
    // exactly as long as this exists, so at no point are there two of the same
    // element on screen. What changes along the way is what the two ends look
    // like — a clip is a translucent bar with a name band, a block is a solid one
    // with the name across it — so the look is interpolated on the same clock as
    // the geometry rather than swapped at either end.
    Rectangle {
        id: flight

        readonly property real t: root.travel
        readonly property real toX: card.x + card.pad
        readonly property real toY: card.y + card.pad + 12 + 10
        readonly property real toWidth: card.width - card.pad * 2
        readonly property real toHeight: 76

        visible: root.element !== null && t < 1
        z: 4

        x: root.from.x + (toX - root.from.x) * t
        y: root.from.y + (toY - root.from.y) * t
        width: Math.max(1, root.from.width + (toWidth - root.from.width) * t)
        height: Math.max(1, root.from.height + (toHeight - root.from.height) * t)

        color: Qt.alpha(root.hue, 0.30 + 0.70 * t)
        radius: 4 + 2 * t
        border.width: 1
        border.color: Qt.rgba(1, 1, 1, 0.15 + 0.03 * t)
        clip: true

        Row {
            anchors { fill: parent; margins: 4; topMargin: 4 + 15 * (1 - flight.t) }
            spacing: 1
            visible: root.kind === "video" || root.kind === "sound"
            opacity: 0.55 - 0.21 * flight.t

            Repeater {
                model: Math.max(Math.round(root.span * 10), 1)

                Rectangle {
                    required property int index
                    readonly property real v: 22 + 78 * Math.abs(
                        Math.sin(index * 0.7) * Math.cos(index * 0.21) * Math.sin(index * 0.05 + 1))
                    width: Math.max((flight.width - 8) / Math.max(Math.round(root.span * 10), 1) - 1, 1)
                    height: parent.height * v / 100
                    anchors.verticalCenter: parent.verticalCenter
                    radius: 1
                    color: "#dff3ee"
                }
            }
        }

        // The clip's name band, on its way out.
        Rectangle {
            anchors { left: parent.left; right: parent.right; top: parent.top }
            anchors.margins: 1
            height: 16 * (1 - flight.t)
            topLeftRadius: 3
            topRightRadius: 3
            color: Qt.alpha(root.hue, 0.92)
            clip: true
            opacity: 1 - flight.t

            Text {
                anchors { left: parent.left; leftMargin: 6; verticalCenter: parent.verticalCenter }
                text: root.element !== null ? root.element.n : ""
                color: Qt.rgba(0.04, 0.06, 0.09, 0.92)
                font.family: Theme.ui
                font.pixelSize: 11
                font.weight: Font.DemiBold
                elide: Text.ElideRight
            }
        }

        // The block's name, on its way in.
        Text {
            anchors { left: parent.left; leftMargin: 16; verticalCenter: parent.verticalCenter }
            text: root.element !== null ? root.element.n : ""
            color: "#eef3f9"
            font.family: Theme.ui
            font.pixelSize: 15
            font.weight: Font.DemiBold
            style: Text.Outline
            styleColor: Qt.rgba(0.043, 0.055, 0.075, 0.85)
            opacity: flight.t
        }
    }

    // ── The library, summoned with E ──────────────────────────────────────
    // Over the card rather than beside it: it is aimed at the block, used, and
    // dismissed, and a permanent column would narrow the block for the whole
    // time it is not there.
    Rectangle {
        id: lib
        z: 5
        visible: opacity > 0
        // Centred, it sits over the very block you are aiming at — so the moment
        // the drag starts it gets out of the way, and takes none of the drop.
        opacity: root.library ? (root.dragging ? 0.12 : 1) : 0
        scale: root.library ? 1 : 0.96
        x: (root.width - width) / 2
        y: (root.height - height) / 2
        width: Math.min(420, root.width - 40)
        height: root.picked !== null
                ? Math.min(root.height * 0.66, fields.contentHeight + carry.height + 96)
                : Math.min(root.height * 0.66, list.contentHeight + 84)
        color: Theme.panel
        radius: Theme.radius
        border.width: 1
        border.color: Theme.edge

        Behavior on opacity { NumberAnimation { duration: Theme.motion(160) } }
        Behavior on scale { NumberAnimation { duration: Theme.motion(180); easing.type: Easing.OutCubic } }

        MouseArea { anchors.fill: parent }

        Item {
            id: libHead
            anchors { left: parent.left; right: parent.right; top: parent.top }
            anchors.margins: 14
            height: 22

            Text {
                id: libTitle
                anchors.left: parent.left
                text: root.picked === null ? "EFFECTS" : root.picked.name
                color: root.picked === null ? Theme.inkFaint : Theme.ink
                font.family: root.picked === null ? Theme.ui : Theme.mono
                font.pixelSize: root.picked === null ? 10 : 12
                font.weight: Font.DemiBold
                font.letterSpacing: root.picked === null ? 0.9 : 0
            }

            Text {
                anchors.right: parent.right
                text: root.picked === null ? root.effectNames.length : "back"
                color: backLink.containsMouse ? Theme.live : Theme.inkDim
                font.family: Theme.mono
                font.pixelSize: 11

                MouseArea {
                    id: backLink
                    anchors.fill: parent
                    anchors.margins: -6
                    enabled: root.picked !== null
                    hoverEnabled: true
                    onClicked: root.unpick()
                }
            }

            Rectangle {
                anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
                height: 1
                color: Theme.edge
            }
        }

        ListView {
            id: list
            visible: root.picked === null
            anchors {
                left: parent.left; right: parent.right
                top: libHead.bottom; topMargin: 4
                bottom: libHint.top; bottomMargin: 8
            }
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            clip: true
            boundsBehavior: Flickable.StopAtBounds

            // Grouped by where the effect lives, because that is what the import
            // will say: `videocode.template.effect.entrance.fade` is an
            // entrance, and the chip that writes the line should say so.
            model: {
                const groups = [];
                const seen = ({});
                for (const fx of root.effectNames) {
                    const parts = String(fx.module).split(".");
                    const family = parts.length > 3 ? parts[3] : "effect";
                    if (seen[family] === undefined) {
                        seen[family] = { name: family, items: [] };
                        groups.push(seen[family]);
                    }
                    seen[family].items.push(fx);
                }
                return groups;
            }

            delegate: Column {
                id: family
                required property var modelData
                width: ListView.view.width
                spacing: 6
                bottomPadding: 5

                Text {
                    text: family.modelData.name.toUpperCase()
                    color: Theme.inkFaint
                    font.family: Theme.ui
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.9
                    topPadding: 6
                }

                Flow {
                    width: parent.width
                    spacing: 6

                    Repeater {
                        model: family.modelData.items

                        Rectangle {
                            id: fxChip
                            required property var modelData
                            width: label.implicitWidth + 18
                            height: 22
                            radius: 4
                            color: fxPick.containsMouse ? Qt.alpha(root.fxHue, 0.14) : Theme.sunk
                            border.width: 1
                            border.color: fxPick.containsMouse ? root.fxHue : Theme.edge

                            Text {
                                id: label
                                anchors.centerIn: parent
                                text: fxChip.modelData.name
                                color: fxPick.containsMouse ? Theme.ink : Theme.inkDim
                                font.family: Theme.mono
                                font.pixelSize: 11
                            }

                            MouseArea {
                                id: fxPick
                                anchors.fill: parent
                                hoverEnabled: true
                                // Chosen, not applied. What it is set to and
                                // where it lands are still open questions, and
                                // an effect written into the scene the instant
                                // you name it answers both of them for you.
                                onClicked: root.pick(fxChip.modelData)
                            }
                        }
                    }
                }
            }
        }

        // What the effect takes, in the field idiom the rest of the chrome uses.
        // Whatever is left at its default is not written into the call: a line
        // that repeats the signature back to it is noise you have to read past
        // every time you open the scene.
        ListView {
            id: fields
            visible: root.picked !== null
            anchors {
                left: parent.left; right: parent.right
                top: libHead.bottom; topMargin: 6
                bottom: carry.top; bottomMargin: 10
            }
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            clip: true
            spacing: 6
            boundsBehavior: Flickable.StopAtBounds
            model: root.picked !== null ? root.picked.params : []

            delegate: Item {
                id: field
                required property var modelData
                width: ListView.view.width
                height: 26

                readonly property bool needed: field.modelData.value.length === 0

                Text {
                    id: fieldName
                    anchors { left: parent.left; verticalCenter: parent.verticalCenter }
                    width: 96
                    text: field.modelData.name
                    color: field.needed ? Theme.ink : Theme.inkDim
                    font.family: Theme.mono
                    font.pixelSize: 11
                    elide: Text.ElideRight
                }

                Rectangle {
                    anchors {
                        left: fieldName.right; leftMargin: 8
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                    }
                    height: 24
                    radius: Theme.radiusSmall
                    color: Theme.sunk
                    border.width: 1
                    border.color: entry.activeFocus
                                  ? root.fxHue
                                  : (field.needed && entry.text.trim().length === 0 ? Theme.bad : Theme.edge)

                    TextInput {
                        id: entry
                        anchors { fill: parent; leftMargin: 8; rightMargin: 8 }
                        verticalAlignment: TextInput.AlignVCenter
                        // Filled once, never bound: a field bound to the same
                        // table it writes back into is a binding loop, and Qt
                        // breaks it by dropping the binding — which is to say by
                        // dropping whichever of the two you happened to do last.
                        Component.onCompleted: entry.text = root.values[field.modelData.name] !== undefined
                                               ? root.values[field.modelData.name] : field.modelData.value
                        color: Theme.ink
                        font.family: Theme.mono
                        font.pixelSize: 11
                        selectByMouse: true
                        selectionColor: Qt.alpha(root.fxHue, 0.4)

                        // Out of the field first. A TextInput swallows the key
                        // it is given, so without this the card's own Escape
                        // never runs and the whole thing feels stuck.
                        Keys.onEscapePressed: root.forceActiveFocus()

                        // Written straight through: the field IS the argument,
                        // and a value the editor second-guessed would be a value
                        // the scene does not contain.
                        //
                        // A fresh table rather than a poke into the old one: the
                        // duration below is computed FROM it, and mutating an
                        // object in place tells QML nothing.
                        onTextEdited: {
                            const next = ({});
                            for (const key in root.values)
                                next[key] = root.values[key];
                            next[field.modelData.name] = text;
                            root.values = next;
                        }
                    }

                    Text {
                        anchors { right: parent.right; rightMargin: 8; verticalCenter: parent.verticalCenter }
                        visible: entry.text.trim().length === 0 && field.needed
                        text: field.modelData.kind
                        color: Theme.inkFaint
                        font.family: Theme.mono
                        font.pixelSize: 10
                    }
                }
            }
        }

        // The effect itself, at the length its fields give it — picked up from
        // here and carried onto the element.
        Item {
            id: carry
            visible: root.picked !== null
            anchors {
                left: parent.left; right: parent.right
                bottom: libHint.top; bottomMargin: 8
            }
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            height: 34

            Rectangle {
                anchors.fill: parent
                radius: 4
                color: root.missing.length > 0 ? Theme.sunk : root.fxHue
                border.width: 1
                border.color: root.missing.length > 0 ? Theme.edge : root.fxHue

                Text {
                    anchors.centerIn: parent
                    text: root.picked === null
                          ? ""
                          : (root.missing.length > 0
                             ? root.missing.join(", ") + " — needed"
                             : root.picked.name + "   " + root.pickedDuration.toFixed(2) + "s")
                    color: root.missing.length > 0 ? Theme.inkFaint : "#21160a"
                    font.family: Theme.mono
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }

                HoverTint { visible: root.missing.length === 0 }

                MouseArea {
                    anchors.fill: parent
                    enabled: root.missing.length === 0
                    cursorShape: enabled ? Qt.OpenHandCursor : Qt.ArrowCursor
                    // ⌘ is read on every move, not only on the press: you decide
                    // to drop exactly here in the middle of aiming, which is the
                    // moment you can see that the snap is one tenth off.
                    onPressed: (mouse) => {
                        root.exact = (mouse.modifiers & Qt.ControlModifier) !== 0;
                        root.dragging = true;
                        const at = mapToItem(null, mouse.x, mouse.y);
                        root.dropAt = root.timeAt(at.x);
                    }

                    onPositionChanged: (mouse) => {
                        if (!pressed)
                            return;
                        root.exact = (mouse.modifiers & Qt.ControlModifier) !== 0;
                        const at = mapToItem(null, mouse.x, mouse.y);
                        root.dropAt = root.timeAt(at.x);
                    }

                    onReleased: (mouse) => {
                        if (!root.dragging)
                            return;
                        root.dragging = false;

                        // Dropped on the element or nowhere: the block is the
                        // only surface that means anything here, and a release
                        // over the rest of the card cancels rather than guessing.
                        const at = mapToItem(null, mouse.x, mouse.y);
                        const inside = bar.mapFromItem(null, at.x, at.y);
                        if (inside.x < 0 || inside.x > bar.width || inside.y < 0 || inside.y > bar.height)
                            return;

                        // Where it lands, counted from the START OF THE SCENE.
                        // The card measures from the element's own left edge —
                        // that is what its axis shows — but the statement has to
                        // be written where the element's cursor makes it land
                        // there, and only the shell knows where that is.
                        root.effectRequested(root.element, root.picked, {
                            at: root.origin + root.dropAt,
                            values: root.values
                        });
                        root.library = false;
                        root.unpick();
                    }
                }
            }
        }

        Text {
            id: libHint
            anchors { left: parent.left; right: parent.right; bottom: parent.bottom }
            anchors.margins: 12
            textFormat: Text.StyledText
            text: root.picked === null
                  ? "Click one to set it up."
                  : "Drag it onto the element · snaps to 0.1 s, hold <b>⌘</b> to drop exactly"
            color: Theme.inkFaint
            font.family: Theme.ui
            font.pixelSize: 11
        }
    }

    // Escape, one step at a time: the field you are typing in, then the effect
    // you were setting up, then the library, then the card. Anything else and a
    // stray key in a parameter box would throw away the whole thing you opened.
    Keys.onEscapePressed: dismiss()

    function dismiss() {
        if (picked !== null)
            unpick();
        else if (library)
            library = false;
        else
            close();
    }

    Keys.onPressed: (event) => {
        if (event.key === Qt.Key_E && root.members.length === 0 && !root.docked) {
            // A group has no `apply` of its own: offering the library there
            // would write a line naming something the scene does not have.
            root.library = !root.library;
            event.accepted = true;
        }
    }

    onVisibleChanged: {
        if (visible)
            forceActiveFocus();
        else
            library = false;
    }
}
