"""Tiene DuckNet raggiungibile quando l'IP pubblico di casa cambia.

Legge l'IP pubblico; se è cambiato aggiorna `DUCKNET_RELAY_IP` e riavvia il DNS, così i nomi .duck puntano
sempre al relay. dns.quezka.uk passa dal tunnel Cloudflare (DNS-over-HTTPS): nessun record da aggiornare.
Lanciato ogni 10 minuti da `ducknet-ddns.timer`.
"""
import ipaddress
import os
import subprocess
import urllib.request

ENV = "/etc/ducknet/ducknet.env"
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


def main():
    ip = public_ip()
    if update_env(ENV, ip):
        print("IP pubblico ora %s: riavvio il DNS" % ip)
        subprocess.run(["systemctl", "restart", "ducknet-dns"], check=True)


if __name__ == "__main__":
    main()
