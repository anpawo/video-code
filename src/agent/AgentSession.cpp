/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** AgentSession
*/

#include "agent/AgentSession.hpp"

#include <QCoreApplication>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QRegularExpression>
#include <QStandardPaths>

#include "agent/LineDiff.hpp"
#include "utils/Paths.hpp"

namespace
{
    // What a tool call is doing, in one line. The pane has a row per call and a
    // row cannot hold a JSON object.
    QString summarise(const QString& name, const QJsonObject& input)
    {
        for (const QString& key : {"file_path", "path", "pattern", "command", "url", "query"}) {
            const QJsonValue value = input.value(key);
            if (value.isString() && !value.toString().isEmpty())
                return value.toString();
        }
        return name;
    }

    // Tool output is unbounded — a Read of a thousand-line file arrives whole.
    // The pane shows the head and says how much it is not showing, rather than
    // growing a scrollback nobody asked for.
    QString shorten(const QString& text, int lines = 12)
    {
        const QStringList all = text.split('\n');
        if (all.size() <= lines)
            return text;
        return all.mid(0, lines).join('\n') + QStringLiteral("\n… %1 more lines").arg(all.size() - lines);
    }

    // The words alone. A MessageDisplay hook written for the terminal colours a
    // line with escape codes and pads it to the terminal's width with no-break
    // spaces, and `-p` hands both over as text — measured, one answer carried
    // two colour runs and 130 of those spaces.
    QString plain(QString text)
    {
        static const QRegularExpression paint(QStringLiteral("\x1b\\[[0-9;]*m"));
        static const QRegularExpression padding(QStringLiteral("\u00a0+$"), QRegularExpression::MultilineOption);
        return text.remove(paint).remove(padding).trimmed();
    }
}

VC::AgentSession::AgentSession(QObject* parent)
    : QObject(parent)
{
    connect(&_agent, &QProcess::readyReadStandardOutput, this, &AgentSession::readAvailable);

    connect(&_agent, &QProcess::errorOccurred, this, [this](QProcess::ProcessError) {
        if (_stopping)
            return;
        Q_EMIT failed(QStringLiteral(
            "`claude` could not be started — it is what the Agent pane talks to. "
            "Install it from claude.com/code, or check that it is on the PATH."
        ));
        setBusy(false);
    });

    // A child that dies mid-turn leaves the pane waiting forever. Say so, and
    // let the next question start a fresh one.
    connect(&_agent, &QProcess::finished, this, [this](int code, QProcess::ExitStatus) {
        Q_EMIT runningChanged();
        if (_stopping || !_busy)
            return;
        setBusy(false);
        Q_EMIT turnEnded(0.0, QStringLiteral("the agent stopped (exit %1)").arg(code));
    });
}

VC::AgentSession::~AgentSession()
{
    _stopping = true;
    stop();
}

bool VC::AgentSession::running() const
{
    return _agent.state() == QProcess::Running;
}

bool VC::AgentSession::revertable() const
{
    // Deliberately not a comparison against the file on disk. Accepting a turn
    // leaves the file exactly as the agent wrote it, and the reason to undo one
    // is almost always the PREVIEW — which is only seen after accepting. So the
    // offer stands until `disarm()`, which the pane calls the moment the author
    // types something of their own.
    return _hasSnapshot && !_watched.isEmpty() && _after != _before;
}

QVariantList VC::AgentSession::diff() const
{
    QVariantList out;
    if (!_hasSnapshot)
        return out;

    const QStringList before = QString::fromUtf8(_before).split('\n');
    const QStringList after = QString::fromUtf8(_after).split('\n');

    for (const auto& [kind, text] : VC::lineDiff(before, after)) {
        out.append(QVariantMap{
            {QStringLiteral("kind"), kind == 0 ? QStringLiteral("same") : kind < 0 ? QStringLiteral("del")
                                                                                   : QStringLiteral("add")},
            {QStringLiteral("text"), text},
        });
    }
    return out;
}

QString VC::AgentSession::accepted() const
{
    return QString::fromUtf8(_after);
}

void VC::AgentSession::accept()
{
    if (!_pending)
        return;
    // The file already holds `_after` — the agent wrote it there. Accepting is
    // only the pane letting go: stop colouring, run the scene. `_before` is
    // kept so the turn can still be taken back once the preview is seen.
    _pending = false;
    Q_EMIT pendingChanged();
}

