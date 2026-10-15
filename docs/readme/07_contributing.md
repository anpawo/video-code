### Contributing

Nothing blocks a push. GitHub Actions checks types, the test suites, the build,
the QML, and whether new public API arrived documented and tested. The two gates
that need this machine's GPU — visual regression and the performance baseline —
are `make check`, run when you want them; the timings it measures travel in the
commit, and CI publishes the curve. `make arm` arms the pre-commit hook once per
clone.

[CONTRIBUTING.md](CONTRIBUTING.md) has the rest: building a change, which binary
the tests run, the commit conventions, and the licence of a contribution.
[docs/WORKFLOWS.md](docs/WORKFLOWS.md) has what each gate can and cannot decide.
