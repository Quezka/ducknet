"""Le pagine interne di Stagno (home, errori, blocco del web normale), come HTML."""
from html import escape
from urllib.parse import parse_qs, urlsplit

from . import memes
from .i18n import _, language

CSS = """
:root{--bg:#f5f6f8;--surface:#fff;--border:#e2e4e9;--text:#16181d;--muted:#636a75;--accent:#5b5bd6}
@media (prefers-color-scheme:dark){:root{--bg:#111214;--surface:#18191c;--border:#2a2c31;--text:#ecedef;--muted:#9aa0aa;--accent:#8182f0}}
html[data-scheme=light]{--bg:#f5f6f8;--surface:#fff;--border:#e2e4e9;--text:#16181d;--muted:#636a75;--accent:#5b5bd6}
html[data-scheme=dark]{--bg:#111214;--surface:#18191c;--border:#2a2c31;--text:#ecedef;--muted:#9aa0aa;--accent:#8182f0}
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;background:var(--bg);color:var(--text);
 font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;padding:24px}
main{max-width:560px;width:100%;text-align:center}
h1{font-size:30px;margin:8px 0}
p{color:var(--muted);margin:6px 0}
a.button{display:inline-block;margin-top:18px;padding:9px 18px;border-radius:10px;background:var(--accent);
 color:#fff;text-decoration:none;font-weight:600}
.big{font-size:84px;line-height:1.1}
.meme{position:relative;margin:22px auto 0;width:min(100%,340px,46vh);aspect-ratio:1;border-radius:14px;
 background:var(--surface);border:1px solid var(--border);display:grid;place-items:center;overflow:hidden}
.meme .emoji{font-size:clamp(60px,18vh,150px)}
.meme span{position:absolute;left:8px;right:8px;font:900 clamp(15px,3.4vh,26px)/1.1 Impact,"Arial Black",sans-serif;color:#fff;
 text-transform:uppercase;text-shadow:-2px -2px 0 #000,2px -2px 0 #000,-2px 2px 0 #000,2px 2px 0 #000}
.meme .top{top:10px}.meme .bottom{bottom:10px}
.small{font-size:13px;margin-top:22px}
"""


_scheme = ""          # "light" | "dark" | "" (lascia decidere al sistema)


def set_scheme(scheme):
    global _scheme
    _scheme = scheme if scheme in ("light", "dark") else ""


def render(title, body):
    return ("<!doctype html><html lang=%s data-scheme=%s><head><meta charset=utf-8><title>%s</title>"
            "<style>%s</style></head><body><main>%s</main></body></html>"
            % (language(), _scheme or "auto", escape(title), CSS, body))


def meme_card(meme=None):
    meme = meme or memes.pick()
    top, bottom = memes.caption(meme, language())
    return ('<div class=meme><div class=emoji>%s</div><span class=top>%s</span><span class=bottom>%s</span></div>'
            % (meme.emoji, escape(top), escape(bottom)))


def home():
    body = ("<div class=big>🦆</div><h1>%s</h1><p>%s</p><p>%s</p><p class=small>%s</p>%s"
            % (escape(_("Quack!")), escape(_("Welcome to the pond.")),
               escape(_("Type a .duck name in the address bar and press Enter.")),
               escape(_("Meme of the moment")), meme_card()))
    body += '<a class=button href="duck://stagno/">%s</a>' % escape(_("Another one"))
    return render(_("Quack!"), body)


def error(title, text, meme=None):
    return render(title, "<div class=big>🦆</div><h1>%s</h1><p>%s</p>%s%s" % (
        escape(title), escape(text), meme_card(meme), _home_link()))


def _home_link():
    return '<a class=button href="duck://stagno/">%s</a>' % escape(_("Back to the pond"))


def not_found(name):
    return error(_("No duck here"), _("{name} is not registered on DuckNet.", name=name), memes.MEMES[1])


def unreachable(reason):
    return error(_("The pond is dry"), _("Could not reach DuckNet: {error}", error=reason), memes.MEMES[7])


def bad_answer():
    return error(_("Quack-atto"), _("The answer was not valid DUCK/1."))


def status_error(code, motto):
    return error(_("Error {code}", code=code), "%s — %s" % (motto, _("This page flew away.")))


def blocked(url):
    return render(_("This is DuckNet, not the web"), "<div class=big>🚫🦆</div><h1>%s</h1><p>%s</p>%s%s" % (
        escape(_("This is DuckNet, not the web")),
        escape(_("{url} is on the regular web. Stagno only speaks DUCK/1.", url=url)),
        meme_card(memes.MEMES[0]), _home_link()))


def internal(path_and_query):
    """Le pagine di duck://stagno/...  Ritorna l'HTML."""
    parts = urlsplit(path_and_query)
    if parts.path == "/blocked":
        return blocked(parse_qs(parts.query).get("url", [""])[0][:300])
    if parts.path in ("", "/"):
        return home()
    return error(_("No duck here"), _("This page flew away."))
