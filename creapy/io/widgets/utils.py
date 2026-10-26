import math
import re
from PySide6.QtGui import QIcon, QPixmap, QImage
import pandas as pd
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QSlider
from PySide6.QtCore import Qt
import matplotlib.pyplot as plt
import numpy as np


# fixations_to_saccades / saccades_to_fixations moved to creapy.gaze.convert (vectorized, 2026-10-24)
from creapy.gaze.convert import fixations_to_saccades, saccades_to_fixations  # noqa: F401  (kept for old imports)


def create_colormap_preview(color, cmap_name, width=30, height=30):
    """
    Create an icon preview either from a colormap or from a solid RGB color.
    """
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
    slider.title_label = title_label  # so apply_tooltips can put the same text on the title

    return slider, value_label, title_label

def add_hint(layout, text, width=210):
    # A wrapped explanatory label; the explicit minimum height works around Qt's wrong heightForWidth for
    # word-wrapped labels inside fixed-width panels (the text used to be clipped).
    text = re.sub(r'<(?=\s)', '&lt;', text)  # a bare "<" (as in "K < 0") would start an HTML tag and swallow the rest
    label = QLabel(text)
    label.setWordWrap(True)
    label.setProperty("sectionTitle", True)
    label.setTextFormat(Qt.RichText)
    # heightForWidth is computed before the stylesheet's 11 px font is applied and comes out short, so the
    # estimate below (about 34 characters per line in the 250 px panel) is the binding one; a little slack is fine
    plain = re.sub(r'<[^>]+>', '', text)
    lines = math.ceil(len(plain) / 34) + 1
    label.setMinimumHeight(max(label.heightForWidth(width), lines * 14) + 18)
    layout.addWidget(label)
    return label


def rich_tooltip(text):
    # Qt word-wraps a tooltip only when it is rich text; a bare "<" (as in "K < 0") must not open a tag
    text = re.sub(r'<(?=\s)', '&lt;', text)
    return f"<p style='white-space:normal'>{text}</p>"


def apply_tooltips(widget, tips):
    # tips: {attribute name of a control: text}. The text also goes on the control's title label (a slider row's
    # title, or the QLabel placed right before the control in the same layout), so hovering the label works too.
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
                if not isinstance(label, QLabel) or label.property('paramLabel'):  # a value readout is no title
                    label = None
        if label is not None:
            label.setToolTip(rich_tooltip(text))