void VC::AgentSession::disarm()
{
    if (!_hasSnapshot && !_pending)
        return;
    _hasSnapshot = false;
    _pending = false;
    _before.clear();
    _after.clear();
    Q_EMIT pendingChanged();
    Q_EMIT revertableChanged();
}

void VC::AgentSession::setRoot(const QString& root)
{
    if (root == _root)
        return;
    _root = root;
    // The root is a command-line argument, so it can only change by starting
    // over. The conversation goes with it — it was about the other project.
    stop();
}

void VC::AgentSession::watch(const QString& path)
{
    _watched = path;
    _hasSnapshot = false;
    Q_EMIT revertableChanged();
}

void VC::AgentSession::ensureStarted()
{
    if (_agent.state() != QProcess::NotRunning)
        return;

    const QString binary = QStandardPaths::findExecutable(QStringLiteral("claude"));
    if (binary.isEmpty()) {
        Q_EMIT failed(QStringLiteral(
            "No `claude` on the PATH — the Agent pane needs Claude Code installed."
        ));
        return;
    }

    QStringList args{
        QStringLiteral("-p"),
        QStringLiteral("--input-format"),
        QStringLiteral("stream-json"),
        QStringLiteral("--output-format"),
        QStringLiteral("stream-json"),
        // Not optional: `--output-format stream-json` is refused without it.
        QStringLiteral("--verbose"),
        // It never stops to ask. Asked for outright: the diff in the editor IS
        // the permission, given after the fact, and a prompt the pane cannot
        // answer would hang the turn anyway.
        QStringLiteral("--permission-mode"),
        QStringLiteral("bypassPermissions"),
        // And it never asks a question back. An ambiguous request is answered
        // with code — which the author reads in green and red, and drops with
        // one key if it guessed wrong. That is a faster loop than a question.
        QStringLiteral("--append-system-prompt"),
        // And it can look at what it did, and at where the author is. The
        // renderer is this very binary, a frame costs milliseconds, and a PNG
        // is something it can read back; the <editor> block the shell puts in
        // front of every question is the half a PNG cannot show.
        QStringLiteral(
            "You are editing a videocode scene from inside the videocode editor. "
            "Never ask the author a clarifying question and never ask for permission: "
            "make the change you believe is meant and write it to the file. "
            "The author reads your edit as a diff and undoes it with one key if you "
            "guessed wrong, so a guess costs less than a question. "
            "Keep the edit as small as the request allows. "
            "Leave every line the request is not about exactly as it is — comments included, "
            "even a comment that says what the author is asking for. "
            "Once the edit is written, your whole reply is the single word \"Fait.\" — "
            "no summary, no explanation, nothing about what you checked: the diff already says "
            "what changed. Only if you could not make the change, say why in one short sentence. "
            "Every question opens with an <editor> block: the file, the caret, the "
            "selected element, the playhead and what the last run said — "
            "\"this\" and \"here\" refer to it. "
            "You can see what you made: `%1 --file <scene> --generate look.png --from 2.5 --width 480 --height 270` "
            "renders the frame at 2.5 s (or at a timestamp() name) in milliseconds, "
            "`--sheet 4 --from 0 --to 6` lays four labelled moments side by side in the one PNG, "
            "and you can read the PNG back — but only when the author asks for a picture, or "
            "when the request is one you cannot answer from the code alone. Rendering to check "
            "yourself turns a turn that takes a second into one that takes a minute, and the author "
            "is already looking at the preview. "
            "For the whole scene as the timeline sees it, run `%1 --inspect --file <scene>`: "
            "JSON, one entry per element with its class, line, on-screen frames and effects. "
            "The editor the author is looking at answers you too: `%1 tell state` prints where they are "
            "(file, caret, selection, playhead, last run, markers) as JSON; `%1 tell seek at=2.5` "
            "(or at=<marker name>) moves the playhead so they see the moment you changed, "
            "`%1 tell select line=12` selects an element, `%1 tell run` re-runs the scene after your edit, "
            "`%1 tell reveal line=12` puts their caret there, `%1 tell say text=...` shows a short note, "
            "`%1 tell export out=film.mp4` renders the file. Do not run the scene for them: ⌘R is "
            "theirs, and running it IS how they accept your edit."
        )
            .arg(QCoreApplication::applicationFilePath()),
    };
    if (!_root.isEmpty())
        args << QStringLiteral("--add-dir") << _root;

    if (!_root.isEmpty())
        _agent.setWorkingDirectory(_root);
    // Its `tell` reaches THIS editor, not whichever opened last.
    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    env.insert(QStringLiteral("VC_SOCKET"), QString::fromStdString(VC::ownSocketPath()));
    _agent.setProcessEnvironment(env);
    _agent.start(binary, args);
    if (!_agent.waitForStarted(8000)) {
        Q_EMIT failed(QStringLiteral("`claude` did not start"));
        return;
    }
    _session.clear();
    Q_EMIT runningChanged();
}

