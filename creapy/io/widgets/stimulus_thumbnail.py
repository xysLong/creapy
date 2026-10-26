# stimulus_thumbnail.py

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtGui import QPixmap, QMouseEvent, QFontMetrics


class StimulusThumbnail(QWidget):
    clicked = Signal(str)  # emits path or id

    def __init__(self, path_to_stim, name=None, thumb_size=120, parent=None):
        super().__init__(parent)

        self.path_to_stim = path_to_stim
        self.name = name or os.path.splitext(os.path.basename(str(path_to_stim)))[0]
        # Plain QWidget subclasses ignore stylesheet backgrounds/borders without this
        self.setAttribute(Qt.WA_StyledBackground, True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.img_label = QLabel()
        self.img_label.setAlignment(Qt.AlignCenter)

        # The image itself arrives later via set_image (the strip decodes
        # thumbnails in background threads); until then the tile is an empty
        # square, which also keeps all tiles uniformly sized
        self.img_label.setFixedSize(thumb_size, thumb_size)

        max_label_width = max(thumb_size, 80)
        self.text_label = QLabel()
        self.text_label.setObjectName('StimulusThumbnailPath')
        self.text_label.setAlignment(Qt.AlignCenter)
        self.text_label.setMaximumWidth(max_label_width)
        metrics = QFontMetrics(self.text_label.font())
        self.text_label.setText(metrics.elidedText(self.name, Qt.ElideMiddle, max_label_width - 4))
        self.setToolTip(self.name)

        layout.addWidget(self.img_label)
        layout.addWidget(self.text_label)

        self.setCursor(Qt.PointingHandCursor)
        self.set_selected(False)

    def set_image(self, image):
        self.img_label.setPixmap(QPixmap.fromImage(image))

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self.path_to_stim)
        super().mousePressEvent(event)

    def set_selected(self, selected: bool):
        if selected:
            self.setStyleSheet("""
                QLabel {
                    color: #f2f3f7;
                    border: none;
                    background-color: transparent;
                }
                StimulusThumbnail {
                    border: 1px solid #4da3ff;
                    border-radius: 8px;
                    background-color: #122236;  /* ~18% #4da3ff over the dark ground */
                }
            """)
        else:
            self.setStyleSheet("""
                QLabel {
                    color: #f2f3f7;
                    border: none;
                    background-color: transparent;
                }
                StimulusThumbnail {
                    border: 1px solid #363a47;
                    border-radius: 8px;
                    background-color: #11141f;
                }
            """)
