"""DUCK/1: il protocollo di DuckNet. Testuale come HTTP, ma con più papere.

Richiesta:   QUACK <nome>.duck <percorso>\\n  + intestazioni + riga vuota (+ corpo)
Risposta:    DUCK/1 <codice> <motto>\\n       + intestazioni + riga vuota + corpo

Una connessione = una richiesta. Il corpo ha sempre Content-Length.
"""
import re

PORT = 4343
MAX_LINE = 8192
MAX_HEADERS = 64
MAX_BODY = 8 * 1024 * 1024

MOTTOS = {
    200: "QUACK", 400: "QUACK-ATTO", 403: "NIENTE-STAGNO", 404: "NESSUNA-PAPERA",
    500: "PAPERA-ROTTA", 502: "STAGNO-ASCIUTTO", 503: "PAPERA-ASSENTE",
}


class DuckError(Exception):
    pass


async def read_line(reader):
    line = await reader.readline()
    if len(line) > MAX_LINE:
        raise DuckError("riga troppo lunga")
    return line.decode("utf-8", "replace").rstrip("\r\n") if line else None


async def read_headers(reader):
    headers = {}
    while True:
        line = await read_line(reader)
        if line is None:
            raise DuckError("connessione chiusa nelle intestazioni")
        if line == "":
            return headers
        if len(headers) >= MAX_HEADERS or ":" not in line:
            raise DuckError("intestazione non valida")
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()


async def read_body(reader, headers):
    try:
        length = int(headers.get("content-length", "0"))
    except ValueError:
        raise DuckError("Content-Length non valido")
    if not 0 <= length <= MAX_BODY:
        raise DuckError("corpo troppo grande")
    return await reader.readexactly(length) if length else b""


async def read_request(reader):
    """Ritorna (nome, percorso, intestazioni, corpo)."""
    line = await read_line(reader)
    parts = (line or "").split(" ")
    if len(parts) != 3 or parts[0] != "QUACK" or not parts[2].startswith("/"):
        raise DuckError("richiesta non valida")
    headers = await read_headers(reader)
    return parts[1], parts[2], headers, await read_body(reader, headers)


async def read_response(reader):
    """Ritorna (codice, motto, intestazioni, corpo)."""
    line = await read_line(reader)
    m = re.match(r"^DUCK/1 (\d{3}) (.*)$", line or "")
    if not m:
        raise DuckError("risposta non valida")
    headers = await read_headers(reader)
    return int(m.group(1)), m.group(2), headers, await read_body(reader, headers)


def build_request(name, path, headers=None, body=b""):
    head = {"content-length": str(len(body)), **(headers or {})}
    lines = ["QUACK %s %s" % (name, path)] + ["%s: %s" % kv for kv in head.items()]
    return ("\r\n".join(lines) + "\r\n\r\n").encode() + body


def build_response(code, body=b"", content_type="text/html; charset=utf-8", headers=None):
    head = {"content-type": content_type, "content-length": str(len(body)), **(headers or {})}
    lines = ["DUCK/1 %d %s" % (code, MOTTOS.get(code, "QUACK"))] + ["%s: %s" % kv for kv in head.items()]
    return ("\r\n".join(lines) + "\r\n\r\n").encode() + body


def error_page(code, text):
    body = ("<!doctype html><meta charset=utf-8><title>%d</title>"
            "<h1>🦆 %d %s</h1><p>%s</p>" % (code, code, MOTTOS.get(code, ""), text)).encode()
    return build_response(code, body)