void VC::AgentSession::ask(const QString& text)
{
    if (text.isEmpty() || _busy)
        return;

    ensureStarted();
    if (_agent.state() != QProcess::Running)
        return;

    // Taken before the turn, so `revert()` has something to put back however
    // the turn ends — including a turn that dies half way through an edit.
    if (!_watched.isEmpty()) {
        QFile file(_watched);
        _hasSnapshot = file.open(QIODevice::ReadOnly);
        _before = _hasSnapshot ? file.readAll() : QByteArray();
        _after = _before;
        _pending = false;
        Q_EMIT pendingChanged();
        Q_EMIT revertableChanged();
    }

    const QJsonObject content{{"type", "text"}, {"text", text}};
    const QJsonObject message{{"role", "user"}, {"content", QJsonArray{content}}};
    const QJsonObject event{{"type", "user"}, {"message", message}};

    _agent.write(QJsonDocument(event).toJson(QJsonDocument::Compact) + "\n");
    setBusy(true);
}

void VC::AgentSession::interrupt()
{
    if (!_busy)
        return;
    // There is no "stop this turn" message in the protocol, so the turn is
    // ended the only way it can be. The conversation is lost with it; the pane
    // says so rather than pretending the next question continues it.
    stop();
    setBusy(false);
    Q_EMIT turnEnded(0.0, QStringLiteral("interrupted"));
}

bool VC::AgentSession::revert()
{
    if (!revertable())
        return false;

    QFile file(_watched);
    if (!file.open(QIODevice::WriteOnly | QIODevice::Truncate))
        return false;
    const bool ok = file.write(_before) == _before.size();
    file.close();

    // One undo, not one per edit: the turn is the unit the author asked for and
    // the unit they remember. Offering the agent's three edits as three steps
    // would mean deciding what happens when the second is kept and the first is
    // not — a question the author never asked.
    disarm();
    return ok;
}

void VC::AgentSession::stop()
{
    if (_agent.state() == QProcess::NotRunning)
        return;

    const bool wasStopping = _stopping;
    _stopping = true;
    _agent.terminate();
    if (!_agent.waitForFinished(1500))
        _agent.kill();
    _stopping = wasStopping;
    Q_EMIT runningChanged();
}

void VC::AgentSession::setBusy(bool busy)
{
    if (busy == _busy)
        return;
    _busy = busy;
    Q_EMIT busyChanged();
}

void VC::AgentSession::readAvailable()
{
    _inbox.append(_agent.readAllStandardOutput());

    // One JSON object per line — but a line can arrive in pieces, and several
    // can arrive at once, so only whole lines are taken off the buffer.
    for (;;) {
        const int end = _inbox.indexOf('\n');
        if (end < 0)
            return;

        const QByteArray line = _inbox.left(end).trimmed();
        _inbox.remove(0, end + 1);
        if (line.isEmpty())
            continue;

        const QJsonDocument parsed = QJsonDocument::fromJson(line);
        if (parsed.isObject())
            handle(parsed.object());
    }
}

