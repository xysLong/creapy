import os
from PySide6.QtGui import QFontDatabase, QFont
from PySide6.QtWidgets import QApplication

STYLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style')
FONT_DIR = os.path.join(STYLE_DIR, 'fonts')
FONT_FAMILY = "Lato"
FONT_PIXEL_SIZE = 13


def install_fonts():
    """Register the bundled typeface with the running application (once) and make it the application font."""
    app = QApplication.instance()
    if app is None or app.property('creapy_fonts'):
        return
    for name in sorted(os.listdir(FONT_DIR)):
        if name.endswith('.ttf'):
            QFontDatabase.addApplicationFont(os.path.join(FONT_DIR, name))
    font = QFont(FONT_FAMILY)
    font.setPixelSize(FONT_PIXEL_SIZE)
    app.setFont(font)
    app.setProperty('creapy_fonts', True)


def stylesheet():
    """Return the application stylesheet (base, start screen and workspace sheets) with icon paths resolved."""
    sheets = []
    for sheet in ('base_dark.qss', 'start_dark.qss', 'main_dark.qss'):
        with open(os.path.join(STYLE_DIR, sheet), encoding='utf-8') as f:
            sheets.append(f.read())
    return "\n".join(sheets).replace('@style@', STYLE_DIR.replace(os.sep, '/'))


def apply_theme():
    """Install the bundled font and the stylesheet on the running application, so every window shares them."""
    app = QApplication.instance()
    if app is None or app.property('creapy_theme'):
        return
    install_fonts()
    app.setStyleSheet(stylesheet())
    app.setProperty('creapy_theme', True)
