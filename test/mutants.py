#!/usr/bin/env python3

"""
Does a test fail when a line the push adds to videocode/ is wrong?

coverage_check.py asks whether a new public NAME appears in a test. That says
nothing of a new branch inside an old function, nor of a line no test runs.
This holds every line a range adds to the library to two things:

  1. it runs under at least one test file, as recorded by
     test/linecov/sitecustomize.py while ./test/run_tests.sh runs;
  2. it is checked, not only run: each small wrong version of it (a comparison
     turned round, + made -, and made or, True made False, a number moved by
     one) makes one of the test files that run it fail. A wrong version that
     every one of them lets through is a mutant that survived.

A line that cannot be held to that says why, on the line: `# untested: <why>`.

It rewrites library files to do this, so on its own it works in a throwaway
worktree of HEAD, never in the tree you or another session are editing.

    python3 test/mutants.py                   # what HEAD has that the remote does not
    python3 test/mutants.py --range A..HEAD   # any range that ends at HEAD
    python3 test/mutants.py --here --recorded DIR --range A..B
                                              # CI: in place, the suite already recorded in DIR
"""

from __future__ import annotations

import argparse
import ast
import io
import keyword
import os
import signal
import subprocess
import sys
import tempfile
import time
import tokenize
import warnings
from collections import defaultdict
from pathlib import Path
from types import CodeType

# One wrong version per token. Whatever does not compile is dropped, which is
# what keeps `for x in y` from becoming `for x not in y`.
SWAP = {
    "==": "!=", "!=": "==", "<": ">=", ">=": "<", ">": "<=", "<=": ">",
    "+": "-", "-": "+", "*": "/", "/": "*", "//": "/", "%": "//",
    "+=": "-=", "-=": "+=", "*=": "/=", "/=": "*=",
    "and": "or", "or": "and", "True": "False", "False": "True",
    "in": "not in", "is": "is not", "not": "",
}  # fmt: skip
# `def f(a, *, b)` made `def f(a, /, b)` compiles, and no test can tell: these
# four only count between two operands.
BINARY_ONLY = {"*", "/", "//", "%"}
SKIP = {tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT}
EXEMPT = "# untested:"


def run(*args: str) -> str:
    return subprocess.run(args, capture_output=True, text=True).stdout


def endsOperand(token: tokenize.TokenInfo | None) -> bool:
    if token is None:
        return False
    if token.type == tokenize.NAME:
        return not keyword.iskeyword(token.string) or token.string in ("True", "False", "None")
    return token.type in (tokenize.NUMBER, tokenize.STRING, tokenize.FSTRING_END) or token.string in ")]}"


def bump(number: str) -> str | None:
    try:
        return str(int(number, 0) + 1)
    except ValueError:
        pass
    try:
        return repr(float(number) + 1)
    except ValueError:
        return None  # 2j


def mutants(source: str, number: int) -> list[tuple[str, str]]:
    """Every wrong version of line `number` that still compiles: (what changed, whole new source)."""
    lines = source.splitlines(keepends=True)
    tokens = [t for t in tokenize.generate_tokens(io.StringIO(source).readline) if t.type not in SKIP]
    out: list[tuple[str, str]] = []
    for i, token in enumerate(tokens):
        if token.start[0] != number or token.end[0] != number:
            continue
        before = tokens[i - 1] if i else None
        after = tokens[i + 1] if i + 1 < len(tokens) else None
        new = bump(token.string) if token.type == tokenize.NUMBER else SWAP.get(token.string)
        if new is None or token.type not in (tokenize.NUMBER, tokenize.NAME, tokenize.OP):
            continue
        if token.string in BINARY_ONLY and not endsOperand(before):
            continue
        if token.string == "is" and after is not None and after.string == "not":
            continue  # `is not` loses its `not` instead
        line = lines[number - 1]
        start, end = token.start[1], token.end[1]
        if not new and line[end : end + 1] == " ":
            end += 1
        text = "".join(lines[: number - 1]) + line[:start] + new + line[end:] + "".join(lines[number:])
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                compile(text, "<mutant>", "exec")
        except SyntaxError:
            continue
        out.append((f"{token.string} → {new or '(removed)'}", text))
    return out


