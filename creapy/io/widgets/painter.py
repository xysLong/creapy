from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect, QSizePolicy

from creapy.io.widgets.zoom import CanvasZoom, ZoomBar


class PainterWidget(QWidget):
    zoomed = Signal(float, str)

    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.canvas = FigureCanvas(Figure())
        self.layout.addWidget(self.canvas, stretch=1)
        self.caption = QLabel()
        self.caption.setObjectName("FigureCaption")
        self.caption.setWordWrap(True)
        self.caption.setContentsMargins(10, 2, 10, 4)
        self.caption.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)
        self.caption.hide()
        self.layout.addWidget(self.caption, stretch=0)
        self.setLayout(self.layout)
        self.current_fig = None
        self.fade_label = None
        self.fade_anim = None
        self.zoom = CanvasZoom(self)
        self.zoom.changed.connect(self.on_zoom_changed)
        self.zoom_key = None
        self.hovered = False
        self.zoom_bar = ZoomBar(self)
        self.zoom_bar.in_btn.clicked.connect(self.zoom_in)
        self.zoom_bar.out_btn.clicked.connect(self.zoom_out)
        self.zoom_bar.level_btn.clicked.connect(self.reset_zoom)
        self.zoom_bar.hide()

    def draw_figure(self, fig, key=None):
        snapshot = self.canvas.grab() if self.current_fig is not None else None
        geometry = self.canvas.geometry()
        view = self.zoom.view() if key is not None and key == self.zoom_key and self.zoom.level() > 1. else None
        self.zoom_key = key
        self.layout.removeWidget(self.canvas)
        self.canvas.setParent(None)
        self.canvas = FigureCanvas(fig)
        self.layout.insertWidget(0, self.canvas, stretch=1)
        self.current_fig = fig
        self.zoom.attach(self.canvas, view)
        if snapshot is not None:
            self.start_cross_fade(snapshot, geometry)
        self.update_zoom_bar()

    def zoom_in(self):
        if self.zoom.available():
            self.zoom.zoom(CanvasZoom.STEP, 'button')

    def zoom_out(self):
        if self.zoom.available():
            self.zoom.zoom(1 / CanvasZoom.STEP, 'button')

    def reset_zoom(self):
        if self.zoom.available():
            self.zoom.reset()

    def set_drag_pan(self, enabled):
        self.zoom.drag_pan = enabled
        if enabled:
            self.zoom.update_cursor()

    def on_zoom_changed(self, level, how):
        self.update_zoom_bar()
        self.zoomed.emit(level, how)

    def update_zoom_bar(self):
        level = self.zoom.level()
        self.zoom_bar.set_level(level)
        self.zoom_bar.setVisible(self.zoom.available() and (self.hovered or level > 1.))
        self.place_zoom_bar()

    def place_zoom_bar(self):
        self.zoom_bar.adjustSize()
        rect = self.canvas.geometry()
        self.zoom_bar.move(rect.right() - self.zoom_bar.width() - 10, rect.top() + 10)
        self.zoom_bar.raise_()

    def enterEvent(self, event):
        self.hovered = True
        self.update_zoom_bar()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update_zoom_bar()
        super().leaveEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.place_zoom_bar()

    def start_cross_fade(self, snapshot, geometry):
        if self.fade_anim is not None:
            self.fade_anim.stop()
        if self.fade_label is not None:
            self.fade_label.deleteLater()
        self.fade_label = QLabel(self)
        self.fade_label.setPixmap(snapshot)
        self.fade_label.setGeometry(geometry)
        effect = QGraphicsOpacityEffect(self.fade_label)
        self.fade_label.setGraphicsEffect(effect)
        self.fade_label.show()
        self.fade_label.raise_()
        self.fade_anim = QPropertyAnimation(effect, b"opacity", self)
        self.fade_anim.setDuration(220)
        self.fade_anim.setStartValue(1.0)
        self.fade_anim.setEndValue(0.0)
        self.fade_anim.setEasingCurve(QEasingCurve.InOutQuad)
        self.fade_anim.finished.connect(self.fade_label.hide)
        self.fade_anim.start()
        self.zoom_bar.raise_()

    def set_caption(self, text):
        self.caption.setText(text or "")
        self.caption.setVisible(bool(text))
