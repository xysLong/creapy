from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PySide6.QtCore import QPropertyAnimation, QEasingCurve
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QGraphicsOpacityEffect, QSizePolicy


class PainterWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.canvas = FigureCanvas(Figure())
        self.layout.addWidget(self.canvas, stretch=1)
        # One explanatory line under charts whose axes carry jargon (glossary.figure_caption); hidden when empty
        self.caption = QLabel()
        self.caption.setObjectName("FigureCaption")
        self.caption.setWordWrap(True)
        self.caption.setContentsMargins(10, 2, 10, 4)
        self.caption.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Maximum)  # the canvas takes the rest
        self.caption.hide()
        self.layout.addWidget(self.caption, stretch=0)
        self.setLayout(self.layout)
        self.current_fig = None
        self.fade_label = None
        self.fade_anim = None

    def draw_figure(self, fig):
        # Cross-fade: keep a snapshot of the old canvas on top of the new one
        # and fade it out, so figure changes don't pop in
        snapshot = self.canvas.grab() if self.current_fig is not None else None
        geometry = self.canvas.geometry()
        self.layout.removeWidget(self.canvas)
        self.canvas.setParent(None)
        self.canvas = FigureCanvas(fig)
        self.layout.insertWidget(0, self.canvas, stretch=1)  # the caption stays below
        self.current_fig = fig
        if snapshot is not None:
            self.start_cross_fade(snapshot, geometry)

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

    def set_caption(self, text):
        self.caption.setText(text or "")
        self.caption.setVisible(bool(text))
