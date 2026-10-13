"""Lo schema duck:// dentro il motore web: ogni richiesta passa dal nostro DNS e dal relay."""
from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QObject, QUrl, Signal
from PySide6.QtWebEngineCore import (QWebEngineUrlRequestInterceptor, QWebEngineUrlRequestJob,
                                     QWebEngineUrlScheme, QWebEngineUrlSchemeHandler)

from ..core import fetcher

SCHEME = b"duck"
ALLOWED_SCHEMES = {"duck", "data", "blob", "about", "qrc"}


def register_scheme():
    """Va chiamato PRIMA di creare QApplication."""
    scheme = QWebEngineUrlScheme(SCHEME)
    scheme.setSyntax(QWebEngineUrlScheme.Syntax.Host)
    scheme.setFlags(QWebEngineUrlScheme.Flag.CorsEnabled)
    QWebEngineUrlScheme.registerScheme(scheme)


class DuckSchemeHandler(QWebEngineUrlSchemeHandler):
    _done = Signal(object, object)

    def __init__(self, get_config, parent=None):
        super().__init__(parent)
        self._get_config = get_config
        self._pool = ThreadPoolExecutor(max_workers=6, thread_name_prefix="duck")
        self._done.connect(self._reply)

    def requestStarted(self, job):
        if bytes(job.requestMethod()) != b"GET":
            job.fail(QWebEngineUrlRequestJob.Error.RequestDenied)
            return
        url = job.requestUrl()
        target = url.path(QUrl.ComponentFormattingOption.FullyEncoded) or "/"
        if url.hasQuery():
            target += "?" + url.query(QUrl.ComponentFormattingOption.FullyEncoded)
        if url.host() == "stagno":
            self._reply(job, fetcher.load_internal(target))
            return
        full, config = "duck://%s%s" % (url.host(), target), self._get_config()
        self._pool.submit(self._work, job, full, config)

    def _work(self, job, full, config):
        self._done.emit(job, fetcher.load(full, config))

    def _reply(self, job, reply):
        try:
            buf = QBuffer(job)
            buf.setData(QByteArray(reply.body))
            buf.open(QIODevice.OpenModeFlag.ReadOnly)
            job.reply(QByteArray(reply.content_type.encode()), buf)
        except RuntimeError:        # la richiesta è stata annullata mentre aspettavamo
            pass


class OnlyDuckInterceptor(QWebEngineUrlRequestInterceptor):
    """Stagno non esce su Internet: né pagine né risorse (immagini, script) dal web normale."""

    def interceptRequest(self, info):
        if info.requestUrl().scheme() not in ALLOWED_SCHEMES:
            info.block(True)


class Bridge(QObject):
    """Tiene in vita handler e interceptor insieme al profilo."""

    def __init__(self, profile, get_config):
        super().__init__(profile)
        self.handler = DuckSchemeHandler(get_config, self)
        self.interceptor = OnlyDuckInterceptor(self)
        profile.installUrlSchemeHandler(SCHEME, self.handler)
        profile.setUrlRequestInterceptor(self.interceptor)
