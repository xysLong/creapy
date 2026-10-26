from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame, QCheckBox
)
import numpy as np
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary
from creapy.io.widgets.half_dial import OrientationSelector
import matplotlib.pyplot as plt
from creapy.misc.colormapping import make_cyclic_colormap


class SaccadeHeatmapToolbar(QWidget):
    AVAILABLE_OPACITY = list(np.arange(0, 1.05, 0.05))

    AVAILABLE_HEATMAP_COLORMAP = sorted(
        [cmap for cmap in plt.colormaps() if not hasattr(plt.get_cmap(cmap), "colors")],
        key=lambda cmap: cmap.lower(),
    )
    AVAILABLE_HEATMAP_SIGMA = [10, 50, 100, 150, 200]
    AVAILABLE_HEATMAP_DEGREE = list(np.arange(0.1, 2.1, 0.1))
    AVAILABLE_HEATMAP_QUANTILE = [0.5, 0.6, 0.7, 0.8, 0.9]

    DEFAULT_HEATMAP_OPACITY = 1.
    DEFAULT_HEATMAP_COLORMAP = "coolwarm"
    DEFAULT_HEATMAP_SIGMA = 50
    DEFAULT_HEATMAP_QUANTILE = 0.8
    DEFAULT_HEATMAP_SENSITIVITY = 1


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

        # Heatmap OOI Dial
        ooi_title = QLabel("Orientation of Interest (OOI):")
        ooi_title.setProperty("boldTitle", True)
        middle_layout.addWidget(ooi_title)

        self.angle_dial = OrientationSelector()
        self.angle_dial.valueChanged.connect(self.update_callback)
        self.angle_dial.setCyclicColormap(make_cyclic_colormap('coolwarm'))
        middle_layout.addWidget(self.angle_dial)

        # -------------------------------------------------------------------------

        # Heatmap Opacity
        self.heatmap_opacity_slider, self.heatmap_opacity_label, heatmap_title = utils.add_slider_row(
            bottom_layout,
            "Heatmap Max. Opacity:",
            0,
            len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(self.DEFAULT_HEATMAP_OPACITY),
            self.update_labels_and_run
        )
        heatmap_title.setProperty("boldTitle", True)

        # Heatmap Colormap
        bottom_layout.addWidget(QLabel("Heatmap Colormap:"))
        self.color_selector = QComboBox()
        for cmap in self.AVAILABLE_HEATMAP_COLORMAP:
            icon, text = utils.create_colormap_preview(color=None, cmap_name=cmap)
            self.color_selector.addItem(icon, text)
        self.color_selector.setCurrentText(self.DEFAULT_HEATMAP_COLORMAP)
        self.color_selector.currentIndexChanged.connect(self.update_ooi_selector)
        self.color_selector.currentIndexChanged.connect(self.update_labels_and_run)
        bottom_layout.addWidget(self.color_selector)

        # Heatmap Smoothing Bandwidth
        self.heatmap_sigma_slider, self.heatmap_sigma_label, _ = utils.add_slider_row(
            bottom_layout,
            "Smoothing Bandwidth:",
            0,
            len(self.AVAILABLE_HEATMAP_SIGMA) - 1,
            self.AVAILABLE_HEATMAP_SIGMA.index(self.DEFAULT_HEATMAP_SIGMA),
            self.update_labels_and_run
        )

        # Heatmap Quantile
        self.heatmap_quantile_slider, self.heatmap_quantile_label, _ = utils.add_slider_row(
            bottom_layout,
            "Quantile:",
            0,
            len(self.AVAILABLE_HEATMAP_QUANTILE) - 1,
            self.AVAILABLE_HEATMAP_QUANTILE.index(self.DEFAULT_HEATMAP_QUANTILE),
            self.update_labels_and_run
        )

        # Heatmap Sensitivity
        self.heatmap_degree_slider, self.heatmap_degree_label, _ = utils.add_slider_row(
            bottom_layout,
            "Sensitivity:",
            0,
            len(self.AVAILABLE_HEATMAP_DEGREE) - 1,
            self.AVAILABLE_HEATMAP_DEGREE.index(self.DEFAULT_HEATMAP_SENSITIVITY),
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
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['sac_heatmap']))

    def get_params(self):
        stimulus_alpha = self.AVAILABLE_OPACITY[self.stimulus_opacity_slider.value()]
        grayscale = self.grayscale_checkbox.isChecked()
        ooi = self.angle_dial.value()
        heatmap_alpha = self.AVAILABLE_OPACITY[self.heatmap_opacity_slider.value()]
        heatmap_cmap = self.color_selector.currentText()
        heatmap_sigma = self.AVAILABLE_HEATMAP_SIGMA[self.heatmap_sigma_slider.value()]
        heatmap_quantile = self.AVAILABLE_HEATMAP_QUANTILE[self.heatmap_quantile_slider.value()]
        heatmap_degree = self.AVAILABLE_HEATMAP_DEGREE[self.heatmap_degree_slider.value()]
        return {
            "stimulus_alpha": stimulus_alpha,
            "grayscale": grayscale,
            "ooi": ooi,
            "alpha": heatmap_alpha,
            "cmap": heatmap_cmap,
            "sigma": heatmap_sigma,
            "quantile": heatmap_quantile,
            "degree": heatmap_degree
        }

    def update_labels_and_run(self, *_, run=True):
        params = self.get_params()
        self.stimulus_opacity_label.setText(f"{int(params['stimulus_alpha'] * 100)}%")
        self.heatmap_opacity_label.setText(f"{int(params['alpha'] * 100)}%")
        self.heatmap_sigma_label.setText(f"{params['sigma']}")
        self.heatmap_quantile_label.setText(f"{params['quantile']}")
        self.heatmap_degree_label.setText(f"{params['degree']}")
        if run:
            self.update_callback()

    def update_ooi_selector(self):
        cyclic_cmap = make_cyclic_colormap(self.color_selector.currentText())
        self.angle_dial.setCyclicColormap(cyclic_cmap)
