from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel


class ProjectTile(QFrame):
    clicked = Signal()

    def __init__(self, title, subtitle="", tooltip="", parent=None):
        super().__init__(parent)
        self.setObjectName("ProjectTile")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tooltip)
        self.title = title
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        self.title_label = QLabel(title)
        self.title_label.setObjectName("TileTitle")
        layout.addWidget(self.title_label)
        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("TileFolder")
        self.subtitle_label.setVisible(bool(subtitle))
        self.subtitle = subtitle
        layout.addWidget(self.subtitle_label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.subtitle:
            metrics = QFontMetrics(self.subtitle_label.font())
            self.subtitle_label.setText(metrics.elidedText(self.subtitle, Qt.ElideMiddle, self.width() - 32))

    def text(self):
        return self.title

    def click(self):
        self.clicked.emit()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
