"""Scarica un indirizzo duck:// e ne fa una risposta pronta per il motore web (o una pagina d'errore)."""
import asyncio
from dataclasses import dataclass

from ducknet import client, protocol

from . import pages
from .address import HOME


@dataclass(frozen=True)
class Config:
    dns_server: str = client.DEFAULT_DNS
    dns_port: int = 53
    relay_port: int = protocol.PORT


@dataclass(frozen=True)
class Reply:
    content_type: str
    body: bytes


def _html(text):
    return Reply("text/html; charset=utf-8", text.encode("utf-8"))


def load(url, config):
    """`url` è duck://nome.duck/percorso. Non solleva mai: gli errori diventano pagine."""
    try:
        code, motto, headers, body = asyncio.run(
            client.fetch(url, config.dns_server, config.dns_port, config.relay_port))
    except LookupError:
        return _html(pages.not_found(client.parse_url(url)[0]))
    except protocol.DuckError:
        return _html(pages.bad_answer())
    except (OSError, asyncio.TimeoutError, asyncio.IncompleteReadError) as e:
        return _html(pages.unreachable(str(e) or type(e).__name__))
    if code >= 400 and not body:
        return _html(pages.status_error(code, motto))
    return Reply(headers.get("content-type", "application/octet-stream"), body)


def load_internal(path_and_query):
    return _html(pages.internal(path_and_query))


__all__ = ["Config", "Reply", "load", "load_internal", "HOME"]
