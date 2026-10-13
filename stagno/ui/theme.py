"""Aspetto di Stagno: lo stesso stile di Quire (indaco, angoli arrotondati), chiaro o scuro."""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from ..core import pages

LIGHT = dict(bg="#f5f6f8", surface="#ffffff", border="#e2e4e9", text="#16181d", muted="#636a75", accent="#5b5bd6")
DARK = dict(bg="#111214", surface="#18191c", border="#2a2c31", text="#ecedef", muted="#9aa0aa", accent="#8182f0")

QSS = """
QMainWindow, QDialog {{ background: {bg}; }}
QToolBar {{ background: {bg}; border: none; spacing: 4px; padding: 6px 8px 4px 8px; }}
QToolButton {{ border: none; border-radius: 8px; padding: 6px; }}
QToolButton:hover {{ background: {border}; }}
QToolButton:disabled {{ opacity: 0.4; }}
QLineEdit {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 7px 12px;
  selection-background-color: {accent}; }}
QLineEdit:focus {{ border: 1px solid {accent}; }}
QTabWidget::pane {{ border: none; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::close-button {{ image: url({close}); subcontrol-position: right; border-radius: 6px; padding: 2px; }}
QTabBar::close-button:hover {{ background: {border}; }}
QTabBar::tab {{ background: transparent; color: {muted}; padding: 7px 14px; margin: 2px 2px 0 2px;
  border-radius: 8px; min-width: 90px; max-width: 200px; }}
QTabBar::tab:selected {{ background: {surface}; color: {text}; border: 1px solid {border}; }}
QTabBar::tab:hover:!selected {{ background: {border}; }}
QProgressBar {{ background: transparent; border: none; max-height: 3px; }}
QProgressBar::chunk {{ background: {accent}; }}
QStatusBar {{ background: {bg}; color: {muted}; }}
QPushButton {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 7px 16px; }}
QPushButton:default {{ background: {accent}; color: white; border: none; }}
QComboBox, QSpinBox {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 6px 10px; }}
QMenu {{ background: {surface}; border: 1px solid {border}; border-radius: 10px; padding: 6px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {accent}; color: white; }}
"""


def resolve(mode, app):
    if mode == "light":
        return LIGHT
    if mode == "dark":
        return DARK
    return DARK if app.palette().color(QPalette.ColorRole.Window).lightness() < 128 else LIGHT


def apply(app: QApplication, mode):
    t = resolve(mode, app)
    app.setStyle("Fusion")
    pal = QPalette()
    for role, key in ((QPalette.ColorRole.Window, "bg"), (QPalette.ColorRole.Base, "surface"),
                      (QPalette.ColorRole.Button, "surface"), (QPalette.ColorRole.Text, "text"),
                      (QPalette.ColorRole.WindowText, "text"), (QPalette.ColorRole.ButtonText, "text"),
                      (QPalette.ColorRole.Highlight, "accent")):
        pal.setColor(role, QColor(t[key]))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(pal)
    close = os.path.join(os.path.dirname(__file__), "..", "assets", "close-%s.svg" % ("dark" if t is DARK else "light"))
    app.setStyleSheet(QSS.format(close=close.replace("\\", "/"), **t))
    pages.set_scheme("dark" if t is DARK else "light")
    hints = app.styleHints()          # le pagine web seguono il tema scelto (prefers-color-scheme)
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Dark if t is DARK else Qt.ColorScheme.Light)
    return t
