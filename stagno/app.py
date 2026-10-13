"""Punto d'ingresso di Stagno: `stagno [indirizzo ...]`."""
import argparse
import os
import sys

from .core import i18n


def main(argv=None):
    parser = argparse.ArgumentParser(prog="stagno", description="Il browser di DuckNet")
    parser.add_argument("urls", nargs="*", help="indirizzi duck:// da aprire")
    parser.add_argument("--dns", help="server DNS solo per questa sessione (di solito dns.quezka.uk)")
    parser.add_argument("--dns-port", type=int)
    parser.add_argument("--relay-port", type=int)
    args, qt_args = parser.parse_known_args(argv if argv is not None else sys.argv[1:])

    from PySide6.QtWidgets import QApplication
    from .ui import scheme
    scheme.register_scheme()                      # prima di QApplication
    app = QApplication([sys.argv[0]] + qt_args)
    app.setApplicationName("Stagno")
    app.setOrganizationName("quezka")
    from . import APP_ID
    app.setDesktopFileName(APP_ID)

    from .ui import theme
    from .ui.settings import Settings
    from .ui.window import MainWindow
    settings = Settings()
    i18n.set_language(i18n.detect_language() if settings.language == "auto" else settings.language)
    theme.apply(app, settings.theme)

    if args.dns or args.dns_port or args.relay_port:
        base = settings.config()
        from dataclasses import replace
        override = replace(base, dns_server=args.dns or base.dns_server,
                           dns_port=args.dns_port or base.dns_port,
                           relay_port=args.relay_port or base.relay_port)
        settings.config = lambda: override        # solo per questa sessione, non viene salvato
    from . import HOMEPAGE, __version__
    from .core.update_sources import GitHubReleaseFeed, platform_installer
    from .core.updates import UpdateService
    repo = HOMEPAGE.rsplit("github.com/", 1)[1]
    updates = UpdateService(GitHubReleaseFeed(repo, __version__), platform_installer(), settings, __version__)
    window = MainWindow(settings, args.urls, updates)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
