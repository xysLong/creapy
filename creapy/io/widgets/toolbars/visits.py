from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox, QCheckBox, QFrame
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary


class VisitsToolbar(QWidget):
    AVAILABLE_DISPLAY = ["Timeline", "Visits (table)", "Episodes (table)", "Totals per stimulus (table)",
                         "Summary per stimulus (table)", "Session summary (table)", "Stimulus sequence (table)"]
    NEEDS_CLOCK = ["Timeline", "Episodes (table)", "Stimulus sequence (table)"]
    AVAILABLE_UNIT = ["Snapshots", "Areas (ticked in Areas of Interest)"]
    AVAILABLE_MERGE = [0., 0.5, 1., 2., 3., 5., 10., 20., 30., None]   # None: whatever the pause
    DEFAULT_MERGE = 2.

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

        unit_title = QLabel("Count visits of:")
        unit_title.setProperty("boldTitle", True)
        top_layout.addWidget(unit_title)
        self.unit_selector = QComboBox()
        self.unit_selector.addItems(self.AVAILABLE_UNIT)
        self.unit_selector.currentIndexChanged.connect(self.update_callback)
        top_layout.addWidget(self.unit_selector)

        title = QLabel("Display:")
        title.setProperty("boldTitle", True)
        top_layout.addWidget(title)
        self.display_selector = QComboBox()
        self.display_selector.addItems(self.AVAILABLE_DISPLAY)
        self.display_selector.currentIndexChanged.connect(self.update_callback)
        top_layout.addWidget(self.display_selector)
        self.hint = utils.add_hint(top_layout, "Every visit of every snapshot on the recording clock: the order in "
                                               "which the walls were looked at, returns, and the time between.")

        line1 = QFrame(self)
        line1.setObjectName("sectionSeparator")
        line1.setFrameShape(QFrame.NoFrame)
        line1.setFixedHeight(1)

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(12, 8, 12, 8)
        middle_layout.setSpacing(8)
        episodes_title = QLabel("Episodes:")
        episodes_title.setProperty("boldTitle", True)
        middle_layout.addWidget(episodes_title)
        self.merge_slider, self.merge_label, _ = utils.add_slider_row(
            middle_layout, "Join visits paused up to:", 0, len(self.AVAILABLE_MERGE) - 1,
            self.AVAILABLE_MERGE.index(self.DEFAULT_MERGE), self.update_labels_and_run)

        line2 = QFrame(self)
        line2.setObjectName("sectionSeparator")
        line2.setFrameShape(QFrame.NoFrame)
        line2.setFixedHeight(1)

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        bottom_layout.setSpacing(8)
        timeline_title = QLabel("Timeline:")
        timeline_title.setProperty("boldTitle", True)
        bottom_layout.addWidget(timeline_title)
        self.relative_checkbox = QCheckBox("Start at each participant's first fixation")
        self.relative_checkbox.setChecked(True)
        self.relative_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.relative_checkbox)
        self.events_checkbox = QCheckBox("Mark logged events")
        self.events_checkbox.setChecked(True)
        self.events_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.events_checkbox)
        self.highlight_checkbox = QCheckBox("Highlight the current stimulus")
        self.highlight_checkbox.setChecked(False)
        self.highlight_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.highlight_checkbox)
        self.save_btn = QPushButton("Save as Image")
        bottom_layout.addWidget(self.save_btn)
        self.export_btn = QPushButton("Export Table…")
        bottom_layout.addWidget(self.export_btn)

        outer.addWidget(top)
        utils.add_section_separator(outer, line1)
        outer.addWidget(middle)
        utils.add_section_separator(outer, line2)
        outer.addWidget(bottom)
        outer.addStretch()
        self.update_labels_and_run(run=False)
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['visits']))

    def set_clock_available(self, available, reason=None):
        for name in self.NEEDS_CLOCK:
            utils.set_combo_item_enabled(self.display_selector, name, available, reason)

    def set_areas_available(self, available, reason=None):
        utils.set_combo_item_enabled(self.unit_selector, self.AVAILABLE_UNIT[1], available, reason)

    def get_params(self):
        return {"display": self.display_selector.currentText(),
                "unit": 'areas' if self.unit_selector.currentIndex() == 1 else 'stimuli',
                "merge_gap_s": self.AVAILABLE_MERGE[self.merge_slider.value()],
                "relative": self.relative_checkbox.isChecked(),
                "show_events": self.events_checkbox.isChecked(),
                "highlight": self.highlight_checkbox.isChecked()}

    def update_labels_and_run(self, *_, run=True):
        gap = self.get_params()['merge_gap_s']
        self.merge_label.setText("any pause" if gap is None else f"{gap:g} s")
        if run:
            self.update_callback()
