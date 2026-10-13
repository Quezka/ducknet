# Architettura

## I pezzi

| Modulo               | Ruolo                                                                       |
|----------------------|-----------------------------------------------------------------------------|
| `ducknet/protocol.py`| lettura/scrittura dei messaggi DUCK/1, limiti, pagina d'errore              |
| `ducknet/registry.py`| nomi `.duck` registrati e hash dei segreti (file JSON)                      |
| `ducknet/dns.py`     | server DNS UDP per i `.duck` + piccolo client `resolve()`                   |
| `ducknet/relay.py`   | il relay: visitatori, host (tunnel inversi), incollaggio delle connessioni  |
| `ducknet/host.py`    | l'host: serve una cartella, si riconnette al relay se cade                  |
| `ducknet/client.py`  | `fetch("duck://...")`: DNS → relay → risposta. Lo userà il browser          |
| `ducknet/cli.py`     | riga di comando `ducknet ...`                                               |

Dipendenze: solo libreria standard (asyncio). Layering: `protocol` e `registry` non importano
nient'altro del progetto; `relay`, `host`, `dns` e `client` dipendono solo da loro.

## Perché i tunnel inversi

Hai un solo server fisico, e chi ospita un sito (tu, i tuoi amici) sta dietro un NAT. Quindi:
l'host apre **lui** la connessione verso il relay e la tiene aperta; il relay non deve mai
raggiungere l'host. Per ogni visita l'host apre una seconda connessione (`FETCH`), che il relay
collega al visitatore. Il relay non guarda il contenuto: copia byte e basta.

## Sicurezza: com'è oggi

- **Il DNS non è un resolver aperto**: risponde solo per i `.duck` registrati, a tutto il resto REFUSED.
- **Registro**: i segreti sono salvati come SHA-256, il file ha permessi 600 e viene riscritto in
  modo atomico. DNS e relay rileggono il file quando cambia, senza riavvio.
- **Percorsi**: l'host risolve il percorso con `realpath` e rifiuta tutto ciò che esce dalla cartella
  (anche con `..`, `%2e%2e`, `%2f`). C'è un test dedicato.
- **Limiti**: righe, intestazioni e corpo hanno un massimo; la prima riga deve arrivare entro 10 s.
- **Il relay non apre mai connessioni verso l'esterno**: sa solo accettare.

## Limiti conosciuti (da sistemare)

1. **Nessuna cifratura**: segreto e traffico in chiaro. Soluzione prevista: TLS sul relay (certificato
   per `dns.quezka.uk` o CA privata distribuita col browser), poi il segreto non è più sniffabile.
2. Nessun limite di banda o di connessioni per host o per IP.
3. Un solo host per nome; nessun bilanciamento.
4. Il DNS risponde solo su IPv4 (A). Per AAAA risponde "esiste ma senza indirizzo".
5. Il relay incolla tutta la risposta: un host lento tiene occupata la connessione (nessun timeout
   dopo l'inizio dello scambio).
6. Il browser (Stagno, vedi `browser.md`) è alla prima versione: mancano segnalibri, cronologia, download.

## Idee per dopo

- Stagno: segnalibri, cronologia, ricerca nella pagina, download, e un installer per Windows.
- Quack **HEAD/POST** e cookie, se serve ai siti.
- Pagina di stato del relay (quali nomi sono online), magari nel Quezka Dash.
- `ducknet register` via rete con un token di amministrazione, invece di lavorare sul file.
