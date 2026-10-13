"""Cosa ha scritto l'utente nella barra degli indirizzi -> dove andare."""
import re
from dataclasses import dataclass
from urllib.parse import quote

from ducknet.registry import valid_name

HOME = "duck://stagno/"
_PATH = re.compile(r"^(/[^\s#]*)?$")


@dataclass(frozen=True)
class Address:
    kind: str      # "duck" | "internal" | "blocked" | "invalid"
    url: str = ""


def parse(text):
    text = (text or "").strip()
    if not text:
        return Address("invalid")
    low = text.lower()
    if low.startswith(("http://", "https://", "ftp://", "file://")):
        return Address("blocked", text)
    rest = text[len("duck://"):] if low.startswith("duck://") else text
    host, slash, tail = rest.partition("/")
    host = host.lower()
    path = slash + tail
    if not _PATH.match(path):
        return Address("invalid")
    path = quote(path or "/", safe="/?&=%:@+,;~-_.!*'()")
    if host == "stagno":
        return Address("internal", "duck://stagno" + path)
    if re.fullmatch(r"[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?", host):
        host += ".duck"                      # «pippo» vale «pippo.duck»
    if not valid_name(host):
        return Address("invalid")
    return Address("duck", "duck://%s%s" % (host, path))
