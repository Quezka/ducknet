"""Aggiornamenti: il caso d'uso con finti, gli adattatori con risposte in scatola, la finestra senza rete."""
import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from stagno.core.update_sources import (DebInstaller, GitHubReleaseFeed, NoInstaller,  # noqa: E402
                                        WindowsSetupInstaller, deb_architecture)
from stagno.core.updates import (ReleaseAsset, ReleaseInfo, UpdateError, UpdateService,  # noqa: E402
                                 parse_version)

DEB = ReleaseAsset("stagno_9.0.0_%s.deb" % deb_architecture(), "https://x/stagno.deb", 10, None)
EXE = ReleaseAsset("Stagno-9.0.0-windows-x64-setup.exe", "https://x/setup.exe", 10, None)


def release(version="9.0.0"):
    return ReleaseInfo(version, "## New\n- Things", "https://github.com/Quezka/ducknet/releases", (DEB, EXE))


class Store(dict):
    def get(self, key, default=None):
        return super().get(key, default)

    def set(self, key, value):
        self[key] = value


class FakeFeed:
    def __init__(self):
        self.release, self.downloaded = None, []

    def latest(self):
        return self.release

    def download(self, asset, progress):
        progress(10, 10)
        self.downloaded.append(asset)
        return "/tmp/" + asset.name


class FakeInstaller:
    def __init__(self, supported=True):
        self._supported, self.installed = supported, []

    def supported(self):
        return self._supported

    def pick(self, assets):
        return next((a for a in assets if a.name.endswith(".deb")), None)

    def install(self, path):
        self.installed.append(path)
        return False


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 13, 12, 0)

    def __call__(self):
        return self.now


class ServiceTest(unittest.TestCase):
    def setUp(self):
        self.feed, self.installer, self.store, self.clock = FakeFeed(), FakeInstaller(), Store(), Clock()
        self.service = UpdateService(self.feed, self.installer, self.store, "0.4.0", self.clock)

    def test_versions_compare_as_numbers(self):
        self.assertGreater(parse_version("v0.10.0"), parse_version("0.9.9"))
        self.assertGreater(parse_version("1.0.0"), parse_version("0.99.0"))
        self.assertEqual(parse_version("0.11.0"), (0, 11, 0))
        self.assertLess(parse_version("nonsense"), parse_version("0.0.1"))

    def test_newer_release_is_offered_with_the_right_file(self):
        self.feed.release = release()
        update = self.service.check()
        self.assertEqual((update.version, update.asset, update.can_install, update.current),
                         ("9.0.0", DEB, True, "0.4.0"))

    def test_nothing_offered_when_up_to_date(self):
        self.assertIsNone(self.service.check())                   # nessuna release
        for version in ("0.4.0", "0.0.1"):
            self.feed.release = release(version)
            self.assertIsNone(self.service.check(), version)

    def test_a_copy_that_cant_install_gets_the_download_page(self):
        self.installer._supported = False
        self.feed.release = release()
        update = self.service.check()
        self.assertFalse(update.can_install)
        self.assertTrue(update.page_url.endswith("/releases"))

    def test_download_and_install(self):
        self.feed.release = release()
        update = self.service.check()
        seen = []
        path = self.service.download(update, lambda d, t: seen.append((d, t)))
        self.assertEqual(seen, [(10, 10)])
        self.assertFalse(self.service.install(path))
        self.assertEqual(self.installer.installed, [path])

    def test_download_without_a_file_for_this_computer_fails_clearly(self):
        update = mock.Mock(asset=None)
        with self.assertRaises(UpdateError):
            self.service.download(update, lambda d, t: None)

    # -- il consenso: senza un sì esplicito Stagno non parla con GitHub da solo -------------------------
    def test_never_checks_by_itself_until_the_user_agrees(self):
        self.assertIsNone(self.service.auto_check())              # non ancora chiesto
        self.assertFalse(self.service.due())
        self.service.set_auto_check(False)
        self.assertFalse(self.service.due())
        self.service.set_auto_check(True)
        self.assertTrue(self.service.due())

    def test_checks_about_once_a_day(self):
        self.service.set_auto_check(True)
        self.service.mark_checked()
        self.assertFalse(self.service.due())
        self.clock.now += timedelta(hours=19)
        self.assertFalse(self.service.due())
        self.clock.now += timedelta(hours=2)
        self.assertTrue(self.service.due())

    def test_skipping_a_version_is_remembered_for_that_version_only(self):
        self.service.skip("9.0.0")
        self.assertTrue(self.service.skipped("9.0.0"))
        self.assertFalse(self.service.skipped("9.1.0"))