void VC::AgentSession::handle(const QJsonObject& event)
{
    const QString type = event.value("type").toString();

    if (type == QLatin1String("system")) {
        // `init` opens EVERY turn, not just the first, so it is not the sign of
        // a new conversation — only of a session id worth keeping. The rest of
        // the system traffic is machinery: one turn measured 2 `hook_started`,
        // 2 `hook_response`, 13 `thinking_tokens` and a `rate_limit_event`.
        // Only the count of its thinking is something a reader wants to see.
        const QString id = event.value("session_id").toString();
        if (!id.isEmpty() && id != _session) {
            _session = id;
            Q_EMIT sessionIdChanged();
        }
        if (event.value("subtype").toString() == QLatin1String("thinking_tokens"))
            Q_EMIT thinking(event.value("estimated_tokens").toInt(), QString());
        return;
    }

    if (type == QLatin1String("assistant")) {
        handleAssistant(event.value("message").toObject());
        return;
    }

    if (type == QLatin1String("user")) {
        // A `user` event coming FROM the agent is a tool answering itself — the
        // question the pane already sent is not echoed back.
        handleToolResult(event.value("message").toObject());
        return;
    }

    if (type == QLatin1String("result")) {
        const double cost = event.value("total_cost_usd").toDouble();
        if (cost > 0.0) {
            _spent += cost;
            Q_EMIT spentChanged();
        }
        setBusy(false);

        // What the agent left behind, read once here rather than on every call
        // to `diff()` — the pane asks for it while drawing.
        if (_hasSnapshot) {
            QFile file(_watched);
            _after = file.open(QIODevice::ReadOnly) ? file.readAll() : _before;
        }
        Q_EMIT revertableChanged();

        const bool ok = event.value("subtype").toString() == QLatin1String("success") && !event.value("is_error").toBool();
        Q_EMIT turnEnded(cost, ok ? QString() : event.value("subtype").toString());

        // The scene is NOT run here. The author sees the colours first and runs
        // it themselves — that is what makes the run an acceptance rather than
        // something that happened to them.
        if (_after != _before) {
            _pending = true;
            Q_EMIT pendingChanged();
            Q_EMIT changed();
        }
    }
}

void VC::AgentSession::handleAssistant(const QJsonObject& message)
{
    const QJsonArray content = message.value("content").toArray();

    for (const QJsonValue& value : content) {
        const QJsonObject block = value.toObject();
        const QString     kind = block.value("type").toString();

        // A `thinking` block arrives whole, once the reasoning is over, and
        // usually empty: the words are withheld and only their count was
        // streamed. When a model does give them, they are a step like a call.
        if (kind == QLatin1String("thinking")) {
            const QString words = block.value("thinking").toString().trimmed();
            if (!words.isEmpty())
                Q_EMIT thinking(0, shorten(words));
        } else if (kind == QLatin1String("text")) {
            const QString sentence = plain(block.value("text").toString());
            if (!sentence.isEmpty())
                Q_EMIT said(sentence);
        } else if (kind == QLatin1String("tool_use")) {
            const QString name = block.value("name").toString();
            const QString id = block.value("id").toString();
            // Kept for the result: a `tool_result` carries the id of the call it
            // answers, never its name, and a row that says "finished" without
            // saying what finished is not worth drawing.
            _calls.insert(id, name);
            const QJsonObject input = block.value("input").toObject();
            Q_EMIT toolStarted(id, name, summarise(name, input), shorten(QString::fromUtf8(QJsonDocument(input).toJson()).trimmed()));
        }
    }
}

void VC::AgentSession::handleToolResult(const QJsonObject& message)
{
    const QJsonArray content = message.value("content").toArray();

    for (const QJsonValue& value : content) {
        const QJsonObject block = value.toObject();
        if (block.value("type").toString() != QLatin1String("tool_result"))
            continue;

        // The payload is a string, or a list of blocks that each hold one —
        // both shapes are legal and which one arrives depends on the tool.
        QString          text;
        const QJsonValue payload = block.value("content");
        if (payload.isString()) {
            text = payload.toString();
        } else if (payload.isArray()) {
            for (const QJsonValue& part : payload.toArray()) {
                const QJsonObject piece = part.toObject();
                if (piece.value("type").toString() == QLatin1String("text"))
                    text += piece.value("text").toString();
            }
        }

        const QString id = block.value("tool_use_id").toString();
        Q_EMIT toolEnded(id, _calls.take(id), shorten(text.trimmed()), block.value("is_error").toBool());
    }
}
