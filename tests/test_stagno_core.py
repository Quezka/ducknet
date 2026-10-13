import asyncio
import os
import re
import tempfile
import threading
import unittest

from ducknet import dns
from ducknet.host import Host
from ducknet.registry import Registry
from ducknet.relay import Relay
from stagno.core import address, fetcher, i18n, memes, pages
from stagno.core.catalogs import IT, RU


class AddressTest(unittest.TestCase):
    def test_names(self):
        self.assertEqual(address.parse("pippo.duck"), address.Address("duck", "duck://pippo.duck/"))
        self.assertEqual(address.parse("  PIPPO "), address.Address("duck", "duck://pippo.duck/"))
        self.assertEqual(address.parse("duck://a.duck/x/y?q=1").url, "duck://a.duck/x/y?q=1")
        self.assertEqual(address.parse("a.duck/pagina uno").kind, "invalid")

    def test_internal_and_blocked(self):
        self.assertEqual(address.parse("stagno").kind, "internal")
        self.assertEqual(address.parse("duck://stagno/blocked?url=x").kind, "internal")
        for url in ("http://example.com", "HTTPS://example.com/x", "file:///etc/passwd"):
            self.assertEqual(address.parse(url).kind, "blocked", url)

    def test_invalid(self):
        for text in ("", "   ", "a b", "-a.duck", "x.com", "duck://", "../etc"):
            self.assertEqual(address.parse(text).kind, "invalid", text)


class PagesTest(unittest.TestCase):
    def test_blocked_page_escapes_the_url(self):
        html = pages.internal("/blocked?url=%3Cscript%3Ealert(1)%3C/script%3E")
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_error_pages_escape_names(self):
        self.assertNotIn("<b>", pages.not_found("<b>x</b>"))
        self.assertNotIn("<b>", pages.unreachable("<b>x</b>"))

    def test_home_has_a_meme_and_utf8(self):
        html = pages.home()
        self.assertIn("charset=utf-8", html)
        self.assertIn('class=meme', html)

    def test_unknown_internal_path_is_a_page(self):
        self.assertIn("<html", pages.internal("/boh"))

    def test_every_meme_has_english(self):
        for m in memes.MEMES:
            self.assertTrue(m.top["en"] and m.bottom["en"])


class I18nTest(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_catalogs_match(self):
        self.assertEqual(set(IT), set(RU))
        for key in IT:
            fields = lambda s: sorted(re.findall(r"\{\w+\}", s))
            self.assertEqual(fields(key), fields(IT[key]), key)
            self.assertEqual(fields(key), fields(RU[key]), key)

    def test_every_used_string_is_translated(self):
        root = os.path.join(os.path.dirname(__file__), "..", "stagno")
        used = set()
        for base, _, files in os.walk(root):
            for name in files:
                if name.endswith(".py") and name != "catalogs.py":
                    with open(os.path.join(base, name), encoding="utf-8") as f:
                        used |= set(re.findall(r'\b(?:_|N_)\(\s*"((?:[^"\\]|\\.)*)"', f.read()))
        self.assertTrue(used)
        self.assertEqual(sorted(used - set(IT)), [])
        self.assertEqual(sorted(set(IT) - used), [], "traduzioni non usate")

    def test_translate_and_format(self):
        i18n.set_language("it")
        self.assertEqual(i18n._("Back"), "Indietro")
        self.assertEqual(i18n._("Version {version}", version="1"), "Versione 1")
        i18n.set_language("xx")
        self.assertEqual(i18n._("Back"), "Back")


class FetcherTest(unittest.TestCase):
    """Un vero DNS + relay + host in un thread, e il fetcher che li usa come farebbe il browser."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.TemporaryDirectory()
        reg = Registry(os.path.join(cls.dir.name, "ducks.json"))
        secret = reg.add("pippo.duck")
        reg.add("spento.duck")
        site = os.path.join(cls.dir.name, "site")
        os.mkdir(site)
        with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as f:
            f.write("<h1>quack</h1>")
        ready, cls.ports = threading.Event(), {}

        async def main():
            relay = await Relay(reg).serve("127.0.0.1", 0)
            cls.ports["relay"] = relay.sockets[0].getsockname()[1]
            d = await dns.serve(reg, "127.0.0.1", "127.0.0.1", 0)
            cls.ports["dns"] = d.get_extra_info("sockname")[1]
            host = Host("pippo.duck", secret, site, "127.0.0.1", cls.ports["relay"])
            cls.host_task = asyncio.ensure_future(host.run())      # tenuto vivo: i task orfani possono sparire
            await host.ready.wait()
            cls.stop = asyncio.Event()
            cls.loop = asyncio.get_running_loop()
            ready.set()
            await cls.stop.wait()

        cls.thread = threading.Thread(target=lambda: asyncio.run(main()), daemon=True)
        cls.thread.start()
        assert ready.wait(10)
        cls.config = fetcher.Config("127.0.0.1", cls.ports["dns"], cls.ports["relay"])

    @classmethod
    def tearDownClass(cls):
        cls.loop.call_soon_threadsafe(cls.stop.set)
        cls.thread.join(5)
        cls.dir.cleanup()

    def test_page(self):
        r = fetcher.load("duck://pippo.duck/", self.config)
        self.assertEqual(r.body, b"<h1>quack</h1>")
        self.assertTrue(r.content_type.startswith("text/html"))

    def test_missing_page_is_the_hosts_404(self):
        r = fetcher.load("duck://pippo.duck/nope", self.config)
        self.assertIn(b"404", r.body)

    def test_unknown_name_gets_error_page(self):
        r = fetcher.load("duck://boh.duck/", self.config)
        self.assertIn("boh.duck".encode(), r.body)
        self.assertTrue(r.content_type.startswith("text/html"))

    def test_offline_name_gets_relay_503_page(self):
        self.assertIn(b"503", fetcher.load("duck://spento.duck/", self.config).body)

    def test_dns_unreachable_gets_error_page(self):
        r = fetcher.load("duck://pippo.duck/", fetcher.Config("127.0.0.1", 1, self.ports["relay"]))
        self.assertTrue(r.content_type.startswith("text/html"))
        self.assertGreater(len(r.body), 100)

    def test_internal(self):
        self.assertIn(b"<html", fetcher.load_internal("/").body)


if __name__ == "__main__":
    unittest.main()
