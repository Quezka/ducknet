"""Prova di fumo del browser vero: motore web, schema duck://, blocco del web normale (senza schermo)."""
import asyncio
import os
import tempfile
import threading
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu")

from PySide6.QtCore import QEvent, QEventLoop, QTimer, QUrl  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from ducknet import dns  # noqa: E402
from ducknet.host import Host  # noqa: E402
from ducknet.registry import Registry  # noqa: E402
from ducknet.relay import Relay  # noqa: E402
from stagno.core.fetcher import Config  # noqa: E402
from stagno.ui import scheme  # noqa: E402

scheme.register_scheme()
APP = QApplication.instance() or QApplication(["stagno-test"])

from stagno.ui.settings import Settings  # noqa: E402
from stagno.ui.window import MainWindow  # noqa: E402


def wait_for(predicate, ms=15000):
    loop, timer = QEventLoop(), QTimer()
    timer.setInterval(50)
    timer.timeout.connect(lambda: loop.quit() if predicate() else None)
    QTimer.singleShot(ms, loop.quit)
    timer.start()
    loop.exec()
    timer.stop()
    return predicate()


class Fixed(Settings):
    theme, language = "light", "en"

    def __init__(self, config):
        self._config = config

    def config(self):
        return self._config


class BrowserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        reg = Registry(os.path.join(cls.dir.name, "ducks.json"))
        secret = reg.add("pippo.duck")
        site = os.path.join(cls.dir.name, "site")
        os.mkdir(site)
        with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as f:
            f.write('<title>Pagina di prova</title><h1 id=h>è tutto à posto</h1><img src="/pic.svg">'
                    '<a id=ext href="http://example.com/">web</a>')
        with open(os.path.join(site, "pic.svg"), "w") as f:
            f.write('<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"/>')
        ports, ready = {}, threading.Event()

        async def main():
            relay = await Relay(reg).serve("127.0.0.1", 0)
            ports["relay"] = relay.sockets[0].getsockname()[1]
            d = await dns.serve(reg, "127.0.0.1", "127.0.0.1", 0)
            ports["dns"] = d.get_extra_info("sockname")[1]
            host = Host("pippo.duck", secret, site, "127.0.0.1", ports["relay"])
            cls.host_task = asyncio.ensure_future(host.run())      # tenuto vivo: i task orfani possono sparire
            await host.ready.wait()
            cls.loop, cls.stop = asyncio.get_running_loop(), asyncio.Event()
            ready.set()
            await cls.stop.wait()

        cls.thread = threading.Thread(target=lambda: asyncio.run(main()), daemon=True)
        cls.thread.start()
        assert ready.wait(10)
        cls.window = MainWindow(Fixed(Config("127.0.0.1", ports["dns"], ports["relay"])), ["duck://stagno/"])
        cls.window.show()

    @classmethod
    def tearDownClass(cls):
        cls.window.close()                # closeEvent cancella pagine e profilo nell'ordine giusto
        cls.window.deleteLater()
        for _ in range(5):
            QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            QApplication.processEvents()
        cls.loop.call_soon_threadsafe(cls.stop.set)
        cls.thread.join(5)
        cls.dir.cleanup()

    def load(self, text):
        view = self.window.view()
        done = []
        view.loadFinished.connect(lambda ok: done.append(ok))
        self.window.go(text)
        self.assertTrue(wait_for(lambda: bool(done)), "caricamento non finito: " + text)
        return view

    def js(self, script):
        out = []
        self.window.view().page().runJavaScript(script, lambda v: out.append(v))
        self.assertTrue(wait_for(lambda: bool(out)))
        return out[0]

    def test_1_home_is_internal(self):
        self.load("stagno")
        self.assertIn("meme", self.js("document.body.innerHTML"))

    def test_2_duck_page_loads_with_utf8_and_title(self):
        self.load("pippo.duck")
        self.assertEqual(self.js("document.getElementById('h').textContent"), "è tutto à posto")
        self.assertEqual(self.window.view().title(), "Pagina di prova")
        self.assertEqual(self.window.view().url().toString(), "duck://pippo.duck/")

    def test_3_subresource_goes_through_duck(self):
        self.load("pippo.duck")
        self.assertTrue(wait_for(lambda: self.js("document.images[0].complete && document.images[0].naturalWidth") == 10))

    def test_4_unknown_name_shows_error_page(self):
        self.load("nessuno.duck")
        self.assertIn("nessuno.duck", self.js("document.body.innerText"))

    def test_5_web_is_blocked(self):
        self.load("https://example.com/")
        self.assertEqual(self.window.view().url().host(), "stagno")
        self.assertIn("example.com", self.js("document.body.innerText"))

    def test_6_clicking_external_link_is_blocked(self):
        view = self.load("pippo.duck")
        done = []
        view.loadFinished.connect(lambda ok: done.append(ok))
        self.js("document.getElementById('ext').click(); 1")
        self.assertTrue(wait_for(lambda: bool(done)))
        self.assertEqual(view.url().host(), "stagno")
        self.assertIn("example.com", self.js("document.body.innerText"))

    def test_7_new_tab_and_close(self):
        before = self.window.tabs.count()
        self.window.new_tab("duck://stagno/")
        self.assertEqual(self.window.tabs.count(), before + 1)
        self.window.close_tab(self.window.tabs.currentIndex())
        self.assertEqual(self.window.tabs.count(), before)

    def test_8_bad_address_does_not_navigate(self):
        before = self.window.view().url()
        self.window.go("not an address")
        self.assertEqual(self.window.view().url(), before)


if __name__ == "__main__":
    unittest.main()
