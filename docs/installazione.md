# Installazione sul server

Il server DuckNet fa girare **due servizi**: il DNS (DNS-over-HTTPS sulla porta 8053, più UDP 53 per la LAN)
e il relay (TCP 4343). Possono stare su un container/VM qualsiasi della rete di casa.

## Prerequisiti

- Python 3.10+ (nessun pacchetto da installare).
- Un tunnel Cloudflare con l'hostname `dns.quezka.uk` → `http://<container>:8053`. Così il DNS non
  apre porte e l'IP di casa non compare in nessun record.
- Sul router: inoltro **TCP 4343** verso il container (il relay è l'unica porta aperta).
- L'IP pubblico va in `DUCKNET_RELAY_IP`: è l'indirizzo a cui il DNS fa puntare tutti i `.duck`.

## Passi

```sh
# sul container
useradd --system --home /opt/ducknet ducknet
mkdir -p /opt/ducknet /etc/ducknet /var/lib/ducknet
chown ducknet: /var/lib/ducknet
# copia il progetto in /opt/ducknet (cartella `ducknet/`), poi:
cp deploy/ducknet.env.example /etc/ducknet/ducknet.env   # e metti l'IP pubblico
cp deploy/ducknet-dns.service deploy/ducknet-relay.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now ducknet-dns ducknet-relay
```

Il DNS usa la porta 53 senza girare da root grazie a `AmbientCapabilities=CAP_NET_BIND_SERVICE`.
Se il container ha già un resolver su 53 (es. `systemd-resolved`), liberala oppure usa un altro IP.

## Registrare un nome

```sh
sudo -u ducknet python3 -m ducknet register pippo.duck --registry /var/lib/ducknet/ducks.json
```

Stampa `DUCKNET_SECRET=...` una volta sola: va dato a chi ospita il sito. Per rimuovere:
`ducknet unregister pippo.duck`. Per elencare: `ducknet names`. Nessun riavvio: DNS e relay
rileggono il registro quando cambia.

## Pubblicare un sito (da qualsiasi computer)

```sh
DUCKNET_SECRET=... python3 -m ducknet host pippo.duck ./cartella
```

Il relay lo trova da solo: chiede al DNS il proprio nome (`--relay HOST` per forzarlo).
Serve `index.html` nella cartella. Se il relay cade o la rete salta, l'host si riconnette da solo
(pause da 1 a 30 secondi). Per tenerlo acceso sempre, fallo girare con un servizio systemd o `tmux`.

## Verifica

```sh
python3 -m ducknet get duck://pippo.duck/      # dal portatile, anche fuori casa (DNS-over-HTTPS)
journalctl -u ducknet-dns -u ducknet-relay -f                       # sul server
```

Se `get` dà "non esiste su DuckNet": il nome non è registrato (o il DNS non è raggiungibile).
Se dà 503: il nome esiste ma nessun host è posato. Se non risponde nulla: controlla l'inoltro delle porte.

## IP che cambia

L'IP pubblico di casa cambia, quindi `ducknet-ddns.timer` lo controlla ogni 10 minuti e aggiorna `DUCKNET_RELAY_IP`.
Il DNS riparte e i `.duck` puntano al nuovo IP. `dns.quezka.uk` passa dal tunnel: nessun record da aggiornare.

```sh
cp deploy/ducknet-ddns.service deploy/ducknet-ddns.timer /etc/systemd/system/
systemctl daemon-reload && systemctl enable --now ducknet-ddns.timer
```
