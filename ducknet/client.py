"""Il client di DuckNet: risolve un indirizzo duck:// col nostro DNS e lo scarica. Lo userà il browser."""
import asyncio
import re
from urllib.parse import urlsplit

from . import dns, protocol

DEFAULT_DNS = "dns.quezka.uk"


def parse_url(url):
    """'duck://nome.duck/percorso' (o anche solo 'nome.duck/percorso') -> (nome, percorso)."""
    m = re.match(r"^(?:duck://)?([^/?#]+)(/[^#]*)?", url.strip())
    if not m:
        raise ValueError("indirizzo non valido: " + url)
    return m.group(1).lower(), m.group(2) or "/"


async def fetch(url, dns_server=DEFAULT_DNS, dns_port=53, relay_port=protocol.PORT, timeout=15.0):
    """Ritorna (codice, motto, intestazioni, corpo)."""
    name, path = parse_url(url)
    loop = asyncio.get_running_loop()
    ip = await loop.run_in_executor(None, dns.resolve, name, dns_server, dns_port)
    reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, relay_port), timeout)
    try:
        writer.write(protocol.build_request(name, path))
        await writer.drain()
        return await asyncio.wait_for(protocol.read_response(reader), timeout)
    finally:
        writer.close()
