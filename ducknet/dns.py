"""Il server DNS di DuckNet (dns.quezka.uk) e il suo client minimale.

Risponde solo per i nomi .duck registrati: li risolve verso il relay. Non è un resolver
generico (per il resto risponde REFUSED), così non può essere usato per amplificare attacchi.

Due ingressi con le stesse risposte: UDP (porta 53, per la LAN) e DNS-over-HTTPS (RFC 8484,
`/dns-query`), che passa dal tunnel Cloudflare: niente porte aperte, IP di casa nascosto.
"""
import asyncio
import base64
import socket
import struct
import urllib.request
from urllib.parse import parse_qs, urlsplit

from . import __version__

TTL = 60
A, AAAA = 1, 28


def _parse_question(packet):
    """Ritorna (nome, tipo, fine_domanda) oppure None se il pacchetto non è una query valida."""
    if len(packet) < 12:
        return None
    _, flags, qd = struct.unpack("!HHH", packet[:6])
    if flags & 0x8000 or qd != 1:  # già una risposta, o numero di domande strano
        return None
    labels, pos = [], 12
    while True:
        if pos >= len(packet):
            return None
        n = packet[pos]
        if n == 0:
            pos += 1
            break
        if n & 0xC0 or pos + 1 + n > len(packet):
            return None
        labels.append(packet[pos + 1:pos + 1 + n].decode("ascii", "replace").lower())
        pos += 1 + n
    if pos + 4 > len(packet):
        return None
    qtype, _ = struct.unpack("!HH", packet[pos:pos + 4])
    return ".".join(labels), qtype, pos + 4


def answer(packet, registry, relay_ip):
    q = _parse_question(packet)
    if q is None:
        return None
    name, qtype, end = q
    qid = packet[:2]
    opcode = (packet[2] >> 3) & 0xF
    rd = packet[2] & 1
    question = packet[12:end]
    if opcode != 0 or not name.endswith(".duck"):
        rcode, ans = 5, b""                                  # REFUSED
    elif not registry.exists(name):
        rcode, ans = 3, b""                                  # NXDOMAIN
    elif qtype == A:
        rcode = 0
        ans = b"\xc0\x0c" + struct.pack("!HHIH", A, 1, TTL, 4) + socket.inet_aton(relay_ip)
    else:
        rcode, ans = 0, b""                                  # il nome esiste, ma non per questo tipo
    flags = 0x8000 | (opcode << 11) | 0x0400 | (rd << 8) | rcode  # QR, AA, RD copiato
    return qid + struct.pack("!HHHHH", flags, 1, 1 if ans else 0, 0, 0) + question + ans


class _Server(asyncio.DatagramProtocol):
    def __init__(self, registry, relay_ip):
        self.registry, self.relay_ip = registry, relay_ip

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        try:
            reply = answer(data, self.registry, self.relay_ip)
        except Exception:
            reply = None
        if reply:
            self.transport.sendto(reply, addr)


async def serve(registry, relay_ip, host="0.0.0.0", port=53):
    transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(
        lambda: _Server(registry, relay_ip), local_addr=(host, port))
    return transport


DOH_PATH = "/dns-query"
DOH_TYPE = "application/dns-message"
_MAX_HEAD, _MAX_QUERY = 8192, 512


def _http(writer, status, body=b"", content_type="text/plain; charset=utf-8", cache=None):
    head = ["HTTP/1.1 %s" % status, "Content-Type: " + content_type, "Content-Length: %d" % len(body),
            "Connection: close"]
    if cache is not None:
        head.append("Cache-Control: max-age=%d" % cache)
    writer.write(("\r\n".join(head) + "\r\n\r\n").encode("ascii") + body)


async def _doh_query(reader):
    """Legge una richiesta HTTP; ritorna (stato_errore, None) oppure (None, pacchetto_dns)."""
    head = await reader.readuntil(b"\r\n\r\n")
    if len(head) > _MAX_HEAD:
        return "431 Request Header Fields Too Large", None
    lines = head.decode("latin-1").split("\r\n")
    try:
        method, target, _ = lines[0].split(" ", 2)
    except ValueError:
        return "400 Bad Request", None
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()
    url = urlsplit(target)
    if url.path != DOH_PATH:
        return "404 Not Found", None
    if method == "GET":
        raw = parse_qs(url.query).get("dns", [""])[0]
        try:
            return None, base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        except ValueError:
            return "400 Bad Request", None
    if method == "POST":
        if headers.get("content-type", "").split(";")[0].strip() != DOH_TYPE:
            return "415 Unsupported Media Type", None
        try:
            length = int(headers.get("content-length", ""))
        except ValueError:
            return "411 Length Required", None
        if not 0 < length <= _MAX_QUERY:
            return "413 Content Too Large", None
        return None, await reader.readexactly(length)
    return "405 Method Not Allowed", None


async def serve_doh(registry, relay_ip, host="127.0.0.1", port=8053):
    """DNS-over-HTTPS in chiaro (HTTP): il TLS lo fa Cloudflare davanti, nel tunnel."""
    async def handle(reader, writer):
        try:
            error, query = await asyncio.wait_for(_doh_query(reader), 10)
            reply = None if error else answer(query, registry, relay_ip)
            if reply:
                _http(writer, "200 OK", reply, DOH_TYPE, cache=TTL)
            else:
                _http(writer, error or "400 Bad Request", (error or "400 Bad Request").encode())
            await writer.drain()
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, asyncio.TimeoutError,
                ConnectionError, UnicodeError):
            pass
        finally:
            writer.close()
    return await asyncio.start_server(handle, host, port, limit=_MAX_HEAD)


def _query(name, qid):
    qname = b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.split(".")) + b"\0"
    return qid + struct.pack("!HHHHH", 0x0100, 1, 0, 0, 0) + qname + struct.pack("!HH", A, 1)


def _resolve_doh(name, url, timeout):
    qid = b"\0\0"  # RFC 8484: id 0, così le cache HTTP funzionano
    request = urllib.request.Request(url, data=_query(name, qid), method="POST", headers={
        "Content-Type": DOH_TYPE, "Accept": DOH_TYPE, "User-Agent": "DuckNet/" + __version__})
    with urllib.request.urlopen(request, timeout=timeout) as r:
        return qid, r.read(_MAX_QUERY)


def resolve(name, server, port=53, timeout=3.0):
    """Chiede a `server` l'IP di `name`. Solleva LookupError se il nome non esiste.

    `server` è un URL https://…/dns-query (DNS-over-HTTPS) oppure un host per il DNS su UDP (`port`)."""
    if server.startswith(("https://", "http://")):
        qid, data = _resolve_doh(name, server, max(timeout, 10.0))
    else:
        qid = b"\xd0\x0c"
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(timeout)
            s.sendto(_query(name, qid), (server, port))
            data, _ = s.recvfrom(512)
    if data[:2] != qid or len(data) < 12:
        raise LookupError("risposta DNS non valida")
    rcode, ancount = data[3] & 0xF, struct.unpack("!H", data[6:8])[0]
    if rcode == 3:
        raise LookupError("%s non esiste su DuckNet" % name)
    if rcode != 0 or not ancount:
        raise LookupError("%s: il DNS non ha un indirizzo da dare" % name)
    return socket.inet_ntoa(data[-4:])
