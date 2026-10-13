"""Il relay: l'unico pezzo con una porta aperta. Collega chi naviga a chi ospita, tramite tunnel inversi.

Tre tipi di connessione in ingresso, riconosciuti dalla prima riga:
  QUACK <nome> <percorso>   un visitatore (il browser)
  PERCH <nome> <segreto>    un host che si posa sul relay: resta aperta come canale di controllo
  FETCH <id>                l'host che risponde a una richiesta: il relay la incolla al visitatore
Il relay fa solo da tubo: non guarda il contenuto e non apre mai connessioni verso l'esterno.
"""
import asyncio
import itertools

from . import protocol
from .registry import valid_name

FETCH_TIMEOUT = 10.0
FIRST_LINE_TIMEOUT = 10.0


class Relay:
    def __init__(self, registry):
        self.registry = registry
        self.perched = {}          # nome -> writer del canale di controllo
        self.pending = {}          # id -> future in attesa della connessione FETCH
        self._ids = itertools.count(1)

    async def serve(self, host="0.0.0.0", port=protocol.PORT):
        return await asyncio.start_server(self.handle, host, port, limit=protocol.MAX_LINE)

    async def handle(self, reader, writer):
        try:
            line = await asyncio.wait_for(protocol.read_line(reader), FIRST_LINE_TIMEOUT)
            parts = (line or "").split(" ")
            if parts[0] == "QUACK" and len(parts) == 3:
                await self._visitor(reader, writer, parts[1], line)
            elif parts[0] == "PERCH" and len(parts) == 3:
                await self._perch(reader, writer, parts[1], parts[2])
            elif parts[0] == "FETCH" and len(parts) == 2:
                if not self._deliver(parts[1], reader, writer):
                    await self._close(writer)
            else:
                writer.write(protocol.error_page(400, "Non so che verso fa questa papera."))
                await self._close(writer)
        except (protocol.DuckError, asyncio.TimeoutError, ConnectionError, asyncio.IncompleteReadError):
            await self._close(writer)

    # -- host ---------------------------------------------------------------------------------------
    async def _perch(self, reader, writer, name, secret):
        if not valid_name(name) or not self.registry.verify(name, secret):
            writer.write(b"NO\n")
            return await self._close(writer)
        old = self.perched.get(name)
        if old is not None:
            await self._close(old)
        self.perched[name] = writer
        writer.write(b"OK\n")
        await writer.drain()
        try:
            while await reader.readline():      # il canale resta aperto; le righe (PING) si ignorano
                pass
        finally:
            if self.perched.get(name) is writer:
                del self.perched[name]
            await self._close(writer)

    def _deliver(self, fetch_id, reader, writer):
        fut = self.pending.pop(fetch_id, None)
        if fut is None or fut.done():
            return False
        fut.set_result((reader, writer))
        return True

    # -- visitatore ---------------------------------------------------------------------------------
    async def _visitor(self, reader, writer, name, first_line):
        if not self.registry.exists(name):
            writer.write(protocol.error_page(404, "Su DuckNet non c'è nessuna papera che si chiama %s." % name))
            return await self._close(writer)
        control = self.perched.get(name)
        if control is None:
            writer.write(protocol.error_page(503, "%s esiste, ma al momento non è online." % name))
            return await self._close(writer)
        fetch_id = str(next(self._ids))
        fut = asyncio.get_running_loop().create_future()
        self.pending[fetch_id] = fut
        try:
            control.write(("INCOMING %s\n" % fetch_id).encode())
            await control.drain()
            host_reader, host_writer = await asyncio.wait_for(fut, FETCH_TIMEOUT)
        except (asyncio.TimeoutError, ConnectionError):
            self.pending.pop(fetch_id, None)
            writer.write(protocol.error_page(502, "%s non ha risposto in tempo." % name))
            return await self._close(writer)
        host_writer.write((first_line + "\r\n").encode())
        await self._splice(reader, writer, host_reader, host_writer)

    async def _splice(self, c_reader, c_writer, h_reader, h_writer):
        async def pump(src, dst, half_close):
            try:
                while True:
                    data = await src.read(65536)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
                if half_close and dst.can_write_eof():
                    dst.write_eof()
            except ConnectionError:
                pass
        up = asyncio.ensure_future(pump(c_reader, h_writer, True))
        down = asyncio.ensure_future(pump(h_reader, c_writer, False))
        await down                      # la risposta finisce quando l'host chiude
        up.cancel()
        await self._close(c_writer)
        await self._close(h_writer)

    @staticmethod
    async def _close(writer):
        try:
            writer.close()
            await writer.wait_closed()
        except (ConnectionError, OSError):
            pass
