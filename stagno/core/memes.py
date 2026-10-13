"""I meme di Stagno: papere, didascalie e frasi di caricamento. Tutto generato, nessuna immagine."""
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class Meme:
    emoji: str
    top: dict
    bottom: dict


MEMES = [
    Meme("🦆", {"en": "ME: I'LL USE HTTP", "it": "IO: USO HTTP"},
         {"en": "THE DUCK: NO", "it": "LA PAPERA: NO"}),
    Meme("🦆", {"en": "404", "it": "404"},
         {"en": "DUCK NOT FOUND", "it": "PAPERA NON TROVATA"}),
    Meme("🐥", {"en": "WHEN THE RELAY IS UP", "it": "QUANDO IL RELAY FUNZIONA"},
         {"en": "QUACK QUACK QUACK", "it": "QUACK QUACK QUACK"}),
    Meme("🦆", {"en": "ONE SERVER", "it": "UN SOLO SERVER"},
         {"en": "INFINITE DUCKS", "it": "PAPERE INFINITE"}),
    Meme("🍞", {"en": "THEY CALL IT A CACHE", "it": "LO CHIAMANO CACHE"},
         {"en": "I CALL IT BREADCRUMBS", "it": "IO LO CHIAMO PANE PER LE PAPERE"}),
    Meme("🦆", {"en": "REVERSE TUNNEL?", "it": "TUNNEL INVERSO?"},
         {"en": "THE DUCK DIVES FIRST", "it": "LA PAPERA SI IMMERGE PRIMA"}),
    Meme("🌊", {"en": "NAT: YOU SHALL NOT PASS", "it": "NAT: NON PASSERAI"},
         {"en": "DUCK: *SWIMS UNDER*", "it": "PAPERA: *PASSA SOTTO*"}),
    Meme("🦆", {"en": "DNS IS DOWN", "it": "IL DNS È GIÙ"},
         {"en": "IT'S ALWAYS THE DUCK", "it": "È SEMPRE COLPA DELLA PAPERA"}),
    Meme("🦢", {"en": "SWAN STARTUP", "it": "STARTUP DI CIGNI"},
         {"en": "UGLY DUCKLING 2.0", "it": "BRUTTO ANATROCCOLO 2.0"}),
    Meme("🦆", {"en": "ENCRYPTION?", "it": "CIFRATURA?"},
         {"en": "NEXT VERSION, PROMISE", "it": "PROSSIMA VERSIONE, PROMESSO"}),
]

LOADING = {
    "en": ["Quacking…", "Waddling to the relay…", "Asking the pond…", "Paddling…", "Ruffling feathers…"],
    "it": ["Quackando…", "Sguazzando verso il relay…", "Chiedendo allo stagno…", "Pagaiando…",
           "Arruffando le piume…"],
    "ru": ["Крякаем…", "Плывём к ретранслятору…", "Спрашиваем у пруда…", "Гребём лапками…"],
}


def _text(table, lang):
    return table.get(lang) or table["en"]


def pick(rng=random):
    return rng.choice(MEMES)


def caption(meme, lang):
    return _text(meme.top, lang), _text(meme.bottom, lang)


def loading_line(lang, rng=random):
    return rng.choice(LOADING.get(lang) or LOADING["en"])
