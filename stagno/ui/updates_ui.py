"""Aggiornamenti dentro Stagno: il controllo in background e la finestra dell'aggiornamento."""
import subprocess
import sys
import threading

from PySide6.QtCore import QObject, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QProgressBar,
                               QPushButton, QTextBrowser, QVBoxLayout)

from ..core.i18n import _
from ..core.updates import AvailableUpdate, UpdateError, UpdateService


def _message(error):
    return str(error) if isinstance(error, UpdateError) else _("Something went wrong: {error}", error=error)


class _Job(QObject):
    """Esegue una funzione su un thread e riporta il risultato sul thread della UI."""

    done = Signal(object)
    failed = Signal(object)


def run_in_background(fn, on_done, on_failed, parent=None):
    job = _Job(parent)
    job.done.connect(on_done)
    job.failed.connect(on_failed)

    def work():
        try:
            result = fn()
        except Exception as e:           # qualunque cosa vada storta torna alla UI come errore
            job.failed.emit(e)
        else:
            job.done.emit(result)

    threading.Thread(target=work, name="stagno-update", daemon=True).start()
    return job


def restart_app():
    """Riapre Stagno (la nuova versione) con gli stessi argomenti, poi esce."""
    args = [sys.executable] + sys.argv[1:] if getattr(sys, "frozen", False) else \
        [sys.executable, "-m", "stagno"] + sys.argv[1:]
    subprocess.Popen(args, close_fds=True)
    QApplication.quit()


class UpdateChecker(QObject):
    """Controlla GitHub circa una volta al giorno (poco dopo l'avvio) e a richiesta.

    Non fa NIENTE finché l'utente non ha detto sì: la prima volta chiede il permesso.
    """

    DELAY_MS = 10_000
    HOURLY_MS = 60 * 60_000

    def __init__(self, service: UpdateService, parent=None, delay_ms=DELAY_MS):
        super().__init__(parent)
        self.service = service
        self._worker = None
        self._interactive = False
        self.timer = QTimer(self, interval=self.HOURLY_MS)
        self.timer.timeout.connect(self._maybe_check)
        self.timer.start()
        QTimer.singleShot(delay_ms, self._first_run_or_check)

    def _first_run_or_check(self):
        if self.service.auto_check() is None:
            self._ask_permission()
        self._maybe_check()

    def _ask_permission(self):
        box = QMessageBox(self.parent())
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(_("Check for updates?"))
        box.setText(_("Stagno can look for new versions on GitHub about once a day. This is the only thing "
                      "Stagno ever does on the regular internet (your pages never do). Allow it?"))
        allow = box.addButton(_("Allow"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(_("No thanks"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        self.service.set_auto_check(box.clickedButton() is allow)

    def _maybe_check(self):
        if self.service.due():
            self.check_now(interactive=False)

    def check_now(self, interactive=True):
        """`interactive`: lo ha chiesto l'utente, quindi si dice anche «niente di nuovo» o l'errore."""
        if self._worker is not None:
            return
        self._interactive = interactive
        self._worker = run_in_background(self.service.check, self._checked, self._failed, self)

    def _checked(self, update):
        self._worker = None
        self.service.mark_checked()
        parent = self.parent()
        if update is None:
            if self._interactive:
                QMessageBox.information(parent, _("No updates"), _(
                    "You have the latest version of Stagno ({version}).", version=self.service.current_version))
            return
        if not self._interactive and self.service.skipped(update.version):
            return
        UpdateDialog(self.service, update, parent).exec()

    def _failed(self, error):
        self._worker = None
        if self._interactive:
            QMessageBox.warning(self.parent(), _("Couldn't check for updates"), _message(error))


class UpdateDialog(QDialog):
    def __init__(self, service: UpdateService, update: AvailableUpdate, parent=None):
        super().__init__(parent)
        self.service, self.update_info, self._worker = service, update, None
        self.setWindowTitle(_("Update available"))
        self.setMinimumSize(520, 400)

        title = QLabel(_("Stagno {version} is available", version=update.version))
        title.setStyleSheet("font-size: 16pt; font-weight: 600;")
        current = QLabel(_("You have {version}. Here's what's new:", version=update.current))
        current.setObjectName("hint")
        notes = QTextBrowser()
        notes.setOpenExternalLinks(False)
        notes.setMarkdown(update.notes or _("No release notes."))
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.hide()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.hide()

        self.skip_btn = QPushButton(_("Skip this version"))
        self.skip_btn.clicked.connect(self._skip)
        self.later_btn = QPushButton(_("Later"))
        self.later_btn.clicked.connect(self.reject)
        if update.can_install:
            self.go_btn = QPushButton(_("Update now"))
            self.go_btn.clicked.connect(self._download)
        else:
            self.go_btn = QPushButton(_("Open download page"))
            self.go_btn.clicked.connect(self._open_page)
            self._show_status(_("This copy of Stagno can't update itself (for example when it runs from "
                                "source). Download the new version from GitHub."))
        self.go_btn.setDefault(True)
        buttons = QHBoxLayout()
        buttons.addWidget(self.skip_btn)
        buttons.addStretch()
        buttons.addWidget(self.later_btn)
        buttons.addWidget(self.go_btn)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(10)
        for widget in (title, current):
            layout.addWidget(widget)
        layout.addWidget(notes, 1)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)
        layout.addLayout(buttons)

    def _show_status(self, text, error=False):
        self.status.setStyleSheet("color: #e5484d;" if error else "")
        self.status.setText(text)
        self.status.setVisible(bool(text))

    def _busy(self, busy):
        for button in (self.skip_btn, self.later_btn, self.go_btn):
            button.setEnabled(not busy)

    def _skip(self):
        self.service.skip(self.update_info.version)
        self.reject()

    def _open_page(self):
        QDesktopServices.openUrl(QUrl(self.update_info.page_url))
        self.accept()

    # -- scarica e installa ---------------------------------------------------------------------------
    def _download(self):
        self._busy(True)
        self.progress.setRange(0, 0)
        self.progress.show()
        self._show_status(_("Downloading…"))
        self._progress = _Progress(self)
        self._progress.changed.connect(self._progressed)
        self._worker = run_in_background(
            lambda: self.service.download(self.update_info, self._progress.changed.emit),
            self._downloaded, self._failed, self)

    def _progressed(self, done, total):
        if total:
            self.progress.setRange(0, 1000)
            self.progress.setValue(int(done * 1000 / total))
            self._show_status(_("Downloading… {done} of {total} MB",
                                done="%.1f" % (done / 1e6), total="%.1f" % (total / 1e6)))

    def _downloaded(self, path):
        self.progress.setRange(0, 0)
        self._show_status(_("Installing… your system may ask for your password."))
        self._worker = run_in_background(lambda: self.service.install(path), self._installed,
                                         self._failed, self)

    def _installed(self, installer_took_over):
        self._worker = None
        self.accept()
        if installer_took_over:      # Windows: il setup sostituisce i file e riapre Stagno
            QApplication.quit()
        else:                        # Linux: la nuova versione è installata, riaprila
            restart_app()

    def _failed(self, error):
        self._worker = None
        self.progress.hide()
        self._busy(False)
        self._show_status(_message(error), error=True)


class _Progress(QObject):
    """Porta l'avanzamento del download dal thread alla finestra."""

    changed = Signal(int, int)
