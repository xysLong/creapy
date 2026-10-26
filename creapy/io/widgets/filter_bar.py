import math
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QSlider, QPushButton, QFrame

from creapy.misc.utils import natural_sorted

ALL_TEXT = "All participants"
GROUP_PREFIX = "Group: "
STEP_S = 0.5  # time-window slider resolution in seconds


class FilterBar(QFrame):
    """
    One row above the canvas: which participants and which part of the viewing time feed every view.
    Emits filter_changed(): the main window reads participants() / t_range() and rebuilds the datasets.
    """
    filter_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FilterBar")
        self._subjects = []
        self._grouping = None
        self._t_max = 30.

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 4, 10, 4)
        layout.setSpacing(10)

        title = QLabel("Show:")
        title.setProperty("boldTitle", True)
        layout.addWidget(title)

        self.participant_selector = QComboBox()
        self.participant_selector.setMinimumWidth(190)
        self.participant_selector.currentIndexChanged.connect(self._emit)
        layout.addWidget(self.participant_selector)

        layout.addSpacing(16)
        time_title = QLabel("Time window:")
        time_title.setProperty("boldTitle", True)
        layout.addWidget(time_title)

        self.from_slider = QSlider(Qt.Horizontal)
        self.to_slider = QSlider(Qt.Horizontal)
        for slider in (self.from_slider, self.to_slider):
            slider.setMinimumWidth(130)
            slider.setTracking(True)
            slider.valueChanged.connect(self._on_slider)
        self.range_label = QLabel()
        self.range_label.setProperty("paramLabel", True)
        self.range_label.setMinimumWidth(110)
        layout.addWidget(QLabel("from"))
        layout.addWidget(self.from_slider)
        layout.addWidget(QLabel("to"))
        layout.addWidget(self.to_slider)
        layout.addWidget(self.range_label)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("SmallButton")
        self.reset_btn.clicked.connect(self.reset)
        layout.addWidget(self.reset_btn)
        layout.addStretch()

        # start with the full window selected, whatever the first stimulus's viewing time turns out to be
        self.to_slider.setRange(0, 1)
        self.to_slider.setValue(1)
        self.set_time_max(30.)

    # ---------- state in ----------

    def set_subjects(self, subjects, grouping=None):
        self._subjects = natural_sorted(subjects)
        self._grouping = grouping or None
        current = self.participant_selector.currentText()
        self.participant_selector.blockSignals(True)
        self.participant_selector.clear()
        self.participant_selector.addItem(ALL_TEXT)
        if self._grouping:
            for name in natural_sorted(set(self._grouping.values())):
                n = sum(1 for g in self._grouping.values() if g == name)
                self.participant_selector.addItem(f"{GROUP_PREFIX}{name} ({n})", userData=('group', name))
        self.participant_selector.insertSeparator(self.participant_selector.count())
        for subj in self._subjects:
            self.participant_selector.addItem(str(subj), userData=('subject', subj))
        idx = self.participant_selector.findText(current) if current else -1  # '' would match the separator
        self.participant_selector.setCurrentIndex(idx if idx >= 0 else 0)
        self.participant_selector.blockSignals(False)

    def set_time_max(self, t_max):
        # Slider range follows the stimulus's viewing time; the current window is kept where possible
        self._t_max = max(float(t_max), STEP_S)
        n_steps = int(math.ceil(self._t_max / STEP_S))
        was_full = self.to_slider.value() >= self.to_slider.maximum()
        for slider in (self.from_slider, self.to_slider):
            slider.blockSignals(True)
            slider.setRange(0, n_steps)
        if was_full or self.to_slider.value() > n_steps:
            self.to_slider.setValue(n_steps)
        if self.from_slider.value() >= self.to_slider.value():
            self.from_slider.setValue(0)
        for slider in (self.from_slider, self.to_slider):
            slider.blockSignals(False)
        self._update_label()

    # ---------- state out ----------

    def participants(self):
        # None = everyone; else the list of selected participants
        data = self.participant_selector.currentData()
        if data is None:
            return None
        kind, value = data
        if kind == 'group':
            return [s for s in self._subjects if self._grouping.get(s) == value]
        return [value]

    def selection_label(self):
        return self.participant_selector.currentText()

    def t_range(self):
        # None = the whole viewing; else (t0, t1) in seconds
        if self.from_slider.value() == 0 and self.to_slider.value() >= self.to_slider.maximum():
            return None
        return self.from_slider.value() * STEP_S, min(self.to_slider.value() * STEP_S, self._t_max)

    def is_active(self):
        return self.participants() is not None or self.t_range() is not None

    def filter_key(self):
        p = self.participants()
        return (tuple(p) if p is not None else None, self.t_range())

    # ---------- internals ----------

    def reset(self):
        self.participant_selector.blockSignals(True)
        self.from_slider.blockSignals(True)
        self.to_slider.blockSignals(True)
        self.participant_selector.setCurrentIndex(0)
        self.from_slider.setValue(0)
        self.to_slider.setValue(self.to_slider.maximum())
        self.participant_selector.blockSignals(False)
        self.from_slider.blockSignals(False)
        self.to_slider.blockSignals(False)
        self._update_label()
        self.filter_changed.emit()

    def _on_slider(self, *_):
        # keep from < to (at least one step apart)
        if self.from_slider.value() >= self.to_slider.value():
            if self.sender() is self.from_slider:
                self.from_slider.blockSignals(True)
                self.from_slider.setValue(max(self.to_slider.value() - 1, 0))
                self.from_slider.blockSignals(False)
            else:
                self.to_slider.blockSignals(True)
                self.to_slider.setValue(min(self.from_slider.value() + 1, self.to_slider.maximum()))
                self.to_slider.blockSignals(False)
        self._update_label()
        self._emit()

    def _update_label(self):
        t0 = self.from_slider.value() * STEP_S
        t1 = min(self.to_slider.value() * STEP_S, self._t_max)
        self.range_label.setText(f"{t0:.1f} – {t1:.1f} s")

    def _emit(self, *_):
        self.filter_changed.emit()
