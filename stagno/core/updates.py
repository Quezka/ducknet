"""Aggiornamenti dall'interno di Stagno: il caso d'uso (senza rete, senza Qt).

`check()` e `download()` parlano con la rete (da eseguire su un thread); `install()` può restare
bloccato mentre l'installer di sistema lavora, quindi va su un thread anch'esso.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional, Protocol

from .i18n import _

CHECK_EVERY = timedelta(hours=20)


class UpdateError(Exception):
    """Un errore da mostrare all'utente così com'è (il testo è già tradotto)."""


@dataclass(frozen=True)
class ReleaseAsset:
    name: str
    url: str
    size: int
    sha256: Optional[str] = None


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    notes: str
    page_url: str
    assets: tuple = ()


@dataclass(frozen=True)
class AvailableUpdate:
    version: str
    current: str
    notes: str
    page_url: str
    asset: Optional[ReleaseAsset]    # il file giusto per questo computer
    can_install: bool                # False: si manda l'utente alla pagina di download


class ReleaseFeed(Protocol):
    def latest(self) -> Optional[ReleaseInfo]: ...
    def download(self, asset: ReleaseAsset, progress: Callable[[int, int], None]) -> str: ...


class UpdateInstaller(Protocol):
    def supported(self) -> bool: ...
    def pick(self, assets) -> Optional[ReleaseAsset]: ...
    def install(self, path: str) -> bool: ...     # True: l'installer ha preso il controllo, chiudi


class KeyValueStore(Protocol):
    def get(self, key: str) -> Optional[str]: ...
    def set(self, key: str, value: str) -> None: ...


def parse_version(text):
    """"v0.11.0" -> (0, 11, 0); quello che non si capisce vale «il più vecchio»."""
    numbers = re.findall(r"\d+", text.split("-")[0])
    return tuple(int(n) for n in numbers[:3]) if numbers else (0,)


class UpdateService:
    PREFIX = "updates."

    def __init__(self, feed, installer, settings, current_version, now=datetime.now):
        self._feed, self._installer, self._settings, self._now = feed, installer, settings, now
        self.current_version = current_version

    # -- consenso: Stagno non parla con Internet finché l'utente non lo permette -----------------------
    def auto_check(self):
        """True = sì, False = no, None = non ancora chiesto."""
        value = self._settings.get(self.PREFIX + "auto")
        return None if value is None else value != "0"

    def set_auto_check(self, on):
        self._settings.set(self.PREFIX + "auto", "1" if on else "0")

    def due(self):
        """È ora del controllo automatico (circa una volta al giorno)? Solo se l'utente ha detto sì."""
        if self.auto_check() is not True:
            return False
        last = self._settings.get(self.PREFIX + "last_check")
        return not last or self._now() - datetime.fromisoformat(last) >= CHECK_EVERY

    def mark_checked(self):
        self._settings.set(self.PREFIX + "last_check", self._now().isoformat(timespec="seconds"))

    def skip(self, version):
        self._settings.set(self.PREFIX + "skipped", version)

    def skipped(self, version):
        return self._settings.get(self.PREFIX + "skipped") == version

    # -- i casi d'uso ---------------------------------------------------------------------------------
    def check(self):
        """L'ultima release, se è più nuova di questa copia."""
        release = self._feed.latest()
        if release is None or parse_version(release.version) <= parse_version(self.current_version):
            return None
        asset = self._installer.pick(release.assets)
        return AvailableUpdate(release.version, self.current_version, release.notes, release.page_url,
                               asset, asset is not None and self._installer.supported())

    def download(self, update, progress):
        if update.asset is None:
            raise UpdateError(_("There's no download for this computer in that release."))
        return self._feed.download(update.asset, progress)

    def install(self, path):
        return self._installer.install(path)