def hunks(patch: str) -> dict[str, set[int]]:
    """{file: line numbers in the new version} for what a `git diff -U0` adds to Python files."""
    out: dict[str, set[int]] = defaultdict(set)
    current = ""
    for line in patch.splitlines():
        if line.startswith("+++ "):
            path = line[4:]
            current = path[2:] if path.startswith("b/") and path.endswith(".py") else ""
        elif line.startswith("@@") and current:
            start, _, count = line.split()[2][1:].partition(",")
            out[current].update(range(int(start), int(start) + (int(count) if count else 1)))
    return dict(out)


def runnable(code: CodeType) -> set[int]:
    lines = {line for _, _, line in code.co_lines() if line is not None}
    for const in code.co_consts:
        if isinstance(const, CodeType):
            lines |= runnable(const)
    return lines


def statements(source: str, path: str, numbers: set[int]) -> dict[int, int]:
    """
    {added line: first line of the statement it is part of}, for the lines that are code.

    The first line, because a statement spread over three lines reports itself
    as run on its first one only. Comments, blank lines and docstrings are not
    code, and neither is a line marked EXEMPT.
    """
    tree = ast.parse(source)
    nodes = [n for n in ast.walk(tree) if isinstance(n, ast.stmt)]
    code = runnable(compile(source, path, "exec"))
    text = source.splitlines()
    out: dict[int, int] = {}
    for n in sorted(numbers):
        line = text[n - 1].strip() if n <= len(text) else ""
        if not line or line.startswith("#"):
            continue
        owners = [s.lineno for s in nodes if s.lineno <= n <= (s.end_lineno or s.lineno)]
        if not owners:
            continue
        first = max(owners)
        if first in code and EXEMPT not in line and EXEMPT not in text[first - 1]:
            out[n] = first
    return out


def record() -> Path:
    folder = Path(tempfile.mkdtemp(prefix="vc-linecov-"))
    log = folder.parent / f"{folder.name}.log"
    print(f"running the suite once to see which lines each test file runs (log: {log})")
    with log.open("w") as out:
        status = subprocess.run(["./test/run_tests.sh"], env={**os.environ, "VC_LINECOV": str(folder)}, stdout=out, stderr=out)
    if status.returncode != 0:
        print(log.read_text()[-3000:])
        sys.exit("the suite fails before anything is mutated: fix that first")
    return folder


def recorded(folder: Path) -> tuple[dict[tuple[str, int], set[str]], dict[str, float]]:
    runs: dict[tuple[str, int], set[str]] = defaultdict(set)
    took: dict[str, float] = {}
    for f in folder.iterdir():
        if f.name == "durations":
            for line in f.read_text().splitlines():
                test, _, seconds = line.rpartition(" ")
                took[test] = float(seconds)
            continue
        test = "test/" + f.name.rsplit(".", 1)[0]
        if not test.endswith("_test.py"):
            continue
        for line in f.read_text().splitlines():
            path, _, n = line.rpartition(":")
            runs[(path, int(n))].add(test)
    return runs, took


