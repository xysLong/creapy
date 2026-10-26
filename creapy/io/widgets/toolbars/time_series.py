from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame, QCheckBox
)
import numpy as np
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary


class TimeSeriesToolbar(QWidget):
    AVAILABLE_CURVE = ["Fixation Duration", "Saccade Amplitude", "Ambient–Focal (K)", "Pupil Size",
                       "Viewing Distance", "Fixations in AOIs"]
    AVAILABLE_DISPLAY = ["Curve over time", "Periodogram", "Scalogram"]
    AVAILABLE_SIGMA = [0.25, 0.5, 1, 2, 3, 5, 10]
    AVAILABLE_BAND = list(np.round(np.arange(0, 1.05, 0.05), 2))

    DEFAULT_SIGMA = 2
    DEFAULT_BAND = 0.05


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

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        bottom_layout.setSpacing(8)

        # -------------------------------------------------------------------------

        curve_title = QLabel("Temporal Profile:")
        curve_title.setProperty("boldTitle", True)
        top_layout.addWidget(curve_title)

        self.curve_selector = QComboBox()
        self.curve_selector.addItems(self.AVAILABLE_CURVE)
        self.curve_selector.currentIndexChanged.connect(self.update_labels_and_run)
        top_layout.addWidget(self.curve_selector)

        self.hint = utils.add_hint(top_layout, "Mean over participants (each weighted equally) smoothed along the "
                                               "viewing time; the dashed tail marks the last 5 s where fewer data "
                                               "remain. K &gt; 0 = focal, K &lt; 0 = ambient (Krejtz et al. 2016).")

        top_layout.addWidget(QLabel("Display:"))
        self.display_selector = QComboBox()
        self.display_selector.addItems(self.AVAILABLE_DISPLAY)
        self.display_selector.currentIndexChanged.connect(self.update_labels_and_run)
        top_layout.addWidget(self.display_selector)

        self.per_group_checkbox = QCheckBox('One curve per group')
        self.per_group_checkbox.setChecked(True)
        self.per_group_checkbox.stateChanged.connect(self.update_callback)
        top_layout.addWidget(self.per_group_checkbox)

        # -------------------------------------------------------------------------

        # Smoothing Bandwidth (in the time unit of the imported table)
        self.sigma_slider, self.sigma_label, sigma_title = utils.add_slider_row(
            bottom_layout,
            "Smoothing Bandwidth:",
            0,
            len(self.AVAILABLE_SIGMA) - 1,
            self.AVAILABLE_SIGMA.index(self.DEFAULT_SIGMA),
            self.update_labels_and_run
        )
        sigma_title.setProperty("boldTitle", True)

        # Variability Band (fraction of the weighted std shown around the mean curve)
        self.band_slider, self.band_label, _ = utils.add_slider_row(
            bottom_layout,
            "Variability Band:",
            0,
            len(self.AVAILABLE_BAND) - 1,
            self.AVAILABLE_BAND.index(self.DEFAULT_BAND),
            self.update_labels_and_run
        )

        # -------------------------------------------------------------------------

        # Buttons
        self.save_btn = QPushButton("Save as Image")  # connect externally if needed
        bottom_layout.addWidget(self.save_btn)

        outer.addWidget(top)
        outer.addWidget(line1)
        outer.addWidget(bottom)
        outer.addStretch()

        self.update_labels_and_run(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['time_series']))

    def get_params(self):
        curve = self.curve_selector.currentText()
        sigma = self.AVAILABLE_SIGMA[self.sigma_slider.value()]
        band = self.AVAILABLE_BAND[self.band_slider.value()]
        return {
            "curve": curve,
            "display": self.display_selector.currentText(),
            "sigma": sigma,
            "n_std": band,
            "per_group": self.per_group_checkbox.isChecked(),
        }

    def update_labels_and_run(self, *_, run=True):
        params = self.get_params()
        self.sigma_label.setText(f"{params['sigma']}")
        self.band_label.setText(f"{params['n_std']}")
        if run:
            self.update_callback()
