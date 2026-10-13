# 🦆 DuckNet

Un'alternativa (giocosa) a HTTP: protocollo **DUCK/1**, indirizzi `duck://nome.duck`, DNS suo
(`dns.quezka.uk`) e tunnel suoi. Solo libreria standard di Python, nessuna dipendenza.

## Come funziona

```
 browser ──DNS──▶ dns.quezka.uk        «dov'è pippo.duck?»  →  IP del relay
 browser ──QUACK pippo.duck /──▶ relay ◀──tunnel── host (dietro NAT, nessuna porta aperta)
```

- **DNS** (`ducknet dns`): risolve solo i `.duck` registrati (gli altri nomi: REFUSED, quindi niente
  open resolver). Tutti puntano al relay.
- **Relay** (`ducknet relay`, porta 4343): l'unica porta aperta del server. Fa da tubo tra visitatore e host.
- **Host** (`ducknet host`): chi pubblica un sito si *posa* sul relay con una connessione in uscita
  (tunnel inverso, come ngrok/frp): per ogni visita il relay avvisa, l'host apre una connessione
  `FETCH` e il relay la incolla al visitatore. Così un solo server fisico basta per ospitare molti siti.
- **Registro** (`ducks.json`): nomi e hash dei segreti, condiviso da DNS e relay.

## Il protocollo DUCK/1

```
QUACK pippo.duck /pagina.html          DUCK/1 200 QUACK
content-length: 0                      content-type: text/html; charset=utf-8
                                       content-length: 14

                                       <h1>quack</h1>
```

Una connessione = una richiesta. Codici: 200 QUACK, 400 QUACK-ATTO, 404 NESSUNA-PAPERA,
502 STAGNO-ASCIUTTO (l'host non risponde), 503 PAPERA-ASSENTE (esiste ma è offline).

## Documentazione

- [Il protocollo DUCK/1](docs/protocollo.md)
- [Architettura, sicurezza e limiti](docs/architettura.md)
- [Installazione sul server](docs/installazione.md)

## Provarlo in locale

```sh
python3 -m ducknet register pippo.duck          # stampa DUCKNET_SECRET=...
python3 -m ducknet dns --relay-ip 127.0.0.1 --port 5353 &
python3 -m ducknet relay &
DUCKNET_SECRET=... python3 -m ducknet host pippo.duck example-site --relay 127.0.0.1 &
python3 -m ducknet get duck://pippo.duck/ --dns 127.0.0.1 --dns-port 5353
```

Test: `python3 -m unittest discover -s tests`

## Mettere online (server di casa)

1. Il nome `dns.quezka.uk` deve avere un record A verso l'IP pubblico del server.
2. Sul router: inoltra **UDP 53** (DNS) e **TCP 4343** (relay) al server.
3. Copia il progetto in `/opt/ducknet`, crea l'utente `ducknet`, `/var/lib/ducknet/`,
   `/etc/ducknet/ducknet.env` (vedi `deploy/`), installa le due unit systemd.
4. Registra i nomi sul server: `python3 -m ducknet register nome.duck --registry /var/lib/ducknet/ducks.json`.
5. Chi ospita un sito, da dove vuole: `DUCKNET_SECRET=... ducknet host nome.duck ./cartella --relay dns.quezka.uk`.

## Il browser (da fare)

Il client (`ducknet/client.py`: `fetch("duck://...")`) è già pronto. Il browser sarà una finestra
con barra degli indirizzi che lo usa e mostra l'HTML, con i meme. Per ora c'è `ducknet get`.

## Limiti attuali, da sapere

- **Niente cifratura**: il segreto dell'host e il traffico viaggiano in chiaro. Prossimo passo: TLS sul relay.
- Il browser deve usare per forza il nostro DNS (nessun sistema DNS normale conosce `.duck`).
- Nessun limite di banda/connessioni per host, e un solo host per nome.
