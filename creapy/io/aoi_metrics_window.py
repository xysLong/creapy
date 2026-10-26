import os
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QSplitter, QWidget,
                               QFileDialog, QCheckBox)
from PySide6.QtCore import Qt
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

from creapy.formats.tobii import aoi_metrics_summary
from creapy.io.widgets.table_view import DataFrameView
from creapy.io.widgets.painter import PainterWidget
from creapy.io.views import DARK_RC, DARK_BG
from creapy.misc.utils import natural_sorted


class AOIMetricsWindow(QDialog):
    """
    Tobii Pro Lab AOI-based metrics export as a table-only workspace: no positions, so nothing to draw on an
    image, but the dwell/visit/fixation totals per AOI are what the museum papers report. Choose a metric, see the
    mean per AOI (optionally split by Media / Condition / ...), read or export the summary and the raw rows.
    """

    def __init__(self, df_aoi, info, source_name, parent=None, log=None):
        super().__init__(parent)
        self.setWindowTitle(f"AOI Metrics - {source_name}")
        self.df_aoi = df_aoi
        self.info = info
        self.log = log
        self.save_dir = os.path.expanduser("~")
        self.current_table = df_aoi

        layout = QVBoxLayout(self)
        n = info.get('n_participants')
        head = QLabel(f"<b>{source_name}</b>: {len(df_aoi):,} rows (participant × interval × AOI)"
                      + (f", {n} participants" if n else "") + f", {df_aoi['AOI'].nunique()} AOIs. "
                      "Pro Lab left cells empty where a participant never looked at an AOI: creapy counts those "
                      "as 0 for totals and counts and keeps latencies empty.")
        head.setWordWrap(True)
        layout.addWidget(head)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Metric:"))
        self.metric_selector = QComboBox()
        for col in info['metrics']:
            self.metric_selector.addItem(info['labels'][col], userData=col)
        controls.addWidget(self.metric_selector, stretch=1)
        controls.addWidget(QLabel("Split by:"))
        self.split_selector = QComboBox()
        self.split_selector.addItem("(nothing)", userData=None)
        for col in info['group_columns']:
            if col not in ('AOI', 'Participant'):
                self.split_selector.addItem(col, userData=col)
        controls.addWidget(self.split_selector)
        self.lookers_only = QCheckBox("Only participants who looked (exclude zeros)")
        controls.addWidget(self.lookers_only)
        layout.addLayout(controls)

        self.painter = PainterWidget()
        self.table = DataFrameView()
        splitter = QSplitter(Qt.Vertical)
        splitter.addWidget(self.painter)
        splitter.addWidget(self.table)
        splitter.setSizes([420, 260])
        layout.addWidget(splitter, stretch=1)

        buttons = QHBoxLayout()
        self.show_raw_btn = QPushButton("Show raw rows")
        self.show_raw_btn.setCheckable(True)
        self.export_btn = QPushButton("Export Table…")
        self.save_btn = QPushButton("Save Figure as Image…")
        close_btn = QPushButton("Close")
        buttons.addWidget(self.show_raw_btn)
        buttons.addStretch()
        buttons.addWidget(self.export_btn)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(close_btn)
        layout.addLayout(buttons)

        self.metric_selector.currentIndexChanged.connect(self.refresh)
        self.split_selector.currentIndexChanged.connect(self.refresh)
        self.lookers_only.stateChanged.connect(self.refresh)
        self.show_raw_btn.toggled.connect(self.refresh)
        self.export_btn.clicked.connect(self.export_table)
        self.save_btn.clicked.connect(self.save_image)
        close_btn.clicked.connect(self.accept)
        self.resize(1100, 760)
        self.refresh()

    def refresh(self, *_):
        metric = self.metric_selector.currentData()
        split = self.split_selector.currentData()
        df = self.df_aoi
        if self.lookers_only.isChecked():
            df = df[df[metric].fillna(0) > 0]
        summary = aoi_metrics_summary(df, metric, by='AOI', group_col=split) if len(df) else pd.DataFrame()
        if self.log:
            self.log.log('params', view="AOI Metrics Table", params={'metric': metric, 'split': split,
                                                                      'lookers_only': self.lookers_only.isChecked()})
        with plt.rc_context(DARK_RC):
            fig = Figure(facecolor=DARK_BG)
            ax = fig.add_subplot()
            ax.set_facecolor(DARK_BG)
            if len(summary):
                aois = natural_sorted(summary['AOI'].unique())
                x = np.arange(len(aois))
                if split:
                    levels = natural_sorted(summary[split].dropna().unique())
                    w = 0.8 / max(len(levels), 1)
                    for i, level in enumerate(levels):
                        df_ = summary[summary[split] == level].set_index('AOI').reindex(aois)
                        ax.bar(x + (i - (len(levels) - 1) / 2) * w, df_['mean'], width=w, yerr=df_['sd'].fillna(0),
                               label=str(level), capsize=2, error_kw={'alpha': 0.4})
                    ax.legend(title=split)
                else:
                    df_ = summary.set_index('AOI').reindex(aois)
                    ax.bar(x, df_['mean'], width=0.7, yerr=df_['sd'].fillna(0), color='#4da3ff', capsize=3,
                           error_kw={'alpha': 0.4})
                ax.set_xticks(x)
                ax.set_xticklabels(aois, rotation=45, ha='right', fontsize=8 if len(aois) > 15 else 9)
                ax.set_ylabel(self.info['labels'][metric])
                ax.set_title(f"{self.info['labels'][metric]} per AOI: mean ± SD over participants"
                             + (" who looked" if self.lookers_only.isChecked() else " (non-lookers count as 0)"),
                             loc='left', fontsize=10)
            fig.tight_layout()
        self.painter.draw_figure(fig)
        if self.show_raw_btn.isChecked():
            self.current_table = self.df_aoi
            self.table.set_dataframe(self.df_aoi, "Raw export rows (identifying columns + known metrics).")
        else:
            self.current_table = summary
            self.table.set_dataframe(summary, f"Summary of <b>{self.info['labels'][metric]}</b> per AOI"
                                              + (f" and {split}" if split else "")
                                              + ": mean, SD, median, n participants, share who looked at all.")

    def export_table(self):
        df = self.current_table
        path, chosen = QFileDialog.getSaveFileName(self, "Export Table", os.path.join(self.save_dir, "aoi_metrics.csv"),
                                                   "CSV (*.csv);;Excel (*.xlsx)")
        if not path:
            return
        if not path.lower().endswith(('.csv', '.xlsx')):
            path += '.xlsx' if 'Excel' in chosen else '.csv'
        if path.lower().endswith('.xlsx'):
            df.to_excel(path, index=False)
        else:
            df.to_csv(path, index=False)
        self.save_dir = os.path.dirname(path)

    def save_image(self):
        fig = self.painter.current_fig
        if fig is None:
            return
        path, chosen = QFileDialog.getSaveFileName(self, "Save Figure", os.path.join(self.save_dir, "aoi_metrics.png"),
                                                   "PNG image (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if not path:
            return
        if not path.lower().endswith(('.png', '.pdf', '.svg')):
            path += '.pdf' if 'PDF' in chosen else ('.svg' if 'SVG' in chosen else '.png')
        fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.1, facecolor=fig.get_facecolor())
        self.save_dir = os.path.dirname(path)
