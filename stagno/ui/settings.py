"""Impostazioni di Stagno (per utente, in QSettings) e la loro finestra."""
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit,
                               QSpinBox, QVBoxLayout)

from ..core.fetcher import Config
from ..core.i18n import N_, _

THEMES = (("system", N_("System")), ("light", N_("Light")), ("dark", N_("Dark")))
LANGS = (("auto", N_("Automatic")), ("en", "English"), ("it", "Italiano"), ("ru", "Русский"))


class Settings:
    def __init__(self):
        self._q = QSettings("quezka", "stagno")

    def config(self):
        d = Config()
        return Config(self._q.value("dns_server", d.dns_server, str),
                      self._q.value("dns_port", d.dns_port, int),
                      self._q.value("relay_port", d.relay_port, int))

    def set_config(self, config):
        self._q.setValue("dns_server", config.dns_server)
        self._q.setValue("dns_port", config.dns_port)
        self._q.setValue("relay_port", config.relay_port)

    theme = property(lambda s: s._q.value("theme", "system", str), lambda s, v: s._q.setValue("theme", v))
    language = property(lambda s: s._q.value("language", "auto", str), lambda s, v: s._q.setValue("language", v))


class SettingsDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Settings"))
        self.setMinimumWidth(420)
        config = settings.config()
        self.dns = QLineEdit(config.dns_server)
        self.dns_port = QSpinBox()
        self.dns_port.setRange(1, 65535)
        self.dns_port.setValue(config.dns_port)
        self.relay_port = QSpinBox()
        self.relay_port.setRange(1, 65535)
        self.relay_port.setValue(config.relay_port)
        self.theme = QComboBox()
        for key, label in THEMES:
            self.theme.addItem(_(label), key)
        self.theme.setCurrentIndex(max(0, self.theme.findData(settings.theme)))
        self.language = QComboBox()
        for key, label in LANGS:
            self.language.addItem(_(label) if key == "auto" else label, key)
        self.language.setCurrentIndex(max(0, self.language.findData(settings.language)))

        form = QFormLayout()
        form.addRow(_("Appearance"), self.theme)
        form.addRow(_("Language"), self.language)
        form.addRow(_("DuckNet DNS server"), self.dns)
        form.addRow(_("DNS port"), self.dns_port)
        form.addRow(_("Relay port"), self.relay_port)
        hint = QLabel(_("Restart Stagno to change the language.") + "\n"
                      + _("Advanced: only change these to try DuckNet on your own machine."))
        hint.setWordWrap(True)
        hint.setObjectName("hint")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(hint)
        layout.addWidget(buttons)

    def apply_to(self, settings):
        settings.set_config(Config(self.dns.text().strip() or Config().dns_server,
                                   self.dns_port.value(), self.relay_port.value()))
        settings.theme = self.theme.currentData()
        settings.language = self.language.currentData()
