import numpy as np
import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QWidget, QVBoxLayout, QLabel


class DataFrameView(QWidget):
    """Read-only table of a DataFrame (the Statistics and AOI-metrics views), with a caption line above."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        self.caption = QLabel()
        self.caption.setWordWrap(True)
        layout.addWidget(self.caption)
        self.table = QTableWidget()
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)
        layout.addWidget(self.table)
        self.df = None

    def set_dataframe(self, df, caption="", decimals=3):
        self.df = df
        self.caption.setText(caption)
        self.table.setSortingEnabled(False)
        self.table.clear()
        self.table.setRowCount(len(df))
        self.table.setColumnCount(len(df.columns))
        self.table.setHorizontalHeaderLabels([str(c) for c in df.columns])
        for row in range(len(df)):
            for col_idx, col in enumerate(df.columns):
                value = df.iloc[row, col_idx]
                item = QTableWidgetItem()
                if isinstance(value, (float, np.floating)):
                    if np.isnan(value):
                        item.setText("")
                    else:
                        item.setData(Qt.DisplayRole, round(float(value), decimals))
                elif isinstance(value, (int, np.integer)):
                    item.setData(Qt.DisplayRole, int(value))
                else:
                    item.setText("" if pd.isna(value) else str(value))
                item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter if isinstance(value, (int, float, np.number))
                                      else Qt.AlignLeft | Qt.AlignVCenter)
                self.table.setItem(row, col_idx, item)
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)
