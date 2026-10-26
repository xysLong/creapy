from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame
import numpy as np
import matplotlib.pyplot as plt
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary


class ScanpathCompareToolbar(QWidget):
    # Classic scanpath-comparison measures between all participants: MultiMatch (five dimensions), ScanMatch,
    # cross-recurrence. Same displays as the HeatMatch similarity view (matrix, group boxplot, viewer map).
    AVAILABLE_METHOD = {"MultiMatch (Dewhurst et al. 2012)": "multimatch",
                        "ScanMatch (Cristino et al. 2010)": "scanmatch",
                        "Cross-recurrence (Anderson et al. 2013)": "cross_recurrence"}
    AVAILABLE_SCORE = {"multimatch": {"Vector (shape)": "mm_vector", "Direction": "mm_direction",
                                      "Length": "mm_length", "Position": "mm_position", "Duration": "mm_duration"},
                       "scanmatch": {"ScanMatch score": "scanmatch"},
                       "cross_recurrence": {"Cross-recurrence rate": "cross_recurrence"}}
    AVAILABLE_VIEW = ["Similarity Matrix", "Group Boxplot", "Viewer Map (MDS)", "Measure overview"]
    AVAILABLE_GRID = [(6, 4), (8, 6), (12, 8), (16, 12), (24, 16)]
    AVAILABLE_TEMPORAL_BIN = [None, 0.05, 0.1, 0.2]  # seconds; None = one letter per fixation
    AVAILABLE_RADIUS = [0.02, 0.03, 0.05, 0.08, 0.12]  # share of the image diagonal
    AVAILABLE_MATRIX_COLORMAP = sorted(
        [cmap for cmap in plt.colormaps() if not hasattr(plt.get_cmap(cmap), "colors")],
        key=lambda cmap: cmap.lower(),
    )

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

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(12, 8, 12, 8)
        middle_layout.setSpacing(8)

        line2 = QFrame(self)
        line2.setObjectName("sectionSeparator")
        line2.setFrameShape(QFrame.NoFrame)
        line2.setFixedHeight(1)

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        bottom_layout.setSpacing(8)

        title = QLabel("Comparison Method:")
        title.setProperty("boldTitle", True)
        top_layout.addWidget(title)
        self.method_selector = QComboBox()
        self.method_selector.addItems(list(self.AVAILABLE_METHOD))
        self.method_selector.currentIndexChanged.connect(self.on_method_changed)
        top_layout.addWidget(self.method_selector)

        self.hint = utils.add_hint(top_layout, "MultiMatch aligns two scanpaths and scores their similarity in shape, "
                                               "direction, length, position and duration (1 = identical). ScanMatch "
                                               "turns scanpaths into letter strings over a grid and aligns them. "
                                               "Cross-recurrence counts how often two viewers fixated the same spots.")

        # Method parameters (not auto-run: the pairwise computation is the slow part)
        self.grid_slider, self.grid_label, self.grid_title = utils.add_slider_row(
            top_layout, "ScanMatch Grid:", 0, len(self.AVAILABLE_GRID) - 1, 2, self.update_labels)
        self.bin_slider, self.bin_label, self.bin_title = utils.add_slider_row(
            top_layout, "Temporal Bin:", 0, len(self.AVAILABLE_TEMPORAL_BIN) - 1, 0, self.update_labels)
        self.radius_slider, self.radius_label, self.radius_title = utils.add_slider_row(
            top_layout, "Recurrence Radius:", 0, len(self.AVAILABLE_RADIUS) - 1, 2, self.update_labels)

        self.compute_btn = QPushButton("Compute Comparison")
        self.compute_btn.clicked.connect(self.update_callback)
        top_layout.addWidget(self.compute_btn)

        grouping_title = QLabel("Grouping:")
        grouping_title.setProperty("boldTitle", True)
        middle_layout.addWidget(grouping_title)
        self.grouping_label = QLabel("No groups assigned.")
        self.grouping_label.setWordWrap(True)
        middle_layout.addWidget(self.grouping_label)
        self.groups_btn = QPushButton("Assign Groups...")
        middle_layout.addWidget(self.groups_btn)

        display_title = QLabel("Display:")
        display_title.setProperty("boldTitle", True)
        bottom_layout.addWidget(display_title)
        bottom_layout.addWidget(QLabel("View:"))
        self.view_selector = QComboBox()
        self.view_selector.addItems(self.AVAILABLE_VIEW)
        self.view_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.view_selector)
        bottom_layout.addWidget(QLabel("Score:"))
        self.score_selector = QComboBox()
        self.score_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.score_selector)
        bottom_layout.addWidget(QLabel("Matrix Colormap:"))
        self.color_selector = QComboBox()
        for cmap in self.AVAILABLE_MATRIX_COLORMAP:
            icon, text = utils.create_colormap_preview(color=None, cmap_name=cmap)
            self.color_selector.addItem(icon, text)
        self.color_selector.setCurrentText("coolwarm")
        self.color_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.color_selector)

        self.export_btn = QPushButton("Export Table…")
        bottom_layout.addWidget(self.export_btn)
        self.save_btn = QPushButton("Save as Image")
        bottom_layout.addWidget(self.save_btn)

        outer.addWidget(top)
        outer.addWidget(line1)
        outer.addWidget(middle)
        outer.addWidget(line2)
        outer.addWidget(bottom)
        outer.addStretch()
        self.on_method_changed(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['scanpath_compare']))

    def method(self):
        return self.AVAILABLE_METHOD[self.method_selector.currentText()]

    def on_method_changed(self, *_, run=False):
        method = self.method()
        self.score_selector.blockSignals(True)
        self.score_selector.clear()
        self.score_selector.addItems(list(self.AVAILABLE_SCORE[method]))
        self.score_selector.blockSignals(False)
        for w in (self.grid_slider, self.grid_label, self.grid_title, self.bin_slider, self.bin_label, self.bin_title):
            w.setVisible(method == 'scanmatch')
        for w in (self.radius_slider, self.radius_label, self.radius_title):
            w.setVisible(method == 'cross_recurrence')
        self.update_labels()

    def get_params(self):
        method = self.method()
        grid = self.AVAILABLE_GRID[self.grid_slider.value()]
        return {
            "method": method,
            "which": self.AVAILABLE_SCORE[method].get(self.score_selector.currentText(),
                                                      list(self.AVAILABLE_SCORE[method].values())[0]),
            "view": self.view_selector.currentText(),
            "cmap": self.color_selector.currentText(),
            "grid_cols": grid[0], "grid_rows": grid[1],
            "temporal_bin": self.AVAILABLE_TEMPORAL_BIN[self.bin_slider.value()],
            "radius_share": self.AVAILABLE_RADIUS[self.radius_slider.value()],
        }

    def update_labels(self, *_):
        params = self.get_params()
        self.grid_label.setText(f"{params['grid_cols']} × {params['grid_rows']}")
        self.bin_label.setText("per fixation" if params['temporal_bin'] is None else f"{int(params['temporal_bin'] * 1000)} ms")
        self.radius_label.setText(f"{params['radius_share'] * 100:.0f}% of diagonal")

    def set_grouping_summary(self, text):
        self.grouping_label.setText(text)
