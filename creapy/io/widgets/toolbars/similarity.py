from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame
)
from collections import Counter
import numpy as np
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary
import matplotlib.pyplot as plt


class SimilarityToolbar(QWidget):
    AVAILABLE_SIGMA = [10, 50, 100, 150, 200]
    AVAILABLE_TRADEOFF = list(np.round(np.arange(0, 1.05, 0.05), 2))
    AVAILABLE_VIEW = ["Similarity Matrix", "Group Boxplot", "Viewer Map (MDS)", "Similarity over Time"]
    AVAILABLE_WINDOWS = [3, 5, 7, 9, 11]  # number of sliding-window positions (50% overlap)
    AVAILABLE_SCORE = {"Saccade Direction (s_dir)": "s_dir",
                       "Saccade Location (s_loc)": "s_loc"}
    AVAILABLE_MATRIX_COLORMAP = sorted(
        [cmap for cmap in plt.colormaps() if not hasattr(plt.get_cmap(cmap), "colors")],
        key=lambda cmap: cmap.lower(),
    )

    DEFAULT_SIGMA = 50
    DEFAULT_TRADEOFF = 0.5
    DEFAULT_WINDOWS = 5
    DEFAULT_MATRIX_COLORMAP = "coolwarm"


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

        # Computation parameters: these do NOT auto-run (the pairwise computation is
        # expensive): new values are applied via the Compute button.
        self.sigma_slider, self.sigma_label, sigma_title = utils.add_slider_row(
            top_layout,
            "Smoothing Bandwidth:",
            0,
            len(self.AVAILABLE_SIGMA) - 1,
            self.AVAILABLE_SIGMA.index(self.DEFAULT_SIGMA),
            self.update_labels
        )
        sigma_title.setProperty("boldTitle", True)

        self.tradeoff_slider, self.tradeoff_label, _ = utils.add_slider_row(
            top_layout,
            "Density-Coherence Tradeoff:",
            0,
            len(self.AVAILABLE_TRADEOFF) - 1,
            self.AVAILABLE_TRADEOFF.index(self.DEFAULT_TRADEOFF),
            self.update_labels
        )

        # Only used by the "Similarity over Time" view
        self.windows_slider, self.windows_label, _ = utils.add_slider_row(
            top_layout,
            "Time Windows:",
            0,
            len(self.AVAILABLE_WINDOWS) - 1,
            self.AVAILABLE_WINDOWS.index(self.DEFAULT_WINDOWS),
            self.update_labels
        )

        self.compute_btn = QPushButton("Compute Similarity")
        self.compute_btn.clicked.connect(self.update_callback)
        top_layout.addWidget(self.compute_btn)

        # -------------------------------------------------------------------------

        grouping_title = QLabel("Grouping:")
        grouping_title.setProperty("boldTitle", True)
        middle_layout.addWidget(grouping_title)

        self.grouping_label = QLabel()
        self.grouping_label.setWordWrap(True)
        middle_layout.addWidget(self.grouping_label)

        self.groups_btn = QPushButton("Assign Groups...")  # connect externally
        middle_layout.addWidget(self.groups_btn)

        # -------------------------------------------------------------------------

        display_title = QLabel("Display:")
        display_title.setProperty("boldTitle", True)
        bottom_layout.addWidget(display_title)

        bottom_layout.addWidget(QLabel("View:"))
        self.view_selector = QComboBox()
        self.view_selector.addItems(self.AVAILABLE_VIEW)
        self.view_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.view_selector)

        bottom_layout.addWidget(QLabel("Similarity Score:"))
        self.score_selector = QComboBox()
        self.score_selector.addItems(list(self.AVAILABLE_SCORE))
        self.score_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.score_selector)

        bottom_layout.addWidget(QLabel("Matrix Colormap:"))
        self.color_selector = QComboBox()
        for cmap in self.AVAILABLE_MATRIX_COLORMAP:
            icon, text = utils.create_colormap_preview(color=None, cmap_name=cmap)
            self.color_selector.addItem(icon, text)
        self.color_selector.setCurrentText(self.DEFAULT_MATRIX_COLORMAP)
        self.color_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.color_selector)

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

        self.set_grouping_summary(None)
        self.update_labels()
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['similarity']))

    def get_params(self):
        sigma = self.AVAILABLE_SIGMA[self.sigma_slider.value()]
        tradeoff = self.AVAILABLE_TRADEOFF[self.tradeoff_slider.value()]
        n_windows = self.AVAILABLE_WINDOWS[self.windows_slider.value()]
        view = self.view_selector.currentText()
        which = self.AVAILABLE_SCORE[self.score_selector.currentText()]
        cmap = self.color_selector.currentText()
        return {
            "sigma": sigma,
            "density_coherence_tradeoff": tradeoff,
            "n_windows": n_windows,
            "view": view,
            "which": which,
            "cmap": cmap
        }

    def update_labels(self, *_):
        params = self.get_params()
        self.sigma_label.setText(f"{params['sigma']}")
        self.tradeoff_label.setText(f"{params['density_coherence_tradeoff']}")
        self.windows_label.setText(f"{params['n_windows']}")

    def set_grouping_summary(self, grouping):
        if not grouping:
            self.grouping_label.setText("No groups assigned.")
        else:
            counts = Counter(grouping.values())
            self.grouping_label.setText("  ·  ".join(f"{name} ({n})" for name, n in sorted(counts.items())))
