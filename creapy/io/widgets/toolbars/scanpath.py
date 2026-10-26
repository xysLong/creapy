from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame, QCheckBox
)
import numpy as np
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary
import matplotlib.pyplot as plt
from creapy.io.widgets.half_dial import OrientationSelector


class SaccadeScanpathToolbar(QWidget):
    AVAILABLE_OPACITY = list(np.arange(0, 1.05, 0.05))

    AVAILABLE_LINE_COLOR = [(1, 1, 0)] + [c for cmap in ['Set3', 'Accent', 'Dark2'] for c in
                                          plt.get_cmap(cmap).colors]  # type: ignore
    AVAILABLE_LINE_WIDTH = [1, 2, 4, 8, 16]

    DEFAULT_LINE_OPACITY = 0.25
    DEFAULT_LINE_COLOR = AVAILABLE_LINE_COLOR[0]
    DEFAULT_LINE_WIDTH = 4

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

        line1 = QFrame(self)
        line1.setObjectName("sectionSeparator")
        line1.setFrameShape(QFrame.NoFrame)  # important: let QSS draw the line
        line1.setFixedHeight(1)  # 1px tall

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(12, 12, 12, 8)
        middle_layout.setSpacing(8)

        line2 = QFrame(self)
        line2.setObjectName("sectionSeparator")
        line2.setFrameShape(QFrame.NoFrame)  # important: let QSS draw the line
        line2.setFixedHeight(1)  # 1px tall

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        bottom_layout.setSpacing(8)

        # -------------------------------------------------------------------------

        # Stimulus Opacity
        self.stimulus_opacity_slider, self.stimulus_opacity_label, stimulus_title = utils.add_slider_row(
            top_layout,
            "Stimulus Opacity:",
            0,
            len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(1.),
            self.update_labels_and_run
        )
        stimulus_title.setProperty("boldTitle", True)

        # Stimulus Black-White Checkbox
        self.grayscale_checkbox = QCheckBox('Grayscale')
        self.grayscale_checkbox.setChecked(True)
        self.grayscale_checkbox.stateChanged.connect(self.update_callback)
        top_layout.addWidget(self.grayscale_checkbox)

        # -------------------------------------------------------------------------

        # Heatmap OOI Checkbox
        ooi_title = QLabel("Orientation of Interest (OOI):")
        ooi_title.setProperty("boldTitle", True)
        middle_layout.addWidget(ooi_title)

        self.ooi_checkbox = QCheckBox('Enable OOI')  # text on the checkbox
        self.ooi_checkbox.stateChanged.connect(self.update_callback)
        middle_layout.addWidget(self.ooi_checkbox)

        self.angle_dial = OrientationSelector()
        self.angle_dial.valueChanged.connect(self.update_callback)
        middle_layout.addWidget(self.angle_dial)

        # -------------------------------------------------------------------------

        # Line Opacity
        self.line_opacity_slider, self.line_opacity_label, line_title = utils.add_slider_row(
            bottom_layout,
            "Line Opacity:",
            0,
            len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(self.DEFAULT_LINE_OPACITY),
            self.update_labels_and_run
        )
        line_title.setProperty("boldTitle", True)

        # Line Color
        bottom_layout.addWidget(QLabel("Line Color:"))
        self.line_color_selector = QComboBox()
        self._default_scatter_index = 0
        for idx, color in enumerate(self.AVAILABLE_LINE_COLOR):
            icon, text = utils.create_colormap_preview(color=color, cmap_name=None)
            self.line_color_selector.addItem(icon, text, userData=color)
            if np.array_equal(color, self.DEFAULT_LINE_COLOR):
                self._default_scatter_index = idx
        self.line_color_selector.setCurrentIndex(self._default_scatter_index)
        self.line_color_selector.currentIndexChanged.connect(self.update_labels_and_run)
        bottom_layout.addWidget(self.line_color_selector)

        # Line Width
        self.line_width_slider, self.line_width_label, _ = utils.add_slider_row(
            bottom_layout,
            "Line Width:",
            0,
            len(self.AVAILABLE_LINE_WIDTH) - 1,
            self.AVAILABLE_LINE_WIDTH.index(self.DEFAULT_LINE_WIDTH),
            self.update_labels_and_run
        )

        # -------------------------------------------------------------------------

        # Buttons
        self.save_btn = QPushButton("Save as Image")  # connect externally if needed
        bottom_layout.addWidget(self.save_btn)

        outer.addWidget(top)
        outer.addWidget(line1)
        outer.addWidget(middle)
        outer.addWidget(line2)
        outer.addWidget(bottom)
        outer.addStretch()

        self.update_labels_and_run(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['sac_scanpath']))

    def get_params(self):
        stimulus_alpha = self.AVAILABLE_OPACITY[self.stimulus_opacity_slider.value()]
        grayscale = self.grayscale_checkbox.isChecked()
        ooi_checked = self.ooi_checkbox.isChecked()
        ooi = self.angle_dial.value()
        line_alpha = self.AVAILABLE_OPACITY[self.line_opacity_slider.value()]
        line_color = self.line_color_selector.currentData()
        line_width = self.AVAILABLE_LINE_WIDTH[self.line_width_slider.value()]
        return {
            "stimulus_alpha": stimulus_alpha,
            "grayscale": grayscale,
            "ooi": ooi if ooi_checked else None,
            "color": line_color,
            "alpha": line_alpha,
            'width': line_width,
        }

    def update_labels_and_run(self, *_, run=True):
        params = self.get_params()
        self.stimulus_opacity_label.setText(f"{int(params['stimulus_alpha'] * 100)}%")
        self.line_opacity_label.setText(f"{int(params['alpha'] * 100)}%")
        self.line_width_label.setText(f"{params['width']}")
        if run:
            self.update_callback()
