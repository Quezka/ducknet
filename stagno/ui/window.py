"""La finestra principale: schede, barra degli indirizzi, navigazione."""
import os

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QIcon, QKeySequence
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (QApplication, QLineEdit, QMainWindow, QMenu, QMessageBox, QProgressBar, QTabWidget,
                               QToolBar, QToolButton, QVBoxLayout, QWidget)

from .. import __version__
from ..core import address, memes
from ..core.i18n import N_, _, language
from . import icons, theme
from .scheme import Bridge
from .settings import SettingsDialog
from .updates_ui import UpdateChecker

ASSETS = os.path.join(os.path.dirname(__file__), "..", "assets")


class DuckPage(QWebEnginePage):
    def acceptNavigationRequest(self, url, nav_type, is_main_frame):
        if is_main_frame and url.scheme() in ("http", "https", "ftp", "file"):
            target = "duck://stagno/blocked?url=" + QUrl.toPercentEncoding(url.toString()).data().decode()
            QTimer.singleShot(0, lambda: self.setUrl(QUrl(target)))
            return False
        return True


class DuckView(QWebEngineView):
    def __init__(self, profile, open_tab, parent=None):
        super().__init__(parent)
        self._open_tab = open_tab
        self.setPage(DuckPage(profile, self))

    def createWindow(self, window_type):         # target=_blank, window.open
        return self._open_tab()


