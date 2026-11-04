"""Aspetto di Stagno: lo stesso stile Material 3 e lo stesso font (Manrope) delle altre app, chiaro o scuro."""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFontDatabase, QPalette
from PySide6.QtWidgets import QApplication

from ..core import pages

LIGHT = dict(bg="#f6f5fc", surface="#ffffff", raised="#e9e8f6", soft="#dddcfb", border="#c9c8dc", text="#0e1116", muted="#3f4654", accent="#4b4bc8", on_accent="#ffffff")
DARK = dict(bg="#111119", surface="#1b1b25", raised="#28283a", soft="#35366b", border="#3d3d55", text="#f4f5f7", muted="#c3c8d2", accent="#9a9bff", on_accent="#0e0f11")

QSS = """
QMainWindow, QDialog {{ background: {bg}; }}
QToolBar {{ background: {bg}; border: none; spacing: 4px; padding: 6px 8px 4px 8px; }}
QToolButton {{ border: none; border-radius: 12px; padding: 6px; }}
QToolButton:hover {{ background: {raised}; }}
QToolButton:checked {{ background: {soft}; }}
QToolButton:disabled {{ opacity: 0.4; }}
QLineEdit {{ background: {raised}; color: {text}; border: 1px solid transparent; border-radius: 12px; padding: 7px 14px;
  selection-background-color: {accent}; selection-color: {on_accent}; }}
QLineEdit:focus {{ background: {surface}; border: 2px solid {accent}; }}
QTabWidget::pane {{ border: none; }}
QTabBar {{ qproperty-drawBase: 0; }}
QTabBar::close-button {{ image: url({close}); subcontrol-position: right; border-radius: 6px; padding: 2px; }}
QTabBar::close-button:hover {{ background: {raised}; }}
QTabBar::tab {{ background: transparent; color: {muted}; padding: 7px 14px; margin: 2px 2px 0 2px;
  border-radius: 12px; min-width: 90px; max-width: 200px; font-weight: 600; }}
QTabBar::tab:selected {{ background: {soft}; color: {text}; }}
QTabBar::tab:hover:!selected {{ background: {raised}; }}
QProgressBar {{ background: transparent; border: none; max-height: 3px; }}
QProgressBar::chunk {{ background: {accent}; }}
QStatusBar {{ background: {bg}; color: {muted}; }}
QPushButton {{ background: {raised}; color: {text}; border: none; border-radius: 12px; padding: 7px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {soft}; }}
QPushButton:default {{ background: {accent}; color: {on_accent}; font-weight: 700; }}
QComboBox, QSpinBox {{ background: {surface}; color: {text}; border: 1px solid {border}; border-radius: 12px; padding: 6px 10px; }}
QMenu {{ background: {surface}; color: {text}; border: 1px solid {border}; border-radius: 12px; padding: 6px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 8px; }}
QMenu::item:selected {{ background: {soft}; }}
"""


def load_font(app: QApplication):
    """Manrope (SIL Open Font License, assets/Manrope-OFL.txt), as in the other apps of the suite."""
    assets = os.path.join(os.path.dirname(__file__), "..", "assets")
    loaded = [QFontDatabase.addApplicationFont(os.path.join(assets, "Manrope-%s.ttf" % weight))
              for weight in ("Regular", "Medium", "SemiBold", "Bold")]
    if any(i >= 0 for i in loaded):
        font = app.font()
        font.setFamily("Manrope")
        app.setFont(font)


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
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(t["on_accent"]))
    app.setPalette(pal)
    close = os.path.join(os.path.dirname(__file__), "..", "assets", "close-%s.svg" % ("dark" if t is DARK else "light"))
    app.setStyleSheet(QSS.format(close=close.replace("\\", "/"), **t))
    pages.set_scheme("dark" if t is DARK else "light")
    hints = app.styleHints()          # le pagine web seguono il tema scelto (prefers-color-scheme)
    if hasattr(hints, "setColorScheme"):
        hints.setColorScheme(Qt.ColorScheme.Dark if t is DARK else Qt.ColorScheme.Light)
    return t
