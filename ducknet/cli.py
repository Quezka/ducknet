"""Riga di comando: ducknet dns | relay | host | register | unregister | names | get"""
import argparse
import asyncio
import os
import sys

from . import client, dns, protocol
from .host import Host
from .registry import Registry
from .relay import Relay


def _registry(args):
    return Registry(args.registry)


async def _serve_forever(*servers):
    await asyncio.Event().wait()


def cmd_dns(args):
    async def main():
        await dns.serve(_registry(args), args.relay_ip, args.bind, args.port)
        print("DNS DuckNet su %s:%d, i nomi .duck puntano a %s" % (args.bind, args.port, args.relay_ip))
        await _serve_forever()
    asyncio.run(main())


def cmd_relay(args):
    async def main():
        server = await Relay(_registry(args)).serve(args.bind, args.port)
        print("Relay DuckNet su %s:%d" % (args.bind, args.port))
        async with server:
            await server.serve_forever()
    asyncio.run(main())


def cmd_host(args):
    secret = os.environ.get("DUCKNET_SECRET")
    if not secret:
        sys.exit("imposta DUCKNET_SECRET col segreto che ti ha dato `ducknet register`")
    print("Servo %s come %s tramite %s:%d" % (args.root, args.name, args.relay, args.relay_port))
    asyncio.run(Host(args.name, secret, args.root, args.relay, args.relay_port).run())


def cmd_register(args):
    try:
        secret = _registry(args).add(args.name)
    except ValueError as e:
        sys.exit(str(e))
    print("Registrato %s\nDUCKNET_SECRET=%s\n(il segreto non si può rivedere: salvalo)" % (args.name, secret))


def cmd_unregister(args):
    try:
        _registry(args).remove(args.name)
    except ValueError as e:
        sys.exit(str(e))
    print("Rimosso", args.name)


def cmd_names(args):
    for name in _registry(args).names():
        print(name)


def cmd_get(args):
    try:
        code, motto, headers, body = asyncio.run(
            client.fetch(args.url, args.dns, args.dns_port, args.relay_port))
    except (LookupError, OSError, protocol.DuckError, asyncio.TimeoutError) as e:
        sys.exit("ducknet: %s" % (e or type(e).__name__))
    print("DUCK/1 %d %s" % (code, motto), file=sys.stderr)
    sys.stdout.buffer.write(body)


def main(argv=None):
    p = argparse.ArgumentParser(prog="ducknet")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_):
        s = sub.add_parser(name, help=help_)
        s.set_defaults(fn=fn)
        return s

    def server_opts(s, port):
        s.add_argument("--registry", default=os.environ.get("DUCKNET_REGISTRY", "ducks.json"))
        s.add_argument("--bind", default="0.0.0.0")
        s.add_argument("--port", type=int, default=port)

    s = add("dns", cmd_dns, "server DNS (dns.quezka.uk)")
    server_opts(s, 53)
    s.add_argument("--relay-ip", required=True, help="IP pubblico del relay, dove puntano i nomi .duck")
    server_opts(add("relay", cmd_relay, "relay dei tunnel"), protocol.PORT)

    s = add("host", cmd_host, "pubblica una cartella su DuckNet")
    s.add_argument("name")
    s.add_argument("root")
    s.add_argument("--relay", default=client.DEFAULT_DNS)
    s.add_argument("--relay-port", type=int, default=protocol.PORT)

    for name, fn, help_ in (("register", cmd_register, "registra un nome .duck"),
                            ("unregister", cmd_unregister, "rimuove un nome")):
        s = add(name, fn, help_)
        s.add_argument("name")
        s.add_argument("--registry", default=os.environ.get("DUCKNET_REGISTRY", "ducks.json"))
    s = add("names", cmd_names, "elenca i nomi registrati")
    s.add_argument("--registry", default=os.environ.get("DUCKNET_REGISTRY", "ducks.json"))

    s = add("get", cmd_get, "scarica un indirizzo duck://")
    s.add_argument("url")
    s.add_argument("--dns", default=client.DEFAULT_DNS)
    s.add_argument("--dns-port", type=int, default=53)
    s.add_argument("--relay-port", type=int, default=protocol.PORT)

    args = p.parse_args(argv)
    try:
        args.fn(args)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
