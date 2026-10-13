# Installazione sul server

Il server DuckNet fa girare **due servizi**: il DNS (UDP 53) e il relay (TCP 4343). Possono stare
su un container/VM qualsiasi della rete di casa; basta che il router inoltri le due porte.

## Prerequisiti

- Python 3.10+ (nessun pacchetto da installare).
- Un record **A** `dns.quezka.uk` → IP pubblico di casa. Se l'IP cambia serve un DNS dinamico.
- Sul router: inoltro **UDP 53** e **TCP 4343** verso il container.
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
DUCKNET_SECRET=... python3 -m ducknet host pippo.duck ./cartella --relay dns.quezka.uk
```

Serve `index.html` nella cartella. Se il relay cade o la rete salta, l'host si riconnette da solo
(pause da 1 a 30 secondi). Per tenerlo acceso sempre, fallo girare con un servizio systemd o `tmux`.

## Verifica

```sh
python3 -m ducknet get duck://pippo.duck/ --dns dns.quezka.uk      # dal portatile, anche fuori casa
journalctl -u ducknet-dns -u ducknet-relay -f                       # sul server
```

Se `get` dà "non esiste su DuckNet": il nome non è registrato (o il DNS non è raggiungibile).
Se dà 503: il nome esiste ma nessun host è posato. Se non risponde nulla: controlla l'inoltro delle porte.

## Promemoria del server

Il server DuckNet non esiste ancora: vedi `homelab-server-pending` nella memoria. Il container
va messo con `onboot` come gli altri.
