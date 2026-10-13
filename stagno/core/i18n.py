"""Traduzioni: le stringhe sorgente sono in inglese, i cataloghi it/ru stanno in catalogs.py."""
import locale
import os

from .catalogs import IT, RU

CATALOGS = {"it": IT, "ru": RU}
_lang = "en"


def detect_language():
    raw = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
    if not raw:
        try:
            raw = locale.getlocale()[0] or ""
        except ValueError:
            raw = ""
    code = raw.lower()[:2]
    return code if code in CATALOGS else "en"


def set_language(code):
    global _lang
    _lang = code if code in CATALOGS else "en"


def language():
    return _lang


def _(text, **values):
    out = CATALOGS.get(_lang, {}).get(text, text)
    return out.format(**values) if values else out


def N_(text):
    """Segna una stringa da tradurre più tardi (con `_(variabile)`), senza tradurla ora."""
    return text
