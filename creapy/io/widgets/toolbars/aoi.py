from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QComboBox, QFrame,
                               QCheckBox, QListWidget, QListWidgetItem)
from PySide6.QtCore import Qt
import numpy as np
import creapy.io.widgets.utils as utils
import creapy.io.glossary as glossary


class AOIToolbar(QWidget):
    AVAILABLE_OPACITY = list(np.round(np.arange(0, 1.05, 0.05), 2))
    AVAILABLE_MODE = ["Draw rectangle", "Draw polygon", "View only"]
    AVAILABLE_DISPLAY = ["Image with AOIs", "Metrics table", "Scarf plot", "Transition matrix", "First-fixation order",
                         "Sequences (table)", "Transitions per participant (table)", "Area comparison (table)"]
    NEEDS_ONE_AREA = ["Metrics table", "Scarf plot", "First-fixation order", "Sequences (table)"]
    NEEDS_TWO_AREAS = ["Transition matrix", "Transitions per participant (table)", "Area comparison (table)"]
    WHOLE_STIMULUS = "Whole stimulus"
    AVAILABLE_UNDERLAY = ["Fixation points", "Fixation heatmap", "Nothing"]
    AVAILABLE_LEVEL = ["Individual areas", "Area types"]
    AVAILABLE_MIN_RUN = [0., 0.1, 0.2, 0.3, 0.5, 1., 2., 3.]
    AVAILABLE_BRIDGE = [0., 0.2, 0.5, 1., 2., 3.]

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

        title = QLabel("Draw:")
        title.setProperty("boldTitle", True)
        top_layout.addWidget(title)

        self.mode_selector = QComboBox()
        self.mode_selector.addItems(self.AVAILABLE_MODE)
        top_layout.addWidget(self.mode_selector)

        self.hint = utils.add_hint(top_layout, "Click the corners on the image; double-click (or right-click) to "
                                               "close the shape. Esc cancels.")
        self.mode_selector.currentIndexChanged.connect(self.update_hint)
        self.update_hint()

        line1 = QFrame(self)
        line1.setObjectName("sectionSeparator")
        line1.setFrameShape(QFrame.NoFrame)
        line1.setFixedHeight(1)

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(12, 8, 12, 8)
        middle_layout.setSpacing(8)

        list_title = QLabel("Areas of this stimulus (tick = used in the tables):")
        list_title.setProperty("boldTitle", True)
        list_title.setWordWrap(True)
        middle_layout.addWidget(list_title)

        self.aoi_list = QListWidget()
        self.aoi_list.setMaximumHeight(140)
        middle_layout.addWidget(self.aoi_list)
        self._names = []

        row0 = QHBoxLayout()
        self.tick_all_btn = QPushButton("Tick all")
        self.tick_all_btn.setObjectName("SmallButton")
        self.untick_all_btn = QPushButton("Untick all")
        self.untick_all_btn.setObjectName("SmallButton")
        self.tick_all_btn.clicked.connect(lambda: self.set_all_checked(True))
        self.untick_all_btn.clicked.connect(lambda: self.set_all_checked(False))
        row0.addWidget(self.tick_all_btn)
        row0.addWidget(self.untick_all_btn)
        middle_layout.addLayout(row0)

        middle_layout.addWidget(QLabel("Shares relative to:"))
        self.reference_selector = QComboBox()
        self.reference_selector.addItem(self.WHOLE_STIMULUS)
        self.reference_selector.currentIndexChanged.connect(self.update_callback)
        middle_layout.addWidget(self.reference_selector)

        row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.setObjectName("SmallButton")
        self.clear_btn = QPushButton("Clear all")
        self.clear_btn.setObjectName("SmallButton")
        row.addWidget(self.remove_btn)
        row.addWidget(self.clear_btn)
        middle_layout.addLayout(row)

        row2 = QHBoxLayout()
        self.save_aoi_btn = QPushButton("Save AOIs…")
        self.save_aoi_btn.setObjectName("SmallButton")
        self.load_aoi_btn = QPushButton("Load AOIs…")
        self.load_aoi_btn.setObjectName("SmallButton")
        row2.addWidget(self.save_aoi_btn)
        row2.addWidget(self.load_aoi_btn)
        middle_layout.addLayout(row2)

        self.auto_btn = QPushButton("Add hot spots as AOI")
        middle_layout.addWidget(self.auto_btn)

        export_title = QLabel("Areas from the export:")
        export_title.setProperty("boldTitle", True)
        middle_layout.addWidget(export_title)
        self.level_selector = QComboBox()
        self.level_selector.addItems(self.AVAILABLE_LEVEL)
        middle_layout.addWidget(self.level_selector)
        self.all_stimuli_checkbox = QCheckBox("On every stimulus")
        self.all_stimuli_checkbox.setChecked(True)
        middle_layout.addWidget(self.all_stimuli_checkbox)
        self.export_aoi_btn = QPushButton("Add areas from the export")
        middle_layout.addWidget(self.export_aoi_btn)
        self.set_export_aois_available(False)

        line2 = QFrame(self)
        line2.setObjectName("sectionSeparator")
        line2.setFrameShape(QFrame.NoFrame)
        line2.setFixedHeight(1)

        bottom = QWidget(self)
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.setContentsMargins(12, 8, 12, 12)
        bottom_layout.setSpacing(8)

        display_title = QLabel("Display:")
        display_title.setProperty("boldTitle", True)
        bottom_layout.addWidget(display_title)

        self.display_selector = QComboBox()
        self.display_selector.addItems(self.AVAILABLE_DISPLAY)
        self.display_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.display_selector)

        self.display_hint = utils.add_hint(bottom_layout, "Scarf plot: one row per participant, fixations coloured "
                                                          "by area over time. Transition matrix: where the gaze went "
                                                          "next after leaving an area (visits, not single fixations).")
        bottom_layout.addWidget(QLabel("Underlay:"))
        self.underlay_selector = QComboBox()
        self.underlay_selector.addItems(self.AVAILABLE_UNDERLAY)
        self.underlay_selector.currentIndexChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.underlay_selector)

        self.labels_checkbox = QCheckBox('Show names')
        self.labels_checkbox.setChecked(True)
        self.labels_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.labels_checkbox)

        self.opacity_slider, self.opacity_label, _ = utils.add_slider_row(
            bottom_layout, "AOI Opacity:", 0, len(self.AVAILABLE_OPACITY) - 1,
            self.AVAILABLE_OPACITY.index(0.35), self.update_labels_and_run)

        self.grayscale_checkbox = QCheckBox('Grayscale stimulus')
        self.grayscale_checkbox.setChecked(True)
        self.grayscale_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.grayscale_checkbox)

        self.outside_checkbox = QCheckBox('Transitions: count looks outside as a station')
        self.outside_checkbox.setChecked(False)
        self.outside_checkbox.stateChanged.connect(self.update_callback)
        bottom_layout.addWidget(self.outside_checkbox)

        self.min_run_slider, self.min_run_label, _ = utils.add_slider_row(
            bottom_layout, "Sequences: ignore runs under", 0, len(self.AVAILABLE_MIN_RUN) - 1, 0,
            self.update_labels_and_run)
        self.bridge_slider, self.bridge_label, _ = utils.add_slider_row(
            bottom_layout, "Sequences: bridge gaps up to", 0, len(self.AVAILABLE_BRIDGE) - 1, 0,
            self.update_labels_and_run)

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
        utils.apply_tooltips(self, dict(glossary.COMMON_TIPS, **glossary.TOOLTIPS['aoi']))

    def update_hint(self, *_):
        mode = self.mode_selector.currentText()
        if mode == "Draw rectangle":
            self.hint.setText("Click and drag on the image. Release to name the area.")
        elif mode == "Draw polygon":
            self.hint.setText("Click the corners on the image; double-click (or right-click) to close the shape. "
                              "Esc cancels.")
        else:
            self.hint.setText("Mouse interaction off.")

    def set_export_aois_available(self, available, reason=None, tags=True, tags_reason=None):
        for control in (self.level_selector, self.all_stimuli_checkbox, self.export_aoi_btn):
            control.setEnabled(bool(available))
        if reason is not None:
            self.export_aoi_btn.setToolTip(utils.rich_tooltip(reason))
        utils.set_combo_item_enabled(self.level_selector, "Area types", bool(tags), tags_reason)

    def set_aois(self, names, active=None):
        """Fill the list; `active` names the ticked areas (default: all)."""
        names = list(names)
        current = self.aoi_list.currentRow()
        self.aoi_list.blockSignals(True)
        self.aoi_list.clear()
        for name in names:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if active is None or name in active else Qt.Unchecked)
            self.aoi_list.addItem(item)
        if 0 <= current < self.aoi_list.count():
            self.aoi_list.setCurrentRow(current)
        self.aoi_list.blockSignals(False)
        self._names = names
        self.refresh_reference()
        self.update_display_availability()

    def set_all_checked(self, checked):
        if self.aoi_list.count() == 0:
            return
        self.aoi_list.blockSignals(True)
        for i in range(self.aoi_list.count()):
            self.aoi_list.item(i).setCheckState(Qt.Checked if checked else Qt.Unchecked)
        self.aoi_list.blockSignals(False)
        self.aoi_list.itemChanged.emit(self.aoi_list.item(0))

    def active_aois(self):
        """The ticked areas, in list order."""
        return [self.aoi_list.item(i).text() for i in range(self.aoi_list.count())
                if self.aoi_list.item(i).checkState() == Qt.Checked]

    def refresh_reference(self):
        current = self.reference_selector.currentText()
        self.reference_selector.blockSignals(True)
        self.reference_selector.clear()
        self.reference_selector.addItems([self.WHOLE_STIMULUS] + self.active_aois())
        idx = self.reference_selector.findText(current)
        self.reference_selector.setCurrentIndex(idx if idx >= 0 else 0)
        self.reference_selector.blockSignals(False)
        self.reference_selector.setEnabled(self.aoi_list.count() > 0)

    def update_display_availability(self):
        n = len(self.active_aois())
        for name in self.NEEDS_ONE_AREA:
            utils.set_combo_item_enabled(self.display_selector, name, n >= 1,
                                         "Needs at least one ticked area: draw one on the image, or add the areas "
                                         "of the export.")
        for name in self.NEEDS_TWO_AREAS:
            utils.set_combo_item_enabled(self.display_selector, name, n >= 2,
                                         "Needs at least two ticked areas: a transition or a comparison runs "
                                         "between areas.")

    def selected_aoi(self):
        item = self.aoi_list.currentItem()
        return item.text() if item is not None else None

    def get_params(self):
        return {
            "mode": self.mode_selector.currentText(),
            "display": self.display_selector.currentText(),
            "underlay": self.underlay_selector.currentText(),
            "labels": self.labels_checkbox.isChecked(),
            "alpha": self.AVAILABLE_OPACITY[self.opacity_slider.value()],
            "grayscale": self.grayscale_checkbox.isChecked(),
            "level": self.level_selector.currentText(),
            "all_stimuli": self.all_stimuli_checkbox.isChecked(),
            "min_run_s": self.AVAILABLE_MIN_RUN[self.min_run_slider.value()],
            "bridge_gap_s": self.AVAILABLE_BRIDGE[self.bridge_slider.value()],
            "include_outside": self.outside_checkbox.isChecked(),
            "names": self.active_aois(),
            "reference": None if self.reference_selector.currentIndex() <= 0 else self.reference_selector.currentText(),
        }

    def update_labels_and_run(self, *_, run=True):
        params = self.get_params()
        self.opacity_label.setText(f"{int(params['alpha'] * 100)}%")
        self.min_run_label.setText(f"{params['min_run_s']:g} s" if params['min_run_s'] else "off")
        self.bridge_label.setText(f"{params['bridge_gap_s']:g} s" if params['bridge_gap_s'] else "off")
        if run:
            self.update_callback()
