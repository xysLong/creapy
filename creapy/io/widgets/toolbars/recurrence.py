from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QFrame
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary


class RecurrenceToolbar(QWidget):
    # Recurrence quantification analysis (Anderson et al. 2013): recurrence plot of one participant, the RQA table
    # of all participants, boxplot of one measure by group
    AVAILABLE_DISPLAY = ["Recurrence plot (one participant)", "RQA table", "Boxplot by group"]
    AVAILABLE_RADIUS = [0.02, 0.03, 0.05, 0.08, 0.12]  # share of the image diagonal (Anderson: 64 px of 1024 ≈ 5 %)
    AVAILABLE_MIN_LINE = [2, 3, 4, 5]
    AVAILABLE_MEASURE = ["recurrence", "determinism", "laminarity", "corm"]

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

        title = QLabel("Recurrence:")
        title.setProperty("boldTitle", True)
        top_layout.addWidget(title)
        self.display_selector = QComboBox()
        self.display_selector.addItems(self.AVAILABLE_DISPLAY)
        self.display_selector.currentIndexChanged.connect(self.update_callback)
        top_layout.addWidget(self.display_selector)

        utils.add_hint(top_layout, "Two fixations recur when they fall within the radius of each other. "
                                   "Recurrence = how much a viewer returns to the same spots; determinism = "
                                   "repeated sequences; laminarity = dwelling in clusters; CORM = whether returns "
                                   "come early (small) or late (large). Pick one participant in the Show bar for the plot.")

        self.radius_slider, self.radius_label, _ = utils.add_slider_row(
            bottom_layout, "Radius:", 0, len(self.AVAILABLE_RADIUS) - 1, 2, self.update_labels_and_run)
        self.min_line_slider, self.min_line_label, _ = utils.add_slider_row(
            bottom_layout, "Minimum Line Length:", 0, len(self.AVAILABLE_MIN_LINE) - 1, 0, self.update_labels_and_run)
        bottom_layout.addWidget(QLabel("Measure (boxplot):"))
        self.measure_selector = QComboBox()
        self.measure_selector.addItems(self.AVAILABLE_MEASURE)
        self.measure_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.measure_selector)

        self.groups_btn = QPushButton("Assign Groups...")
        bottom_layout.addWidget(self.groups_btn)
        self.export_btn = QPushButton("Export Table…")
        bottom_layout.addWidget(self.export_btn)
        self.save_btn = QPushButton("Save as Image")
        bottom_layout.addWidget(self.save_btn)

        outer.addWidget(top)
        outer.addWidget(line1)
        outer.addWidget(bottom)
        outer.addStretch()
        self.update_labels_and_run(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['recurrence']))

    def get_params(self):
        return {"display": self.display_selector.currentText(),
                "radius_share": self.AVAILABLE_RADIUS[self.radius_slider.value()],
                "min_line": self.AVAILABLE_MIN_LINE[self.min_line_slider.value()],
                "measure": self.measure_selector.currentText()}

    def update_labels_and_run(self, *_, run=True):
        params = self.get_params()
        self.radius_label.setText(f"{params['radius_share'] * 100:.0f}% of diagonal")
        self.min_line_label.setText(f"{params['min_line']}")
        if run:
            self.update_callback()
