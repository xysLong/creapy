from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QFrame,
                               QCheckBox, QListWidget)
import numpy as np
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary


class AOIToolbar(QWidget):
    """
    Areas of Interest: draw rectangles or polygons on the stimulus, manage the list, read the metrics table.
    Drawing happens on the canvas (the main window wires the mouse events); this panel holds mode + list + display.
    """
    AVAILABLE_OPACITY = list(np.round(np.arange(0, 1.05, 0.05), 2))
    AVAILABLE_MODE = ["Draw rectangle", "Draw polygon", "View only"]
    AVAILABLE_DISPLAY = ["Image with AOIs", "Metrics table", "Scarf plot", "Transition matrix", "First-fixation order"]
    AVAILABLE_UNDERLAY = ["Fixation points", "Fixation heatmap", "Nothing"]

    def __init__(self, update_callback, parent=None):
        super().__init__(parent)
        self.update_callback = update_callback

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QWidget(self)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(12, 12, 12, 8)
        top_layout.setSpacing(8)

        title = QLabel("Draw:")
        title.setProperty("boldTitle", True)
        top_layout.addWidget(title)

        self.mode_selector = QComboBox()
        self.mode_selector.addItems(self.AVAILABLE_MODE)
        top_layout.addWidget(self.mode_selector)

        self.hint = utils.add_hint(top_layout, "Click the corners on the image; double-click (or right-click) to "
                                               "close the shape. Esc cancels.")  # the longest of the three texts
        self.mode_selector.currentIndexChanged.connect(self.update_hint)
        self.update_hint()

        line1 = QFrame(self)
        line1.setObjectName("sectionSeparator")
        line1.setFrameShape(QFrame.NoFrame)
        line1.setFixedHeight(1)

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(12, 8, 12, 8)
        middle_layout.setSpacing(8)

        list_title = QLabel("Areas of this stimulus:")
        list_title.setProperty("boldTitle", True)
        middle_layout.addWidget(list_title)

        self.aoi_list = QListWidget()
        self.aoi_list.setMaximumHeight(140)
        middle_layout.addWidget(self.aoi_list)

        row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setObjectName("SmallButton")
        self.clear_btn = QPushButton("Clear all")
        self.clear_btn.setObjectName("SmallButton")
        row.addWidget(self.remove_btn)
        row.addWidget(self.clear_btn)
        middle_layout.addLayout(row)

        row2 = QHBoxLayout()
        self.save_aoi_btn = QPushButton("Save AOIs…")
        self.save_aoi_btn.setObjectName("SmallButton")
        self.load_aoi_btn = QPushButton("Load AOIs…")
        self.load_aoi_btn.setObjectName("SmallButton")
        row2.addWidget(self.save_aoi_btn)
        row2.addWidget(self.load_aoi_btn)
        middle_layout.addLayout(row2)

        self.auto_btn = QPushButton("Add hot spots as AOI")
        middle_layout.addWidget(self.auto_btn)

        line2 = QFrame(self)
        line2.setObjectName("sectionSeparator")
        line2.setFrameShape(QFrame.NoFrame)
        line2.setFixedHeight(1)

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        bottom_layout.setSpacing(8)

        display_title = QLabel("Display:")
        display_title.setProperty("boldTitle", True)
        bottom_layout.addWidget(display_title)

        self.display_selector = QComboBox()
        self.display_selector.addItems(self.AVAILABLE_DISPLAY)
        self.display_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.display_selector)

        self.display_hint = utils.add_hint(bottom_layout, "Scarf plot: one row per participant, fixations coloured "
                                                          "by area over time. Transition matrix: where the gaze went "
                                                          "next after leaving an area (visits, not single fixations).")
        bottom_layout.addWidget(QLabel("Underlay:"))
        self.underlay_selector = QComboBox()
        self.underlay_selector.addItems(self.AVAILABLE_UNDERLAY)
        self.underlay_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.underlay_selector)

        self.labels_checkbox = QCheckBox('Show names')
        self.labels_checkbox.setChecked(True)
        self.labels_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.labels_checkbox)

        self.opacity_slider, self.opacity_label, _ = utils.add_slider_row(
            bottom_layout, "AOI Opacity:", 0, len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(0.35), self.update_labels_and_run)

        self.grayscale_checkbox = QCheckBox('Grayscale stimulus')
        self.grayscale_checkbox.setChecked(True)
        self.grayscale_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.grayscale_checkbox)

        self.save_btn = QPushButton("Save as Image")
        bottom_layout.addWidget(self.save_btn)
        self.export_btn = QPushButton("Export Table…")
        bottom_layout.addWidget(self.export_btn)

        outer.addWidget(top)
        outer.addWidget(line1)
        outer.addWidget(middle)
        outer.addWidget(line2)
        outer.addWidget(bottom)
        outer.addStretch()
        self.update_labels_and_run(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['aoi']))

    def update_hint(self, *_):
        mode = self.mode_selector.currentText()
        if mode == "Draw rectangle":
            self.hint.setText("Click and drag on the image. Release to name the area.")
        elif mode == "Draw polygon":
            self.hint.setText("Click the corners on the image; double-click (or right-click) to close the shape. "
                              "Esc cancels.")
        else:
            self.hint.setText("Mouse interaction off.")

    def set_aois(self, names):
        current = self.aoi_list.currentRow()
        self.aoi_list.clear()
        self.aoi_list.addItems(list(names))
        if 0 <= current < self.aoi_list.count():
            self.aoi_list.setCurrentRow(current)

    def selected_aoi(self):
        item = self.aoi_list.currentItem()
        return item.text() if item is not None else None

    def get_params(self):
        return {
            "mode": self.mode_selector.currentText(),
            "display": self.display_selector.currentText(),
            "underlay": self.underlay_selector.currentText(),
            "labels": self.labels_checkbox.isChecked(),
            "alpha": self.AVAILABLE_OPACITY[self.opacity_slider.value()],
            "grayscale": self.grayscale_checkbox.isChecked(),
        }

    def update_labels_and_run(self, *_, run=True):
        params = self.get_params()
        self.opacity_label.setText(f"{int(params['alpha'] * 100)}%")
        if run:
            self.update_callback()
