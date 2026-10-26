import json
import os
import sys
import time
import traceback
from contextlib import contextmanager
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QLabel, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QPushButton, QFrame,
    QSplitter, QListWidget, QStackedWidget, QMessageBox, QGraphicsOpacityEffect, QInputDialog, QProgressDialog,
    QToolButton, QDockWidget, QTextBrowser
)
from PySide6.QtGui import QPixmap, QAction, QDesktopServices
from PySide6.QtCore import Qt, QStandardPaths, QTimer, QEventLoop, QPropertyAnimation, QUrl, QLocale, QSettings
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
import matplotlib.patches as patches

import creapy
from creapy.io.widgets.toolbars.scanpath import SaccadeScanpathToolbar
from creapy.io.widgets.toolbars.fix_heatmap import FixationHeatmapToolbar
from creapy.io.widgets.toolbars.fix_scanpath import FixationScanpathToolbar
from creapy.io.widgets.toolbars.sac_heatmap import SaccadeHeatmapToolbar
from creapy.io.widgets.toolbars.rose import RoseToolbar
from creapy.io.widgets.toolbars.aoi import AOIToolbar
from creapy.io.widgets.toolbars.similarity import SimilarityToolbar
from creapy.io.widgets.toolbars.scanpath_compare import ScanpathCompareToolbar
from creapy.io.widgets.toolbars.recurrence import RecurrenceToolbar
from creapy.io.widgets.toolbars.time_series import TimeSeriesToolbar
from creapy.io.widgets.toolbars.stats import StatisticsToolbar
from creapy.io.widgets.painter import PainterWidget
from creapy.io.widgets.stimulus_strip import StimulusStrip
from creapy.io.widgets.column_mapping import ColumnMappingDialog
from creapy.io.widgets.grouping_dialog import GroupingDialog
from creapy.io.widgets.filter_bar import FilterBar
from creapy.io.widgets.table_view import DataFrameView
from creapy.io.widgets.compare_dialog import CompareDialog
from creapy.io.session_log import SessionLog
from creapy.io.worker import JobRunner
from creapy.io import help as help_texts
from creapy.io import views
from creapy.io import glossary
import creapy.io.widgets.utils as widget_utils
from creapy.io.views import Hint, DARK_BG, DARK_RC, VIEW_SPECS, COMPARABLE_VIEWS
from creapy.io import project as project_io
from creapy.io.aoi_metrics_window import AOIMetricsWindow

from creapy.formats import read_table, detect_format, guess_mapping, load_prolab_export, load_prolab_aoi_metrics_export
from creapy.formats import FIXATION_FIELDS, SACCADE_FIELDS
from creapy.formats.tobii import load_prolab_data_export_chunked
from creapy.misc.utils import find_images
from creapy.aoi.aoi import AOI

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE_DIR = os.path.join(HERE, 'style')

DEV_MODE = bool(os.environ.get("CREAPY_DEV_TABLE"))  # developer start: open this fixation table at once; also prints tracebacks
SYNCHRONOUS = False  # True: computations run inline instead of in a worker thread (tests, self-test)
CHUNKED_IMPORT_BYTES = 1_500_000_000  # Data exports above this are read in chunks (the WOQ room files are 70 GB)


def style(name):
    with open(os.path.join(STYLE_DIR, name), encoding='utf-8') as f:
        return f.read()


