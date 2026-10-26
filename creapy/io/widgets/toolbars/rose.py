from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame, QCheckBox
import matplotlib.pyplot as plt
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary


class RoseToolbar(QWidget):
    # Saccade direction histogram ("rose diagram"): share of saccades per direction bin, participants weighted equally
    AVAILABLE_BINS = [8, 12, 16, 24, 36, 72]
    AVAILABLE_COLORMAP = sorted(
        [cmap for cmap in plt.colormaps() if not hasattr(plt.get_cmap(cmap), "colors")],
        key=lambda cmap: cmap.lower(),
    )

    DEFAULT_BINS = 24
    DEFAULT_COLORMAP = "GnBu"

    def __init__(self, update_callback, parent=None):
        super().__init__(parent)
        self.update_callback = update_callback

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        top = QWidget(self)
        top_layout = QVBoxLayout(top)
        top_layout.setContentsMargins(12, 12, 12, 12)
        top_layout.setSpacing(8)

        title = QLabel("Saccade Directions:")
        title.setProperty("boldTitle", True)
        top_layout.addWidget(title)

        utils.add_hint(top_layout, "Each bar is the share of saccades going in that direction (0° = to the right, "
                                   "90° = upwards). Every participant counts equally.")

        self.bins_slider, self.bins_label, _ = utils.add_slider_row(
            top_layout, "Direction Bins:", 0, len(self.AVAILABLE_BINS) - 1,
            self.AVAILABLE_BINS.index(self.DEFAULT_BINS), self.update_labels_and_run)

        self.fold_checkbox = QCheckBox('Fold opposite directions')
        self.fold_checkbox.stateChanged.connect(self.update_callback)
        top_layout.addWidget(self.fold_checkbox)

        self.rays_checkbox = QCheckBox('Bars')
        self.rays_checkbox.setChecked(True)
        self.rays_checkbox.stateChanged.connect(self.update_callback)
        top_layout.addWidget(self.rays_checkbox)

        self.hull_checkbox = QCheckBox('Outline')
        self.hull_checkbox.setChecked(True)
        self.hull_checkbox.stateChanged.connect(self.update_callback)
        top_layout.addWidget(self.hull_checkbox)

        self.numbers_checkbox = QCheckBox('Percentages')
        self.numbers_checkbox.stateChanged.connect(self.update_callback)
        top_layout.addWidget(self.numbers_checkbox)

        top_layout.addWidget(QLabel("Colormap:"))
        self.color_selector = QComboBox()
        for cmap in self.AVAILABLE_COLORMAP:
            icon, text = utils.create_colormap_preview(color=None, cmap_name=cmap)
            self.color_selector.addItem(icon, text)
        self.color_selector.setCurrentText(self.DEFAULT_COLORMAP)
        self.color_selector.currentIndexChanged.connect(self.update_callback)
        top_layout.addWidget(self.color_selector)

        line1 = QFrame(self)
        line1.setObjectName("sectionSeparator")
        line1.setFrameShape(QFrame.NoFrame)
        line1.setFixedHeight(1)

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        self.save_btn = QPushButton("Save as Image")
        bottom_layout.addWidget(self.save_btn)

        outer.addWidget(top)
        outer.addWidget(line1)
        outer.addWidget(bottom)
        outer.addStretch()
        self.update_labels_and_run(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['rose']))

    def get_params(self):
        return {
            "bins": self.AVAILABLE_BINS[self.bins_slider.value()],
            "center_symmetric": self.fold_checkbox.isChecked(),
            "rays": self.rays_checkbox.isChecked(),
            "hull": self.hull_checkbox.isChecked(),
            "num": self.numbers_checkbox.isChecked(),
            "cmap": self.color_selector.currentText(),
        }

    def update_labels_and_run(self, *_, run=True):
        params = self.get_params()
        self.bins_label.setText(f"{params['bins']}")
        if run:
            self.update_callback()
