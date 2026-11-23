import math
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QComboBox, QSlider, QPushButton, QFrame

from creapy.misc.utils import natural_sorted

ALL_TEXT = "All participants"
GROUP_PREFIX = "Group: "
STEP_S = 0.5


class FilterBar(QFrame):
    filter_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FilterBar")
        self._subjects = []
        self._grouping = None
        self._t_max = 30.
        self._visit_mode = False  # mobile eye tracking: only the first N seconds of each visit

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
        self.time_title = QLabel("Time window:")
        self.time_title.setProperty("boldTitle", True)
        layout.addWidget(self.time_title)

        self.from_slider = QSlider(Qt.Horizontal)
        self.to_slider = QSlider(Qt.Horizontal)
        for slider in (self.from_slider, self.to_slider):
            slider.setMinimumWidth(130)
            slider.setTracking(True)
            slider.valueChanged.connect(self._on_slider)
        self.range_label = QLabel()
        self.range_label.setProperty("paramLabel", True)
        self.range_label.setMinimumWidth(110)
        self.from_label = QLabel("from")
        self.to_label = QLabel("to")
        layout.addWidget(self.from_label)
        layout.addWidget(self.from_slider)
        layout.addWidget(self.to_label)
        layout.addWidget(self.to_slider)
        layout.addWidget(self.range_label)

        self.reset_btn = QPushButton("Reset")
        self.reset_btn.setObjectName("SmallButton")
        self.reset_btn.clicked.connect(self.reset)
        layout.addWidget(self.reset_btn)
        layout.addStretch()

        self.to_slider.setRange(0, 1)
        self.to_slider.setValue(1)
        self.set_time_max(30.)


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
        idx = self.participant_selector.findText(current) if current else -1
        self.participant_selector.setCurrentIndex(idx if idx >= 0 else 0)
        self.participant_selector.blockSignals(False)

    def set_time_title(self, text):
        self.time_title.setText(text)

    def set_visit_mode(self, on):
        self._visit_mode = bool(on)
        self.from_label.setVisible(not on)
        self.from_slider.setVisible(not on)
        self.time_title.setText("Each visit:" if on else "Time window:")
        self.to_label.setText("first" if on else "to")
        self.to_slider.setToolTip(
            "Only the first seconds of every visit of the snapshot: what visitors look at when they arrive. "
            "Visits shorter than this count completely. Later windows are not offered, because they would only "
            "contain the visitors who stayed that long." if on else "")
        if on and self.from_slider.value() != 0:
            self.from_slider.blockSignals(True)
            self.from_slider.setValue(0)
            self.from_slider.blockSignals(False)
            self._emit()
        self._update_label()

    def describe(self):
        t_range = self.t_range()
        if t_range is None:
            return None
        t0, t1 = t_range
        return f"first {t1:.1f} s of each visit" if self._visit_mode else f"{t0:.1f}–{t1:.1f} s"

    def set_time_max(self, t_max):
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


    def participants(self):
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
        if self.from_slider.value() == 0 and self.to_slider.value() >= self.to_slider.maximum():
            return None
        return self.from_slider.value() * STEP_S, min(self.to_slider.value() * STEP_S, self._t_max)

    def is_active(self):
        return self.participants() is not None or self.t_range() is not None

    def filter_key(self):
        p = self.participants()
        return (tuple(p) if p is not None else None, self.t_range())


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
        if self._visit_mode:
            full = self.to_slider.value() >= self.to_slider.maximum()
            self.range_label.setText("whole visit" if full else f"{t1:.1f} s")
        else:
            self.range_label.setText(f"{t0:.1f} – {t1:.1f} s")

    def _emit(self, *_):
        self.filter_changed.emit()