def opener_for(payload=None, error=None, chunks=None):
    class Response(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def opener(request, timeout=None):
        if error:
            raise error
        return Response(payload)
    return opener


def api_payload(**over):
    data = {"tag_name": "v9.0.0", "body": "notes", "html_url": "https://github.com/Quezka/ducknet/releases/tag/v9.0.0",
            "draft": False, "prerelease": False,
            "assets": [{"name": DEB.name, "browser_download_url": "https://x/a.deb", "size": 10,
                        "digest": "sha256:" + hashlib.sha256(b"0123456789").hexdigest()}]}
    data.update(over)
    return json.dumps(data).encode()


class FeedTest(unittest.TestCase):
    def feed(self, opener, folder=None):
        return GitHubReleaseFeed("Quezka/ducknet", "0.4.0", opener, folder)

    def test_reads_the_latest_release(self):
        r = self.feed(opener_for(api_payload())).latest()
        self.assertEqual((r.version, r.notes), ("9.0.0", "notes"))
        self.assertEqual(r.assets[0].sha256, hashlib.sha256(b"0123456789").hexdigest())

    def test_drafts_and_prereleases_are_ignored(self):
        self.assertIsNone(self.feed(opener_for(api_payload(draft=True))).latest())
        self.assertIsNone(self.feed(opener_for(api_payload(prerelease=True))).latest())

    def test_no_release_yet_is_not_an_error(self):
        err = urllib.error.HTTPError("u", 404, "nf", {}, None)
        self.assertIsNone(self.feed(opener_for(error=err)).latest())

    def test_errors_become_update_errors(self):
        for error in (urllib.error.HTTPError("u", 403, "x", {}, None), urllib.error.HTTPError("u", 500, "x", {}, None),
                      urllib.error.URLError("no network"), TimeoutError()):
            with self.assertRaises(UpdateError, msg=repr(error)):
                self.feed(opener_for(error=error)).latest()
        with self.assertRaises(UpdateError):
            self.feed(opener_for(b"not json")).latest()

    def test_download_checks_size_and_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            good = ReleaseAsset("stagno.deb", "https://x", 10, hashlib.sha256(b"0123456789").hexdigest())
            seen = []
            path = self.feed(opener_for(b"0123456789"), Path(d)).download(good, lambda a, b: seen.append(a))
            self.assertEqual(Path(path).read_bytes(), b"0123456789")
            self.assertEqual(seen[-1], 10)
            bad = ReleaseAsset("bad.deb", "https://x", 10, "0" * 64)          # checksum sbagliato
            with self.assertRaises(UpdateError):
                self.feed(opener_for(b"0123456789"), Path(d)).download(bad, lambda a, b: None)
            short = ReleaseAsset("short.deb", "https://x", 99, None)           # troncato
            with self.assertRaises(UpdateError):
                self.feed(opener_for(b"0123456789"), Path(d)).download(short, lambda a, b: None)
            self.assertEqual(sorted(os.listdir(d)), ["stagno.deb"], "nessun file a metà deve restare")

    def test_a_hostile_asset_name_cannot_leave_the_folder(self):
        with tempfile.TemporaryDirectory() as d:
            evil = ReleaseAsset("../../evil.deb", "https://x", 10, None)
            path = self.feed(opener_for(b"0123456789"), Path(d)).download(evil, lambda a, b: None)
            self.assertEqual(Path(path).parent, Path(d))


class InstallerTest(unittest.TestCase):
    def test_deb_install_success_and_failures(self):
        calls = []

        def runner(code, err=""):
            def run(cmd, **kw):
                calls.append(cmd)
                return subprocess.CompletedProcess(cmd, code, stdout="", stderr=err)
            return run
        self.assertFalse(DebInstaller("/opt/stagno/Stagno", runner(0)).install("/tmp/x.deb"))
        self.assertEqual(calls[0][:2], ["pkexec", "apt-get"])
        for code in (126, 127):
            with self.assertRaises(UpdateError):
                DebInstaller("/opt/stagno/Stagno", runner(code)).install("/tmp/x.deb")
        with self.assertRaises(UpdateError) as ctx:
            DebInstaller("/opt/stagno/Stagno", runner(100, "E: broken\nE: really broken")).install("/tmp/x.deb")
        self.assertIn("really broken", str(ctx.exception))

    def test_deb_only_updates_the_packaged_copy(self):
        with mock.patch.object(sys, "frozen", True, create=True), mock.patch("shutil.which", return_value="/usr/bin/pkexec"):
            self.assertTrue(DebInstaller("/opt/stagno/Stagno").supported())
            self.assertFalse(DebInstaller("/home/me/Stagno").supported())
        self.assertFalse(DebInstaller("/opt/stagno/Stagno").supported())     # non congelato: da sorgente

    def test_deb_picks_its_architecture(self):
        other = ReleaseAsset("stagno_9.0.0_s390x.deb", "u", 1)
        self.assertEqual(DebInstaller().pick((other, DEB, EXE)), DEB)
        self.assertIsNone(DebInstaller().pick((other, EXE)))

    def test_windows_runs_the_setup_silently_and_asks_to_quit(self):
        launched = []
        installer = WindowsSetupInstaller("C:/x/Stagno.exe", lambda cmd, **kw: launched.append(cmd))
        self.assertTrue(installer.install("C:/tmp/setup.exe"))
        self.assertIn("/SILENT", launched[0])
        self.assertEqual(installer.pick((DEB, EXE)), EXE)

    def test_windows_needs_the_uninstaller_next_to_the_exe(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.object(sys, "frozen", True, create=True):
            exe = Path(d) / "Stagno.exe"
            self.assertFalse(WindowsSetupInstaller(str(exe)).supported())
            (Path(d) / "unins000.exe").write_text("x")
            self.assertTrue(WindowsSetupInstaller(str(exe)).supported())

    def test_source_copies_cannot_self_update(self):
        n = NoInstaller()
        self.assertFalse(n.supported())
        self.assertIsNone(n.pick((DEB, EXE)))
        with self.assertRaises(UpdateError):
            n.install("x")


class UiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        from stagno.ui import scheme
        scheme.register_scheme()
        cls.app = QApplication.instance() or QApplication(["stagno-test"])

    def service(self, installable=True):
        store, feed = Store(), FakeFeed()
        feed.release = release()
        return UpdateService(feed, FakeInstaller(installable), store, "0.4.0"), store

    def test_dialog_skip_is_remembered(self):
        from stagno.ui.updates_ui import UpdateDialog
        service, store = self.service()
        dialog = UpdateDialog(service, service.check())
        dialog.skip_btn.click()
        self.assertTrue(service.skipped("9.0.0"))

    def test_dialog_for_a_copy_that_cannot_install_offers_the_page(self):
        from stagno.ui.updates_ui import UpdateDialog
        service, _store = self.service(installable=False)
        dialog = UpdateDialog(service, service.check())
        self.assertEqual(dialog.go_btn.text(), "Open download page")
        self.assertFalse(dialog.status.isHidden())

    def test_first_run_asks_permission_but_later_runs_do_not(self):
        from stagno.ui.updates_ui import UpdateChecker
        service, store = self.service()
        with mock.patch.object(UpdateChecker, "_ask_permission") as ask:
            checker = UpdateChecker(service, delay_ms=10 ** 9)
            checker._first_run_or_check()
            ask.assert_called_once()
            service.set_auto_check(False)
            checker._first_run_or_check()
            ask.assert_called_once()                  # già deciso: non lo richiede
            self.assertIsNone(checker._worker)        # e con il no non controlla nulla

    def test_nothing_is_checked_without_consent(self):
        from stagno.ui.updates_ui import UpdateChecker
        service, store = self.service()
        checker = UpdateChecker(service, delay_ms=10 ** 9)
        checker._maybe_check()
        self.assertIsNone(checker._worker)


if __name__ == "__main__":
    unittest.main()
