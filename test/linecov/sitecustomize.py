"""
Writes down which lines of videocode/ a Python process runs, for test/mutants.py.

Python imports `sitecustomize` at startup from anywhere on PYTHONPATH, so a
test file, every process it starts and the interpreter embedded in
./video-code are all recorded, not only the test itself. Nothing happens unless
VC_LINECOV names the folder to write into (./test/run_tests.sh sets it up).

One line per first run of a line, written straight to the file: the editor
tests stop `--serve` with a signal, and a process that never reaches its
atexit hooks would otherwise take everything it ran with it.
"""

import os
import sys

out = os.environ.get("VC_LINECOV")
if out and hasattr(sys, "monitoring"):
    root = os.path.realpath(os.environ["VC_LINECOV_ROOT"])
    library = os.path.join(root, "videocode") + os.sep
    tag = os.path.basename(os.environ.get("VC_LINECOV_TEST", "unknown"))
    fd = os.open(os.path.join(out, f"{tag}.{os.getpid()}"), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    known: dict[str, str | None] = {}
    monitoring = sys.monitoring

    def line(code, number):  # type: ignore[no-untyped-def]
        name = code.co_filename
        if name not in known:
            path = os.path.realpath(name)
            known[name] = os.path.relpath(path, root) if path.startswith(library) else None
        if known[name]:
            os.write(fd, f"{known[name]}:{number}\n".encode())
        # Each place reports once and is then switched off: the cost is one
        # call per line ever run, not one per line run.
        return monitoring.DISABLE

    monitoring.use_tool_id(monitoring.COVERAGE_ID, "vc-linecov")
    monitoring.register_callback(monitoring.COVERAGE_ID, monitoring.events.LINE, line)
    monitoring.set_events(monitoring.COVERAGE_ID, monitoring.events.LINE)