class MainWindow(QMainWindow):
    def __init__(self, settings, start_urls=(), updates=None):
        super().__init__()
        self.settings = settings
        self.updates = updates
        self.setWindowTitle("Stagno")
        self.setWindowIcon(QIcon(os.path.join(ASSETS, "stagno.svg")))
        self.resize(1100, 760)
        self.profile = QWebEngineProfile("stagno")      # senza genitore: lo cancelliamo noi, dopo le pagine
        self.bridge = Bridge(self.profile, settings.config)

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self._current_changed)
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        central = QWidget()
        box = QVBoxLayout(central)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        box.addWidget(self.progress)
        box.addWidget(self.tabs)
        self.setCentralWidget(central)
        self._build_toolbar()
        self._restyle()
        self.updater = UpdateChecker(updates, self) if updates is not None else None
        for url in start_urls or ["duck://stagno/"]:
            self.new_tab(url)

    def closeEvent(self, event):
        # Qt vuole le pagine cancellate PRIMA del profilo, altrimenti avvisa e può crashare in uscita.
        while self.tabs.count():
            view = self.tabs.widget(0)
            self.tabs.removeTab(0)
            view.deleteLater()
        self.profile.deleteLater()
        super().closeEvent(event)

    # -- costruzione ---------------------------------------------------------------------------------
    def _build_toolbar(self):
        bar = QToolBar()
        bar.setMovable(False)
        bar.setIconSize(QSize(20, 20))
        self.addToolBar(bar)
        self.act_back = self._action(bar, "back", N_("Back"), "Alt+Left", lambda: self.view().back())
        self.act_forward = self._action(bar, "forward", N_("Forward"), "Alt+Right", lambda: self.view().forward())
        self.act_reload = self._action(bar, "reload", N_("Reload"), "F5", self._reload_or_stop)
        self.act_home = self._action(bar, "home", N_("Home"), "Alt+Home", lambda: self.go("duck://stagno/"))
        self.address = QLineEdit()
        self.address.setPlaceholderText(_("Type a .duck name, e.g. pippo.duck"))
        self.address.setClearButtonEnabled(True)
        self.address.returnPressed.connect(lambda: self.go(self.address.text()))
        bar.addWidget(self.address)
        self.act_new = self._action(bar, "plus", N_("New tab"), "Ctrl+T", lambda: self.new_tab("duck://stagno/"))
        menu_button = QToolButton()
        menu_button.setToolTip(_("Menu"))
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        menu = QMenu(menu_button)
        for label, shortcut, fn in ((N_("Close tab"), "Ctrl+W", lambda: self.close_tab(self.tabs.currentIndex())),
                                    (N_("Zoom in"), "Ctrl++", lambda: self._zoom(+0.1)),
                                    (N_("Zoom out"), "Ctrl+-", lambda: self._zoom(-0.1)),
                                    (N_("Reset zoom"), "Ctrl+0", lambda: self._zoom(None)),
                                    (N_("Settings…"), "Ctrl+,", self.open_settings),
                                    (N_("Check for updates…"), "", lambda: self.updater and self.updater.check_now()),
                                    (N_("About Stagno"), "", self.about),
                                    (N_("Quit"), "Ctrl+Q", self.close)):
            act = menu.addAction(_(label))
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.triggered.connect(fn)
            self.addAction(act)
        menu_button.setMenu(menu)
        self._menu_button = menu_button
        bar.addWidget(menu_button)
        focus = QAction(self)
        focus.setShortcut(QKeySequence("Ctrl+L"))
        focus.triggered.connect(lambda: (self.address.setFocus(), self.address.selectAll()))
        self.addAction(focus)
        self.statusBar().showMessage("")

    def _action(self, bar, icon_name, label, shortcut, fn):
        act = QAction(_(label), self)
        act.setShortcut(QKeySequence(shortcut))
        act.setToolTip("%s (%s)" % (_(label), shortcut))
        act.setData(icon_name)
        act.triggered.connect(fn)
        bar.addAction(act)
        self.addAction(act)
        return act

    def _restyle(self):
        colors = theme.resolve(self.settings.theme, QApplication.instance())
        for act in (self.act_back, self.act_forward, self.act_reload, self.act_home, self.act_new):
            act.setIcon(icons.icon(act.data(), colors["text"]))
        self._menu_button.setIcon(icons.icon("menu", colors["text"]))
        self._icon_color = colors["text"]

    # -- schede --------------------------------------------------------------------------------------
    def view(self):
        return self.tabs.currentWidget()

    def new_tab(self, url=None):
        view = DuckView(self.profile, lambda: self.new_tab(None), self)
        index = self.tabs.addTab(view, _("New tab"))
        self.tabs.setCurrentIndex(index)
        view.titleChanged.connect(lambda title, v=view: self._title(v, title))
        view.iconChanged.connect(lambda icon, v=view: self.tabs.setTabIcon(self.tabs.indexOf(v), icon))
        view.urlChanged.connect(lambda u, v=view: self._url(v, u))
        view.loadStarted.connect(lambda v=view: self._started(v))
        view.loadProgress.connect(lambda p, v=view: self._progress(v, p))
        view.loadFinished.connect(lambda ok, v=view: self._finished(v))
        view.page().linkHovered.connect(lambda link: self.statusBar().showMessage(link))
        if url:
            view.setUrl(QUrl(url))
        return view

    def close_tab(self, index):
        if self.tabs.count() <= 1:
            self.close()
            return
        view = self.tabs.widget(index)
        self.tabs.removeTab(index)
        view.deleteLater()

    def _title(self, view, title):
        index = self.tabs.indexOf(view)
        if index >= 0:
            self.tabs.setTabText(index, title.replace("&", "&&") or _("New tab"))
            self.tabs.setTabToolTip(index, title)
            if view is self.view():
                self.setWindowTitle("%s — Stagno" % title if title else "Stagno")

    def _url(self, view, url):
        if view is self.view() and not self.address.hasFocus():
            self._show_address(url)

    def _show_address(self, url):
        text = url.toString()
        self.address.setText("" if url.host() == "stagno" and url.path() in ("", "/") else text)
        self.act_back.setEnabled(self.view().history().canGoBack())
        self.act_forward.setEnabled(self.view().history().canGoForward())

    def _current_changed(self, index):
        view = self.view()
        if view is None:
            return
        self._show_address(view.url())
        self.setWindowTitle("%s — Stagno" % view.title() if view.title() else "Stagno")
        self._set_loading(view.property("loading") or False)

    def _started(self, view):
        view.setProperty("loading", True)
        if view is self.view():
            self.statusBar().showMessage(memes.loading_line(language()))
            self._set_loading(True)

    def _progress(self, view, percent):
        if view is self.view():
            self.progress.setValue(percent)

    def _finished(self, view):
        view.setProperty("loading", False)
        if view is self.view():
            self.statusBar().clearMessage()
            self._set_loading(False)
            self.progress.setValue(0)

    def _set_loading(self, loading):
        self.act_reload.setIcon(icons.icon("stop" if loading else "reload", self._icon_color))
        self.act_reload.setText(_("Stop") if loading else _("Reload"))

    def _reload_or_stop(self):
        view = self.view()
        view.stop() if view.property("loading") else view.reload()

    # -- navigazione ---------------------------------------------------------------------------------
    def go(self, text):
        target = address.parse(text)
        if target.kind == "invalid":
            self.statusBar().showMessage(_("That doesn't look like a DuckNet address."), 4000)
            return
        if target.kind == "blocked":
            target = address.Address("internal", "duck://stagno/blocked?url="
                                     + QUrl.toPercentEncoding(target.url).data().decode())
        self.view().setUrl(QUrl(target.url))
        self.view().setFocus()

    def _zoom(self, delta):
        view = self.view()
        view.setZoomFactor(1.0 if delta is None else min(3.0, max(0.3, view.zoomFactor() + delta)))

    def open_settings(self):
        dialog = SettingsDialog(self.settings, self, self.updates)
        if dialog.exec():
            dialog.apply_to(self.settings)
            theme.apply(QApplication.instance(), self.settings.theme)
            self._restyle()
            self._set_loading(bool(self.view().property("loading")))

    def about(self):
        QMessageBox.about(self, _("About Stagno"), "<h3>🦆 Stagno</h3><p>%s</p><p>%s</p>" % (
            _("Stagno is the DuckNet browser. It speaks DUCK/1, not HTTP."),
            _("Version {version}", version=__version__)))
