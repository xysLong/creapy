from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QFrame, QComboBox, QCheckBox
import matplotlib.pyplot as plt
import numpy as np
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary




class FixationHeatmapToolbar(QWidget):
    AVAILABLE_OPACITY = list(np.arange(0, 1.05, 0.05))
    AVAILABLE_CONTOUR_BW_METHOD = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
    AVAILABLE_CONTOUR_NUM_LEVELS = range(3, 21)
    AVAILABLE_CONTOUR_COLORMAP = sorted(
        [cmap for cmap in plt.colormaps() if not hasattr(plt.get_cmap(cmap), "colors")],
        key=lambda cmap: cmap.lower(),
    )
    AVAILABLE_SCATTER_COLOR = [(1, 1, 0)] + [c for cmap in ['Set3', 'Accent', 'Dark2'] for c in
                               plt.get_cmap(cmap).colors]  # type: ignore
    AVAILABLE_SCATTER_SIZE = [1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]

    DEFAULT_CONTOUR_OPACITY = 0.75
    DEFAULT_CONTOUR_COLORMAP = "coolwarm"
    DEFAULT_CONTOUR_BW_METHOD = 0.1
    DEFAULT_CONTOUR_NUM_LEVELS = 10
    DEFAULT_CONTOUR_FROM_LEVEL = 1

    DEFAULT_SCATTER_OPACITY = 0.5
    DEFAULT_SCATTER_COLOR = AVAILABLE_SCATTER_COLOR[0]
    DEFAULT_SCATTER_SIZE = 16


    def __init__(self, update_callback):
        super().__init__()
        self.update_callback = update_callback

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Helper to add a "title + value label + slider" row.


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

        # Contour Opacity
        self.contour_opacity_slider, self.contour_opacity_label, contour_title =  utils.add_slider_row(
            middle_layout,
            "Contour Opacity:",
            0,
            len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(self.DEFAULT_CONTOUR_OPACITY),
            self.update_labels_and_run
        )
        contour_title.setProperty("boldTitle", True)

        # Colormap selection
        middle_layout.addWidget(QLabel("Contour Colormap:"))
        self.color_selector = QComboBox()
        for cmap in self.AVAILABLE_CONTOUR_COLORMAP:
            icon, text = utils.create_colormap_preview(color=None, cmap_name=cmap)
            self.color_selector.addItem(icon, text)
        self.color_selector.setCurrentText(self.DEFAULT_CONTOUR_COLORMAP)
        self.color_selector.currentIndexChanged.connect(self.update_labels_and_run)
        middle_layout.addWidget(self.color_selector)

        # Smoothing Bandwidth
        self.bw_method_slider, self.bw_method_label, _ =  utils.add_slider_row(
            middle_layout,
            "Smoothing Bandwidth:",
            0,
            len(self.AVAILABLE_CONTOUR_BW_METHOD) - 1,
            self.AVAILABLE_CONTOUR_BW_METHOD.index(self.DEFAULT_CONTOUR_BW_METHOD),
            self.update_labels_and_run
        )

        # Number of Levels
        self.num_levels_slider, self.num_levels_label, _ =  utils.add_slider_row(
            middle_layout,
            "Number of Levels:",
            0,
            len(self.AVAILABLE_CONTOUR_NUM_LEVELS) - 1,
            list(self.AVAILABLE_CONTOUR_NUM_LEVELS).index(self.DEFAULT_CONTOUR_NUM_LEVELS),
            self.update_labels_and_run
        )

        # Show from Level (index into levels; max will be updated dynamically)
        self.from_level_slider, self.from_level_label, _ =  utils.add_slider_row(
            middle_layout,
            "Show from Level:",
            0,
            self.DEFAULT_CONTOUR_NUM_LEVELS - 1,
            self.DEFAULT_CONTOUR_FROM_LEVEL,
            self.update_labels_and_run
        )

        # Shared colour scale: off = every heatmap normalised to its own maximum (the classic rendering, and the
        # study's default); on = one scale across stimuli, groups and time windows (densities above saturate)
        self.shared_scale_checkbox = QCheckBox('Same colour scale for all stimuli / selections')
        self.shared_scale_checkbox.setChecked(False)
        self.shared_scale_checkbox.stateChanged.connect(self.update_callback)
        middle_layout.addWidget(self.shared_scale_checkbox)

        # -------------------------------------------------------------------------

        # Scatter Opacity
        self.scatter_opacity_slider, self.scatter_opacity_label, scatter_title = utils.add_slider_row(
            bottom_layout,
            "Scatter Opacity:",
            0,
            len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(self.DEFAULT_SCATTER_OPACITY),
            self.update_labels_and_run
        )
        scatter_title.setProperty("boldTitle", True)

        # Scatter Color
        bottom_layout.addWidget(QLabel("Scatter Color:"))
        self.scatter_color_selector = QComboBox()
        self._default_scatter_index = 0
        for idx, color in enumerate(self.AVAILABLE_SCATTER_COLOR):
            icon, text = utils.create_colormap_preview(color=color, cmap_name=None)
            self.scatter_color_selector.addItem(icon, text, userData=color)
            if np.array_equal(color, self.DEFAULT_SCATTER_COLOR):
                self._default_scatter_index = idx
        self.scatter_color_selector.setCurrentIndex(self._default_scatter_index)
        self.scatter_color_selector.currentIndexChanged.connect(self.update_labels_and_run)
        bottom_layout.addWidget(self.scatter_color_selector)

        # Scatter Size
        self.scatter_size_slider, self.scatter_size_label, _ =  utils.add_slider_row(
            bottom_layout,
            "Scatter Size:",
            0,
            len(self.AVAILABLE_SCATTER_SIZE) - 1,
            self.AVAILABLE_SCATTER_SIZE.index(self.DEFAULT_SCATTER_SIZE),
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

        # Initialize labels with current slider states
        self.update_labels_and_run(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['fix_heatmap']))

    def get_params(self):
        stimulus_alpha = self.AVAILABLE_OPACITY[self.stimulus_opacity_slider.value()]
        grayscale = self.grayscale_checkbox.isChecked()

        bw_method = self.AVAILABLE_CONTOUR_BW_METHOD[self.bw_method_slider.value()]
        num_levels = list(self.AVAILABLE_CONTOUR_NUM_LEVELS)[self.num_levels_slider.value()]

        # from_level is an index into the levels, clamped to [0, num_levels-1]
        from_level_index = min(self.from_level_slider.value(), num_levels - 1)

        cmap = self.color_selector.currentText()
        alpha = self.AVAILABLE_OPACITY[self.contour_opacity_slider.value()]

        # RGB array for scatter color
        scatter_color = self.scatter_color_selector.currentData()

        scatter_size = self.AVAILABLE_SCATTER_SIZE[self.scatter_size_slider.value()]
        scatter_alpha = self.AVAILABLE_OPACITY[self.scatter_opacity_slider.value()]

        return {
            "stimulus_alpha": stimulus_alpha,
            'grayscale': grayscale,
            "bw_method": bw_method,
            "num_levels": num_levels,
            "from_level": from_level_index,
            "cmap": cmap,
            "alpha": alpha,
            "scatter_color": scatter_color,
            "scatter_size": scatter_size,
            "scatter_alpha": scatter_alpha,
            "shared_scale": self.shared_scale_checkbox.isChecked(),
        }

    def update_labels_and_run(self, *args, run=True):
        """
        Update labels from current widget state and optionally call the callback.

        *args is there so this can be used directly as a Qt slot (it will
        receive the slider value, which we just ignore here).
        """
        params = self.get_params()
        self.stimulus_opacity_label.setText(f"{int(params['stimulus_alpha'] * 100)}%")
        self.bw_method_label.setText(f"{params['bw_method']}")
        self.num_levels_label.setText(f"{params['num_levels']}")

        self.from_level_slider.blockSignals(True)
        self.from_level_slider.setMaximum(params["num_levels"])
        self.from_level_slider.setValue(params["from_level"])
        self.from_level_slider.blockSignals(False)
        self.from_level_label.setText(f"{params['from_level']}")

        self.contour_opacity_label.setText(f"{int(params['alpha'] * 100)}%")
        self.scatter_size_label.setText(f"{params['scatter_size']}")
        self.scatter_opacity_label.setText(f"{int(params['scatter_alpha'] * 100)}%")

        if run:
            self.update_callback()

