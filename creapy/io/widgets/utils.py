import math
import re
from PySide6.QtGui import QIcon, QPixmap, QImage
import pandas as pd
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider
from PySide6.QtCore import Qt
import matplotlib.pyplot as plt
import numpy as np


from creapy.gaze.convert import fixations_to_saccades, saccades_to_fixations  # noqa: F401


def create_colormap_preview(color, cmap_name, width=30, height=30):
    if color is None:
        cmap = plt.get_cmap(cmap_name)
        gradient = np.linspace(0, 1, width).reshape(1, -1)
        gradient = np.vstack([gradient] * height)
        image = (cmap(gradient)[:, :, :3] * 255).astype(np.uint8)
        name = cmap_name
    else:
        arr = np.array(color, dtype=float)
        if arr.max() <= 1.0:
            arr = (arr * 255).astype(np.uint8)
        else:
            arr = arr.astype(np.uint8)

        r, g, b = arr
        image = np.zeros((height, width, 3), dtype=np.uint8)
        image[:, :] = (r, g, b)
        name = str((int(r), int(g), int(b)))

    qimage = QImage(
        image.data,
        image.shape[1],
        image.shape[0],
        image.shape[1] * 3,
        QImage.Format.Format_RGB888,
    )
    pixmap = QPixmap.fromImage(qimage)
    return QIcon(pixmap), name


def add_slider_row(layout, title, minimum, maximum, value, callback):
    row = QWidget()
    row_layout = QHBoxLayout(row)
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(6)

    title_label = QLabel(title)
    value_label = QLabel()

    row_layout.addWidget(title_label)
    row_layout.addWidget(value_label)
    layout.addWidget(row)

    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    slider.setTickInterval(1)
    slider.setTickPosition(QSlider.TickPosition.TicksBelow)
    slider.valueChanged.connect(callback)
    layout.addWidget(slider)

    value_label.setProperty("paramLabel", True)
    slider.title_label = title_label

    return slider, value_label, title_label

def add_hint(layout, text, width=210):
    text = re.sub(r'<(?=\s)', '&lt;', text)
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("sectionTitle", True)
    label.setTextFormat(Qt.RichText)
    plain = re.sub(r'<[^>]+>', '', text)
    lines = math.ceil(len(plain) / 34) + 1
    label.setMinimumHeight(max(label.heightForWidth(width), lines * 14) + 18)
    layout.addWidget(label)
    return label


def rich_tooltip(text):
    text = re.sub(r'<(?=\s)', '&lt;', text)
    return f"<p style='white-space:normal'>{text}</p>"


def apply_tooltips(widget, tips):
    for name, text in tips.items():
        control = getattr(widget, name, None)
        if control is None or not text:
            continue
        control.setToolTip(rich_tooltip(text))
        label = getattr(control, 'title_label', None)
        if label is None and control.parentWidget() is not None and control.parentWidget().layout() is not None:
            layout = control.parentWidget().layout()
            idx = layout.indexOf(control)
            if idx > 0 and layout.itemAt(idx - 1).widget() is not None:
                label = layout.itemAt(idx - 1).widget()
                if not isinstance(label, QLabel) or label.property('paramLabel'):
                    label = None
        if label is not None:
            label.setToolTip(rich_tooltip(text))
