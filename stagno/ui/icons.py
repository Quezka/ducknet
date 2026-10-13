"""Icone a linea (SVG in linea), ricolorate secondo il tema."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS = {
    "back": "M15 5l-7 7 7 7",
    "forward": "M9 5l7 7-7 7",
    "reload": "M20 12a8 8 0 1 1-2.4-5.7M20 4v5h-5",
    "stop": "M6 6l12 12M18 6L6 18",
    "home": "M4 11l8-7 8 7M6 10v9h12v-9",
    "plus": "M12 5v14M5 12h14",
    "menu": "M4 7h16M4 12h16M4 17h16",
}


def icon(name, color):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="%s" '
           'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="%s"/></svg>'
           % (color, PATHS[name]))
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    image = QImage(48, 48, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QIcon(QPixmap.fromImage(image))