def fails(test: str, limit: float) -> bool:
    env = {k: v for k, v in os.environ.items() if not k.startswith("VC_LINECOV")}
    # A mutant's bytecode left in __pycache__ would be run again as the real
    # file: same size, and the restore can land within the same second.
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    child = subprocess.Popen([sys.executable, test], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return child.wait(timeout=limit) != 0
    except subprocess.TimeoutExpired:
        return True  # a test the mutant hangs has noticed it
    finally:
        # The editor tests start `--serve`; a test the mutant broke halfway may
        # not stop it.
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def resolve(span: str) -> str:
    a, _, b = span.partition("..")
    b = b or "HEAD"
    # A new branch's push names no `before`, and a forced one names a commit
    # the clone may not have.
    if not a or set(a) == {"0"} or subprocess.run(["git", "cat-file", "-e", f"{a}^{{commit}}"], capture_output=True).returncode:
        a = run("git", "merge-base", "origin/main", b).strip()
    return f"{a}..{b}"


def check(span: str, folder: Path | None, budget: float) -> int:
    added = {f: n for f, n in hunks(run("git", "diff", "-U0", "--no-color", span, "--", "videocode/")).items() if Path(f).exists()}
    owned = {f: statements(Path(f).read_text(), f, n) for f, n in added.items()}
    owned = {f: o for f, o in owned.items() if o}
    if not owned:
        print(f"mutants: {span} adds no code to videocode/")
        return 0

    runs, took = recorded(folder or record())
    text = {f: Path(f).read_text().splitlines() for f in owned}
    untested = [(f, n) for f, o in owned.items() for n, first in o.items() if not runs.get((f, first))]
    for f, n in untested:
        print(f"untested  {f}:{n}  {text[f][n - 1].strip()}")

    deadline = time.monotonic() + budget
    killed, survived, unrun = 0, 0, 0
    for path, lines in owned.items():
        original = Path(path).read_bytes()
        stat = os.stat(path)
        try:
            for n, first in lines.items():
                tests = sorted(runs.get((path, first), ()), key=lambda t: took.get(t, 1e9))
                if not tests:
                    continue
                for what, source in mutants(original.decode(), n):
                    if time.monotonic() > deadline:
                        unrun += 1
                        continue
                    Path(path).write_text(source)
                    by = next((t for t in tests if fails(t, max(60.0, 3 * took.get(t, 60.0)))), None)
                    if by:
                        killed += 1
                        print(f"killed    {path}:{n}  {what}  by {by}")
                    else:
                        survived += 1
                        print(f"SURVIVED  {path}:{n}  {what}  — {len(tests)} test file(s) run this line, none failed: {', '.join(tests)}")
        finally:
            Path(path).write_bytes(original)
            os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns))

    print(f"\nmutants: {span}: {sum(map(len, owned.values()))} line(s) of code added, {len(untested)} run by no test; "
          f"{killed} mutant(s) killed, {survived} survived" + (f", {unrun} not run for want of time" if unrun else ""))
    if untested or survived:
        print("A test must run each line and fail when it is wrong. A line that cannot be held to that says why: `# untested: <why>`.")
        return 1
    return 0


def throwaway(span: str, budget: float) -> int:
    if run("git", "rev-parse", span.partition("..")[2]) != run("git", "rev-parse", "HEAD"):
        sys.exit("the range must end at HEAD: its lines are looked up in HEAD's files")
    home = Path.cwd()
    tree = Path(tempfile.mkdtemp(prefix="vc-mutants-")) / "tree"
    subprocess.run(["git", "worktree", "add", "--detach", "-q", str(tree), "HEAD"], check=True)
    try:
        # Neither is in git. .cache holds the compiled TeX, and a Mac with a
        # basic TeX Live cannot compile it again: mathtex_test fails without it.
        for kept in ("video-code", ".cache"):
            if (home / kept).exists():
                (tree / kept).symlink_to(home / kept)
        argv = [sys.executable, "test/mutants.py", "--here", "--range", span, "--budget", str(budget)]
        return subprocess.run(argv, cwd=tree).returncode
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(tree)])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--range", help="A..B; default: what HEAD has that its upstream does not")
    parser.add_argument("--here", action="store_true", help="mutate this tree in place (CI, or a throwaway worktree)")
    parser.add_argument("--recorded", type=Path, help="a folder ./test/run_tests.sh filled with VC_LINECOV set")
    parser.add_argument("--budget", type=float, default=1200, help="seconds of mutants before the rest are left unrun")
    args = parser.parse_args()
    upstream = run("git", "rev-parse", "--abbrev-ref", "@{upstream}").strip()
    span = resolve(args.range or f"{upstream or 'HEAD~1'}..HEAD")
    if not args.here:
        return throwaway(span, args.budget)
    return check(span, args.recorded, args.budget)


if __name__ == "__main__":
    sys.exit(main())