class MainWindow(QMainWindow):
    VIEWS = ["Fixation Heatmap", "Fixation Scanpath", "Saccade Scanpath", "Saccade Heatmap",
             "Saccade Directions", "Areas of Interest", "Time Series", "Saccade Similarity", "Scanpath Comparison",
             "Recurrence", "Statistics"]

    def __init__(self, synchronous=None):
        super().__init__()
        self.setWindowTitle("creapy.io")
        self.setGeometry(100, 100, 1320, 860)
        self.log = SessionLog()
        self.settings = QSettings("CReA", "creapy.io")
        self.jobs = JobRunner(self, synchronous=SYNCHRONOUS if synchronous is None else synchronous)
        self.dataset_fix = None
        self.dataset_sac = None
        self.source_name = None
        self.source_path = None  # table file behind the workspace (for project files)
        self.project_path = None
        self.save_dir = QStandardPaths.writableLocation(QStandardPaths.PicturesLocation)
        self.current_table = None  # the DataFrame behind the current table view (for Export Table)
        self.current_caption = None  # the explanatory line under the current chart (also written on save)
        self.current_axes_kind = 'image'
        self.current_path = None
        self.drawing = None  # AOI drawing state (see run_aoi)
        self.canvas_connections = []
        self.compare = None  # side-by-side spec {'kind', 'items'} or None
        self.undo_stack = []  # (label, undo_fn, redo_fn)
        self.redo_stack = []
        self.init_menu()
        if DEV_MODE:
            dev_table = os.environ["CREAPY_DEV_TABLE"]
            df, mapping = creapy.load_fixations(dev_table)
            stim_2_df = {str(stim): df_stim for stim, df_stim in df.groupby(mapping['stim_col'])}
            self.setup_workspace(stim_2_df, mapping, is_fixation=True, source_name=os.path.basename(dev_table))
        else:
            self.init_start_ui()
        self.log.log('app_start', version=creapy.__version__)

    # =====================================================================================
    # Menu, status bar, help
    # =====================================================================================

    def init_menu(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)  # same look on macOS and Windows, and visible in screenshots

        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.make_action("Import Fixation Table…", lambda: self.import_dataset(True), "Ctrl+O"))
        file_menu.addAction(self.make_action("Import Saccade Table…", lambda: self.import_dataset(False)))
        file_menu.addAction(self.make_action("Import Tobii Pro Lab Export…", self.import_tobii))
        file_menu.addAction(self.make_action("Open Tobii AOI Metrics Table…", self.open_aoi_metrics))
        file_menu.addAction(self.make_action("Open Example Dataset", self.open_example))
        file_menu.addSeparator()
        file_menu.addAction(self.make_action("Open Project…", self.open_project, "Ctrl+Shift+O"))
        self.save_project_action = self.make_action("Save Project…", self.save_project, "Ctrl+Shift+S")
        file_menu.addAction(self.save_project_action)
        self.recent_menu = file_menu.addMenu("Recent Projects")
        self.refresh_recent_menu()
        file_menu.addSeparator()
        self.save_image_action = self.make_action("Save Figure as Image…", self.save_image, "Ctrl+S")
        self.export_table_action = self.make_action("Export Current Table…", self.export_table, "Ctrl+E")
        self.batch_action = self.make_action("Export This View for All Stimuli…", self.batch_export, "Ctrl+Shift+E")
        file_menu.addAction(self.save_image_action)
        file_menu.addAction(self.export_table_action)
        file_menu.addAction(self.batch_action)
        file_menu.addSeparator()
        file_menu.addAction(self.make_action("Quit", self.close, "Ctrl+Q"))

        edit_menu = menubar.addMenu("&Edit")
        self.undo_action = self.make_action("Undo", self.undo, "Ctrl+Z")
        self.redo_action = self.make_action("Redo", self.redo, "Ctrl+Shift+Z")
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)
        self.update_undo_actions()

        analysis_menu = menubar.addMenu("&Analysis")
        self.groups_action = self.make_action("Assign Participants to Groups…", self.assign_groups, "Ctrl+G")
        analysis_menu.addAction(self.groups_action)
        self.compare_action = self.make_action("Compare Side by Side…", self.choose_compare, "Ctrl+D")
        self.stop_compare_action = self.make_action("Stop Comparing", self.stop_compare)
        analysis_menu.addAction(self.compare_action)
        analysis_menu.addAction(self.stop_compare_action)
        analysis_menu.addAction(self.make_action("Reset Filters", self.reset_filters))

        logging_menu = menubar.addMenu("&Logging")
        self.logging_action = QAction("Record session log (on this computer only)", self, checkable=True)
        self.logging_action.setChecked(self.log.enabled)
        self.logging_action.toggled.connect(self.toggle_logging)
        logging_menu.addAction(self.logging_action)
        logging_menu.addAction(self.make_action("Open log folder", self.open_log_folder))
        logging_menu.addAction(self.make_action("What is logged?", lambda: self.show_help("About creapy.io",
                                                                                           help_texts.ABOUT)))

        help_menu = menubar.addMenu("&Help")
        help_menu.addAction(self.make_action("Quick Guide", lambda: self.show_help("Quick Guide",
                                                                                   help_texts.QUICK_GUIDE), "F1"))
        help_menu.addAction(self.make_action("Supported Data Formats", lambda: self.show_help("Supported Data Formats",
                                                                                              help_texts.FORMATS)))
        help_menu.addAction(self.make_action("The Analyses Explained", lambda: self.show_help("The Analyses Explained",
                                                                                              help_texts.ANALYSES)))
        self.explainer_action = self.make_action("About This View", lambda: self.toggle_explainer(True), "Shift+F1")
        help_menu.addAction(self.explainer_action)
        help_menu.addAction(self.make_action("About creapy.io", lambda: self.show_help("About creapy.io",
                                                                                       help_texts.ABOUT)))

        self.status_dataset = QLabel("No dataset loaded")
        self.status_compare = QLabel()
        self.status_compare.setStyleSheet("color: #ffd166; padding: 0 8px;")
        self.status_logging = QLabel()
        self.status_logging.setObjectName("LoggingIndicator")
        self.statusBar().addWidget(self.status_dataset, stretch=1)
        self.statusBar().addPermanentWidget(self.status_compare)
        self.statusBar().addPermanentWidget(self.status_logging)
        self.update_logging_indicator()
        self.set_workspace_actions_enabled(False)

    def make_action(self, text, slot, shortcut=None):
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(shortcut)
        return action

    def set_workspace_actions_enabled(self, enabled):
        for action in (self.save_image_action, self.export_table_action, self.groups_action, self.batch_action,
                       self.save_project_action, self.compare_action, self.stop_compare_action):
            action.setEnabled(enabled)

    def show_help(self, title, html):
        help_texts.HelpDialog(title, html, parent=self).exec()

    def toggle_logging(self, enabled):
        self.log.set_enabled(enabled)
        self.update_logging_indicator()
        if enabled:
            QMessageBox.information(
                self, "Session Log Enabled",
                "creapy now records which views, parameters and filters you use into a text file on this "
                f"computer:\n\n{self.log.path}\n\nNothing is sent anywhere. You can switch this off at any time "
                "under Logging and delete the files whenever you like.")

    def update_logging_indicator(self):
        if self.log.enabled:
            self.status_logging.setText("● Logging on")
            self.status_logging.setStyleSheet("color: #7fd18c; padding: 0 8px;")
        else:
            self.status_logging.setText("○ Logging off")
            self.status_logging.setStyleSheet("color: #767c8c; padding: 0 8px;")

    def open_log_folder(self):
        os.makedirs(self.log.folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.log.folder))

    def closeEvent(self, event):
        self.jobs.cancel()
        self.log.close()
        super().closeEvent(event)

    # ---------- undo / redo (AOI edits and group assignments) ----------

    def push_undo(self, label, undo_fn, redo_fn):
        self.undo_stack.append((label, undo_fn, redo_fn))
        del self.undo_stack[:-50]
        self.redo_stack.clear()
        self.update_undo_actions()

    def undo(self):
        if not self.undo_stack:
            return
        label, undo_fn, redo_fn = self.undo_stack.pop()
        undo_fn()
        self.redo_stack.append((label, undo_fn, redo_fn))
        self.log.log('undo', what=label)
        self.update_undo_actions()
        self.statusBar().showMessage(f"Undone: {label}", 3000)

    def redo(self):
        if not self.redo_stack:
            return
        label, undo_fn, redo_fn = self.redo_stack.pop()
        redo_fn()
        self.undo_stack.append((label, undo_fn, redo_fn))
        self.log.log('redo', what=label)
        self.update_undo_actions()
        self.statusBar().showMessage(f"Redone: {label}", 3000)

    def update_undo_actions(self):
        self.undo_action.setEnabled(bool(self.undo_stack))
        self.undo_action.setText(f"Undo {self.undo_stack[-1][0]}" if self.undo_stack else "Undo")
        self.redo_action.setEnabled(bool(self.redo_stack))
        self.redo_action.setText(f"Redo {self.redo_stack[-1][0]}" if self.redo_stack else "Redo")

    # =====================================================================================
    # Start screen
    # =====================================================================================

    def init_start_ui(self):
        # self.setStyleSheet(style("start_light.qss"))
        self.setStyleSheet(style("start_dark.qss"))
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(40, 30, 40, 30)
        main_layout.setSpacing(24)

        # ---------- HEADER ----------
        header_layout = QVBoxLayout()
        header_layout.setAlignment(Qt.AlignLeft | Qt.AlignTop)

        title_label = QLabel("creapy.io")
        title_label.setObjectName("TitleLabel")
        title_label.setAlignment(Qt.AlignLeft)

        subtitle_label = QLabel("Eye-tracking data visualisation for art history: import a table, explore, export")
        subtitle_label.setObjectName("SubtitleLabel")
        subtitle_label.setAlignment(Qt.AlignLeft)

        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        main_layout.addLayout(header_layout)

        # ---------- THREE CARDS ----------
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)

        fix_card, self.import_btn_fix = self.make_card(
            "Fixation table",
            os.path.join(STYLE_DIR, "fix_thumbnail.png"),
            """
            <p><b>Each row is one fixation</b>: e.g. an EyeLink DataViewer <i>fixation report</i>
            (.csv / .xlsx / .tsv).</p>
            <p>Needed columns: stimulus image (name or path), participant, start time, duration, X, Y.
            Optional: trial, pupil size.</p>
            <p><i>Saccades are derived from consecutive fixations, so all views are available.</i></p>
            """,
            "Import Fixation Table…")
        self.import_btn_fix.clicked.connect(lambda: self.import_dataset(True))

        sac_card, self.import_btn_sac = self.make_card(
            "Saccade table",
            os.path.join(STYLE_DIR, "sac_thumbnail.png"),
            """
            <p><b>Each row is one saccade</b>: e.g. an EyeLink DataViewer <i>saccade report</i>.</p>
            <p>Needed columns: stimulus image, participant, start time, amplitude, start X/Y, end X/Y.
            Optional: trial.</p>
            <p><i>Fixations are inferred between consecutive saccades.</i></p>
            """,
            "Import Saccade Table…")
        self.import_btn_sac.clicked.connect(lambda: self.import_dataset(False))

        tobii_card, self.import_btn_tobii = self.make_card(
            "Tobii Pro Lab export",
            os.path.join(STYLE_DIR, "fix_thumbnail.png"),
            """
            <p><b>Mobile or screen-based Tobii data</b>: the Pro Lab <i>event-based metrics export</i>
            (one row per fixation; the usual lab file) or the <i>Data export</i> (one row per gaze sample, any size).</p>
            <p>Each snapshot / medium becomes one stimulus; you will be asked for the folder with the snapshot
            images (subfolders are searched).</p>
            <p><i>AOI-based metrics exports (no positions) open as a table with charts per AOI.</i></p>
            """,
            "Import Tobii Pro Lab Export…")
        self.import_btn_tobii.clicked.connect(self.import_tobii)

        cards_layout.addWidget(fix_card)
        cards_layout.addWidget(sac_card)
        cards_layout.addWidget(tobii_card)
        main_layout.addLayout(cards_layout)

        footer = QHBoxLayout()
        example_btn = QPushButton("Open the example dataset")
        example_btn.setToolTip("A small synthetic dataset (two images, twelve viewers in two groups) to try every view")
        example_btn.clicked.connect(self.open_example)
        project_btn = QPushButton("Open a project…")
        project_btn.setToolTip("Resume a saved creapy project (table, images, groups and areas of interest)")
        project_btn.clicked.connect(self.open_project)
        guide_btn = QPushButton("Quick guide")
        guide_btn.clicked.connect(lambda: self.show_help("Quick Guide", help_texts.QUICK_GUIDE))
        footer.addWidget(example_btn)
        footer.addWidget(project_btn)
        footer.addWidget(guide_btn)
        footer.addStretch()
        credits_label = QLabel(f"v{creapy.__version__} · Support: Xingyu Long @CReA (xingyu.long@univie.ac.at)")
        credits_label.setObjectName("CreditsLabel")
        footer.addWidget(credits_label)
        main_layout.addLayout(footer)
        main_layout.addStretch()

    def make_card(self, title, logo_path, html, button_text):
        card = QFrame()
        card.setObjectName("DataCard")
        layout = QVBoxLayout(card)
        layout.setSpacing(10)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.load_logo(logo_path))
        desc = QLabel(html)
        desc.setObjectName("BodyLabel")
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        button = QPushButton(button_text)
        layout.addLayout(header_layout)
        layout.addWidget(desc)
        layout.addStretch()
        layout.addWidget(button, alignment=Qt.AlignRight)
        return card, button

    def load_logo(self, path, thumb_size=50):
        logo = QLabel()
        logo.setObjectName("ThumbLabel")
        logo.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        pix = QPixmap(path)
        dpr = self.devicePixelRatioF()
        target_px = int(thumb_size * dpr)
        pix = pix.scaled(target_px, target_px, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pix.setDevicePixelRatio(dpr)
        logo.setScaledContents(False)
        logo.setPixmap(pix)
        return logo

    # =====================================================================================
    # Import
    # =====================================================================================

    def pick_table_file(self, title):
        path, _ = QFileDialog.getOpenFileName(
            self, title, "",
            "Data tables (*.csv *.tsv *.txt *.xlsx *.xls);;CSV / TSV (*.csv *.tsv *.txt);;Excel (*.xlsx *.xls)")
        return path or None

    def read_table_or_complain(self, path):
        try:
            df = read_table(path)
        except Exception as e:
            self.log.log_error('read_table', e)
            QMessageBox.critical(
                self, "Import Failed",
                "The file could not be read.\n\n"
                "Please make sure it is a .csv, .tsv, .txt or .xlsx table and try again.\n\n"
                f"Technical detail: {e}")
            return None
        if len(df) == 0 or len(df.columns) < 3:
            QMessageBox.critical(self, "Import Failed",
                                 "The table is empty or has fewer than three columns.")
            return None
        return df

    def import_dataset(self, is_fixation, path=None):
        if path is None:
            path = self.pick_table_file("Open Fixation Table" if is_fixation else "Open Saccade Table")
        if path is None:
            return
        if os.path.getsize(path) > CHUNKED_IMPORT_BYTES:
            # too large to read whole: only a Tobii Data export makes sense at this size
            self.import_tobii(path=path)
            return
        df = self.read_table_or_complain(path)
        if df is None:
            return
        detected = detect_format(df.columns)
        if detected in ('tobii_data_export', 'tobii_event_export'):
            what = "data export (one row per gaze sample)" if detected == 'tobii_data_export' \
                else "event-based metrics export (one row per fixation / saccade / glance)"
            answer = QMessageBox.question(
                self, "Tobii Pro Lab Export Detected",
                f"This looks like a Tobii Pro Lab {what}.\n\nConvert it to a fixation table and import it as such?",
                QMessageBox.Yes | QMessageBox.No)
            if answer == QMessageBox.Yes:
                self.import_tobii(path=path, df=df)
            return
        if detected == 'tobii_metrics_export':
            answer = QMessageBox.question(
                self, "AOI-based Metrics Export",
                "This is a Tobii Pro Lab *AOI-based* metrics export (one row per AOI and interval, no positions), "
                "so there is nothing to draw on an image.\n\nOpen it as an AOI metrics table with charts per AOI "
                "instead?", QMessageBox.Yes | QMessageBox.No)
            if answer == QMessageBox.Yes:
                self.open_aoi_metrics(path=path, df=df)
            return
        if is_fixation and detected == 'eyelink_saccade':
            QMessageBox.information(self, "Saccade Report Detected",
                                    "This table looks like an EyeLink saccade report. It will be imported as saccades.")
            is_fixation = False
        elif not is_fixation and detected == 'eyelink_fixation':
            QMessageBox.information(self, "Fixation Report Detected",
                                    "This table looks like an EyeLink fixation report. It will be imported as fixations.")
            is_fixation = True
        self.finish_import(df, is_fixation=is_fixation, source_name=os.path.basename(path), detected=detected,
                           source_path=path, source_kind='table')

    def import_tobii(self, path=None, df=None):
        if path is None:
            path = self.pick_table_file("Open Tobii Pro Lab Export")
            if path is None:
                return
        chunked = df is None and os.path.getsize(path) > CHUNKED_IMPORT_BYTES
        if chunked:
            # a whole-room Data export: read only the needed columns, chunk by chunk, with a cancellable progress bar
            size_gb = os.path.getsize(path) / 1e9
            progress = QProgressDialog(f"Reading the {size_gb:.1f} GB export in chunks: this takes a while "
                                       "(about a minute per gigabyte) …", "Cancel", 0, 1000, self)
            progress.setWindowTitle("Importing Tobii Data Export")
            progress.setMinimumDuration(0)
            progress.setValue(0)

            def report(done, total, text):
                progress.setLabelText(f"{text} …")
                progress.setValue(min(999, int(1000 * done / max(total, 1))) if total else 0)
                QApplication.processEvents()
                return not progress.wasCanceled()

            try:
                df_fix, mapping = load_prolab_data_export_chunked(path, progress=report)
            except InterruptedError:
                return
            except Exception as e:
                self.log.log_error('tobii_import', e)
                QMessageBox.critical(self, "Tobii Import Failed", f"The export could not be converted to fixations.\n\n{e}")
                return
            finally:
                progress.close()
            detected = 'tobii_data_export'
        else:
            if df is None:
                df = self.read_table_or_complain(path)
                if df is None:
                    return
            detected = detect_format(df.columns)
            if detected == 'tobii_metrics_export':
                self.open_aoi_metrics(path=path, df=df)
                return
            try:
                with self.wait_cursor():
                    df_fix, mapping = load_prolab_export(df)
            except Exception as e:
                self.log.log_error('tobii_import', e)
                QMessageBox.critical(self, "Tobii Import Failed",
                                     "The export could not be converted to fixations.\n\n"
                                     f"{e}\n\nSee Help > Supported Data Formats for the required columns.")
                return
        if detected == 'tobii_event_export':
            kind = ("event-based metrics export: positions are relative to each medium (snapshot or screen), "
                    "times restart at every interval of the time of interest, each interval counts as a trial")
            media_word = "media (snapshots)"
        else:
            n_snap = int(df_fix['snapshot_mapped'].sum())
            kind = "glasses recordings mapped onto snapshots" if n_snap else "screen-based recordings"
            media_word = 'snapshots' if n_snap else 'media'
        QMessageBox.information(
            self, "Tobii Export Converted",
            f"{len(df_fix):,} fixations from {df_fix['participant'].nunique()} participants on "
            f"{df_fix['stimulus'].nunique()} {media_word} ({kind}).\n\n"
            "Next: confirm the column mapping, then locate the folder with the snapshot / stimulus images "
            "(subfolders are searched; names are matched with or without extension).")
        self.finish_import(df_fix, is_fixation=True, source_name=os.path.basename(path),
                           detected=detected, mapping=mapping, source_path=path, source_kind='tobii')

    def open_aoi_metrics(self, path=None, df=None):
        # Tobii AOI-based metrics export -> table window (no stimuli involved, independent of the workspace)
        if path is None:
            path = self.pick_table_file("Open Tobii Pro Lab AOI-based Metrics Export")
            if path is None:
                return
        try:
            with self.wait_cursor():
                df_aoi, info = load_prolab_aoi_metrics_export(df if df is not None else path)
        except Exception as e:
            self.log.log_error('aoi_metrics_import', e)
            QMessageBox.critical(self, "Not an AOI Metrics Export",
                                 "The file does not look like a Tobii Pro Lab AOI-based metrics export.\n\n"
                                 f"Technical detail: {e}")
            return
        self.log.log('import', source=os.path.basename(path), format='tobii_metrics_export', n_rows=len(df_aoi))
        window = AOIMetricsWindow(df_aoi, info, os.path.basename(path), parent=self, log=self.log)
        window.setWindowModality(Qt.NonModal)
        window.show()
        self.aoi_metrics_windows = getattr(self, 'aoi_metrics_windows', []) + [window]

    def finish_import(self, df, is_fixation, source_name, detected=None, mapping=None, source_path=None,
                      source_kind='table', stim_2_path=None, confirm_mapping=True):
        if confirm_mapping:
            dialog = ColumnMappingDialog(df, is_fixation=is_fixation, mapping=mapping, parent=self, detected=detected)
            if not dialog.exec():
                return False
            mapping = dict(mapping or {}, **dialog.get_mapping())  # keeps loader flags such as normalized_xy
        try:
            stim_col = mapping['stim_col']
            df = df[df[stim_col].notna()]
            groups = dict(list(df.groupby(stim_col)))
            if stim_2_path is None:
                stim_2_path = self.resolve_stimulus_paths(list(groups))
            if stim_2_path is None:  # user cancelled the folder selection
                return False
            stim_2_df = {stim_2_path[stim]: df_stim for stim, df_stim in groups.items() if stim in stim_2_path}
            # The busy pill only exists once the workspace is built: a wait
            # cursor covers the thumbnail loading until then
            with self.wait_cursor():
                self.setup_workspace(stim_2_df, mapping, is_fixation, source_name=source_name)
            self.source_path = source_path
            self.source_kind = source_kind
            self.stim_values = {path: stim for stim, path in stim_2_path.items() if stim in groups}  # path -> table value
            self.log.log('import', source=source_name, format=detected, is_fixation=is_fixation,
                         n_rows=len(df), n_stimuli=len(stim_2_df), mapping=mapping)
            return True
        except Exception as e:
            self.log.log_error('import', e)
            QMessageBox.critical(
                self, "Import Failed",
                "The dataset could not be imported.\n\n"
                "Please check that the column mapping matches your table\n"
                "(e.g., coordinate columns contain numbers, the stimulus\n"
                "column contains image names).\n\n"
                f"Technical detail: {e}")
            return False

    def open_example(self):
        from creapy.examples import example_dataset
        try:
            with self.wait_cursor():
                path = example_dataset()
                df, mapping = creapy.load_fixations(path)
            stim_2_df = {stim: df_stim for stim, df_stim in df.groupby(mapping['stim_col'])}
            # example rows carry paths relative to the examples folder
            folder = os.path.dirname(path)
            stim_2_path = {stim: os.path.join(folder, os.path.basename(str(stim))) for stim in stim_2_df}
            stim_2_df = {stim_2_path[stim]: df_stim for stim, df_stim in stim_2_df.items()}
            with self.wait_cursor():
                self.setup_workspace(stim_2_df, mapping, is_fixation=True, source_name="example dataset")
            self.source_path, self.source_kind = path, 'example'
            self.stim_values = {p: s for s, p in stim_2_path.items()}
            self.log.log('import', source='example', format='example', is_fixation=True, n_rows=len(df))
            QMessageBox.information(
                self, "Example Dataset",
                "Twelve synthetic viewers (six 'experts', six 'laypersons') looked at two synthetic pictures for "
                "30 seconds each. The data are invented, so nothing here says anything about real people: "
                "but every view works, and Analysis > Assign Groups can prefill the groups from the 'group' column.")
        except Exception as e:
            self.log.log_error('example', e)
            QMessageBox.critical(self, "Example Failed", f"The example dataset could not be opened.\n\nTechnical detail: {e}")

    def resolve_stimulus_paths(self, stim_values, folder=None):
        # stim value in the table -> local image path; missing entries trigger a folder picker, then
        # the names from the table are matched (case-insensitively, with or without extension) against the folder.
        resolved = {stim: str(stim) for stim in stim_values if os.path.isfile(str(stim))}
        missing = [stim for stim in stim_values if stim not in resolved]

        if missing:
            if folder is None:
                QMessageBox.information(
                    self, "Locate Stimulus Images",
                    "The stimulus images referenced in your table could not be found on this computer.\n\n"
                    "In the next step, please select the folder that contains your stimulus images "
                    "(for Tobii glasses data: the snapshot images).\n"
                    "The image file names must match the names in the table (the extension may be omitted).")
                folder = QFileDialog.getExistingDirectory(self, "Select the Folder Containing Your Stimulus Images")
            if not folder:
                return None
            self.image_folder = folder
            with self.wait_cursor():
                folder_files = find_images(folder)  # subfolders included (WOQ keeps snapshots per room)
            for stim in missing:
                file_name = os.path.basename(str(stim).replace('\\', '/')).lower()  # tolerate Windows paths
                stem = os.path.splitext(file_name)[0]
                if file_name in folder_files:
                    resolved[stim] = folder_files[file_name]
                elif stem in folder_files:
                    resolved[stim] = folder_files[stem]

        still_missing = [stim for stim in stim_values if stim not in resolved]
        if not resolved:
            QMessageBox.critical(
                self, "Stimulus Images Not Found",
                "None of the stimulus images referenced in your table were found in the selected folder.\n\n"
                "Please check that the folder contains the images and that their file names match the table.")
            return None
        if still_missing:
            names = "\n".join(f"  · {stim}" for stim in still_missing[:10])
            if len(still_missing) > 10:
                names += f"\n  · ... and {len(still_missing) - 10} more"
            QMessageBox.warning(
                self, "Some Stimulus Images Not Found",
                f"The following stimuli were not found in the selected folder and will be skipped:\n\n{names}")
        return resolved

    # =====================================================================================
    # Projects (table path + mapping + images + groups + AOIs, no gaze data)
    # =====================================================================================

    def project_state(self):
        sizes = {path: (fix.width, fix.height) for path, (fix, _) in self.base_cache.items()}
        return {
            'source_path': self.source_path, 'source_kind': getattr(self, 'source_kind', 'table'),
            'source_name': self.source_name, 'is_fixation': self.is_fixation, 'mapping': self.mapping,
            'stimuli': [{'value': str(self.stim_values.get(path, path)), 'path': path} for path in self.stim_dfs],
            'image_folder': getattr(self, 'image_folder', None),
            'grouping': {str(k): v for k, v in (self.grouping or {}).items()},
            'aois': project_io.aois_to_records(self.aois, sizes),
            'view': self.VIEWS[self.left_toolbar.currentRow()] if self.left_toolbar.currentRow() >= 0 else None,
            'compare': self.compare,
        }

    def save_project(self):
        if self.dataset_fix is None:
            return
        default = self.project_path or os.path.join(
            self.save_dir, os.path.splitext(self.source_name or 'creapy')[0] + project_io.PROJECT_SUFFIX)
        path, _ = QFileDialog.getSaveFileName(self, "Save Project", default, "creapy project (*.creapy.json)")
        if not path:
            return
        if not path.endswith(project_io.PROJECT_SUFFIX):
            path += project_io.PROJECT_SUFFIX
        try:
            project_io.save_project(path, self.project_state())
        except Exception as e:
            self.log.log_error('project_save', e)
            QMessageBox.critical(self, "Save Failed", f"The project could not be saved.\n\nTechnical detail: {e}")
            return
        self.project_path = path
        self.save_dir = os.path.dirname(path)
        self.add_recent_project(path)
        self.setWindowTitle(f"creapy.io - {os.path.basename(path)}")
        self.statusBar().showMessage(f"Project saved: {path}", 4000)
        self.log.log('project_saved', path=os.path.basename(path))

    def open_project(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open Project", self.save_dir, "creapy project (*.creapy.json)")
            if not path:
                return
        try:
            state = project_io.load_project(path)
        except Exception as e:
            self.log.log_error('project_open', e)
            QMessageBox.critical(self, "Open Failed", f"The project file could not be read.\n\nTechnical detail: {e}")
            return
        project_dir = os.path.dirname(path)
        source = project_io.relocate(state.get('source_path'), project_dir)
        kind = state.get('source_kind', 'table')
        if kind == 'example':
            from creapy.examples import example_dataset
            source = example_dataset()
        if source is None:
            QMessageBox.warning(self, "Table Not Found",
                                f"The data table of this project is not where it was:\n{state.get('source_path')}\n\n"
                                "Please locate it.")
            source = self.pick_table_file("Locate the Project's Data Table")
            if source is None:
                return
        try:
            with self.wait_cursor():
                if kind == 'tobii':
                    if os.path.getsize(source) > CHUNKED_IMPORT_BYTES:
                        df, _ = load_prolab_data_export_chunked(source)
                    else:
                        df, _ = load_prolab_export(read_table(source))
                else:
                    df = read_table(source)
        except Exception as e:
            self.log.log_error('project_open', e)
            QMessageBox.critical(self, "Open Failed", f"The project's table could not be read.\n\nTechnical detail: {e}")
            return
        mapping = state['mapping']
        # stimulus values -> image paths: stored paths first, then the stored image folder, then ask
        stim_2_path = {}
        for entry in state.get('stimuli', []):
            img = project_io.relocate(entry['path'], project_dir)
            if img:
                stim_2_path[entry['value']] = img
        values = [str(v) for v in df[mapping['stim_col']].dropna().unique()]
        missing = [v for v in values if v not in stim_2_path]
        if missing:
            folder = state.get('image_folder')
            resolved = self.resolve_stimulus_paths(missing, folder=folder if folder and os.path.isdir(folder) else None)
            if resolved is None:
                return
            stim_2_path.update(resolved)
        # the table's stimulus column may hold non-string values: map through str
        by_str = {str(v): v for v in df[mapping['stim_col']].dropna().unique()}
        stim_2_path = {by_str[v]: p for v, p in stim_2_path.items() if v in by_str}
        ok = self.finish_import(df, is_fixation=state['is_fixation'], source_name=state.get('source_name'),
                                detected='project', mapping=mapping, source_path=source, source_kind=kind,
                                stim_2_path=stim_2_path, confirm_mapping=False)
        if not ok:
            return
        self.project_path = path
        self.add_recent_project(path)
        # groups and AOIs
        grouping = state.get('grouping') or None
        if grouping:
            by_str = {str(s): s for s in self.all_subjects}
            self.set_grouping({by_str[k]: v for k, v in grouping.items() if k in by_str} or None, record_undo=False)
        for entry in project_io.aois_from_records(state.get('aois', [])).items():
            stim_path, aois = entry
            resolved_path = project_io.relocate(stim_path, project_dir)
            if resolved_path in self.stim_dfs:
                self.aois[resolved_path] = aois
        if self.current_path in self.aois:
            self.aoi_toolbar.set_aois(self.aois[self.current_path].keys())
        if state.get('compare'):
            self.compare = state['compare']
            if self.compare.get('kind') == 'time':
                self.compare['items'] = [tuple(w) for w in self.compare['items']]
            self.update_compare_indicator()
        if state.get('view') in self.VIEWS:
            self.left_toolbar.setCurrentRow(self.VIEWS.index(state['view']))
        self.setWindowTitle(f"creapy.io - {os.path.basename(path)}")
        self.log.log('project_opened', path=os.path.basename(path))

    def recent_projects(self):
        return [p for p in self.settings.value("projects/recent", [], type=list) if os.path.exists(p)]

    def add_recent_project(self, path):
        recent = [path] + [p for p in self.recent_projects() if p != path]
        self.settings.setValue("projects/recent", recent[:8])
        self.refresh_recent_menu()

    def refresh_recent_menu(self):
        self.recent_menu.clear()
        recent = self.recent_projects()
        if not recent:
            self.recent_menu.addAction("(none yet)").setEnabled(False)
        for p in recent:
            self.recent_menu.addAction(self.make_action(os.path.basename(p), lambda _=False, p=p: self.open_project(p)))

    # =====================================================================================
    # Workspace
    # =====================================================================================

    def setup_workspace(self, stim_2_df, mapping, is_fixation, source_name=None):
        # One imported table serves all its stimuli: datasets are built lazily on the first click of each
        # thumbnail and cached, so the import stays fast and the expensive similarity caches (which live on the
        # dataset objects) survive stimulus switches. Filtered views (participants / time window) are cached too.
        self.jobs.cancel()
        self.stim_dfs = stim_2_df  # stimulus path -> table rows for that stimulus
        self.stim_values = {path: path for path in stim_2_df}
        self.mapping = mapping
        self.is_fixation = is_fixation
        self.source_name = source_name
        self.project_path = None
        self.base_cache = {}  # stimulus path -> (FixationData, SaccadeData) of everything
        self.filtered_cache = {}  # (stimulus path, filter key) -> (FixationData, SaccadeData)
        self.aois = {}  # stimulus path -> {name -> AOI}, shared by every dataset object of that stimulus
        self.dataset_fix = None
        self.dataset_sac = None
        self.current_path = None
        self.grouping = None  # subj -> group name, set via GroupingDialog
        self.compare = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_undo_actions()
        self.similarity_confirmed = set()  # (stimulus, sigma, tradeoff, view) the user accepted as a long computation
        self.all_subjects = creapy.natural_sorted(
            pd.concat([df[mapping['subj_index_col']] for df in stim_2_df.values()]).dropna().unique())
        self.init_main_layout()
        self.setWindowTitle(f"creapy.io - {source_name}" if source_name else "creapy.io")
        self.status_dataset.setText(
            f"{source_name or 'dataset'}: {len(stim_2_df)} stimuli, {len(self.all_subjects)} participants, "
            f"{sum(len(df) for df in stim_2_df.values()):,} {'fixations' if is_fixation else 'saccades'}")
        self.update_compare_indicator()
        self.set_workspace_actions_enabled(True)

    def init_main_layout(self):
        # self.setStyleSheet(style("main_light.qss"))
        self.setStyleSheet(style("main_dark.qss"))

        # Renders never run inside a click or slider handler: schedule_render defers them through this timer.
        # That collapses bursts (a slider drag fires once per tick) and lets the GUI repaint first.
        self.pending_run = lambda: None
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(lambda: self.pending_run())

        self.left_toolbar = QListWidget()
        for name in self.VIEWS:
            self.left_toolbar.addItem(name)
            self.left_toolbar.item(self.left_toolbar.count() - 1).setToolTip(
                widget_utils.rich_tooltip(glossary.VIEW_SUMMARY[name]))
        self.left_toolbar.setFixedWidth(160)
        self.left_toolbar.currentRowChanged.connect(self.change_analysis_view)

        self.fix_heatmap_toolbar = FixationHeatmapToolbar(self.debounced("Fixation Heatmap"))
        self.fix_scanpath_toolbar = FixationScanpathToolbar(self.debounced("Fixation Scanpath"))
        self.sac_scanpath_toolbar = SaccadeScanpathToolbar(self.debounced("Saccade Scanpath"))
        self.sac_heatmap_toolbar = SaccadeHeatmapToolbar(self.debounced("Saccade Heatmap"))
        self.rose_toolbar = RoseToolbar(self.debounced("Saccade Directions"))
        self.aoi_toolbar = AOIToolbar(self.debounced("Areas of Interest"))
        self.time_series_toolbar = TimeSeriesToolbar(self.debounced("Time Series"))
        self.similarity_toolbar = SimilarityToolbar(self.debounced("Saccade Similarity"))
        self.scanpath_compare_toolbar = ScanpathCompareToolbar(self.debounced("Scanpath Comparison"))
        self.recurrence_toolbar = RecurrenceToolbar(self.debounced("Recurrence"))
        self.stats_toolbar = StatisticsToolbar(self.debounced("Statistics"))

        # Same order as the left_toolbar rows / VIEWS
        self.view_toolbars = [self.fix_heatmap_toolbar, self.fix_scanpath_toolbar, self.sac_scanpath_toolbar,
                              self.sac_heatmap_toolbar, self.rose_toolbar, self.aoi_toolbar,
                              self.time_series_toolbar, self.similarity_toolbar, self.scanpath_compare_toolbar,
                              self.recurrence_toolbar, self.stats_toolbar]
        self.view_runs = [self.make_runner(name) for name in self.VIEWS]
        for toolbar in self.view_toolbars:
            toolbar.setObjectName("heatmapToolbar")
            toolbar.setFixedWidth(250)
            toolbar.save_btn.clicked.connect(self.save_image)
            if hasattr(toolbar, 'groups_btn'):
                toolbar.groups_btn.clicked.connect(self.assign_groups)
            if hasattr(toolbar, 'export_btn'):
                toolbar.export_btn.clicked.connect(self.export_table)
        self.aoi_toolbar.remove_btn.clicked.connect(self.remove_selected_aoi)
        self.aoi_toolbar.clear_btn.clicked.connect(self.clear_aois)
        self.aoi_toolbar.save_aoi_btn.clicked.connect(self.save_aois)
        self.aoi_toolbar.load_aoi_btn.clicked.connect(self.load_aois)
        self.aoi_toolbar.auto_btn.clicked.connect(self.add_hotspot_aoi)
        self.aoi_toolbar.mode_selector.currentIndexChanged.connect(lambda *_: self.cancel_drawing())

        self.right_toolbar_stack = QStackedWidget()
        for toolbar in self.view_toolbars:
            self.right_toolbar_stack.addWidget(toolbar)

        # Header over the parameter panel: the view's name and the ⓘ button that opens the explainer panel
        self.panel_title = QLabel(self.VIEWS[0])
        self.panel_title.setObjectName("PanelTitle")
        self.info_btn = QToolButton()
        self.info_btn.setObjectName("InfoButton")
        self.info_btn.setText("i")
        self.info_btn.setCheckable(True)
        self.info_btn.setCursor(Qt.PointingHandCursor)
        self.info_btn.setToolTip(widget_utils.rich_tooltip("What this view shows and how to read it. The panel "
                                                           "stays open and follows the view (Shift+F1)."))
        self.info_btn.toggled.connect(self.toggle_explainer)
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 10, 12, 0)
        header_layout.addWidget(self.panel_title)
        header_layout.addStretch()
        header_layout.addWidget(self.info_btn)
        self.right_panel = QWidget()
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(header)
        right_layout.addWidget(self.right_toolbar_stack)
        self.right_panel.setFixedWidth(250)

        # The explainer: one page per view (glossary.EXPLAINERS) in a dock the user can keep open, move or float
        self.explainer_browser = QTextBrowser()
        self.explainer_browser.setOpenExternalLinks(True)
        self.explainer_browser.setMinimumWidth(280)
        self.explainer_dock = QDockWidget("About this view", self)
        self.explainer_dock.setObjectName("ExplainerDock")
        self.explainer_dock.setWidget(self.explainer_browser)
        self.explainer_dock.setAllowedAreas(Qt.RightDockWidgetArea | Qt.LeftDockWidgetArea | Qt.BottomDockWidgetArea)
        self.explainer_dock.visibilityChanged.connect(self.on_explainer_visibility)
        self.addDockWidget(Qt.RightDockWidgetArea, self.explainer_dock)
        self.explainer_dock.hide()

        # Fade-in for the parameter panel on view switches
        self.toolbar_effect = QGraphicsOpacityEffect(self.right_toolbar_stack)
        self.toolbar_effect.setOpacity(1.0)
        self.right_toolbar_stack.setGraphicsEffect(self.toolbar_effect)
        self.toolbar_fade = QPropertyAnimation(self.toolbar_effect, b"opacity", self)
        self.toolbar_fade.setDuration(140)
        self.toolbar_fade.setStartValue(0.25)
        self.toolbar_fade.setEndValue(1.0)

        self.painter = PainterWidget()
        self.table_view = DataFrameView()

        self.main_area = QStackedWidget()
        self.main_area.addWidget(self.painter)
        self.main_area.addWidget(self.table_view)

        # Thumbnail strip above the canvas: click to switch between stimuli
        self.stimulus_strip = StimulusStrip(list(self.stim_dfs))
        self.stimulus_strip.stimulus_selected.connect(self.on_stimulus_selected)

        # Filter bar: participants + time window, applied to every view
        self.filter_bar = FilterBar()
        self.filter_bar.set_subjects(self.all_subjects, self.grouping)
        self.filter_bar.filter_changed.connect(self.on_filter_changed)
        widget_utils.apply_tooltips(self.filter_bar, glossary.FILTER_TIPS)

        self.canvas_area = QWidget()
        canvas_layout = QVBoxLayout(self.canvas_area)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(0)
        canvas_layout.addWidget(self.stimulus_strip)
        canvas_layout.addWidget(self.filter_bar)
        canvas_layout.addWidget(self.main_area)

        # Status pill over the canvas while a computation runs in the worker thread, with a Cancel button
        self.busy_frame = QFrame(self.canvas_area)
        self.busy_frame.setObjectName("BusyPill")
        self.busy_frame.setStyleSheet(
            "QFrame#BusyPill { background-color: #11141f; border: 1px solid #4da3ff; border-radius: 14px; }"
            "QFrame#BusyPill QLabel { color: #f2f3f7; background: transparent; border: none; }"
            "QFrame#BusyPill QPushButton { padding: 2px 10px; border-radius: 9px; }")
        busy_layout = QHBoxLayout(self.busy_frame)
        busy_layout.setContentsMargins(14, 5, 8, 5)
        busy_layout.setSpacing(10)
        self.busy_label = QLabel()
        self.busy_cancel = QPushButton("Cancel")
        self.busy_cancel.setObjectName("SmallButton")
        self.busy_cancel.clicked.connect(self.cancel_job)
        busy_layout.addWidget(self.busy_label)
        busy_layout.addWidget(self.busy_cancel)
        self.busy_frame.hide()
        self.busy_effect = QGraphicsOpacityEffect(self.busy_frame)
        self.busy_frame.setGraphicsEffect(self.busy_effect)
        self.busy_fade = QPropertyAnimation(self.busy_effect, b"opacity", self)
        self.busy_fade.setDuration(250)
        self.busy_fade.setStartValue(1.0)
        self.busy_fade.setEndValue(0.0)
        self.busy_fade.finished.connect(self.busy_frame.hide)
        # the pill appears only when a job takes longer than a blink, so slider ticks on fast views do not flash
        self.busy_timer = QTimer(self)
        self.busy_timer.setSingleShot(True)
        self.busy_timer.setInterval(180)
        self.busy_timer.timeout.connect(lambda: self.show_busy(self.busy_pending_text))
        self.busy_pending_text = ""

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.left_toolbar)
        splitter.addWidget(self.right_panel)
        splitter.addWidget(self.canvas_area)
        splitter.setSizes([160, 250, 900])

        self.setCentralWidget(splitter)

        # AOI drawing state (see run_aoi)
        self.drawing = None
        self.canvas_connections = []

        # Load the first stimulus (currentRow is still -1, so nothing renders yet), then trigger the default view
        self.stimulus_strip.select(next(iter(self.stim_dfs)))
        self.left_toolbar.setCurrentRow(0)

    # ---------- datasets ----------

    def build_base(self, path):
        dataset_fix, dataset_sac = creapy.build_pair(self.stim_dfs[path], path, self.mapping, self.is_fixation)
        dataset_fix.areas_of_interest = self.aois.setdefault(path, {})
        return dataset_fix, dataset_sac

    def base_datasets(self, path):
        # (FixationData, SaccadeData) of everything on a stimulus, built on first use (also from the worker thread;
        # a dict assignment is atomic and a double build is merely wasted work)
        if path not in self.base_cache:
            self.base_cache[path] = self.build_base(path)
        return self.base_cache[path]

    def datasets_for(self, path, subjects=None, t_range=None):
        # Filtered datasets of any stimulus, cached per (stimulus, selection)
        key = (tuple(subjects) if subjects is not None else None, t_range)
        base_fix, base_sac = self.base_datasets(path)
        if key == (None, None):
            return base_fix, base_sac
        if (path, key) not in self.filtered_cache:
            fix = base_fix.subset(subjects=subjects, t_range=t_range)
            sac = base_sac.subset(subjects=subjects, t_range=t_range)
            fix.areas_of_interest = self.aois.setdefault(path, {})
            self.filtered_cache[(path, key)] = (fix, sac)
        return self.filtered_cache[(path, key)]

    def current_datasets(self):
        subjects, t_range = self.filter_bar.filter_key()
        return self.datasets_for(self.current_path, subjects, t_range)

    def on_stimulus_selected(self, path):
        if path not in self.base_cache:
            try:
                with self.busy_now(f"Loading {os.path.basename(path)} ..."):
                    self.base_cache[path] = self.build_base(path)
            except Exception as e:
                self.log.log_error('load_stimulus', e)
                QMessageBox.critical(
                    self, "Stimulus Failed to Load",
                    "The data for this stimulus could not be loaded.\n\n"
                    "Please check that the column mapping matches your table (e.g., coordinate columns contain "
                    "numbers) and that the image file can be opened.\n\n"
                    f"Technical detail: {e}")
                if self.current_path is not None:  # revert the highlight to the working stimulus
                    self.stimulus_strip.mark(self.current_path)
                return
        self.current_path = path
        base_fix, _ = self.base_cache[path]
        self.filter_bar.set_time_max(base_fix.t_max)
        self.aoi_toolbar.set_aois(self.aois.setdefault(path, {}).keys())
        self.log.log('stimulus_selected', stimulus=os.path.basename(path))
        self.refresh_current_datasets()
        # The parameter toolbars deliberately keep their current settings across stimulus switches:
        # identical settings make stimuli comparable.
        self.schedule_current_view(delay=30)

    def refresh_current_datasets(self):
        try:
            self.dataset_fix, self.dataset_sac = self.current_datasets()
            return True
        except Exception as e:
            self.log.log_error('filter', e)
            QMessageBox.warning(
                self, "Nothing to Show",
                "The current participant / time-window selection leaves no data on this stimulus.\n\n"
                "The filter has been reset.\n\n"
                f"Technical detail: {e}")
            self.filter_bar.blockSignals(True)
            self.filter_bar.reset()
            self.filter_bar.blockSignals(False)
            self.dataset_fix, self.dataset_sac = self.base_cache[self.current_path]
            return False

    def on_filter_changed(self):
        if self.current_path is None:
            return
        self.log.log('filter', participants=self.filter_bar.selection_label(), t_range=self.filter_bar.t_range())
        if self.refresh_current_datasets():
            self.schedule_current_view(delay=200)

    def reset_filters(self):
        if hasattr(self, 'filter_bar'):
            self.filter_bar.reset()

    # ---------- plumbing ----------

    def schedule_render(self, fn, delay):
        self.pending_run = fn
        self.render_timer.start(delay)

    def schedule_current_view(self, delay):
        row = self.left_toolbar.currentRow()
        if row >= 0:
            self.schedule_render(self.view_runs[row], delay=delay)

    def debounced(self, view_name):
        # Toolbar callback wrapper: parameter changes only schedule the render, so a burst of them
        # (a slider drag) results in a single one.
        def request(*_):
            self.schedule_render(lambda: self.run_view(view_name), delay=200)
        return request

    def make_runner(self, view_name):
        return lambda: self.run_view(view_name)

    @contextmanager
    def wait_cursor(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            yield
        finally:
            QApplication.restoreOverrideCursor()

    def show_busy(self, message, cancellable=True):
        self.busy_fade.stop()
        self.busy_effect.setOpacity(1.0)
        self.busy_label.setText(message)
        self.busy_cancel.setVisible(cancellable)
        self.busy_frame.adjustSize()
        self.busy_frame.move(max((self.canvas_area.width() - self.busy_frame.width()) // 2, 8),
                             self.stimulus_strip.height() + self.filter_bar.height() + 16)
        self.busy_frame.show()
        self.busy_frame.raise_()
        self.busy_frame.repaint()  # synchronous paint: the pill must never be skipped

    def show_busy_soon(self, message):
        self.busy_pending_text = message
        self.busy_timer.start()

    def hide_busy(self):
        self.busy_timer.stop()
        if self.busy_frame.isVisible():
            self.busy_fade.start()

    @contextmanager
    def busy_now(self, message):
        # For the few things that still block the GUI thread (image loading, drawing): pill + wait cursor
        self.show_busy(message, cancellable=False)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        QApplication.processEvents(QEventLoop.ExcludeUserInputEvents)
        try:
            yield
        finally:
            QApplication.restoreOverrideCursor()
            self.hide_busy()

    def cancel_job(self):
        self.jobs.cancel()
        self.hide_busy()
        self.log.log('cancelled')
        self.statusBar().showMessage("Computation cancelled.", 3000)

    def report_view_error(self, view_name, exc):
        if isinstance(exc, Hint):
            self.log.log('hint', view=view_name, message=str(exc))
            QMessageBox.information(self, view_name, str(exc))
        elif isinstance(exc, InterruptedError):
            pass
        else:
            self.log.log_error(view_name, exc)
            if DEV_MODE:
                traceback.print_exception(exc)
            QMessageBox.critical(
                self, f"{view_name} Failed",
                f"The {view_name.lower()} could not be computed for this selection.\n\n"
                "Try the whole viewing time and all participants (Reset in the Show bar), or another stimulus. "
                "If the problem persists, please send the file and this message to the support address "
                "(Help > About).\n\n"
                f"Technical detail: {exc}")

    @contextmanager
    def guarded(self, view_name):
        # Every draw runs inside this: no traceback ever reaches the user, every failure is logged
        t0 = time.time()
        try:
            yield
            self.log.log('render', view=view_name, seconds=round(time.time() - t0, 3))
        except Exception as e:  # noqa: BLE001  (reported to the user in words)
            self.report_view_error(view_name, e)

    def change_analysis_view(self, index):
        self.render_timer.stop()  # a pending render would be for the previous view
        self.cancel_drawing()
        if index < 0:
            return
        self.right_toolbar_stack.setCurrentWidget(self.view_toolbars[index])
        self.panel_title.setText(self.VIEWS[index])
        if not self.explainer_dock.isHidden():  # isVisible() is false while the window itself is hidden
            self.update_explainer()
        self.log.log('view', view=self.VIEWS[index])
        # The render is deferred so the click can repaint and the panel fade in before the computation starts
        self.toolbar_fade.stop()
        self.toolbar_fade.start()
        self.schedule_render(self.view_runs[index], delay=160)

    def show_figure(self, fig, caption=None):
        self.main_area.setCurrentWidget(self.painter)
        self.painter.draw_figure(fig)
        self.painter.set_caption(caption)
        self.current_caption = caption
        plt.close(fig)
        self.current_table = None

    # ---------- explanations ----------

    def current_view_name(self):
        row = self.left_toolbar.currentRow()
        return self.VIEWS[row] if row >= 0 else self.VIEWS[0]

    def toggle_explainer(self, show):
        if show:
            self.update_explainer()
            self.explainer_dock.show()
            self.explainer_dock.raise_()
            self.info_btn.setChecked(True)
        else:
            self.explainer_dock.hide()

    def on_explainer_visibility(self, visible):
        # closing the dock via its title bar must release the button too
        self.info_btn.blockSignals(True)
        self.info_btn.setChecked(visible)
        self.info_btn.blockSignals(False)

    def update_explainer(self):
        view = self.current_view_name()
        html = glossary.EXPLAINERS[view] + ("<p style='color:#8a8f9c'><i>The complete text of all views: "
                                             "Help &gt; The Analyses Explained.</i></p>")
        self.explainer_browser.setHtml(html)
        self.log.log('explainer', view=view)

    @staticmethod
    @contextmanager
    def caption_on_figure(fig, caption, axes_kind):
        # Writes the caption under the figure for the duration of a savefig (bbox_inches='tight' includes it);
        # image views (heatmaps, scanpaths) get none: their canvas stays untouched
        text = None
        if caption and axes_kind != 'image':
            text = fig.text(0.01, -0.012, caption, ha='left', va='top', fontsize=7.5, color='#a0a4b3', wrap=True)
        try:
            yield
        finally:
            if text is not None:
                text.remove()

    def show_table(self, df, caption):
        self.table_view.set_dataframe(df, caption)
        self.main_area.setCurrentWidget(self.table_view)
        self.current_table = df

    def selection_note(self):
        # One line describing the active filter, for figure titles and table captions
        parts = []
        if self.filter_bar.participants() is not None:
            parts.append(self.filter_bar.selection_label())
        if self.filter_bar.t_range() is not None:
            t0, t1 = self.filter_bar.t_range()
            parts.append(f"{t0:.1f}–{t1:.1f} s")
        return " · ".join(parts)

    # =====================================================================================
    # Views, one generic runner: prepare in the worker thread, draw on the GUI thread
    # =====================================================================================

    def toolbar_for(self, view_name):
        return self.view_toolbars[self.VIEWS.index(view_name)]

    def make_ctx(self, view_name, params, fix):
        participants = self.filter_bar.participants()
        ctx = {'grouping': self.grouping_for(fix.subjects), 'note': self.selection_note(),
               'stim': os.path.basename(self.current_path), 'filtered_participants': participants is not None,
               'selected_subject': participants[0] if participants and len(participants) == 1 else None,
               'vmax': None}
        if view_name == 'Statistics':
            ctx['on_measures'] = self.stats_toolbar.set_measures
        if view_name == 'Time Series':
            ctx['on_default_aoi'] = lambda fix_: self.aoi_toolbar.set_aois(fix_.areas_of_interest.keys())
            t_range = self.filter_bar.t_range()
            path = self.current_path
            ctx['subset_fn'] = lambda subs: self.datasets_for(path, list(subs), t_range)
        return ctx

    def panels(self, view_name):
        # [(panel title or None, fix, sac)]: one panel normally, several in compare mode
        if not self.compare or view_name not in COMPARABLE_VIEWS:
            return [(None, self.dataset_fix, self.dataset_sac)]
        kind, items = self.compare['kind'], self.compare['items']
        subjects, t_range = self.filter_bar.filter_key()
        panels = []
        if kind == 'groups':
            base_fix, _ = self.base_datasets(self.current_path)
            for name in items:
                members = [s for s in base_fix.subjects if self.grouping and self.grouping.get(s) == name]
                if members:
                    panels.append((name, *self.datasets_for(self.current_path, members, t_range)))
        elif kind == 'stimuli':
            for path in items:
                if path in self.stim_dfs:
                    try:
                        panels.append((os.path.splitext(os.path.basename(path))[0],
                                       *self.datasets_for(path, subjects, t_range)))
                    except AssertionError:
                        pass  # the selection leaves nothing on this stimulus
        else:  # time windows
            for t0, t1 in items:
                try:
                    panels.append((f"{t0:.1f}–{t1:.1f} s", *self.datasets_for(self.current_path, subjects, (t0, t1))))
                except AssertionError:
                    pass
        if not panels:
            raise Hint("Nothing to compare for this selection: check the groups / stimuli / time windows "
                       "(Analysis > Compare Side by Side) or reset the filters.")
        return panels

    def run_view(self, view_name):
        if not (self.dataset_fix and self.dataset_sac):
            return
        toolbar = self.toolbar_for(view_name)
        params = toolbar.get_params()
        if view_name == 'Areas of Interest':
            self.cancel_drawing()
        if view_name == 'Saccade Similarity' and not self.confirm_large_similarity(params):
            return
        self.log.log('params', view=view_name, params=params, compare=self.compare)
        prepare, draw, kind = VIEW_SPECS[view_name]
        try:
            panels = self.panels(view_name)
        except Hint as e:
            self.report_view_error(view_name, e)
            return
        ctx = self.make_ctx(view_name, params, self.dataset_fix)
        shared_scale = view_name == 'Fixation Heatmap' and params.get('shared_scale')
        paths = list(self.stim_dfs)

        def work(progress):
            # worker thread: numeric caches only, no Qt, no matplotlib figures
            if shared_scale:
                progress(0, 0, "shared colour scale over all stimuli")
                vmax = 0.
                for path in paths:
                    if progress(0, 0, None) is False:
                        raise InterruptedError
                    vmax = max(vmax, self.base_datasets(path)[0].heatmap_max(params['bw_method']))
                ctx['vmax'] = vmax if vmax > 0 else None
            if prepare is not None:
                for _, fix, sac in panels:
                    prepare(fix, sac, params, ctx, progress)
            return True

        def done(_):
            self.hide_busy()
            with self.guarded(view_name):
                self.draw_panels(view_name, draw, kind, panels, params, ctx)

        def failed(exc):
            self.hide_busy()
            self.report_view_error(view_name, exc)

        busy_text = {'Saccade Heatmap': "Computing the saccade heatmap ...",
                     'Saccade Similarity': "Computing similarity scores ...",
                     'Scanpath Comparison': "Comparing scanpaths pairwise ...",
                     'Fixation Heatmap': "Rendering fixation heatmap ..."}.get(view_name, f"Rendering {view_name.lower()} ...")
        if prepare is None and not shared_scale:
            done(True)  # nothing slow to do: draw right away
            return
        if self.jobs.synchronous:
            self.show_busy(busy_text)
        else:
            self.show_busy_soon(busy_text)

        def on_progress(text):
            self.busy_pending_text = f"{busy_text[:-4]}: {text}"
            if self.busy_frame.isVisible():
                self.busy_label.setText(self.busy_pending_text)
                self.busy_frame.adjustSize()

        self.jobs.start(work, done, failed, on_progress=on_progress)

    def draw_panels(self, view_name, draw, kind, panels, params, ctx):
        axes_kind = views.axes_kind(view_name, params)
        multi = len(panels) > 1
        with plt.rc_context(DARK_RC if axes_kind != 'image' or multi else {}):
            fig = plt.figure(facecolor=DARK_BG)
            if not multi:
                if axes_kind == 'image':
                    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
                ax = views.new_axes(fig, axes_kind)
                result = draw(panels[0][1], panels[0][2], params, ctx, fig, ax)
            else:
                n = len(panels)
                n_cols = n if n <= 3 else (2 if n == 4 else 3 if n <= 9 else 4)
                n_rows = int(np.ceil(n / n_cols))
                result = None
                for i, (title, fix, sac) in enumerate(panels):
                    ax = views.new_axes(fig, axes_kind, (n_rows, n_cols, i + 1))
                    ctx_panel = dict(ctx, note=None, grouping=self.grouping_for(fix.subjects))
                    res = draw(fix, sac, params, ctx_panel, fig, ax)
                    if isinstance(res, tuple):
                        res = res[0]
                    if isinstance(res, pd.DataFrame):
                        res = res.assign(panel=title)
                        result = res if result is None else pd.concat([result, res], ignore_index=True)
                    ax.set_title(title, color='white', fontsize=10, loc='left')
                fig.suptitle(f"{view_name} · " + {'groups': "by group", 'stimuli': "by stimulus",
                                                   'time': "by time window"}[self.compare['kind']]
                             + (f" · {ctx['note']}" if ctx.get('note') and self.compare['kind'] != 'groups' else ""),
                             color='white', fontsize=11, x=0.01, ha='left')
                fig.subplots_adjust(left=0.02, right=0.98, bottom=0.03, top=0.9, wspace=0.08, hspace=0.18)
        if isinstance(result, tuple) and result[1] is not None:
            plt.close(fig)
            self.show_table(result[0], result[1])
            return
        self.show_figure(fig, glossary.figure_caption(view_name, params) if axes_kind != 'image' else None)
        self.current_axes_kind = axes_kind
        self.current_table = result[0] if isinstance(result, tuple) else result
        if view_name == 'Areas of Interest' and params['display'] == 'Image with AOIs' and not multi \
                and params['mode'] != 'View only':
            self.connect_drawing(fig.axes[0], params['mode'])

    def confirm_large_similarity(self, params):
        n = self.dataset_sac.n_subjects()
        key = (self.current_path, params['sigma'], params['density_coherence_tradeoff'], params['view'])
        if n > 60 and key not in self.similarity_confirmed:
            answer = QMessageBox.question(
                self, "Large Similarity Computation",
                f"{n} participants means {n * (n - 1) // 2:,} pairwise comparisons; this can take several "
                "minutes (the window stays usable and you can cancel).\n\nCompute anyway? (Tip: select a group "
                "or a smaller set in the Show bar.)", QMessageBox.Yes | QMessageBox.No)
            if answer != QMessageBox.Yes:
                return False
            self.similarity_confirmed.add(key)
        return True

    # Back-compatible names used by tests / notebooks
    def run_fixation_heatmap(self):
        self.run_view("Fixation Heatmap")

    def run_fixation_scanpath(self):
        self.run_view("Fixation Scanpath")

    def run_saccade_scanpath(self):
        self.run_view("Saccade Scanpath")

    def run_saccade_heatmap(self):
        self.run_view("Saccade Heatmap")

    def run_rose(self):
        self.run_view("Saccade Directions")

    def run_aoi(self):
        self.run_view("Areas of Interest")

    def run_time_series(self):
        self.run_view("Time Series")

    def run_similarity(self):
        self.run_view("Saccade Similarity")

    def run_scanpath_comparison(self):
        self.run_view("Scanpath Comparison")

    def run_recurrence(self):
        self.run_view("Recurrence")

    def run_statistics(self):
        self.run_view("Statistics")

    # ---------- compare mode ----------

    def choose_compare(self):
        if self.dataset_fix is None:
            return
        base_fix, _ = self.base_datasets(self.current_path)
        dialog = CompareDialog(list(self.stim_dfs), self.grouping, base_fix.t_max, parent=self, current=self.compare)
        if not dialog.exec():
            return
        spec = dialog.get_spec()
        if spec['kind'] == 'stimuli' and len(spec['items']) < 2:
            QMessageBox.information(self, "Compare", "Pick at least two stimuli to compare.")
            return
        self.compare = spec
        self.log.log('compare', **spec)
        self.update_compare_indicator()
        view = self.VIEWS[self.left_toolbar.currentRow()]
        if view not in COMPARABLE_VIEWS:
            self.left_toolbar.setCurrentRow(0)  # jump to the heatmap, the most common comparison
        else:
            self.schedule_current_view(delay=30)

    def stop_compare(self):
        if self.compare is None:
            return
        self.compare = None
        self.log.log('compare_off')
        self.update_compare_indicator()
        self.schedule_current_view(delay=30)

    def update_compare_indicator(self):
        if not self.compare:
            self.status_compare.setText("")
            return
        kind, items = self.compare['kind'], self.compare['items']
        what = {'groups': f"{len(items)} groups", 'stimuli': f"{len(items)} stimuli",
                'time': f"{len(items)} time windows"}[kind]
        self.status_compare.setText(f"◫ Comparing {what} (Analysis > Stop Comparing)")

    # ---------- batch export ----------

    def batch_export(self):
        # The current view with the current parameters and filter, once per stimulus, into a folder
        if self.dataset_fix is None:
            return
        view_name = self.VIEWS[self.left_toolbar.currentRow()]
        folder = QFileDialog.getExistingDirectory(self, "Folder for the Exported Figures / Tables", self.save_dir)
        if not folder:
            return
        toolbar = self.toolbar_for(view_name)
        params = toolbar.get_params()
        prepare, draw, kind = VIEW_SPECS[view_name]
        subjects, t_range = self.filter_bar.filter_key()
        paths = list(self.stim_dfs)
        progress = QProgressDialog(f"Exporting {view_name} for {len(paths)} stimuli …", "Cancel", 0, len(paths), self)
        progress.setWindowTitle("Export for All Stimuli")
        progress.setMinimumDuration(0)
        view_slug = view_name.lower().replace(' ', '_')
        written, skipped = [], []
        vmax = None
        if view_name == 'Fixation Heatmap' and params.get('shared_scale'):
            vmax = max(self.base_datasets(p)[0].heatmap_max(params['bw_method']) for p in paths) or None
        for i, path in enumerate(paths):
            progress.setValue(i)
            progress.setLabelText(f"{os.path.basename(path)} …")
            QApplication.processEvents()
            if progress.wasCanceled():
                break
            stim_name = os.path.splitext(os.path.basename(path))[0]
            try:
                fix, sac = self.datasets_for(path, subjects, t_range)
                ctx = {'grouping': self.grouping_for(fix.subjects), 'note': self.selection_note(), 'stim': stim_name,
                       'filtered_participants': subjects is not None,
                       'selected_subject': subjects[0] if subjects and len(subjects) == 1 else None, 'vmax': vmax}
                if prepare is not None:
                    prepare(fix, sac, params, ctx, lambda *a, **k: True)
                axes_kind = views.axes_kind(view_name, params)
                with plt.rc_context(DARK_RC if axes_kind != 'image' else {}):
                    fig = Figure(facecolor=DARK_BG, figsize=(10, 7.5))
                    if axes_kind == 'image':
                        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
                    ax = views.new_axes(fig, axes_kind)
                    result = draw(fix, sac, params, ctx, fig, ax)
                table, caption = (result if isinstance(result, tuple) else (result, None))
                if caption is None:
                    out = os.path.join(folder, f"{stim_name}_{view_slug}.png")
                    with self.caption_on_figure(fig, glossary.figure_caption(view_name, params), axes_kind):
                        fig.savefig(out, dpi=200, bbox_inches="tight", pad_inches=0, facecolor=fig.get_facecolor())
                    written.append(out)
                if isinstance(table, pd.DataFrame):
                    out = os.path.join(folder, f"{stim_name}_{view_slug}.csv")
                    table.to_csv(out, index=False)
                    written.append(out)
            except Exception as e:  # noqa: BLE001  (one stimulus failing must not stop the others)
                skipped.append(f"{stim_name}: {e}")
        progress.setValue(len(paths))
        self.save_dir = folder
        self.log.log('batch_export', view=view_name, n_files=len(written), n_skipped=len(skipped))
        text = f"{len(written)} file(s) written to\n{folder}"
        if skipped:
            text += "\n\nSkipped:\n" + "\n".join(f"  · {s}" for s in skipped[:8])
        QMessageBox.information(self, "Export Finished", text)

    # ---------- AOIs (drawing on the canvas, list management, JSON) ----------

    def connect_drawing(self, ax, mode):
        canvas = self.painter.canvas
        self.drawing = {'mode': mode, 'ax': ax, 'start': None, 'vertices': [], 'artists': []}
        self.canvas_connections = [
            canvas.mpl_connect('button_press_event', self.on_canvas_press),
            canvas.mpl_connect('motion_notify_event', self.on_canvas_motion),
            canvas.mpl_connect('button_release_event', self.on_canvas_release),
            canvas.mpl_connect('key_press_event', self.on_canvas_key),
        ]
        canvas.setFocusPolicy(Qt.StrongFocus)
        canvas.setFocus()
        canvas.setCursor(Qt.CrossCursor)

    def cancel_drawing(self):
        if self.drawing is None:
            return
        for artist in self.drawing['artists']:
            try:
                artist.remove()
            except (ValueError, NotImplementedError):
                pass
        canvas = self.painter.canvas
        for cid in self.canvas_connections:
            canvas.mpl_disconnect(cid)
        self.canvas_connections = []
        canvas.setCursor(Qt.ArrowCursor)
        self.drawing = None
        canvas.draw_idle()

    def on_canvas_press(self, event):
        d = self.drawing
        if d is None or event.inaxes is not d['ax'] or event.xdata is None:
            return
        ax = d['ax']
        if d['mode'] == 'Draw rectangle':
            if event.button != 1:
                return
            d['start'] = (event.xdata, event.ydata)
            rect = patches.Rectangle(d['start'], 0, 0, facecolor='#4da3ff', alpha=0.3, edgecolor='#4da3ff', lw=1.5)
            ax.add_patch(rect)
            d['artists'] = [rect]
        elif d['mode'] == 'Draw polygon':
            if event.button == 3 or event.dblclick:
                self.finish_polygon()
                return
            if event.button != 1:
                return
            d['vertices'].append((event.xdata, event.ydata))
            xs, ys = zip(*d['vertices'])
            for artist in d['artists']:
                artist.remove()
            line, = ax.plot(xs, ys, '-o', color='#4da3ff', ms=4, lw=1.5)
            d['artists'] = [line]
            if len(d['vertices']) >= 3:
                poly = patches.Polygon(d['vertices'], closed=True, facecolor='#4da3ff', alpha=0.2, edgecolor='none')
                ax.add_patch(poly)
                d['artists'].append(poly)
        self.painter.canvas.draw_idle()

    def on_canvas_motion(self, event):
        d = self.drawing
        if d is None or d['mode'] != 'Draw rectangle' or d['start'] is None or event.xdata is None:
            return
        x0, y0 = d['start']
        rect = d['artists'][0]
        rect.set_bounds(min(x0, event.xdata), min(y0, event.ydata), abs(event.xdata - x0), abs(event.ydata - y0))
        self.painter.canvas.draw_idle()

    def on_canvas_release(self, event):
        d = self.drawing
        if d is None or d['mode'] != 'Draw rectangle' or d['start'] is None:
            return
        x0, y0 = d['start']
        x1 = event.xdata if event.xdata is not None else x0
        y1 = event.ydata if event.ydata is not None else y0
        d['start'] = None
        for artist in d['artists']:
            artist.remove()
        d['artists'] = []
        self.painter.canvas.draw_idle()
        if abs(x1 - x0) < 5 or abs(y1 - y0) < 5:
            return  # a click, not a rectangle
        width, height = self.dataset_fix.width, self.dataset_fix.height
        x0, x1 = np.clip([x0, x1], 0, width)
        y0, y1 = np.clip([y0, y1], 0, height)
        name = self.ask_aoi_name()
        if name:
            self.add_aoi(AOI.rectangle(name, x0, y0, x1, y1))

    def finish_polygon(self):
        d = self.drawing
        vertices = list(d['vertices'])
        for artist in d['artists']:
            artist.remove()
        d['artists'] = []
        d['vertices'] = []
        self.painter.canvas.draw_idle()
        if len(vertices) < 3:
            QMessageBox.information(self, "Polygon", "A polygon needs at least three corners. Click the corners, "
                                                     "then double-click or right-click to close it.")
            return
        name = self.ask_aoi_name()
        if name:
            self.add_aoi(AOI.polygon(name, vertices))

    def on_canvas_key(self, event):
        if self.drawing is None:
            return
        if event.key == 'escape':
            mode = self.drawing['mode']
            self.cancel_drawing()
            self.connect_drawing(self.painter.current_fig.axes[0], mode)
        elif event.key == 'enter' and self.drawing['mode'] == 'Draw polygon':
            self.finish_polygon()

    def ask_aoi_name(self):
        aois = self.aois.setdefault(self.current_path, {})
        default = f"AOI {len(aois) + 1}"
        name, ok = QInputDialog.getText(self, "Name the Area", "Name of this area of interest:", text=default)
        name = name.strip()
        if not ok or not name:
            return None
        if name in aois:
            QMessageBox.warning(self, "Name Taken", f"An area called '{name}' exists already on this stimulus.")
            return None
        return name

    def set_aois_of(self, path, aois):
        # Replace the AOI set of a stimulus in place (the dict is shared by every dataset object of that stimulus)
        target = self.aois.setdefault(path, {})
        target.clear()
        target.update(aois)
        if path == self.current_path:
            self.aoi_toolbar.set_aois(target.keys())
            self.schedule_render(self.run_aoi, delay=30)

    def record_aoi_change(self, label, before, path=None):
        path = path or self.current_path
        after = dict(self.aois.get(path, {}))
        self.push_undo(label, lambda: self.set_aois_of(path, before), lambda: self.set_aois_of(path, after))

    def add_aoi(self, aoi):
        aois = self.aois.setdefault(self.current_path, {})
        before = dict(aois)
        aois[aoi.name] = aoi
        self.log.log('aoi_added', name=aoi.name, area_share=aoi.area() / (self.dataset_fix.width * self.dataset_fix.height))
        self.record_aoi_change(f"add area '{aoi.name}'", before)
        self.aoi_toolbar.set_aois(aois.keys())
        self.schedule_render(self.run_aoi, delay=30)

    def remove_selected_aoi(self):
        name = self.aoi_toolbar.selected_aoi()
        if name is None or self.current_path is None:
            return
        aois = self.aois.setdefault(self.current_path, {})
        before = dict(aois)
        aois.pop(name, None)
        self.log.log('aoi_removed', name=name)
        self.record_aoi_change(f"remove area '{name}'", before)
        self.aoi_toolbar.set_aois(aois.keys())
        self.schedule_render(self.run_aoi, delay=30)

    def clear_aois(self):
        if self.current_path is None or not self.aois.get(self.current_path):
            return
        if QMessageBox.question(self, "Clear AOIs", "Remove all areas of interest of this stimulus? (Undo is available.)",
                                QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        before = dict(self.aois[self.current_path])
        self.aois[self.current_path].clear()
        self.log.log('aoi_cleared')
        self.record_aoi_change("clear areas", before)
        self.aoi_toolbar.set_aois([])
        self.schedule_render(self.run_aoi, delay=30)

    def add_hotspot_aoi(self):
        if not self.dataset_fix:
            return
        with self.guarded("Areas of Interest"):
            before = dict(self.aois.setdefault(self.current_path, {}))
            params = self.fix_heatmap_toolbar.get_params()
            name = self.dataset_fix.set_bottom_up_aoi(bw_method=params['bw_method'], num_levels=params['num_levels'],
                                                      from_level=max(params['from_level'], params['num_levels'] // 2))
            self.log.log('aoi_added', name=name, hotspot=True)
            self.record_aoi_change("add hot-spot area", before)
            self.aoi_toolbar.set_aois(self.aois[self.current_path].keys())
            self.schedule_render(self.run_aoi, delay=30)

    def save_aois(self):
        aois = self.aois.get(self.current_path, {})
        if not aois:
            QMessageBox.information(self, "No AOIs", "There are no areas of interest on this stimulus yet.")
            return
        stim_name = os.path.splitext(os.path.basename(self.current_path))[0]
        path, _ = QFileDialog.getSaveFileName(self, "Save AOIs", os.path.join(self.save_dir, f"{stim_name}_aois.json"),
                                              "AOI files (*.json)")
        if not path:
            return
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'stimulus': os.path.basename(self.current_path),
                       'width': self.dataset_fix.width, 'height': self.dataset_fix.height,
                       'aois': [aoi.to_record() for aoi in aois.values()]}, f, indent=2)
        self.save_dir = os.path.dirname(path)
        self.log.log('aoi_saved', n=len(aois))

    def load_aois(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load AOIs", self.save_dir, "AOI files (*.json)")
        if not path:
            return
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            aois = self.aois.setdefault(self.current_path, {})
            before = dict(aois)
            for record in data['aois']:
                aoi = AOI.from_record(record)
                aois[aoi.name] = aoi
            if (data.get('width'), data.get('height')) != (self.dataset_fix.width, self.dataset_fix.height):
                QMessageBox.warning(self, "Different Image Size",
                                    "These AOIs were drawn on an image of a different size; they may not line up.")
        except Exception as e:
            self.log.log_error('aoi_load', e)
            QMessageBox.critical(self, "Load Failed", f"The AOI file could not be read.\n\nTechnical detail: {e}")
            return
        self.record_aoi_change("load areas", before)
        self.log.log('aoi_loaded', n=len(data['aois']))
        self.aoi_toolbar.set_aois(self.aois[self.current_path].keys())
        self.schedule_render(self.run_aoi, delay=30)

    # ---------- groups ----------

    def grouping_for(self, subjects):
        # The stored grouping restricted to the participants present in the current dataset
        if not self.grouping:
            return None
        present = set(subjects)
        grouping = {s: g for s, g in self.grouping.items() if s in present}
        return grouping or None

    def set_grouping(self, grouping, record_undo=True):
        before = dict(self.grouping) if self.grouping else None
        self.grouping = grouping or None
        text = self.grouping_summary_text(self.grouping)
        for toolbar in (self.similarity_toolbar, self.scanpath_compare_toolbar):
            toolbar.set_grouping_summary(text if toolbar is self.scanpath_compare_toolbar else self.grouping)
        self.stats_toolbar.grouping_label.setText(text)
        self.filter_bar.set_subjects(self.all_subjects, self.grouping)
        if self.compare and self.compare['kind'] == 'groups':
            self.compare = {'kind': 'groups', 'items': creapy.natural_sorted(set(self.grouping.values()))} \
                if self.grouping else None
            self.update_compare_indicator()
        if record_undo:
            after = dict(self.grouping) if self.grouping else None
            self.push_undo("group assignment", lambda: self.set_grouping(before, record_undo=False),
                           lambda: self.set_grouping(after, record_undo=False))
        self.schedule_current_view(delay=30)

    @staticmethod
    def grouping_summary_text(grouping):
        if not grouping:
            return "No groups assigned."
        from collections import Counter
        counts = Counter(grouping.values())
        return "  ·  ".join(f"{name} ({n})" for name, n in sorted(counts.items()))

    def assign_groups(self):
        if not self.dataset_sac:
            return
        base_fix, base_sac = self.base_cache[self.current_path]
        # For the prefill shortcut, use the imported table (it keeps the user's extra columns, e.g. a
        # condition/group column): the auto-derived dataset only has synthetic columns.
        if len(base_fix.df.columns) >= len(base_sac.df.columns):
            df, subj_index = base_fix.df, base_fix.subj_index
        else:
            df, subj_index = base_sac.df, base_sac.subj_index
        dialog = GroupingDialog(self.all_subjects, df, subj_index, grouping=self.grouping, parent=self)
        if dialog.exec():
            self.set_grouping(dialog.get_grouping() or None)
            self.log.log('groups_assigned', grouping=self.grouping)

    # ---------- export ----------

    def save_image(self):
        fig = self.painter.current_fig
        if fig is None or self.main_area.currentWidget() is not self.painter:
            QMessageBox.information(self, "No Figure", "The current view is a table: use Export Table instead.")
            return
        stim_name = os.path.splitext(os.path.basename(self.current_path))[0]
        view_name = self.left_toolbar.currentItem().text().lower().replace(' ', '_')
        suggestion = os.path.join(self.save_dir, f"{stim_name}_{view_name}.png")
        file_path, chosen = QFileDialog.getSaveFileName(
            self, "Save Figure", suggestion, "PNG image (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ('.png', '.pdf', '.svg'):
                file_path += '.pdf' if 'PDF' in chosen else ('.svg' if 'SVG' in chosen else '.png')
            with self.caption_on_figure(fig, self.current_caption, self.current_axes_kind):
                fig.savefig(file_path, dpi=200, bbox_inches="tight", pad_inches=0, facecolor=fig.get_facecolor())
            self.save_dir = os.path.dirname(file_path)
            self.log.log('export_image', view=view_name, path=os.path.basename(file_path))

    def export_table(self):
        df = self.current_table
        if df is None:
            QMessageBox.information(self, "No Table",
                                    "This view has no table to export. Tables exist in Statistics, Areas of "
                                    "Interest, Recurrence, the similarity matrices and the periodogram.")
            return
        stim_name = os.path.splitext(os.path.basename(self.current_path))[0]
        view_name = self.left_toolbar.currentItem().text().lower().replace(' ', '_')
        suggestion = os.path.join(self.save_dir, f"{stim_name}_{view_name}.csv")
        file_path, chosen = QFileDialog.getSaveFileName(
            self, "Export Table", suggestion, "CSV (*.csv);;Excel (*.xlsx)")
        if not file_path:
            return
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ('.csv', '.xlsx'):
            file_path += '.xlsx' if 'Excel' in chosen else '.csv'
        if file_path.lower().endswith('.xlsx'):
            df.to_excel(file_path, index=False)
        else:
            df.to_csv(file_path, index=False)
        self.save_dir = os.path.dirname(file_path)
        self.log.log('export_table', view=view_name, path=os.path.basename(file_path), n_rows=len(df))


def main():
    if '--selftest' in sys.argv:
        return selftest()
    app = QApplication(sys.argv)
    # numbers in tables with a decimal point, matching the CSV exports and the Python side, whatever the OS locale
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    app.setApplicationName("creapy.io")
    app.setOrganizationName("CReA")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


def selftest():
    # `creapy-io --selftest`: open the example dataset offscreen and render every view once. Used to check a
    # packaged build (PyInstaller .app / .exe) on a machine without a developer: prints OK or the failure.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QApplication(sys.argv)
    app.setApplicationName("creapy.io")
    failures = []
    QMessageBox.critical = lambda *a, **k: failures.append(str(a[2])[:300])  # type: ignore
    QMessageBox.information = lambda *a, **k: None  # type: ignore
    QMessageBox.question = lambda *a, **k: QMessageBox.No  # type: ignore
    try:
        window = MainWindow(synchronous=True)
        window.open_example()
        for i, name in enumerate(window.VIEWS):
            t0 = time.time()
            window.left_toolbar.setCurrentRow(i)
            window.view_runs[i]()
            print(f"  {name:20s} {time.time() - t0:5.2f} s")
    except Exception as e:  # noqa: BLE001  (the self-test reports anything)
        failures.append(f"{type(e).__name__}: {e}")
    if failures:
        print("SELFTEST FAILED:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"SELFTEST OK: creapy {creapy.__version__}, Python {sys.version.split()[0]}")
    sys.exit(0)


if __name__ == "__main__":
    main()
