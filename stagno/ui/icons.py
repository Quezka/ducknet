"""Icone Material Symbols, ricolorate secondo il tema."""
from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

# Material Symbols Outlined by Google, Apache License 2.0 (assets/MaterialSymbols-LICENSE.txt).
PATHS = {
    "back": "m326.15-434.5 218.74 218.74L480-151.87 151.87-480 480-808.13l64.89 63.89L326.15-525.5h481.98v91H326.15Z",
    "forward": "M633.85-434.5H151.87v-91h481.98L415.11-744.24 480-808.13 808.13-480 480-151.87l-64.89-63.89L633.85-434.5Z",
    "reload": "M479.04-151.87q-137.11 0-232.62-95.51-95.51-95.51-95.51-232.62t95.51-232.62q95.51-95.51 232.62-95.51 71.16 0 135.71 29.22 64.55 29.21 110.51 83.89v-113.11h83.83v291.72H517.13V-600H683.7q-32-54.57-86.43-85.85-54.42-31.28-118.23-31.28-98.8 0-167.96 69.16Q241.91-578.8 241.91-480t69.17 167.97q69.16 69.16 167.96 69.16 75.57 0 136.73-43.28T702.17-400h95.24q-28.24 109.35-116.63 178.74-88.39 69.39-201.74 69.39Z",
    "stop": "M256-192.35 192.35-256l224-224-224-224L256-767.65l224 224 224-224L767.65-704l-224 224 224 224L704-192.35l-224-224-224 224Z",
    "home": "M242.87-202.87H354.5V-445.5h251v242.63h111.63v-355.7L480-736.41 242.87-558.57v355.7Zm-91 91v-492.2L480-850.28l328.13 246.13v492.28H518.09v-246.22h-76.18v246.22H151.87ZM480-469.52Z",
    "plus": "M434.5-434.5H191.87v-91H434.5v-242.63h91v242.63h242.63v91H525.5v242.63h-91V-434.5Z",
    "menu": "M111.87-228.28v-91h736.26v91H111.87Zm0-206.22v-91h736.26v91H111.87Zm0-206.22v-91h736.26v91H111.87Z",
}


def icon(name, color):
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 -960 960 960" fill="%s"><path d="%s"/></svg>'
           % (color, PATHS[name]))
    renderer = QSvgRenderer(QByteArray(svg.encode()))
    image = QImage(48, 48, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    painter = QPainter(image)
    renderer.render(painter)
    painter.end()
    return QIcon(QPixmap.fromImage(image))
