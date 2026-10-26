import pandas as pd
from PySide6.QtWidgets import (QPushButton, QDialog, QComboBox, QFormLayout, QHBoxLayout, QVBoxLayout, QLabel,
                               QTableWidget, QTableWidgetItem, QMessageBox, QDialogButtonBox)
from PySide6.QtCore import Qt

from creapy.formats.detect import FIXATION_FIELDS, SACCADE_FIELDS, guess_mapping, validate_mapping, detect_format

NONE_TEXT = "(none)"

FORMAT_LABELS = {
    'eyelink_fixation': "EyeLink DataViewer fixation report",
    'eyelink_saccade': "EyeLink DataViewer saccade report",
    'tobii_event_export': "Tobii Pro Lab event-based metrics export (fixation rows; positions 0–1 on the medium)",
    'tobii_data_export': "Tobii Pro Lab data export (converted to fixations)",
    'tobii_metrics_export': "Tobii Pro Lab AOI-based metrics export",
    'unknown': "generic table",
}


def find_column_mapping(columns, is_fixation):
    # Kept for callers that only have the column names (the dev-mode shortcut, old notebooks)
    df = pd.DataFrame({col: pd.Series(dtype=float) for col in columns})
    return guess_mapping(df, FIXATION_FIELDS if is_fixation else SACCADE_FIELDS)


class ColumnMappingDialog(QDialog):
    """Tell creapy which column is which. Required fields must be set; optional ones may stay '(none)'."""

    def __init__(self, df, is_fixation=True, mapping=None, parent=None, detected=None):
        super().__init__(parent)
        self.setWindowTitle("Map Table Columns")
        self.df = df
        self.fields = FIXATION_FIELDS if is_fixation else SACCADE_FIELDS
        columns = [str(c) for c in df.columns]
        if mapping is None:
            mapping = guess_mapping(df, self.fields)
        if detected is None:
            detected = detect_format(columns)

        layout = QVBoxLayout(self)

        intro = QLabel(
            f"<b>Detected format:</b> {FORMAT_LABELS.get(detected, detected)}.<br>"
            "Check that each field points at the right column of your table; the first rows are shown below. "
            "Fields marked <i>(optional)</i> can be left at <i>(none)</i>."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        body = QHBoxLayout()
        form = QFormLayout()
        self.combos = {}
        for key, (name, required, _) in self.fields.items():
            combo = QComboBox()
            if not required:
                combo.addItem(NONE_TEXT)
            combo.addItems(columns)
            current = mapping.get(key)
            if current is not None and str(current) in columns:
                combo.setCurrentText(str(current))
            elif not required:
                combo.setCurrentText(NONE_TEXT)
            combo.currentIndexChanged.connect(self.highlight_preview)
            form.addRow(f"{name}:", combo)
            self.combos[key] = combo
        body.addLayout(form, stretch=0)

        # Preview of the first rows so the user can see what the columns hold
        self.preview = QTableWidget(min(8, len(df)), len(columns))
        self.preview.setHorizontalHeaderLabels(columns)
        self.preview.verticalHeader().setVisible(False)
        self.preview.setEditTriggers(QTableWidget.NoEditTriggers)
        for row in range(self.preview.rowCount()):
            for col_idx, col in enumerate(df.columns):
                value = df.iloc[row, col_idx]
                text = "" if pd.isna(value) else (f"{value:.3f}" if isinstance(value, float) else str(value))
                self.preview.setItem(row, col_idx, QTableWidgetItem(text))
        self.preview.resizeColumnsToContents()
        self.preview.setMinimumWidth(420)
        body.addWidget(self.preview, stretch=1)
        layout.addLayout(body)

        self.problems_label = QLabel()
        self.problems_label.setWordWrap(True)
        self.problems_label.setStyleSheet("color: #ff9f6e;")
        layout.addWidget(self.problems_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Confirm")
        buttons.accepted.connect(self.try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.resize(1000, 480)
        self.highlight_preview()

    def get_mapping(self):
        mapping = {}
        for key, combo in self.combos.items():
            text = combo.currentText()
            mapping[key] = None if text == NONE_TEXT else text
        return mapping

    def highlight_preview(self, *_):
        # Mapped columns get a tinted header so mistakes (two fields on one column) are visible at a glance
        mapped = {v for v in self.get_mapping().values() if v is not None}
        for col_idx in range(self.preview.columnCount()):
            item = self.preview.horizontalHeaderItem(col_idx)
            if item is None:
                continue
            item.setBackground(Qt.darkCyan if item.text() in mapped else Qt.transparent)
            item.setForeground(Qt.white if item.text() in mapped else Qt.lightGray)

    def try_accept(self):
        problems = validate_mapping(self.df, self.get_mapping(), self.fields)
        if problems:
            self.problems_label.setText("Please fix:\n• " + "\n• ".join(problems))
            return
        self.accept()
