from PySide6.QtWidgets import (
    QPushButton, QDialog, QComboBox, QLabel, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem
)
from PySide6.QtCore import Qt
import pandas as pd
from creapy.misc.utils import natural_sorted


class GroupingDialog(QDialog):
    def __init__(self, subjects, df, subj_index, grouping=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Assign Participants to Groups")
        self.subjects = natural_sorted(subjects)
        self.df = df
        self.subj_index = subj_index
        if grouping is None:
            grouping = {}

        layout = QVBoxLayout(self)

        info = QLabel(
            "Type a group name for each participant (e.g. expert / layperson), or prefill the groups "
            "from a column of your table. Participants with an empty group are left out of the comparison."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Prefill shortcut: columns that are constant within each participant
        # and split the participants into at least 2 (but not all-distinct) groups
        candidates = []
        for col in df.columns:
            per_subj_nunique = df.groupby(subj_index)[col].nunique(dropna=False)
            if (per_subj_nunique == 1).all() and 2 <= df[col].nunique(dropna=False) < len(self.subjects):
                candidates.append(col)

        prefill_layout = QHBoxLayout()
        prefill_layout.addWidget(QLabel("Prefill from column:"))
        self.prefill_selector = QComboBox()
        self.prefill_selector.addItems(["(choose a column)"] + candidates)
        self.prefill_selector.currentIndexChanged.connect(self.prefill_from_column)
        prefill_layout.addWidget(self.prefill_selector, stretch=1)
        layout.addLayout(prefill_layout)

        self.table = QTableWidget(len(self.subjects), 2)
        self.table.setHorizontalHeaderLabels(["Participant", "Group"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        for row, subj in enumerate(self.subjects):
            subj_item = QTableWidgetItem(str(subj))
            subj_item.setFlags(subj_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row, 0, subj_item)
            self.table.setItem(row, 1, QTableWidgetItem(str(grouping.get(subj, ""))))
        layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self.clear_all)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        confirm_btn = QPushButton("Confirm")
        confirm_btn.clicked.connect(self.accept)
        btn_layout.addWidget(clear_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        layout.addLayout(btn_layout)

        self.resize(380, 540)

    def prefill_from_column(self, index):
        if index == 0:
            return
        col = self.prefill_selector.currentText()
        subj_to_value = self.df.groupby(self.subj_index)[col].first()
        for row, subj in enumerate(self.subjects):
            value = subj_to_value.get(subj, "")  # participants absent from this stimulus keep an empty group
            self.table.setItem(row, 1, QTableWidgetItem("" if pd.isna(value) else str(value)))

    def clear_all(self):
        for row in range(len(self.subjects)):
            self.table.setItem(row, 1, QTableWidgetItem(""))

    def get_grouping(self):
        # subj -> group name; blank rows are excluded
        grouping = {}
        for row, subj in enumerate(self.subjects):
            name = self.table.item(row, 1).text().strip()
            if name:
                grouping[subj] = name
        return grouping
