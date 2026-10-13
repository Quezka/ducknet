import asyncio
import os
import socket
import struct
import tempfile
import unittest

from ducknet import client, dns, protocol
from ducknet.host import Host, respond
from ducknet.registry import Registry
from ducknet.relay import Relay


def make_query(name, qtype=1):
    qname = b"".join(bytes([len(p)]) + p.encode() for p in name.split(".")) + b"\0"
    return b"\x12\x34" + struct.pack("!HHHHH", 0x0100, 1, 0, 0, 0) + qname + struct.pack("!HH", qtype, 1)


def write(path, text):
    with open(path, "w") as f:
        f.write(text)


class RegistryTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.reg = Registry(os.path.join(self.dir.name, "ducks.json"))

    def tearDown(self):
        self.dir.cleanup()

    def test_add_verify_remove(self):
        secret = self.reg.add("pippo.duck")
        self.assertTrue(self.reg.verify("pippo.duck", secret))
        self.assertFalse(self.reg.verify("pippo.duck", "sbagliato"))
        self.assertTrue(self.reg.exists("pippo.duck"))
        self.reg.remove("pippo.duck")
        self.assertFalse(self.reg.exists("pippo.duck"))

    def test_rejects_bad_and_duplicate_names(self):
        for bad in ("pippo.com", "Pippo.duck", "-a.duck", "a b.duck", ".duck", "a/b.duck"):
            with self.assertRaises(ValueError):
                self.reg.add(bad)
        self.reg.add("a.duck")
        with self.assertRaises(ValueError):
            self.reg.add("a.duck")

    def test_secret_not_stored_in_clear(self):
        secret = self.reg.add("a.duck")
        with open(self.reg.path) as f:
            self.assertNotIn(secret, f.read())


class DnsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.reg = Registry(os.path.join(self.dir.name, "ducks.json"))
        self.reg.add("pippo.duck")

    def tearDown(self):
        self.dir.cleanup()

    def test_known_name_gets_relay_ip(self):
        r = dns.answer(make_query("pippo.duck"), self.reg, "203.0.113.7")
        self.assertEqual(r[3] & 0xF, 0)
        self.assertEqual(r[-4:], socket.inet_aton("203.0.113.7"))

    def test_unknown_duck_is_nxdomain(self):
        self.assertEqual(dns.answer(make_query("nope.duck"), self.reg, "1.2.3.4")[3] & 0xF, 3)

    def test_other_domains_refused(self):
        self.assertEqual(dns.answer(make_query("example.com"), self.reg, "1.2.3.4")[3] & 0xF, 5)

    def test_aaaa_is_empty_noerror(self):
        r = dns.answer(make_query("pippo.duck", 28), self.reg, "1.2.3.4")
        self.assertEqual((r[3] & 0xF, struct.unpack("!H", r[6:8])[0]), (0, 0))

    def test_garbage_is_ignored(self):
        self.assertIsNone(dns.answer(b"\x00\x01", self.reg, "1.2.3.4"))
        self.assertIsNone(dns.answer(b"\x00" * 12 + b"\xff", self.reg, "1.2.3.4"))


class HostFilesTest(unittest.TestCase):
    def test_no_path_traversal(self):
        with tempfile.TemporaryDirectory() as d:
            site, secret = os.path.join(d, "site"), os.path.join(d, "segreto.txt")
            os.mkdir(site)
            write(secret, "no")
            write(os.path.join(site, "index.html"), "ok")
            self.assertIn(b"200", respond(os.path.realpath(site), "/")[:20])
            for p in ("/../segreto.txt", "/%2e%2e/segreto.txt", "/..%2fsegreto.txt"):
                self.assertIn(b"404", respond(os.path.realpath(site), p)[:20], p)


class EndToEndTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.reg = Registry(os.path.join(self.dir.name, "ducks.json"))
        self.secret = self.reg.add("pippo.duck")
        site = os.path.join(self.dir.name, "site")
        os.mkdir(site)
        write(os.path.join(site, "index.html"), "<h1>quack</h1>")
        self.site = site
        self.relay = Relay(self.reg)
        self.server = await self.relay.serve("127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]
        self.dns = await dns.serve(self.reg, "127.0.0.1", "127.0.0.1", 0)
        self.dns_port = self.dns.get_extra_info("sockname")[1]

    async def asyncTearDown(self):
        self.dns.close()
        self.server.close()
        self.dir.cleanup()

    async def get(self, url):
        return await client.fetch(url, "127.0.0.1", self.dns_port, self.port, timeout=5)

    async def start_host(self, secret=None):
        host = Host("pippo.duck", secret or self.secret, self.site, "127.0.0.1", self.port)
        task = asyncio.ensure_future(host.run())
        await asyncio.wait_for(host.ready.wait(), 5)
        self.addCleanup(task.cancel)
        return host

    async def test_full_trip(self):
        await self.start_host()
        code, motto, headers, body = await self.get("duck://pippo.duck/")
        self.assertEqual((code, body), (200, b"<h1>quack</h1>"))
        self.assertTrue(headers["content-type"].startswith("text/html"))
        self.assertEqual((await self.get("pippo.duck/nope"))[0], 404)

    async def test_many_requests_in_parallel(self):
        await self.start_host()
        results = await asyncio.gather(*(self.get("pippo.duck/") for _ in range(20)))
        self.assertTrue(all(r[0] == 200 for r in results))

    async def test_offline_is_503(self):
        self.assertEqual((await self.get("pippo.duck/"))[0], 503)

    async def test_unregistered_name_does_not_resolve(self):
        with self.assertRaises(LookupError):
            await self.get("nope.duck/")

    async def test_unregistered_name_at_relay_is_404(self):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write(protocol.build_request("nope.duck", "/"))
        self.assertEqual((await protocol.read_response(r))[0], 404)
        w.close()

    async def test_wrong_secret_rejected(self):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write(b"PERCH pippo.duck sbagliato\n")
        self.assertEqual(await r.readline(), b"NO\n")
        w.close()
        self.assertNotIn("pippo.duck", self.relay.perched)

    async def test_garbage_gets_400_and_relay_survives(self):
        r, w = await asyncio.open_connection("127.0.0.1", self.port)
        w.write(b"GET / HTTP/1.1\r\n\r\n")
        self.assertIn(b"400", await r.read(100))
        w.close()
        await self.start_host()
        self.assertEqual((await self.get("pippo.duck/"))[0], 200)

    async def test_host_going_away_is_offline_again(self):
        task_host = await self.start_host()
        self.assertEqual((await self.get("pippo.duck/"))[0], 200)
        self.relay.perched["pippo.duck"].close()
        await asyncio.sleep(0.1)
        self.assertEqual((await self.get("pippo.duck/"))[0], 503)


class ParseUrlTest(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(client.parse_url("duck://A.duck/x/y"), ("a.duck", "/x/y"))
        self.assertEqual(client.parse_url("a.duck"), ("a.duck", "/"))


if __name__ == "__main__":
    unittest.main()
