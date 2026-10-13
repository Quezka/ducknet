# Changelog

All notable changes to DuckNet and its browser Stagno. Versions follow [Semantic Versioning](https://semver.org):
patch for fixes, minor for new features, major for breaking changes (while below 1.0,
breaking changes bump the minor version).

## [0.4.0] - 2026-10-13

- Stagno can update itself: "Check for updates…" in the menu, and an automatic check about once a day. It asks your permission the first time (and there is a switch in Settings). Updates come from the GitHub releases, are checked against their SHA-256, and install through `pkexec apt` on Linux or silently with the setup on Windows; other copies are pointed to the download page.

## [0.3.1] - 2026-10-13

- Fix: the host could silently stop answering (its tasks were garbage-collected on some Python versions), so pages showed as offline.
- Fix: Stagno cleans up its web pages before its profile when it closes (no crash or warning at exit).
- Add the GPL-3.0 licence file.

## [0.3.0] - 2026-10-13

- Stagno is now installable: a `.deb` for Debian and Ubuntu, and a Windows setup wizard (per user, no admin needed). Both register Stagno as the program for `duck://` links.

## [0.2.0] - 2026-10-13

- Stagno, the DuckNet browser: native Qt window with tabs, light and dark theme, English, Italian and Russian, and generated memes. It only opens `duck://` and never regular web pages.

## [0.1.0] - 2026-10-13

- DuckNet: the DUCK/1 protocol, the DNS server for `.duck` names, the relay with reverse tunnels, the host that publishes a folder, and the `ducknet` command.
