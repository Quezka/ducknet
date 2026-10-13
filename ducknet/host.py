"""L'host: serve una cartella su DuckNet restando dietro il suo NAT. Si posa sul relay e aspetta."""
import asyncio
import mimetypes
import os
import sys
from urllib.parse import unquote, urlsplit

from . import protocol

BACKOFF = (1, 2, 5, 10, 30)
CHANNEL_LIMIT = 1 << 20


def _resolve(root, raw_path):
    """Percorso di un file dentro `root`, o None se esce dalla cartella o non esiste."""
    path = unquote(urlsplit(raw_path).path)
    if "\0" in path:
        return None
    target = os.path.realpath(os.path.join(root, path.lstrip("/")))
    if os.path.isdir(target):
        target = os.path.join(target, "index.html")
    inside = target == root or target.startswith(root + os.sep)
    return target if inside and os.path.isfile(target) else None


def respond(root, raw_path):
    target = _resolve(root, raw_path)
    if target is None:
        return protocol.error_page(404, "Questa pagina è volata via.")
    with open(target, "rb") as f:
        body = f.read()
    ctype = mimetypes.guess_type(target)[0] or "application/octet-stream"
    if ctype.startswith("text/") or ctype in ("application/javascript", "application/json"):
        ctype += "; charset=utf-8"
    return protocol.build_response(200, body, ctype)


class Host:
    def __init__(self, name, secret, root, relay_host, relay_port=protocol.PORT):
        self.name, self.secret = name, secret
        self.root = os.path.realpath(root)
        self.relay = (relay_host, relay_port)
        self.ready = asyncio.Event()
        self._tasks = set()      # l'event loop tiene solo riferimenti deboli ai task: senza questo possono sparire a metà

    async def run(self):
        """Resta posato per sempre; se il relay cade, si riconnette con una pausa crescente."""
        attempt = 0
        while True:
            try:
                await self._session()
                attempt = 0
            except PermissionError as e:
                raise SystemExit(str(e))
            except (OSError, asyncio.IncompleteReadError, protocol.DuckError) as e:
                print("ducknet host: relay non raggiungibile (%s)" % e, file=sys.stderr)
            self.ready.clear()
            await asyncio.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
            attempt += 1

    async def _session(self):
        reader, writer = await asyncio.open_connection(*self.relay, limit=CHANNEL_LIMIT)
        try:
            writer.write(("PERCH %s %s\n" % (self.name, self.secret)).encode())
            if (await protocol.read_line(reader)) != "OK":
                raise PermissionError("il relay ha rifiutato %s: nome o segreto sbagliato" % self.name)
            self.ready.set()
            async for raw in reader:
                parts = raw.decode("utf-8", "replace").split()
                if len(parts) == 2 and parts[0] == "INCOMING":
                    task = asyncio.ensure_future(self._answer(parts[1]))
                    self._tasks.add(task)
                    task.add_done_callback(self._tasks.discard)
        finally:
            writer.close()

    async def _answer(self, fetch_id):
        try:
            reader, writer = await asyncio.open_connection(*self.relay)
            writer.write(("FETCH %s\n" % fetch_id).encode())
            try:
                _, path, _, _ = await protocol.read_request(reader)
                writer.write(respond(self.root, path))
            except protocol.DuckError:
                writer.write(protocol.error_page(400, "Richiesta non valida."))
            await writer.drain()
            writer.close()
        except OSError:
            pass
