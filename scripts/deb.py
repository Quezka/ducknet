"""Wrap a PyInstaller folder build of Stagno into an installable .deb.

Layout inside the package:
    /opt/stagno/                      the frozen app (binary + bundled Qt/Python)
    /usr/bin/stagno                   symlink to /opt/stagno/Stagno
    /usr/share/applications/<APP_ID>.desktop
    /usr/share/metainfo/<APP_ID>.metainfo.xml   developer/publisher info for app stores
    /usr/share/icons/hicolor/...        scalable SVG + 256px PNG named <APP_ID>

The desktop database and icon cache refresh through dpkg triggers, so no
maintainer scripts are needed.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import stagno  # noqa: E402  (release metadata only; no Qt imports)

PACKAGING = ROOT / "packaging"

# Bundled Qt and Chromium (QtWebEngine) still link against these system libraries. The list comes
# from `ldd` over the whole frozen app; the "a | b" forms cover both the Debian 12 / Ubuntu 22.04
# names and the t64 names of Debian 13 / Ubuntu 24.04+.
DEPENDS = [
    "libc6", "libegl1", "libgl1", "libfontconfig1", "libfreetype6", "libdbus-1-3",
    "libglib2.0-0t64 | libglib2.0-0",
    "libnss3", "libnspr4", "libdrm2", "libgbm1", "libpulse0",
    "libasound2t64 | libasound2",
    "libcups2t64 | libcups2",
    "libatk1.0-0t64 | libatk1.0-0",
    "libatk-bridge2.0-0t64 | libatk-bridge2.0-0",
    "libxkbcommon0", "libxkbcommon-x11-0", "libxkbfile1",
    "libx11-6", "libx11-xcb1", "libxext6", "libxfixes3", "libxi6", "libxcursor1", "libxrender1",
    "libxcomposite1", "libxdamage1", "libxrandr2", "libxtst6",
    "libxcb1", "libxcb-cursor0", "libxcb-icccm4", "libxcb-image0", "libxcb-keysyms1",
    "libxcb-render-util0", "libxcb-shape0", "libxcb-xkb1",
]


def _architecture() -> str:
    return subprocess.run(["dpkg", "--print-architecture"], check=True,
                          capture_output=True, text=True).stdout.strip()


def _installed_size_kib(root: Path) -> int:
    total = sum(p.lstat().st_size for p in root.rglob("*") if not p.is_dir())
    return (total + 1023) // 1024


def build_deb(app_dir: Path, png_icon: Path, out_dir: Path, work_dir: Path) -> Path:
    if shutil.which("dpkg-deb") is None:
        raise SystemExit("dpkg-deb not found; build the .deb on a Debian/Ubuntu system")
    version, arch, app_id = stagno.__version__, _architecture(), stagno.APP_ID
    stage = work_dir / "deb-root"
    shutil.rmtree(stage, ignore_errors=True)

    opt = stage / "opt" / "stagno"
    shutil.copytree(app_dir, opt, symlinks=True)

    bin_dir = stage / "usr" / "bin"
    bin_dir.mkdir(parents=True)
    os.symlink("/opt/stagno/Stagno", bin_dir / "stagno")

    share = stage / "usr" / "share"
    for folder, name in [("applications", f"{app_id}.desktop"),
                         ("metainfo", f"{app_id}.metainfo.xml")]:
        (share / folder).mkdir(parents=True)
        shutil.copy(PACKAGING / name, share / folder / name)
    doc = share / "doc" / "stagno"
    doc.mkdir(parents=True)
    year = __import__("datetime").date.today().year
    (doc / "copyright").write_text(
        "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/\n"
        f"Upstream-Name: Stagno\nSource: {stagno.HOMEPAGE}\n\n"
        f"Files: *\nCopyright: {year} {stagno.DEVELOPER} <{stagno.MAINTAINER_EMAIL}>\n"
        "License: GPL-3.0-or-later\n"
        " On Debian systems, the full text of the GNU General Public License version 3\n"
        " can be found in /usr/share/common-licenses/GPL-3.\n")
    icons = share / "icons" / "hicolor"
    (icons / "scalable" / "apps").mkdir(parents=True)
    shutil.copy(ROOT / "stagno" / "assets" / "stagno.svg", icons / "scalable" / "apps" / f"{app_id}.svg")
    (icons / "256x256" / "apps").mkdir(parents=True)
    shutil.copy(png_icon, icons / "256x256" / "apps" / f"{app_id}.png")

    for path in stage.rglob("*"):
        if path.is_symlink():
            continue
        if path.is_dir() or os.access(path, os.X_OK):
            path.chmod(0o755)
        else:
            path.chmod(0o644)

    debian = stage / "DEBIAN"
    debian.mkdir()
    (debian / "control").write_text(
        f"Package: stagno\n"
        f"Version: {version}\n"
        f"Architecture: {arch}\n"
        f"Maintainer: {stagno.DEVELOPER} <{stagno.MAINTAINER_EMAIL}>\n"
        f"Installed-Size: {_installed_size_kib(stage)}\n"
        f"Depends: {', '.join(DEPENDS)}\n"
        f"Section: utils\n"
        f"Priority: optional\n"
        f"Homepage: {stagno.HOMEPAGE}\n"
        f"Description: browser for DuckNet, the playful alternative to HTTP\n"
        f" Stagno opens duck:// addresses: it asks the DuckNet DNS where a name lives\n"
        f" and speaks the DUCK/1 protocol through the DuckNet relay. It never opens\n"
        f" regular http(s) pages. It has tabs, a light and a dark theme, and memes.\n"
    )
    debian.chmod(0o755)
    (debian / "control").chmod(0o644)

    out_dir.mkdir(parents=True, exist_ok=True)
    deb = out_dir / f"stagno_{version}_{arch}.deb"
    subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", str(stage), str(deb)],
                   check=True)
    return deb
