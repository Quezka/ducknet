"""Tiene DuckNet raggiungibile quando l'IP pubblico di casa cambia.

Legge l'IP pubblico; se è cambiato aggiorna `DUCKNET_RELAY_IP` e riavvia il DNS. Se c'è un token Cloudflare
(`/etc/ducknet/cloudflare.token`, permesso Zone → DNS → Edit) tiene aggiornato anche il record A di dns.quezka.uk,
senza proxy: UDP 53 e TCP 4343 non passano dal proxy di Cloudflare. Lanciato ogni 10 minuti da `ducknet-ddns.timer`.
"""
import ipaddress
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

ENV = "/etc/ducknet/ducknet.env"
TOKEN = "/etc/ducknet/cloudflare.token"
ZONE, NAME = "quezka.uk", "dns.quezka.uk"
API = "https://api.cloudflare.com/client/v4"
ASK_IP = "https://api.ipify.org"


def public_ip(opener=urllib.request.urlopen):
    with opener(ASK_IP, timeout=20) as r:
        text = r.read().decode().strip()
    ip = ipaddress.ip_address(text)  # un errore qui non deve mai finire nella configurazione
    if ip.version != 4 or not ip.is_global:
        raise ValueError("non è un IPv4 pubblico: %s" % text)
    return text


def update_env(path, ip):
    """Scrive il nuovo IP; vero se è cambiato."""
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    new = ["DUCKNET_RELAY_IP=" + ip if l.startswith("DUCKNET_RELAY_IP=") else l for l in lines]
    if not any(l.startswith("DUCKNET_RELAY_IP=") for l in new):
        new.append("DUCKNET_RELAY_IP=" + ip)
    if new == lines:
        return False
    with open(path + ".part", "w", encoding="utf-8") as f:
        f.write("\n".join(new) + "\n")
    os.replace(path + ".part", path)
    return True


def _call(opener, token, method, path, body=None):
    request = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                     headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with opener(request, timeout=20) as r:
        answer = json.loads(r.read())
    if not answer.get("success"):
        raise RuntimeError("Cloudflare: %s" % answer.get("errors"))
    return answer["result"]


def update_record(token, ip, opener=urllib.request.urlopen):
    """Crea o corregge il record A; vero se ha cambiato qualcosa."""
    zones = _call(opener, token, "GET", "/zones?name=" + urllib.parse.quote(ZONE))
    if not zones:
        raise RuntimeError("Cloudflare: zona %s non trovata" % ZONE)
    base = "/zones/%s/dns_records" % zones[0]["id"]
    found = _call(opener, token, "GET", base + "?type=A&name=" + urllib.parse.quote(NAME))
    wanted = {"type": "A", "name": NAME, "content": ip, "proxied": False, "ttl": 300,
              "comment": "DuckNet: lo aggiorna ducknet-ddns"}
    if not found:
        _call(opener, token, "POST", base, wanted)
        return True
    if found[0]["content"] == ip and not found[0].get("proxied"):
        return False
    _call(opener, token, "PUT", "%s/%s" % (base, found[0]["id"]), wanted)
    return True


def main():
    ip = public_ip()
    if update_env(ENV, ip):
        print("IP pubblico ora %s: riavvio il DNS" % ip)
        subprocess.run(["systemctl", "restart", "ducknet-dns"], check=True)
    if os.path.exists(TOKEN):
        with open(TOKEN, encoding="utf-8") as f:
            if update_record(f.read().strip(), ip):
                print("Record %s ora punta a %s" % (NAME, ip))
    else:
        print("Nessun token Cloudflare in %s: il record %s non viene toccato" % (TOKEN, NAME), file=sys.stderr)


if __name__ == "__main__":
    main()
