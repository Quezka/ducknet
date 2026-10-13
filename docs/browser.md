# Stagno, il browser di DuckNet

Stagno è un browser **nativo** (Qt / PySide6) che parla DUCK/1. Dentro usa il motore web di Chromium
(QtWebEngine) per mostrare l'HTML, ma ogni richiesta `duck://` passa dal nostro DNS e dal relay,
non da HTTP.

## Installare (solo per l'utente, senza root)

```sh
./install.sh        # crea ~/.local/share/stagno/venv, i comandi stagno e ducknet, l'icona e la voce di menu
./uninstall.sh      # toglie tutto
```

Serve Python 3.10+ con il modulo `venv` (su Debian/Ubuntu: `sudo apt install python3-venv`).
La prima volta scarica PySide6 (~250 MB). Tutto vive in `~/.local`, nessun `sudo`.
Registra anche Stagno come programma per i link `duck://` (`xdg-mime`).

Alternative: `pipx install "./ducknet[browser]"` oppure, dentro un venv, `pip install ".[browser]"`.
Su Windows: `pip install --user ".[browser]"`, poi `stagno`.

## Usarlo

```sh
stagno                       # apre la home
stagno duck://pippo.duck/    # apre un indirizzo
```

- Barra degli indirizzi: scrivi `pippo.duck`, `pippo` (vale `pippo.duck`) o `duck://pippo.duck/pagina`.
- Schede, indietro/avanti, ricarica/ferma, zoom, `Ctrl+T` `Ctrl+W` `Ctrl+L` `F5` `Alt+←/→` `Ctrl +/−/0`.
- Menu ☰ → Impostazioni: tema (sistema/chiaro/scuro), lingua (it, ru, en), server DNS (di default
  `dns.quezka.uk`).
- **Solo DuckNet**: Stagno non apre `http://` né `https://`, né pagine né risorse (immagini, script)
  caricate da una pagina duck. Mostra invece una pagina a tema. Così nessun sito può far uscire il
  browser su Internet o verso la tua rete locale.
- Le pagine interne stanno a `duck://stagno/` (home, avvisi): il nome `stagno` non ha il `.duck`,
  quindi nessun host può spacciarsi per lui.

Provarlo in locale, contro un DNS e un relay di prova (vedi il README):

```sh
stagno --dns 127.0.0.1 --dns-port 5353 duck://pippo.duck/     # valgono solo per questa sessione
```

## Aggiornamenti automatici (OTA)

- Menu ☰ → **Cerca aggiornamenti…** controlla subito. In più, circa una volta al giorno, in automatico.
- **Il consenso**: la prima volta Stagno chiede il permesso; finché non dici sì non contatta GitHub da solo.
  Si cambia in Impostazioni → «Cerca aggiornamenti automaticamente».
- Le versioni vengono dalle release di GitHub (`Quezka/ducknet`). Il download è verificato col SHA-256 che
  GitHub pubblica; se non coincide non si installa nulla.
- **Linux** (copia installata col .deb): scarica il nuovo .deb e lo installa con `pkexec apt-get`, quindi
  compare la finestra della password di sistema; poi Stagno si riapre da solo.
- **Windows** (copia installata col setup): lancia il nuovo setup in silenzio, che chiude Stagno, lo
  aggiorna sul posto e lo riapre.
- Una copia lanciata dai sorgenti o portatile non si aggiorna da sola: la finestra offre «Apri la pagina di download».
- Tutto questo parla col web normale **solo da Python** (`stagno/core/update_sources.py`), mai dal motore web:
  le pagine duck restano chiuse al web. Per far funzionare l'aggiornamento i file delle release devono
  chiamarsi `stagno_<v>_<arch>.deb` e `Stagno-<v>-windows-x64-setup.exe`.

## Com'è fatto

```
stagno/core/   (senza Qt, testabile da solo)
  address.py   cosa hai scritto -> duck / interna / bloccata / non valida
  fetcher.py   scarica via ducknet.client; gli errori diventano pagine, non eccezioni
  pages.py     home, errori e blocco, come HTML (con meme)
  memes.py     meme e frasi di caricamento
  updates.py   gli aggiornamenti come caso d'uso (consenso, versioni, download/installazione)
  update_sources.py   le release di GitHub e gli installer per sistema (.deb, setup Windows)
  i18n.py, catalogs.py   inglese di base + italiano e russo
stagno/ui/     (Qt)
  scheme.py    lo schema duck:// nel motore web + blocco del web normale
  window.py    finestra, schede, barra degli indirizzi
  settings.py, theme.py, icons.py, updates_ui.py (controllo in background e finestra)
```

- Lo schema `duck://` è registrato prima di creare `QApplication`. Le richieste vanno su un pool
  di thread (il DNS e il relay sono bloccanti) e la risposta torna al thread della UI.
- `OnlyDuckInterceptor` blocca ogni richiesta con schema diverso da `duck`, `data`, `blob`, `about`, `qrc`.
- Le stringhe dell'interfaccia passano da `_()` (o `N_()` se tradotte più tardi); un test controlla
  che italiano e russo abbiano le stesse chiavi e che ogni stringa usata sia tradotta.
- `tests/test_architecture.py` impedisce a `stagno/core` di importare Qt o la UI.
- `tests/test_stagno_ui.py` avvia il browser vero (senza schermo) contro un DNS, un relay e un host
  reali e controlla caricamento, UTF-8, immagini, errori, blocco dei link http.

## Limiti attuali

- Niente segnalibri, cronologia persistente, ricerca nella pagina, download, né finestre private.
- Niente cifratura (limite di DuckNet, vedi `architettura.md`): le pagine `duck://` non sono "sicure" per il motore.
- Le pagine duck usano il normale modello di sicurezza del web (same-origin ecc.), come un sito qualunque.
- Il primo avvio non è stato provato su Windows; l'installer (Inno Setup, come Quire) non c'è ancora.
- Un'icona vera per il launcher è abbozzata (`stagno/assets/stagno.svg`): da rifinire.
