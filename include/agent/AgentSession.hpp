/*
** EPITECH PROJECT, 2026
** video-code
** File description:
** AgentSession
*/

#pragma once

#include <QByteArray>
#include <QHash>
#include <QJsonObject>
#include <QObject>
#include <QProcess>
#include <QString>
#include <QVariantList>

namespace VC
{
    // -----------------------------------------------------------------------
    // AgentSession
    //   Claude Code, talking to the Agent pane.
    //
    //   Shape
    //   ─────
    //   The same shape as LanguageServer, and for the same reason: a child
    //   process that speaks JSON on its stdin and stdout.  pyright frames with
    //   Content-Length; `claude --output-format stream-json` writes one JSON
    //   object per line, which is simpler and needs no header parsing.
    //
    //   Why the CLI and not a library
    //   ─────────────────────────────
    //   `claude` IS the agent — the loop, the tools, the permissions, the
    //   sessions.  The Messages API underneath it gives a model and nothing
    //   else; reaching for it would mean writing Claude Code again.  The
    //   official SDK exists only in TypeScript and Python, so linking it would
    //   put a third process between this one and the agent for no gain.
    //
    //   Why not the terminal
    //   ────────────────────
    //   The interactive `claude` draws a TUI: colour codes, cursor moves, a
    //   redrawn frame per keystroke.  The Agent pane is a list of messages, not
    //   a terminal emulator, and `stream-json` hands over the same conversation
    //   already taken apart — one event per assistant message, per tool call,
    //   per tool result.  That is exactly what the pane was drawn to show.
    //
    //   One process, many turns
    //   ───────────────────────
    //   With `--input-format stream-json` the child stays up between questions
    //   and keeps its context: measured, asking it to remember a number and
    //   then asking for it back works across two turns on one process.  A
    //   `result` event closes each turn.  An `init` event opens each one — NOT
    //   only the first, so it is not the sign of a new session.
    // -----------------------------------------------------------------------
    class AgentSession : public QObject
    {
        Q_OBJECT
        Q_PROPERTY(bool busy READ busy NOTIFY busyChanged)
        Q_PROPERTY(bool running READ running NOTIFY runningChanged)
        Q_PROPERTY(QString sessionId READ sessionId NOTIFY sessionIdChanged)
        //: What this conversation has cost so far, in dollars. Shown rather
        //: than hidden: an agent that reads twenty files to answer one question
        //: should say so.
        Q_PROPERTY(double spent READ spent NOTIFY spentChanged)
        //: Whether the last turn can still be taken back as one piece. True
        //: from the moment the agent changes the file until the author edits it
        //: themselves — accepting does NOT clear it, because the reason to undo
        //: is usually the preview, which is only seen after accepting.
        Q_PROPERTY(bool revertable READ revertable NOTIFY revertableChanged)
        //: A turn has landed and has not been accepted or dropped: the editor
        //: is showing colours and the scene has NOT been run.
        Q_PROPERTY(bool pending READ pending NOTIFY pendingChanged)

    public:

        explicit AgentSession(QObject* parent = nullptr);
        ~AgentSession() override;

        bool busy() const { return _busy; }

        bool running() const;

        QString sessionId() const { return _session; }

        double spent() const { return _spent; }

        bool revertable() const;

        bool pending() const { return _pending; }

        //: The project the agent is allowed to work in. Set before the first
        //: question; changing it later restarts the child.
        Q_INVOKABLE void setRoot(const QString& root);

        //: The file `revert()` puts back. One file, not the whole tree: the
        //: scene is what the agent is asked to change here, and promising to
        //: undo more than we snapshot would be a lie.
        Q_INVOKABLE void watch(const QString& path);

        Q_INVOKABLE void ask(const QString& text);
        Q_INVOKABLE void interrupt();

        //: The turn's changes, line by line, as the pane draws them: a list of
        //: `{kind, text}` where kind is "same", "add" or "del". The whole file,
        //: not a hunk — the pane IS the file, and a line it does not receive is
        //: a line it would have to invent.
        Q_INVOKABLE QVariantList diff() const;

        //: The text as it stands if the turn is taken — every line but the
        //: deletions. What `accept()` writes, and what the editor shows once it
        //: has stopped colouring.
        Q_INVOKABLE QString accepted() const;

        //: Keep the turn. The file already holds this text — the agent wrote it
        //: — so accepting only stops the colouring and lets the scene run.
        Q_INVOKABLE void accept();

        //: Drop the turn, before OR after accepting. The snapshot is kept until
        //: the author types something of their own, because "undo what the
        //: agent did" stops being a safe thing to offer the moment there is
        //: work of theirs sitting on top of it.
        Q_INVOKABLE bool revert();

        //: Called when the author edits the buffer themselves: the turn stops
        //: being undoable as one piece, and Cmd+Z goes back to being the
        //: editor's own undo.
        Q_INVOKABLE void disarm();

        Q_INVOKABLE void stop();

    Q_SIGNALS:
        //: A sentence from the agent.
        void said(const QString& text);
        //: It is reasoning. `tokens` is how much so far: the stream counts
        //: while it thinks and — measured on 2 Oct. 2026 — hands over an EMPTY
        //: block once it has, the words signed and withheld. `text` is those
        //: words, for a model that does give them.
        void thinking(int tokens, const QString& text);
        //: It is about to use a tool. `summary` is a short human line — the
        //: file for a read, the command for a shell call — and `input` its
        //: arguments as they were sent. `id` is what the answer will carry.
        void toolStarted(const QString& id, const QString& name, const QString& summary, const QString& input);
        //: The tool answered. Matched to its call by `id` and NOT by arrival
        //: order: calls go out in parallel and come back in whichever order they
        //: finish — measured, two `Read`s returned with the failing one first.
        void toolEnded(const QString& id, const QString& name, const QString& output, bool failed);
        //: The turn is over. `error` is empty when it ended normally.
        void turnEnded(double cost, const QString& error);
        //: The child could not be started, or died.
        void failed(const QString& why);

        void busyChanged();
        void runningChanged();
        void sessionIdChanged();
        void spentChanged();
        void revertableChanged();
        void pendingChanged();
        //: The agent finished and the file is not what it was. The pane colours
        //: the buffer and waits — it does NOT run the scene.
        void changed();

    private:

        void ensureStarted();
        void readAvailable();
        void handle(const QJsonObject& event);
        void handleAssistant(const QJsonObject& message);
        void handleToolResult(const QJsonObject& message);
        void setBusy(bool busy);

        QProcess   _agent;
        QByteArray _inbox;
        //: tool_use id -> tool name, so a result can say what it answered.
        QHash<QString, QString> _calls;
        QString                 _root;
        QString                 _session;
        QString                 _watched;
        //: The watched file as it stood when the current turn opened.
        QByteArray _before;
        //: The file as it stood before the turn, and as it stands after it.
        //: Both kept: the diff is drawn from the pair, and `revert()` needs the
        //: first one however the turn ended.
        QByteArray _after;
        bool       _hasSnapshot = false;
        bool       _pending = false;
        bool       _busy = false;
        bool       _stopping = false;
        double     _spent = 0.0;
    };
}
