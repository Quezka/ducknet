# Il protocollo DUCK/1

DUCK/1 è un protocollo testuale a richiesta/risposta, volutamente simile a HTTP/1.0 ma più semplice.
**Una connessione TCP = una richiesta.** Porta del relay: **4343**.

## Richiesta

```
QUACK <nome>.duck <percorso>\r\n
<intestazione>: <valore>\r\n
...
\r\n
<corpo>
```

- La prima riga ha esattamente tre campi separati da uno spazio. Il percorso comincia con `/`.
- Il nome è in minuscolo: lettere, cifre e trattini, al massimo 40 caratteri, termina con `.duck`.
- Il corpo è presente solo se c'è `content-length`. Il client invia sempre `content-length`.
- Limiti: riga massima 8192 byte, 64 intestazioni, corpo massimo 8 MiB.

## Risposta

```
DUCK/1 <codice> <motto>\r\n
content-type: ...\r\n
content-length: N\r\n
\r\n
<corpo di N byte>
```

| Codice | Motto           | Quando                                                       |
|--------|-----------------|--------------------------------------------------------------|
| 200    | QUACK           | tutto bene                                                   |
| 400    | QUACK-ATTO      | richiesta malformata                                         |
| 403    | NIENTE-STAGNO   | riservato (accesso negato)                                   |
| 404    | NESSUNA-PAPERA  | nome non registrato (dal relay) o pagina inesistente (dall'host) |
| 500    | PAPERA-ROTTA    | errore interno dell'host                                     |
| 502    | STAGNO-ASCIUTTO | l'host non ha risposto entro 10 s                            |
| 503    | PAPERA-ASSENTE  | il nome esiste ma l'host non è online                        |

I nomi in intestazione sono sempre minuscoli. Il corpo può essere qualsiasi cosa; oggi il browser
si aspetta HTML.

## Messaggi interni del relay (tunnel)

Sulla stessa porta 4343 il relay riconosce la **prima riga** della connessione:

| Prima riga                | Chi la manda | Significato                                               |
|---------------------------|--------------|-----------------------------------------------------------|
| `QUACK <nome> <percorso>` | visitatore   | una richiesta normale (vedi sopra)                        |
| `PERCH <nome> <segreto>`  | host         | "mi posano su questo nome"; risposta `OK\n` oppure `NO\n` |
| `FETCH <id>`              | host         | risposta a un `INCOMING`: il relay la incolla al visitatore |

Dopo un `PERCH` riuscito la connessione resta aperta come **canale di controllo**:

- il relay scrive `INCOMING <id>\n` per ogni visita;
- l'host può scrivere righe qualsiasi (es. `PING`), che vengono ignorate;
- se la connessione cade, il nome torna offline (503).

Una nuova `PERCH` per lo stesso nome sostituisce la precedente (un solo host per nome).

## Sequenza di una visita

```
visitatore        relay                 host
   │ QUACK n /p ───▶│                      │
   │                │── INCOMING 7 ───────▶│  (canale di controllo)
   │                │◀──────── FETCH 7 ────│  (nuova connessione dell'host)
   │                │── QUACK n /p ───────▶│  (la prima riga viene ripassata all'host)
   │◀══ DUCK/1 200 ═╪══════════════════════│  (da qui il relay fa solo da tubo)
```
