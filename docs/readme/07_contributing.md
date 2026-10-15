### Contributing

Nothing blocks a push. GitHub Actions checks types, the test suites, the build,
the QML, and whether new public API arrived documented and tested. It also
keeps the perf record: it cannot measure this renderer — a shared runner has no
GPU and rasterises ~30x slower — so the timings are measured here and travel in
the commit, and CI publishes the curve. What CI *can* measure exactly is what
the scenes ask the renderer to do, and it holds that to zero tolerance.

The two gates that need this machine's GPU — visual regression and the
performance baseline — are one command, run when you want them:

```bash
make check
```

Arm the pre-commit hook once per clone (coverage, types, the QML chrome, ~15s):

```bash
make arm
```

See [docs/WORKFLOWS.md](docs/WORKFLOWS.md) for what each gate can and cannot
decide, and how to re-baseline performance deliberately.
