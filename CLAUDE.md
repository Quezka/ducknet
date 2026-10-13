# DuckNet / Stagno

Playful alternative to HTTP by Quezka. Python 3.10+, stdlib only for DuckNet; the browser Stagno is
PySide6 + QtWebEngine. One repo, one version (`ducknet/__init__.py`), Italian docs in `docs/`.
Shared memory note: `ducknet-project` in the user's claude-memory repo (read it first).

- `ducknet/` protocol DUCK/1, registry, DNS (UDP 53), relay (TCP 4343, reverse tunnels), host, client, CLI. No Qt, no `stagno` imports.
- `stagno/core/` browser logic with NO Qt (address parsing, fetcher, HTML pages, memes, i18n); `stagno/ui/` Qt only. `tests/test_architecture.py` enforces it.
- Run/test: no venv here; use `../ligature/.venv/bin/python -m unittest discover -s tests` (has PySide6 + PyInstaller). UI tests need `QT_QPA_PLATFORM=offscreen` (set by the tests).
- Stagno never opens http(s): `OnlyDuckInterceptor` + `DuckPage.acceptNavigationRequest`. Keep that. `duck://stagno/` is the internal page host (no `.duck`, so no host can spoof it).
- UI text: wrap in `_()` / `N_()`, add it + ru to `stagno/core/catalogs.py` (tests check both).
- Packaging (like Quire/Ligature): `python scripts/build.py --deb` (Linux) and `--installer` (Windows, Inno Setup, `packaging/stagno.iss`, per-user). The .exe can only be built on Windows, i.e. by `.github/workflows/build.yml` on a `v*` tag. Never change the Inno `AppId`. `DEPENDS` in `scripts/deb.py` came from `ldd` over the frozen app.
- Release: bump `ducknet.__version__`, add CHANGELOG + metainfo `<release>` (tests/test_release.py checks), tag `vX.Y.Z`.
- `install.sh`/`uninstall.sh` are the from-source per-user install (venv in ~/.local/share/stagno).
- asyncio gotcha (bit us on CI, Python 3.12): the loop keeps only WEAK references to tasks. Always keep a strong reference to fire-and-forget tasks (`host.py` keeps `self._tasks`). Local Python is 3.14, CI is 3.12: a bug that "works here" can still fail in CI.
- Qt gotcha: delete web pages before their `QWebEngineProfile` (`MainWindow.closeEvent`), else a warning and a segfault at exit.
- OTA updates (0.4.0): `stagno/core/updates.py` (use case) + `update_sources.py` (GitHub feed, .deb/Windows installers) + `ui/updates_ui.py`. Asset names `stagno_<v>_<arch>.deb` / `Stagno-<v>-windows-x64-setup.exe` and the Inno `skipifnotsilent` restart line are load-bearing. Stagno asks consent before any automatic check; never make it check silently. Only this code touches the regular web, from Python, never from the web engine.
