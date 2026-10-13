"""I nomi .duck registrati e i loro segreti. Un file JSON, condiviso da DNS e relay."""
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile

NAME = re.compile(r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?\.duck$")


def valid_name(name):
    return bool(NAME.match(name or ""))


def _hash(secret):
    return hashlib.sha256(secret.encode()).hexdigest()


class Registry:
    def __init__(self, path):
        self.path = path
        self._mtime = None
        self._names = {}

    def _load(self):
        try:
            mtime = os.stat(self.path).st_mtime_ns
        except FileNotFoundError:
            self._names, self._mtime = {}, None
            return
        if mtime != self._mtime:
            with open(self.path) as f:
                self._names = json.load(f)
            self._mtime = mtime

    def names(self):
        self._load()
        return sorted(self._names)

    def exists(self, name):
        self._load()
        return name in self._names

    def verify(self, name, secret):
        self._load()
        stored = self._names.get(name)
        return stored is not None and hmac.compare_digest(stored, _hash(secret or ""))

    def add(self, name):
        """Registra un nome nuovo e ritorna il suo segreto (l'unica volta che lo si vede)."""
        if not valid_name(name):
            raise ValueError("nome non valido: solo lettere minuscole, cifre e trattini, e finisce in .duck")
        self._load()
        if name in self._names:
            raise ValueError("nome già registrato")
        secret = secrets.token_urlsafe(24)
        self._names[name] = _hash(secret)
        self._save()
        return secret

    def remove(self, name):
        self._load()
        if self._names.pop(name, None) is None:
            raise ValueError("nome non registrato")
        self._save()

    def _save(self):
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(self.path)))
        with os.fdopen(fd, "w") as f:
            json.dump(self._names, f, indent=1, sort_keys=True)
        os.chmod(tmp, 0o600)
        os.replace(tmp, self.path)
        self._mtime = None
