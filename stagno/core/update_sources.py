"""Da dove arrivano gli aggiornamenti (le release di GitHub) e come si installano, per sistema.

- Linux (.deb installato in /opt/stagno): il nuovo .deb si installa con `pkexec apt-get`, che chiede la
  password in una normale finestra di sistema; poi Stagno si riavvia.
- Windows (installato col wizard): il nuovo setup parte in silenzio, chiude Stagno, lo aggiorna sul
  posto e lo riapre.
- Altro (da sorgente, copia portatile): la finestra rimanda alla pagina della release.

Questo è l'unico codice di Stagno che parla col web normale, e lo fa da Python, mai dal motore web.
"""
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

from .i18n import _
from .updates import ReleaseAsset, ReleaseInfo, UpdateError

API = "https://api.github.com/repos/{repo}/releases/latest"
CHUNK = 256 * 1024


class GitHubReleaseFeed:
    def __init__(self, repo, version, opener=urllib.request.urlopen, folder=None, timeout=30):
        self._repo = repo
        self._headers = {"Accept": "application/vnd.github+json", "User-Agent": "Stagno/%s" % version}
        self._open, self._folder, self._timeout = opener, folder, timeout

    def latest(self):
        request = urllib.request.Request(API.format(repo=self._repo), headers=self._headers)
        try:
            with self._open(request, timeout=self._timeout) as response:
                data = json.loads(response.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:                      # nessuna release ancora (o repo non pubblico)
                return None
            if e.code in (403, 429):
                raise UpdateError(_("GitHub is limiting update checks right now: try again in an hour.")) from e
            raise UpdateError(_("GitHub answered with an error ({code}).", code=e.code)) from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise UpdateError(_("Can't reach GitHub to check for updates. Check your internet connection.")) from e
        except ValueError as e:
            raise UpdateError(_("GitHub sent an answer Stagno doesn't understand.")) from e
        if data.get("draft") or data.get("prerelease"):
            return None
        assets = []
        for a in data.get("assets", []):
            digest = a.get("digest") or ""
            assets.append(ReleaseAsset(a["name"], a["browser_download_url"], int(a["size"]),
                                       digest.split(":", 1)[1] if digest.startswith("sha256:") else None))
        return ReleaseInfo(data["tag_name"].lstrip("v"), data.get("body") or "",
                           data.get("html_url", ""), tuple(assets))

    def download(self, asset, progress):
        folder = self._folder or Path(tempfile.gettempdir()) / "stagno-update"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / Path(asset.name).name           # solo il nome: niente percorsi dalla rete
        partial = target.with_name(target.name + ".part")
        request = urllib.request.Request(asset.url, headers={"User-Agent": self._headers["User-Agent"]})
        digest, done = hashlib.sha256(), 0
        try:
            with self._open(request, timeout=self._timeout) as response, open(partial, "wb") as out:
                while chunk := response.read(CHUNK):
                    out.write(chunk)
                    digest.update(chunk)
                    done += len(chunk)
                    progress(done, asset.size)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            partial.unlink(missing_ok=True)
            raise UpdateError(_("The download didn't finish. Check your internet connection and try again.")) from e
        if done != asset.size or (asset.sha256 and digest.hexdigest() != asset.sha256.lower()):
            partial.unlink(missing_ok=True)
            raise UpdateError(_("The download was damaged (its checksum doesn't match), so it wasn't "
                                "installed. Try again."))
        partial.replace(target)
        return str(target)


def deb_architecture():
    machine = platform.machine().lower()
    return {"x86_64": "amd64", "amd64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(machine, machine)


class DebInstaller:
    """Per la copia .deb, che vive in /opt/stagno."""

    PREFIX = Path("/opt/stagno")

    def __init__(self, executable=None, runner=subprocess.run):
        self._executable, self._run = Path(executable or sys.executable), runner

    def supported(self):
        return (getattr(sys, "frozen", False) and self._executable.resolve().is_relative_to(self.PREFIX)
                and shutil.which("pkexec") is not None)

    def pick(self, assets):
        suffix = "_%s.deb" % deb_architecture()
        return next((a for a in assets if a.name.endswith(suffix)), None)

    def install(self, path):
        # pkexec mostra la finestra della password di sistema; apt controlla il pacchetto e aggiorna.
        result = self._run(["pkexec", "apt-get", "install", "-y", "--allow-downgrades", os.path.abspath(path)],
                           capture_output=True, text=True)
        if result.returncode in (126, 127):
            raise UpdateError(_("Installing was cancelled."))
        if result.returncode != 0:
            detail = (result.stderr or result.stdout or "").strip().splitlines()[-1:]
            raise UpdateError(_("Installing the update failed: {detail}", detail=detail[0])
                              if detail else _("Installing the update failed."))
        return False          # installato: va riavviato per usarlo


class WindowsSetupInstaller:
    """Per la copia installata dal wizard (ha il suo disinstallatore accanto)."""

    def __init__(self, executable=None, launcher=subprocess.Popen):
        self._executable, self._launch = Path(executable or sys.executable), launcher

    def supported(self):
        return getattr(sys, "frozen", False) and any(self._executable.parent.glob("unins*.exe"))

    def pick(self, assets):
        return next((a for a in assets if a.name.endswith("-windows-x64-setup.exe")), None)

    def install(self, path):
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            self._launch([path, "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/CLOSEAPPLICATIONS"],
                         creationflags=flags, close_fds=True)
        except OSError as e:
            raise UpdateError(_("Couldn't start the installer.")) from e
        return True           # il setup prende il controllo: esci per fargli sostituire i file


class NoInstaller:
    """Da sorgente o copia portatile: rimanda alla pagina di download."""

    def supported(self):
        return False

    def pick(self, assets):
        return None

    def install(self, path):
        raise UpdateError(_("This copy of Stagno can't update itself."))


def platform_installer():
    if sys.platform == "win32":
        return WindowsSetupInstaller()
    if sys.platform.startswith("linux"):
        return DebInstaller()
    return NoInstaller()
