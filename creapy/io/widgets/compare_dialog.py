import os
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QRadioButton, QListWidget, QListWidgetItem,
                               QSpinBox, QDialogButtonBox, QGroupBox)
from PySide6.QtCore import Qt

from creapy.misc.utils import natural_sorted


class CompareDialog(QDialog):
    """
    Side-by-side comparison: the current view drawn once per group, per stimulus or per time window, in one figure.
    Returns a spec {'kind': 'groups' | 'stimuli' | 'time', 'items': [...]} via get_spec().
    """

    def __init__(self, stimulus_paths, grouping, t_max, parent=None, current=None):
        super().__init__(parent)
        self.setWindowTitle("Compare Side by Side")
        layout = QVBoxLayout(self)
        intro = QLabel("Draw the current view several times in one figure: one panel per group, per stimulus or "
                       "per time window. Same parameters everywhere, so the panels are comparable. Switch off with "
                       "Analysis > Stop Comparing.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.groups = natural_sorted(set(grouping.values())) if grouping else []
        self.radio_groups = QRadioButton(f"Groups ({', '.join(self.groups)})" if self.groups
                                         else "Groups (assign groups first)")
        self.radio_groups.setEnabled(bool(self.groups))
        self.radio_stimuli = QRadioButton("Stimuli (pick two or more below)")
        self.radio_time = QRadioButton("Time windows of equal length:")
        layout.addWidget(self.radio_groups)

        layout.addWidget(self.radio_stimuli)
        self.stimulus_list = QListWidget()
        self.stimulus_list.setSelectionMode(QListWidget.MultiSelection)
        for path in stimulus_paths:
            item = QListWidgetItem(os.path.basename(path))
            item.setData(Qt.UserRole, path)
            self.stimulus_list.addItem(item)
            item.setSelected(True)
        self.stimulus_list.setMaximumHeight(160)
        layout.addWidget(self.stimulus_list)

        time_row = QHBoxLayout()
        time_row.addWidget(self.radio_time)
        self.n_windows = QSpinBox()
        self.n_windows.setRange(2, 6)
        self.n_windows.setValue(3)
        time_row.addWidget(self.n_windows)
        time_row.addWidget(QLabel(f"(viewing time {t_max:.1f} s)"))
        time_row.addStretch()
        layout.addLayout(time_row)

        kind = (current or {}).get('kind')
        if kind == 'groups' and self.groups:
            self.radio_groups.setChecked(True)
        elif kind == 'time':
            self.radio_time.setChecked(True)
            self.n_windows.setValue(len(current['items']))
        elif kind == 'stimuli' or not self.groups:
            self.radio_stimuli.setChecked(True)
            if kind == 'stimuli':
                chosen = set(current['items'])
                for i in range(self.stimulus_list.count()):
                    item = self.stimulus_list.item(i)
                    item.setSelected(item.data(Qt.UserRole) in chosen)
        else:
            self.radio_groups.setChecked(True)
        self.t_max = t_max

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Compare")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(460, 420)

    def get_spec(self):
        if self.radio_groups.isChecked():
            return {'kind': 'groups', 'items': list(self.groups)}
        if self.radio_time.isChecked():
            n = self.n_windows.value()
            step = self.t_max / n
            return {'kind': 'time', 'items': [(round(i * step, 2), round((i + 1) * step, 2)) for i in range(n)]}
        paths = [item.data(Qt.UserRole) for item in self.stimulus_list.selectedItems()]
        return {'kind': 'stimuli', 'items': paths}
