"""Il server DNS di DuckNet (dns.quezka.uk) e il suo client minimale.

Risponde solo per i nomi .duck registrati: li risolve verso il relay. Non è un resolver
generico (per il resto risponde REFUSED), così non può essere usato per amplificare attacchi.
"""
import asyncio
import socket
import struct

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


def resolve(name, server, port=53, timeout=3.0):
    """Chiede a `server` l'IP di `name`. Solleva LookupError se il nome non esiste."""
    qid = b"\xd0\x0c"
    qname = b"".join(bytes([len(p)]) + p.encode("ascii") for p in name.split(".")) + b"\0"
    query = qid + struct.pack("!HHHHH", 0x0100, 1, 0, 0, 0) + qname + struct.pack("!HH", A, 1)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(timeout)
        s.sendto(query, (server, port))
        data, _ = s.recvfrom(512)
    if data[:2] != qid or len(data) < 12:
        raise LookupError("risposta DNS non valida")
    rcode, ancount = data[3] & 0xF, struct.unpack("!H", data[6:8])[0]
    if rcode == 3:
        raise LookupError("%s non esiste su DuckNet" % name)
    if rcode != 0 or not ancount:
        raise LookupError("%s: il DNS non ha un indirizzo da dare" % name)
    return socket.inet_ntoa(data[-4:])
