from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame, QCheckBox
import numpy as np
import matplotlib.pyplot as plt
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary


class FixationScanpathToolbar(QWidget):
    # The textbook scanpath: circles sized by fixation duration, connected in order, numbered.
    # Which participant(s) are drawn is decided by the filter bar above the canvas.
    AVAILABLE_OPACITY = list(np.round(np.arange(0, 1.05, 0.05), 2))
    AVAILABLE_COLOR = [(1, 1, 0)] + [c for cmap in ['Set3', 'Accent', 'Dark2'] for c in
                                     plt.get_cmap(cmap).colors]  # type: ignore
    AVAILABLE_SIZE = [0.25, 0.5, 1, 2, 4, 8]
    AVAILABLE_LINE_WIDTH = [0.5, 1, 1.5, 2, 3, 4]

    DEFAULT_OPACITY = 0.85
    DEFAULT_SIZE = 1
    DEFAULT_LINE_WIDTH = 1.5

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
        line1.setFrameShape(QFrame.NoFrame)
        line1.setFixedHeight(1)

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        bottom_layout.setSpacing(8)

        # -------------------------------------------------------------------------

        self.stimulus_opacity_slider, self.stimulus_opacity_label, stimulus_title = utils.add_slider_row(
            top_layout, "Stimulus Opacity:", 0, len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(1.), self.update_labels_and_run)
        stimulus_title.setProperty("boldTitle", True)

        self.grayscale_checkbox = QCheckBox('Grayscale')
        self.grayscale_checkbox.setChecked(True)
        self.grayscale_checkbox.stateChanged.connect(self.update_callback)
        top_layout.addWidget(self.grayscale_checkbox)

        # -------------------------------------------------------------------------

        utils.add_hint(bottom_layout, "Pick a participant in the <i>Show</i> bar above the image to see one numbered "
                                      "scanpath; with several participants each gets a colour.")

        self.numbered_checkbox = QCheckBox('Number the fixations')
        self.numbered_checkbox.setChecked(True)
        self.numbered_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.numbered_checkbox)

        self.opacity_slider, self.opacity_label, opacity_title = utils.add_slider_row(
            bottom_layout, "Opacity:", 0, len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(self.DEFAULT_OPACITY), self.update_labels_and_run)
        opacity_title.setProperty("boldTitle", True)

        bottom_layout.addWidget(QLabel("Color (single participant):"))
        self.color_selector = QComboBox()
        for color in self.AVAILABLE_COLOR:
            icon, text = utils.create_colormap_preview(color=color, cmap_name=None)
            self.color_selector.addItem(icon, text, userData=color)
        self.color_selector.setCurrentIndex(0)
        self.color_selector.currentIndexChanged.connect(self.update_labels_and_run)
        bottom_layout.addWidget(self.color_selector)

        self.size_slider, self.size_label, _ = utils.add_slider_row(
            bottom_layout, "Circle Size:", 0, len(self.AVAILABLE_SIZE) - 1,
            self.AVAILABLE_SIZE.index(self.DEFAULT_SIZE), self.update_labels_and_run)

        self.line_width_slider, self.line_width_label, _ = utils.add_slider_row(
            bottom_layout, "Line Width:", 0, len(self.AVAILABLE_LINE_WIDTH) - 1,
            self.AVAILABLE_LINE_WIDTH.index(self.DEFAULT_LINE_WIDTH), self.update_labels_and_run)

        # -------------------------------------------------------------------------

        self.save_btn = QPushButton("Save as Image")
        bottom_layout.addWidget(self.save_btn)

        outer.addWidget(top)
        outer.addWidget(line1)
        outer.addWidget(bottom)
        outer.addStretch()

        self.update_labels_and_run(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['fix_scanpath']))

    def get_params(self):
        return {
            "stimulus_alpha": self.AVAILABLE_OPACITY[self.stimulus_opacity_slider.value()],
            "grayscale": self.grayscale_checkbox.isChecked(),
            "numbered": self.numbered_checkbox.isChecked(),
            "alpha": self.AVAILABLE_OPACITY[self.opacity_slider.value()],
            "color": self.color_selector.currentData(),
            "size": self.AVAILABLE_SIZE[self.size_slider.value()],
            "line_width": self.AVAILABLE_LINE_WIDTH[self.line_width_slider.value()],
        }

    def update_labels_and_run(self, *_, run=True):
        params = self.get_params()
        self.stimulus_opacity_label.setText(f"{int(params['stimulus_alpha'] * 100)}%")
        self.opacity_label.setText(f"{int(params['alpha'] * 100)}%")
        self.size_label.setText(f"{params['size']}")
        self.line_width_label.setText(f"{params['line_width']}")
        if run:
            self.update_callback()
