import json
import os
import re
import shutil
import sys
import time
import traceback
import zipfile
from contextlib import contextmanager
from datetime import datetime
import numpy as np
import pandas as pd
from PySide6.QtWidgets import (
    QLabel, QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QFileDialog, QPushButton, QFrame,
    QSplitter, QListWidget, QStackedWidget, QMessageBox, QGraphicsOpacityEffect, QInputDialog, QProgressDialog,
    QToolButton, QDockWidget, QTextBrowser, QScrollArea, QGridLayout
)
from PySide6.QtGui import QPixmap, QAction, QDesktopServices, QActionGroup, QKeySequence
from PySide6 import QtCore
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
from creapy.io.widgets.toolbars.visits import VisitsToolbar
from creapy.formats import load_prolab_intervals, attach_intervals, aoi_names_by_stimulus, AOI_HIT_COLUMN, AOI_TAG_COLUMN
from creapy.gaze.fixation import make_label_aois, labels_in_column
from PySide6.QtWidgets import QInputDialog
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
from creapy.io.widgets.project_tile import ProjectTile
from creapy.io.widgets.compare_dialog import CompareDialog
from creapy.io.session_log import SessionLog
from creapy.io.worker import JobRunner
from creapy.io import help as help_texts
from creapy.io import views
from creapy.io import glossary
import creapy.io.widgets.utils as widget_utils
from creapy.io.views import Hint, DARK_BG, DARK_RC, VIEW_SPECS, COMPARABLE_VIEWS
from creapy.io import project as project_io
from creapy.io.theme import apply_theme
from creapy.io.aoi_metrics_window import AOIMetricsWindow

from creapy.formats import read_table, detect_format, guess_mapping, load_prolab_export, load_prolab_aoi_metrics_export
from creapy.formats import FIXATION_FIELDS, SACCADE_FIELDS
from creapy.formats.tobii import load_prolab_data_export_chunked
from creapy.misc.utils import find_images, grouping_from_stimulus_names, grouping_from_participant_names
from creapy.aoi.aoi import AOI

HERE = os.path.dirname(os.path.abspath(__file__))
STYLE_DIR = os.path.join(HERE, 'style')

DEV_MODE = bool(os.environ.get("CREAPY_DEV_TABLE"))
SYNCHRONOUS = False
CHUNKED_IMPORT_BYTES = 1_500_000_000


class MainWindow(QMainWindow):
    VIEWS = ["Fixation Heatmap", "Fixation Scanpath", "Saccade Scanpath", "Saccade Heatmap",
             "Saccade Directions", "Areas of Interest", "Time Series", "Saccade Similarity", "Scanpath Comparison",
             "Recurrence", "Statistics", "Visits"]
    ADVANCED_VIEWS = ["Scanpath Comparison", "Recurrence"]
    MOBILE_VIEWS = ["Fixation Heatmap", "Fixation Scanpath", "Saccade Scanpath", "Saccade Directions",
                    "Areas of Interest", "Statistics", "Visits"]
    MOBILE_ONLY_VIEWS = ["Visits"]
    DATASET_VIEWS = ["Visits"]   # computed over every stimulus at once, not per stimulus
    SETTINGS = {'lab': "Lab / screen (fixed presentation)", 'mobile': "Mobile, mapped onto snapshots"}

    def __init__(self, synchronous=None):
        super().__init__()
        self.setWindowTitle("creapy.io")
        self.setGeometry(100, 100, 1320, 860)
        apply_theme()
        self.log = SessionLog()
        self.settings = QSettings("CReA", "creapy.io")
        self.jobs = JobRunner(self, synchronous=SYNCHRONOUS if synchronous is None else synchronous)
        self.dataset_fix = None
        self.dataset_sac = None
        self.source_name = None
        self.source_path = None
        self.project_path = None
        self.save_dir = None  # export folder chosen for the current dataset; see start_dir()
        self.setting = 'lab'  # 'lab' or 'mobile', see SETTINGS / MOBILE_VIEWS
        self.min_fix_dur_ms = 0   # fixations shorter than this are dropped before anything is computed
        self.intervals_path = None   # AOI-based export that gave the recording clock (t_abs), see attach_intervals_file
        self.df_events = None
        self.aoi_sizes = {}
        self.aoi_names = {}   # stimulus -> {area: tag} from the AOI-based export, areas nobody fixated included
        self.attributes = None   # per-participant table (Analysis > Import Participant Table), indexed by participant
        self.attributes_path = None
        self.attributes_id_col = None
        self.current_table = None
        self.current_caption = None
        self.current_axes_kind = 'image'
        self.current_path = None
        self.drawing = None
        self.canvas_connections = []
        self.compare = None
        self.undo_stack = []
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
        self.log.watch(QApplication.instance(), self)
        self.log.log_environment(advanced_views=self.advanced_views_shown(), synchronous=bool(self.jobs.synchronous))


    def init_menu(self):
        menubar = self.menuBar()
        menubar.setNativeMenuBar(False)

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

        view_menu = menubar.addMenu("&View")
        self.zoom_in_action = self.make_action("Zoom In", lambda: self.zoom_canvas('in'))
        self.zoom_in_action.setShortcuts([QKeySequence.ZoomIn, QKeySequence("Ctrl+=")])
        self.zoom_out_action = self.make_action("Zoom Out", lambda: self.zoom_canvas('out'))
        self.zoom_out_action.setShortcuts([QKeySequence.ZoomOut])
        self.zoom_reset_action = self.make_action("Show Whole Figure", lambda: self.zoom_canvas('reset'), "Ctrl+0")
        for action in (self.zoom_in_action, self.zoom_out_action, self.zoom_reset_action):
            view_menu.addAction(action)

        analysis_menu = menubar.addMenu("&Analysis")
        self.groups_action = self.make_action("Assign Participants to Groups…", self.assign_groups, "Ctrl+G")
        analysis_menu.addAction(self.groups_action)
        self.compare_action = self.make_action("Compare Side by Side…", self.choose_compare, "Ctrl+D")
        self.stop_compare_action = self.make_action("Stop Comparing", self.stop_compare)
        analysis_menu.addAction(self.compare_action)
        analysis_menu.addAction(self.stop_compare_action)
        analysis_menu.addAction(self.make_action("Reset Filters", self.reset_filters))
        analysis_menu.addSeparator()
        self.clock_action = self.make_action("Add Recording Clock (Tobii AOI-based Export)…", self.attach_intervals_file)
        analysis_menu.addAction(self.clock_action)
        self.attributes_action = self.make_action("Import Participant Table…", self.import_attributes)
        analysis_menu.addAction(self.attributes_action)
        self.min_dur_action = self.make_action("Minimum Fixation Duration…", self.set_min_fixation_duration)
        analysis_menu.addAction(self.min_dur_action)
        self.zero_rows_action = QAction("Keep Non-Viewers as Zero Rows", self, checkable=True)
        self.zero_rows_action.setChecked(True)
        self.zero_rows_action.setToolTip("Tables list every participant of the dataset; those without a fixation on "
                                         "the stimulus get zeros (looked = False) instead of vanishing.")
        self.zero_rows_action.toggled.connect(lambda *_: self.schedule_current_view(delay=30))
        analysis_menu.addAction(self.zero_rows_action)
        analysis_menu.addSeparator()
        self.advanced_action = QAction("Show Advanced Analyses", self, checkable=True)
        self.advanced_action.setChecked(self.advanced_views_shown())
        self.advanced_action.toggled.connect(self.toggle_advanced_views)
        analysis_menu.addAction(self.advanced_action)
        setting_menu = analysis_menu.addMenu("Recording Setting")
        self.setting_actions = {}
        setting_group = QActionGroup(self)
        for key, text in self.SETTINGS.items():
            action = QAction(text, self, checkable=True)
            action.setChecked(key == self.setting)
            action.triggered.connect(lambda _=False, key=key: self.set_setting(key))
            setting_group.addAction(action)
            setting_menu.addAction(action)
            self.setting_actions[key] = action

        logging_menu = menubar.addMenu("&Logging")
        self.logging_action = QAction("Keep a Session Log (on this computer only)", self, checkable=True)
        self.logging_action.setChecked(self.log.enabled)
        self.logging_action.toggled.connect(self.toggle_logging)
        logging_menu.addAction(self.logging_action)
        logging_menu.addAction(self.make_action("Save Logs for a Bug Report…", self.export_logs))
        logging_menu.addAction(self.make_action("Open Log Folder", self.open_log_folder))
        logging_menu.addAction(self.make_action("What Is Logged?", lambda: self.show_help("About creapy.io",
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
        self.status_compare.setStyleSheet("color: #ffc766; padding: 0 8px;")
        self.status_logging = QLabel()
        self.status_logging.setObjectName("LoggingIndicator")
        self.status_setting = QLabel()
        self.status_setting.setStyleSheet("color: #8fd3a8; padding: 0 8px;")
        self.status_setting.setToolTip("Change under Analysis > Recording Setting")
        self.statusBar().addWidget(self.status_dataset, stretch=1)
        self.statusBar().addPermanentWidget(self.status_setting)
        self.statusBar().addPermanentWidget(self.status_compare)
        self.statusBar().addPermanentWidget(self.status_logging)
        self.update_logging_indicator()
        self.set_workspace_actions_enabled(False)

    def make_action(self, text, slot, shortcut=None):
        action = QAction(text, self)
        action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(shortcut)
        self.log.hook_action(action)
        return action

    def set_workspace_actions_enabled(self, enabled):
        for action in (self.save_image_action, self.export_table_action, self.groups_action, self.batch_action,
                       self.save_project_action, self.compare_action, self.stop_compare_action, self.clock_action,
                       self.attributes_action, self.min_dur_action, self.zero_rows_action, self.zoom_in_action,
                       self.zoom_out_action, self.zoom_reset_action):
            action.setEnabled(enabled)

    def zoom_canvas(self, how):
        if self.main_area.currentWidget() is not self.painter:
            return
        {'in': self.painter.zoom_in, 'out': self.painter.zoom_out, 'reset': self.painter.reset_zoom}[how]()

    def on_zoomed(self, level, how):
        self.zoom_hows.add(how)
        self.zoom_log_timer.start()

    def log_zoom(self):
        zoom = self.painter.zoom
        view = [[round(v, 3) for v in limits] for limits in zoom.view()]
        self.log.log('zoom', level=round(zoom.level(), 2), how=sorted(self.zoom_hows), visible=view)
        self.zoom_hows = set()

    def show_help(self, title, html):
        help_texts.HelpDialog(title, html, parent=self).exec()

    def advanced_views_shown(self):
        return self.settings.value("views/advanced", False, type=bool)

    def toggle_advanced_views(self, shown):
        self.settings.setValue("views/advanced", bool(shown))
        self.log.log('advanced_views', shown=bool(shown))
        self.apply_advanced_views()

    def apply_advanced_views(self):
        if not hasattr(self, 'left_toolbar'):
            return
        shown = self.advanced_views_shown()
        for name in self.ADVANCED_VIEWS:
            self.left_toolbar.item(self.VIEWS.index(name)).setHidden(not shown)
        self.time_series_toolbar.set_advanced(shown)
        for name in self.VIEWS:
            item = self.left_toolbar.item(self.VIEWS.index(name))
            available = self.view_available(name)
            item.setFlags(item.flags() | Qt.ItemIsEnabled if available else item.flags() & ~Qt.ItemIsEnabled)
            summary = glossary.VIEW_SUMMARY[name]
            if not available and name in self.MOBILE_ONLY_VIEWS:
                summary = f"<b>Not available in the lab setting.</b> {glossary.LAB_UNAVAILABLE[name]}<br><br>" \
                          f"<i>Mobile recordings: {summary}</i>"
            elif not available:
                summary = f"<b>Not available for mobile eye tracking on snapshots.</b> " \
                          f"{glossary.MOBILE_UNAVAILABLE[name]}<br><br>" \
                          f"<i>Lab recordings: {summary}</i>"
            item.setToolTip(widget_utils.rich_tooltip(summary))
        current = self.left_toolbar.currentRow()
        if current >= 0 and (not self.view_available(self.VIEWS[current])
                             or (not shown and self.VIEWS[current] in self.ADVANCED_VIEWS)):
            self.left_toolbar.setCurrentRow(0)

    def view_available(self, name):
        if name in self.MOBILE_ONLY_VIEWS:
            return self.setting == 'mobile'
        return self.setting != 'mobile' or name in self.MOBILE_VIEWS

    def set_setting(self, setting, render=True):
        assert setting in self.SETTINGS
        self.setting = setting
        for key, action in self.setting_actions.items():
            action.setChecked(key == setting)
        self.status_setting.setText(self.SETTINGS[setting] if getattr(self, 'stim_dfs', None) else "")
        if not hasattr(self, 'left_toolbar'):
            return
        self.filter_bar.set_visit_mode(setting == 'mobile')
        self.update_export_aoi_controls()
        if setting == 'mobile' and self.compare and self.compare.get('kind') == 'time':
            self.compare = None   # time windows are not offered for mobile eye tracking
            self.update_compare_indicator()
        self.apply_advanced_views()
        if render:
            self.jobs.cancel()
            self.base_cache = {}
            self.filtered_cache = {}
            self.log.log('setting', setting=setting)
            if self.current_path is not None:
                self.on_stimulus_selected(self.current_path)

    @staticmethod
    def infer_setting(df, source_kind):
        if source_kind != 'tobii':
            return 'lab'
        mapped = 'snapshot_mapped' in df.columns and bool(df['snapshot_mapped'].any())
        return 'mobile' if mapped or 'toi' in df.columns else 'lab'

    def toggle_logging(self, enabled):
        self.log.set_enabled(enabled)
        self.update_logging_indicator()
        if enabled:
            QMessageBox.information(
                self, "Session Log On",
                "creapy records what you do in the app (views, parameters, clicks, dialogs, errors) into a text "
                f"file on this computer:\n\n{self.log.path}\n\nNothing is sent anywhere. Logging > Save Logs for a "
                "Bug Report packs the files so you can attach them to a report; you can switch the log off here "
                "and delete the files whenever you like.")

    def update_logging_indicator(self):
        if self.log.enabled:
            self.status_logging.setText("● Log on")
            self.status_logging.setStyleSheet("color: #7fd18c; padding: 0 8px;")
            self.status_logging.setToolTip("creapy keeps a log of what you do in the app on this computer only "
                                           "(Logging menu). Attach it to a bug report; nothing is sent anywhere.")
        else:
            self.status_logging.setText("○ Log off")
            self.status_logging.setStyleSheet("color: #6c7180; padding: 0 8px;")
            self.status_logging.setToolTip("No session log is written (Logging menu).")

    def open_log_folder(self):
        os.makedirs(self.log.folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.log.folder))

    def export_logs(self):
        suggested = os.path.join(QStandardPaths.writableLocation(QStandardPaths.DesktopLocation),
                                 f"creapy_logs_{datetime.now().strftime('%Y-%m-%d')}.zip")
        path, _ = QFileDialog.getSaveFileName(self, "Save Logs for a Bug Report", suggested, "Zip archive (*.zip)")
        if not path:
            return
        try:
            n = self.log.export_zip(path)
        except OSError as e:
            QMessageBox.critical(self, "Logs Not Saved", f"The archive could not be written.\n\nTechnical detail: {e}")
            return
        QMessageBox.information(self, "Logs Saved",
                                f"{n} session log(s) packed into\n{path}\n\nAttach this file to your bug report "
                                "together with a screenshot and two sentences on what you did. The log holds no gaze "
                                "data, only what you did in the app.")

    def closeEvent(self, event):
        self.jobs.cancel()
        self.log.close()
        super().closeEvent(event)


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


    START_COLUMN_WIDTH = 920
    TILE_COLUMNS = 3

    def init_start_ui(self):
        self.start_stack = QStackedWidget()
        self.setCentralWidget(self.start_stack)
        self.start_stack.addWidget(self.make_front_page())
        self.start_stack.addWidget(self.make_bundle_page())
        self.start_stack.addWidget(self.make_import_page())
        self.start_stack.setCurrentIndex(0)

    def start_page(self, width=START_COLUMN_WIDTH):
        page = QWidget()
        outer = QHBoxLayout(page)
        outer.setContentsMargins(40, 0, 40, 0)
        outer.setSpacing(0)
        column = QWidget()
        column.setMaximumWidth(width)
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 44, 0, 24)
        layout.setSpacing(18)
        outer.addStretch(1)
        outer.addWidget(column, 100)   # the column grows to its maximum width first, then the margins share the rest
        outer.addStretch(1)
        return page, layout

    def start_header(self, layout, subtitle):
        title_label = QLabel("creapy.io")
        title_label.setObjectName("TitleLabel")
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("SubtitleLabel")
        subtitle_label.setWordWrap(True)
        header = QVBoxLayout()
        header.setSpacing(6)
        header.addWidget(title_label)
        header.addWidget(subtitle_label)
        layout.addLayout(header)
        layout.addSpacing(6)

    def start_footer(self, layout, back=False, links=()):
        footer = QHBoxLayout()
        footer.setSpacing(18)
        if back:
            back_btn = QPushButton("Back")
            back_btn.setObjectName("LinkButton")
            back_btn.setCursor(Qt.PointingHandCursor)
            back_btn.clicked.connect(lambda: self.start_stack.setCurrentIndex(0))
            footer.addWidget(back_btn)
        for btn in links:
            footer.addWidget(btn)
        guide_btn = QPushButton("Quick guide")
        guide_btn.setObjectName("LinkButton")
        guide_btn.setCursor(Qt.PointingHandCursor)
        guide_btn.clicked.connect(lambda: self.show_help("Quick Guide", help_texts.QUICK_GUIDE))
        footer.addWidget(guide_btn)
        footer.addStretch()
        credits_label = QLabel(f"creapy {creapy.__version__}  ·  Xingyu Long, CReA  ·  xingyu.long@univie.ac.at")
        credits_label.setObjectName("CreditsLabel")
        footer.addWidget(credits_label)
        layout.addLayout(footer)

    def start_card(self, layout, title, meta=""):
        card = QFrame()
        card.setObjectName("StartCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 18)
        card_layout.setSpacing(12)
        head = QHBoxLayout()
        head.setSpacing(10)
        title_label = QLabel(title)
        title_label.setObjectName("CardTitle")
        head.addWidget(title_label)
        meta_label = QLabel(meta)
        meta_label.setObjectName("CardMeta")
        head.addWidget(meta_label)
        head.addStretch()
        card_layout.addLayout(head)
        layout.addWidget(card)
        return card, card_layout, title_label, meta_label

    def link_button(self, text, tooltip, slot):
        btn = QPushButton(text)
        btn.setObjectName("LinkButton")
        btn.setCursor(Qt.PointingHandCursor)
        btn.setToolTip(widget_utils.rich_tooltip(tooltip))
        btn.clicked.connect(slot)
        return btn

    def make_front_page(self):
        page, layout = self.start_page()
        self.start_header(layout, "Eye-tracking data visualisation for art history. Open a bundle or a project, "
                                  "explore and export.")

        actions = QHBoxLayout()
        actions.setSpacing(12)
        self.bundle_btn = QPushButton("Open a bundle…")
        self.bundle_btn.setObjectName("PrimaryButton")
        self.bundle_btn.setCursor(Qt.PointingHandCursor)
        self.bundle_btn.setToolTip(widget_utils.rich_tooltip(
            "A bundle is one file (.creapy) with ready-made projects (one per room or experiment): the data, the images "
            "and the areas are already in place. A bundle with several projects "
            "lets you pick one."))
        self.bundle_btn.clicked.connect(self.open_bundle)
        actions.addWidget(self.bundle_btn)
        self.project_btn = QPushButton("Open a project…")
        self.project_btn.setObjectName("SecondaryAction")
        self.project_btn.setCursor(Qt.PointingHandCursor)
        self.project_btn.setToolTip(widget_utils.rich_tooltip(
            "One saved creapy project (.creapy.json): table, images, groups and areas of interest."))
        self.project_btn.clicked.connect(self.open_project)
        actions.addWidget(self.project_btn)
        actions.addStretch()
        layout.addLayout(actions)

        self.recent_buttons = []
        self.last_bundle_buttons = []
        bundle_projects = []
        last_bundle = self.settings.value("bundles/last", "", type=str)
        if last_bundle and os.path.isdir(last_bundle):
            bundle_projects = project_io.find_projects(last_bundle)
        if bundle_projects:
            name = os.path.basename(last_bundle.rstrip(os.sep))
            card, body, title, _ = self.start_card(layout, name, f"last bundle  ·  {self.count_projects(bundle_projects)}")
            title.setToolTip(last_bundle)
            self.last_bundle_buttons = self.add_project_buttons(body, bundle_projects, last_bundle)
        recent = [p for p in self.recent_projects() if p not in bundle_projects][:6]
        if recent:
            card, body, _, _ = self.start_card(layout, "Recent projects")
            self.recent_buttons = self.add_project_buttons(body, recent)
        layout.addStretch()

        self.import_page_btn = self.link_button(
            "Import your own data…",
            "EyeLink reports, Tobii Pro Lab exports or any fixation / saccade table, with the images in a folder.",
            lambda: self.start_stack.setCurrentIndex(2))
        example_btn = self.link_button(
            "Example dataset", "A small synthetic dataset (two images, twelve viewers in two groups) to try every view",
            self.open_example)
        self.start_footer(layout, links=(self.import_page_btn, example_btn))
        return page

    @staticmethod
    def count_projects(projects):
        return f"{len(projects)} project" + ("" if len(projects) == 1 else "s")

    def add_project_buttons(self, layout, paths, root=None):
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(10)
        home = os.path.expanduser("~")
        buttons = []
        for i, p in enumerate(paths):
            title = project_io.project_title(p)
            folder = os.path.dirname(p)
            if root and folder.startswith(root):
                shown = folder[len(root):].strip(os.sep) or "."
            else:
                shown = "~" + folder[len(home):] if folder.startswith(home) else folder
            tile = ProjectTile(title, "" if shown == title else shown, tooltip=p)   # a room folder named like its project
            tile.clicked.connect(lambda p=p: self.open_project(p))
            grid.addWidget(tile, i // self.TILE_COLUMNS, i % self.TILE_COLUMNS)
            buttons.append(tile)
        for col in range(self.TILE_COLUMNS):
            grid.setColumnStretch(col, 1)
        layout.addLayout(grid)
        return buttons

    def make_bundle_page(self):
        page, layout = self.start_page()
        self.start_header(layout, "Choose the room or experiment to open.")
        card, self.bundle_list_layout, self.bundle_title, self.bundle_meta = self.start_card(layout, "")
        self.bundle_buttons = []
        layout.addStretch()
        self.start_footer(layout, back=True)
        return page

    def make_import_page(self):
        page, layout = self.start_page(width=1100)
        self.start_header(layout, "Import your own data: one table, plus the folder with the images it refers to.")
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

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
            images (subfolders are searched). The AOI-based export of the same project adds the recording clock.</p>
            <p><i>AOI-based metrics exports alone (no positions) open as a table with charts per AOI.</i></p>
            """,
            "Import Tobii Pro Lab Export…")
        self.import_btn_tobii.clicked.connect(self.import_tobii)

        cards_layout.addWidget(fix_card)
        cards_layout.addWidget(sac_card)
        cards_layout.addWidget(tobii_card)
        layout.addLayout(cards_layout)
        layout.addStretch()
        self.start_footer(layout, back=True)
        return page

    BUNDLE_SUFFIX = '.creapy'

    def bundle_cache_dir(self):
        return os.path.join(QStandardPaths.writableLocation(QStandardPaths.AppLocalDataLocation), "bundles")

    def unpack_bundle(self, path):
        """Unpack a bundle file once into the app's data folder; an unchanged file is reused on the next open."""
        stamp = f"{os.path.getsize(path)} {int(os.path.getmtime(path))}"
        folder = os.path.join(self.bundle_cache_dir(), os.path.splitext(os.path.basename(path))[0])
        marker = os.path.join(folder, ".bundle_source")
        if os.path.isfile(marker):
            with open(marker) as f:
                if f.read().strip() == stamp:
                    return folder
        if os.path.isdir(folder):
            shutil.rmtree(folder)
        progress = QProgressDialog(f"Unpacking {os.path.basename(path)} …", "Cancel", 0, 1, self)
        progress.setWindowTitle("Open a Bundle")
        progress.setMinimumDuration(500)
        try:
            with zipfile.ZipFile(path) as zf:
                members = [m for m in zf.infolist() if not m.filename.startswith('__MACOSX/')]
                progress.setMaximum(len(members))
                os.makedirs(folder)
                for i, member in enumerate(members):
                    progress.setValue(i)
                    QApplication.processEvents()
                    if progress.wasCanceled():
                        shutil.rmtree(folder, ignore_errors=True)
                        return None
                    zf.extract(member, folder)
                progress.setValue(len(members))
            with open(marker, 'w') as f:
                f.write(stamp)
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        finally:
            progress.close()
        return folder

    def open_bundle(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open a Bundle", self.start_dir('bundle'),
                                                  f"creapy bundle (*{self.BUNDLE_SUFFIX})")
            if not path:
                return False
        if os.path.isfile(path):
            self.remember_dir('bundle', os.path.dirname(path))
            try:
                folder = self.unpack_bundle(path)
            except Exception as e:   # noqa: BLE001  a damaged download must never leave a stuck dialog
                self.log.log_error('bundle_open', e)
                QMessageBox.critical(self, "Open Failed",
                                     f"The bundle file could not be unpacked. Download it again.\n\n"
                                     f"Technical detail: {e}")
                return False
            if not folder:
                return False
        else:
            folder = path
            self.remember_dir('bundle', folder)
        projects = project_io.find_projects(folder)
        if not projects:
            QMessageBox.information(self, "No Projects in This Bundle",
                                    "This bundle holds no creapy project (*.creapy.json), not even in a subfolder.\n\n"
                                    "A bundle is one file with one project per room or experiment.")
            return False
        self.settings.setValue("bundles/last", folder)
        self.log.log('bundle_opened', folder=os.path.basename(folder), n_projects=len(projects))
        if len(projects) == 1:
            self.open_project(projects[0])
            return True
        self.bundle_title.setText(os.path.basename(folder.rstrip(os.sep)))
        self.bundle_title.setToolTip(folder)
        self.bundle_meta.setText(self.count_projects(projects))
        while self.bundle_list_layout.count() > 1:   # keep the card head, drop the previous grid
            item = self.bundle_list_layout.takeAt(1)
            if item.widget() is not None:
                item.widget().deleteLater()
            elif item.layout() is not None:
                widget_utils.clear_layout(item.layout())
        self.bundle_buttons = self.add_project_buttons(self.bundle_list_layout, projects, folder)
        self.start_stack.setCurrentIndex(1)
        return True

    def make_card(self, title, logo_path, html, button_text):
        card = QFrame()
        card.setObjectName("DataCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(10)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)
        title_label = QLabel(title)
        title_label.setObjectName("SectionTitle")
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.load_logo(logo_path, thumb_size=40))
        desc = QLabel(html)
        desc.setObjectName("BodyLabel")
        desc.setWordWrap(True)
        desc.setTextFormat(Qt.RichText)
        button = QPushButton(button_text)
        button.setCursor(Qt.PointingHandCursor)
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


    def pick_table_file(self, title):
        path, _ = QFileDialog.getOpenFileName(
            self, title, self.start_dir('data'),
            "Data tables (*.csv *.tsv *.txt *.xlsx *.xls);;CSV / TSV (*.csv *.tsv *.txt);;Excel (*.xlsx *.xls)")
        if path:
            self.remember_dir('data', os.path.dirname(path))
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
        setting = self.infer_setting(df_fix, 'tobii')
        ok = self.finish_import(df_fix, is_fixation=True, source_name=os.path.basename(path),
                                detected=detected, mapping=mapping, source_path=path, source_kind='tobii',
                                setting=setting)
        if ok and setting == 'mobile':
            self.explain_mobile()
        if ok and detected == 'tobii_event_export':
            self.offer_recording_clock()

    def offer_recording_clock(self):
        answer = QMessageBox.question(
            self, "Recording Clock",
            "The event-based export restarts its times with every visit of a snapshot, so the order of visits "
            "across snapshots, returns and the time between walls are unknown.\n\nThe AOI-based metrics export of "
            "the same Pro Lab project states when every visit started. Do you have it at hand and want to add it "
            "now? (Later: Analysis > Add Recording Clock.)", QMessageBox.Yes | QMessageBox.No)
        if answer == QMessageBox.Yes:
            self.attach_intervals_file()

    def attach_intervals_file(self, path=None, quiet=False):
        if self.dataset_fix is None:
            return False
        if self.mapping.get('subj_index_col') != 'participant' or self.mapping.get('stim_col') != 'stimulus' \
                or self.mapping.get('trial_col') != 'trial':
            QMessageBox.information(self, "Recording Clock",
                                    "The recording clock can only be added to a Tobii Pro Lab event-based export "
                                    "(its intervals are the visits the AOI-based export times).")
            return False
        if path is None:
            path = self.pick_table_file("Open the AOI-based Metrics Export of the Same Project")
            if path is None:
                return False
        try:
            with self.wait_cursor():
                df_aoi = read_table(path)
                df_iv, aoi_sizes, df_events = load_prolab_intervals(df_aoi)
                aoi_names = aoi_names_by_stimulus(df_aoi)
                stim_dfs = {p: attach_intervals(df, df_iv) for p, df in self.stim_dfs.items()}
        except Exception as e:
            self.log.log_error('intervals_import', e)
            QMessageBox.critical(self, "Recording Clock Failed",
                                 "The file could not be read as a Tobii Pro Lab AOI-based metrics export with "
                                 f"interval times.\n\nTechnical detail: {e}")
            return False
        n_rows = sum(len(df) for df in stim_dfs.values())
        n_clock = sum(int(df['t_abs'].notna().sum()) for df in stim_dfs.values())
        if n_clock == 0:
            QMessageBox.warning(self, "Recording Clock",
                                "No interval of this export matches the participants, snapshots and intervals of the "
                                "loaded data. Is it the AOI-based export of the same Pro Lab project and room?")
            return False
        self.stim_dfs = stim_dfs
        self.intervals_path = path
        self.df_events = df_events if len(df_events) else None
        self.aoi_sizes = aoi_sizes
        self.aoi_names = aoi_names
        self.jobs.cancel()
        self.base_cache = {}
        self.filtered_cache = {}
        self.log.log('intervals_attached', source=os.path.basename(path), n_rows=n_rows, n_clock=n_clock,
                     n_events=int(len(df_events)))
        self.refresh_clock_controls()
        if not quiet:
            QMessageBox.information(
                self, "Recording Clock Added",
                f"{n_clock:,} of {n_rows:,} fixations now sit on the recording clock"
                + (f"; {df_events['event'].nunique()} kinds of logged events found" if len(df_events) else "")
                + ".\n\nThe view 'Visits' shows the visits in order; the AOI tables know the areas' sizes.")
        if self.current_path is not None:
            self.on_stimulus_selected(self.current_path)
        return True

    def import_attributes(self, path=None, id_col=None, quiet=False):
        if self.dataset_fix is None:
            return False
        if path is None:
            path = self.pick_table_file("Open a Table with One Row per Participant")
            if path is None:
                return False
        df = self.read_table_or_complain(path)
        if df is None:
            return False
        subjects = {str(s) for s in self.all_subjects}
        if id_col is None or id_col not in df.columns:
            overlap = {col: df[col].astype(str).str.strip().isin(subjects).sum() for col in df.columns}
            id_col = max(overlap, key=overlap.get)
        matched = int(df[id_col].astype(str).str.strip().isin(subjects).sum())
        if matched == 0:
            QMessageBox.warning(self, "Participant Table",
                                "No column of this table contains the participant names of the dataset "
                                f"(for example {', '.join(sorted(subjects)[:3])}).")
            return False
        df_attr = df.drop_duplicates(subset=[id_col]).copy()
        df_attr['participant'] = df_attr[id_col].astype(str).str.strip()
        by_str = {str(s): s for s in self.all_subjects}
        df_attr = df_attr[df_attr['participant'].isin(by_str)]
        df_attr['participant'] = df_attr['participant'].map(by_str)
        self.attributes = df_attr.drop(columns=[id_col]).set_index('participant')
        self.attributes_path, self.attributes_id_col = path, str(id_col)
        self.log.log('attributes_imported', source=os.path.basename(path), id_col=str(id_col), n_matched=matched,
                     n_columns=int(len(self.attributes.columns)))
        if not quiet:
            QMessageBox.information(
                self, "Participant Table Imported",
                f"{matched} of {len(self.all_subjects)} participants matched through the column '{id_col}'; "
                f"{len(self.attributes.columns)} columns are now appended to every exported table and offered in "
                "Analysis > Assign Participants to Groups (prefill).")
        return True

    def with_attributes(self, df):
        if df is None or self.attributes is None or 'participant' not in df.columns:
            return df
        extra = self.attributes.loc[:, [c for c in self.attributes.columns if c not in df.columns]].copy()
        extra.index = extra.index.astype(str)
        df_ = df.assign(_key=df['participant'].astype(str))
        return df_.merge(extra, left_on='_key', right_index=True, how='left').drop(columns=['_key'])

    def set_min_fixation_duration(self):
        if self.dataset_fix is None:
            return
        ms, ok = QInputDialog.getInt(self, "Minimum Fixation Duration",
                                     "Drop fixations shorter than (ms; 0 keeps all):", self.min_fix_dur_ms, 0, 2000, 10)
        if ok:
            self.apply_min_fixation_duration(ms)

    def apply_min_fixation_duration(self, ms, render=True):
        self.min_fix_dur_ms = int(ms)
        self.jobs.cancel()
        self.base_cache = {}
        self.filtered_cache = {}
        self.log.log('min_fixation_duration', ms=self.min_fix_dur_ms)
        self.update_status_dataset()
        if render and self.current_path is not None:
            self.on_stimulus_selected(self.current_path)

    def filter_min_dur(self, df):
        if not self.min_fix_dur_ms or not self.is_fixation:
            return df
        dur = pd.to_numeric(df[self.mapping['fix_dur_col']], errors='coerce')
        threshold = self.min_fix_dur_ms if float(dur.median()) > 5 else self.min_fix_dur_ms / 1000.
        return df[dur >= threshold]

    def full_table(self):
        return pd.concat([self.filter_min_dur(df) for df in self.stim_dfs.values()], ignore_index=True)

    def zero_rows_enabled(self):
        return bool(self.zero_rows_action.isChecked())

    def update_status_dataset(self):
        if not getattr(self, 'stim_dfs', None):
            return
        n_rows = sum(len(df) for df in self.stim_dfs.values())
        text = (f"{self.source_name or 'dataset'}: {len(self.stim_dfs)} stimuli, {len(self.all_subjects)} participants, "
                f"{n_rows:,} {'fixations' if self.is_fixation else 'saccades'}")
        if self.min_fix_dur_ms:
            text += f" · fixations under {self.min_fix_dur_ms} ms dropped"
        self.status_dataset.setText(text)

    def stimulus_names_per_participant(self):
        subj_col = self.mapping['subj_index_col']
        subj_to_names = {}
        for p, df_ in self.stim_dfs.items():
            name = str(self.stim_values.get(p, p))
            for subj, n in df_[subj_col].value_counts().items():
                subj_to_names.setdefault(subj, []).extend([name] * int(n))
        return subj_to_names

    def roster_for(self, path):
        """Who owes a zero row on this stimulus: everyone, or only the participants of its condition when every viewer
        of the stimulus belongs to one group (assigned, or read off the snapshot / participant names)."""
        grouping = getattr(self, 'derived_grouping', None) or self.grouping
        if not grouping:
            return list(self.all_subjects)
        viewers = set(self.stim_dfs[path][self.mapping['subj_index_col']].dropna().unique())
        counts = pd.Series([grouping.get(s) for s in viewers]).value_counts(dropna=False)
        if len(counts) and counts.index[0] is not None and counts.iloc[0] >= 0.9 * len(viewers):
            group = counts.index[0]   # a stray fixation mapped onto the other condition's wall does not change the roster
            return [s for s in self.all_subjects if grouping.get(s) == group or s in viewers]
        return list(self.all_subjects)

    def active_aoi_names(self, path):
        inactive = self.aoi_inactive.get(path, set())
        return [name for name in self.aois.get(path, {}) if name not in inactive]

    def any_aois(self):
        return any(self.active_aoi_names(path) for path in self.stim_dfs)

    def refresh_aoi_controls(self):
        if self.current_path is None:
            return
        names = list(self.aois.setdefault(self.current_path, {}).keys())
        self.aoi_toolbar.set_aois(names, active=self.active_aoi_names(self.current_path))
        self.stats_toolbar.set_areas_available(bool(self.active_aoi_names(self.current_path)) or self.any_aois())
        self.visits_toolbar.set_areas_available(self.any_aois(), "No area is ticked on any stimulus: draw areas in the "
                                                                 "view Areas of Interest or add the areas of the export "
                                                                 "there (tick 'On every stimulus').")

    def on_aoi_ticked(self, *_):
        if self.current_path is None:
            return
        names = set(self.aois.get(self.current_path, {}))
        active = set(self.aoi_toolbar.active_aois())
        self.aoi_inactive[self.current_path] = names - active
        self.aoi_toolbar.refresh_reference()
        self.aoi_toolbar.update_display_availability()
        self.log.log('aoi_ticked', active=sorted(active), inactive=sorted(names - active))
        self.refresh_aoi_controls()
        if self.current_view_name() in ('Areas of Interest', 'Statistics', 'Visits'):
            self.schedule_current_view(delay=150)

    def stimulus_name(self, path):
        return os.path.splitext(os.path.basename(path))[0]

    def match_stimulus(self, path):
        """The loaded stimulus a stored path refers to: the same file, else the one with the same name."""
        if path in self.stim_dfs:
            return path
        same_file = {os.path.normcase(os.path.abspath(p)): p for p in self.stim_dfs}
        if os.path.normcase(os.path.abspath(str(path))) in same_file:
            return same_file[os.path.normcase(os.path.abspath(str(path)))]
        same_name = {os.path.basename(str(p).replace('\\', '/')).lower(): p for p in self.stim_dfs}
        return same_name.get(os.path.basename(str(path).replace('\\', '/')).lower())

    def all_datasets(self, progress=None):
        datasets = {}
        paths = list(self.stim_dfs)
        for i, path in enumerate(paths):
            if progress is not None and progress(i, len(paths), f"loading {os.path.basename(path)}") is False:
                raise InterruptedError
            try:
                datasets[self.stimulus_name(path)] = self.base_datasets(path)
            except (AssertionError, Hint):
                continue   # no fixation of this stimulus survives the minimum duration
        return datasets

    def clock_available(self):
        return any('t_abs' in df.columns and df['t_abs'].notna().any() for df in self.stim_dfs.values())

    def refresh_clock_controls(self):
        if hasattr(self, 'visits_toolbar'):
            self.visits_toolbar.set_clock_available(
                self.clock_available(), "Needs the recording clock: the event-based export restarts its times with "
                                        "every visit, so the order of visits across snapshots is unknown. Analysis > "
                                        "Add Recording Clock loads the AOI-based metrics export of the same Pro Lab "
                                        "project, which states when every visit started.")

    def label_column_available(self):
        return any(AOI_HIT_COLUMN in df.columns and df[AOI_HIT_COLUMN].notna().any() for df in self.stim_dfs.values())

    def update_export_aoi_controls(self):
        if not hasattr(self, 'aoi_toolbar'):
            return
        available = self.label_column_available()
        reason = None if available else ("The imported table has no column with areas assigned by the eye-tracking "
                                         "software (a Tobii Pro Lab event-based export carries one).")
        tags = any(AOI_TAG_COLUMN in df.columns and df[AOI_TAG_COLUMN].notna().any() for df in self.stim_dfs.values())
        self.aoi_toolbar.set_export_aois_available(available, reason, tags=tags,
                                                   tags_reason="The export carries no area types (tags) for its areas.")
        self.refresh_clock_controls()

    def add_export_aois(self):
        if self.dataset_fix is None or not self.label_column_available():
            return
        params = self.aoi_toolbar.get_params()
        column = AOI_TAG_COLUMN if params['level'] == 'Area types' else AOI_HIT_COLUMN
        paths = list(self.stim_dfs) if params['all_stimuli'] else [self.current_path]
        before = dict(self.aois.setdefault(self.current_path, {}))
        n_added = 0
        for path in paths:
            df = self.stim_dfs[path]
            if column not in df.columns:
                continue
            stimulus = str(df[self.mapping['stim_col']].iloc[0]) if len(df) else ''
            labels = set(labels_in_column(df[column]))
            listed = self.aoi_names.get(stimulus, {})
            labels |= set(listed) if column == AOI_HIT_COLUMN else {t for t in listed.values() if t}
            aois = make_label_aois(creapy.natural_sorted(labels), column, sizes=self.aoi_sizes.get(stimulus))
            self.aois.setdefault(path, {}).update(aois)
            n_added += len(aois)
        self.log.log('aoi_from_export', level=params['level'], all_stimuli=params['all_stimuli'], n=n_added)
        self.record_aoi_change("add areas from the export", before)
        self.refresh_aoi_controls()
        if n_added == 0:
            QMessageBox.information(self, "No Areas", "The export names no areas for the fixations of this stimulus.")
        self.schedule_render(self.run_aoi, delay=30)

    def explain_mobile(self):
        self.settings.setValue("hints/mobile_seen", True)
        QMessageBox.information(
            self, "Mobile Eye Tracking",
            "Opened as mobile eye tracking mapped onto snapshots. Visitors decide how long they look, come "
            "back to a wall and look away in between, so:\n\n"
            "· scanpaths and saccades break between visits and wherever the eyes were off the snapshot or not "
            f"tracked for more than {creapy.MOBILE_MAX_GAP:g} s (no line across a look at another wall);\n"
            "· the time filter means the time within each visit;\n"
            "· views that assume a fixed viewing time or a fixed distance to the image are greyed out "
            "(hover over them for the reason);\n"
            "· Statistics counts the visits and the viewing time over all visits.\n\n"
            "Analysis > Recording Setting switches back to the lab setting.")

    def open_aoi_metrics(self, path=None, df=None):
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
        window = AOIMetricsWindow(df_aoi, info, os.path.basename(path), parent=self, log=self.log,
                                  save_dir=self.start_dir('export'))
        window.setWindowModality(Qt.NonModal)
        window.show()
        self.aoi_metrics_windows = getattr(self, 'aoi_metrics_windows', []) + [window]

    def finish_import(self, df, is_fixation, source_name, detected=None, mapping=None, source_path=None,
                      source_kind='table', stim_2_path=None, confirm_mapping=True, setting='lab'):
        if confirm_mapping:
            dialog = ColumnMappingDialog(df, is_fixation=is_fixation, mapping=mapping, parent=self, detected=detected)
            if not dialog.exec():
                return False
            mapping = dict(mapping or {}, **dialog.get_mapping())
        try:
            stim_col = mapping['stim_col']
            df = df[df[stim_col].notna()]
            groups = dict(list(df.groupby(stim_col)))
            if stim_2_path is None:
                stim_2_path = self.resolve_stimulus_paths(
                    list(groups), near=os.path.dirname(source_path) if source_path else None)
            if stim_2_path is None:
                return False
            stim_2_df = {stim_2_path[stim]: df_stim for stim, df_stim in groups.items() if stim in stim_2_path}
            with self.wait_cursor():
                self.setup_workspace(stim_2_df, mapping, is_fixation, source_name=source_name, setting=setting)
            self.source_path = source_path
            self.source_kind = source_kind
            self.stim_values = {path: stim for stim, path in stim_2_path.items() if stim in groups}
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
                "but every view works, and Analysis > Assign Participants to Groups can prefill the groups from the 'group' column.")
        except Exception as e:
            self.log.log_error('example', e)
            QMessageBox.critical(self, "Example Failed", f"The example dataset could not be opened.\n\nTechnical detail: {e}")

    def resolve_stimulus_paths(self, stim_values, folder=None, near=None):
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
                folder = QFileDialog.getExistingDirectory(self, "Select the Folder Containing Your Stimulus Images",
                                                          self.start_dir('images', near=near))
                if folder:
                    self.remember_dir('images', folder)
            if not folder:
                return None
            self.image_folder = folder
            with self.wait_cursor():
                folder_files = find_images(folder)
            for stim in missing:
                file_name = os.path.basename(str(stim).replace('\\', '/')).lower()
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
            'setting': self.setting,
            'min_fix_dur_ms': self.min_fix_dur_ms,
            'intervals_path': self.intervals_path,
            'attributes': {'path': self.attributes_path, 'id_col': self.attributes_id_col} if self.attributes_path else None,
            'zero_rows': self.zero_rows_enabled(),
            'aoi_inactive': {path: sorted(names) for path, names in self.aoi_inactive.items() if names},
            'aoi_reference': self.aoi_toolbar.get_params()['reference'],
        }

    def save_project(self):
        if self.dataset_fix is None:
            return
        default = self.project_path
        if not default or default.startswith(self.bundle_cache_dir()):
            name = os.path.basename(default) if default else \
                os.path.splitext(self.source_name or 'creapy')[0] + project_io.PROJECT_SUFFIX
            default = os.path.join(self.start_dir('project'), name)   # never inside the cache, which a new download empties
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
        self.add_recent_project(path)
        self.setWindowTitle(f"creapy.io - {os.path.basename(path)}")
        self.statusBar().showMessage(f"Project saved: {path}", 4000)
        self.log.log('project_saved', path=os.path.basename(path))

    def open_project(self, path=None):
        if not path:
            path, _ = QFileDialog.getOpenFileName(self, "Open Project", self.start_dir('project'),
                                                  "creapy project (*.creapy.json)")
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
        stim_2_path = {}
        for entry in state.get('stimuli', []):
            img = project_io.relocate(entry['path'], project_dir)
            if img:
                stim_2_path[entry['value']] = img
        values = [str(v) for v in df[mapping['stim_col']].dropna().unique()]
        missing = [v for v in values if v not in stim_2_path]
        if missing:
            folder = state.get('image_folder')
            resolved = self.resolve_stimulus_paths(missing, folder=folder if folder and os.path.isdir(folder) else None,
                                                   near=os.path.dirname(source))
            if resolved is None:
                return
            stim_2_path.update(resolved)
        by_str = {str(v): v for v in df[mapping['stim_col']].dropna().unique()}
        stim_2_path = {by_str[v]: p for v, p in stim_2_path.items() if v in by_str}
        setting = state.get('setting') if state.get('setting') in self.SETTINGS else self.infer_setting(df, kind)
        ok = self.finish_import(df, is_fixation=state['is_fixation'], source_name=state.get('source_name'),
                                detected='project', mapping=mapping, source_path=source, source_kind=kind,
                                stim_2_path=stim_2_path, confirm_mapping=False, setting=setting)
        if not ok:
            return
        self.render_timer.stop()
        self.project_path = path
        self.add_recent_project(path)
        grouping = state.get('grouping') or None
        if grouping:
            by_str = {str(s): s for s in self.all_subjects}
            self.set_grouping({by_str[k]: v for k, v in grouping.items() if k in by_str} or None, record_undo=False)
        for entry in project_io.aois_from_records(state.get('aois', [])).items():
            stim_path, aois = entry
            resolved_path = project_io.relocate(stim_path, project_dir)
            if resolved_path in self.stim_dfs:
                self.aois[resolved_path] = aois
        self.aoi_inactive = {project_io.relocate(k, project_dir) or k: set(v) for k, v in (state.get('aoi_inactive') or {}).items()}
        self.refresh_aoi_controls()
        if state.get('aoi_reference'):
            self.aoi_toolbar.reference_selector.setCurrentText(state['aoi_reference'])
        self.zero_rows_action.setChecked(bool(state.get('zero_rows', True)))
        if state.get('min_fix_dur_ms'):
            self.apply_min_fixation_duration(state['min_fix_dur_ms'], render=False)
        intervals = project_io.relocate(state.get('intervals_path'), project_dir)
        if intervals:
            self.attach_intervals_file(intervals, quiet=True)
        elif state.get('intervals_path'):
            QMessageBox.warning(self, "Recording Clock", "The AOI-based export that gave this project its recording "
                                f"clock is not where it was:\n{state['intervals_path']}\n\nAdd it again under "
                                "Analysis > Add Recording Clock.")
        attributes = state.get('attributes') or {}
        attr_path = project_io.relocate(attributes.get('path'), project_dir)
        if attr_path:
            self.import_attributes(attr_path, id_col=attributes.get('id_col'), quiet=True)
        if state.get('compare') and not (self.setting == 'mobile' and state['compare'].get('kind') == 'time'):
            self.compare = dict(state['compare'])
            if self.compare.get('kind') == 'time':
                self.compare['items'] = [tuple(w) for w in self.compare['items']]
            elif self.compare.get('kind') == 'stimuli':
                items = [self.match_stimulus(project_io.relocate(p, project_dir) or p) for p in self.compare['items']]
                self.compare['items'] = [p for p in items if p is not None]
                if len(self.compare['items']) < 2:
                    self.compare = None
            self.update_compare_indicator()
        view = state.get('view')
        if view in self.VIEWS and (view not in self.ADVANCED_VIEWS or self.advanced_views_shown()):
            self.left_toolbar.setCurrentRow(self.VIEWS.index(view))
        self.schedule_current_view(delay=30)
        self.setWindowTitle(f"creapy.io - {os.path.basename(path)}")
        self.log.log('project_opened', path=os.path.basename(path))
        if self.setting == 'mobile' and not self.settings.value("hints/mobile_seen", False, type=bool):
            self.explain_mobile()

    def recent_projects(self):
        return [p for p in self.settings.value("projects/recent", [], type=list) if os.path.exists(p)]

    def add_recent_project(self, path):
        recent = [path] + [p for p in self.recent_projects() if p != path]
        self.settings.setValue("projects/recent", recent[:8])
        self.remember_dir('project', os.path.dirname(path))
        self.refresh_recent_menu()

    def refresh_recent_menu(self):
        self.recent_menu.clear()
        recent = self.recent_projects()
        if not recent:
            self.recent_menu.addAction("(none yet)").setEnabled(False)
        for p in recent:
            self.recent_menu.addAction(self.make_action(os.path.basename(p), lambda _=False, p=p: self.open_project(p)))

    def start_dir(self, kind, near=None):
        assert kind in ['project', 'data', 'images', 'export', 'bundle']
        remembered = self.settings.value(f"dirs/{kind}", "", type=str)
        data_dir = self.settings.value("dirs/data", "", type=str)
        documents = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)
        if kind == 'project':
            recent = self.recent_projects()
            candidates = [remembered, os.path.dirname(recent[0]) if recent else None, data_dir]
        elif kind == 'images':
            candidates = [near, remembered, data_dir]   # snapshots usually sit next to the table
        elif kind == 'export':
            candidates = [self.save_dir, os.path.dirname(self.project_path) if self.project_path else None, remembered]
        elif kind == 'bundle':
            downloads = QStandardPaths.writableLocation(QStandardPaths.DownloadLocation)
            candidates = [remembered, downloads, data_dir]
        else:
            candidates = [remembered]
        for folder in candidates + [documents]:
            if folder and os.path.isdir(folder) and (kind != 'export' or os.access(folder, os.W_OK)):
                return folder
        return os.path.expanduser("~")

    def remember_dir(self, kind, folder):
        if folder and os.path.isdir(folder):
            self.settings.setValue(f"dirs/{kind}", folder)

    def exported_to(self, folder):
        self.save_dir = folder
        self.remember_dir('export', folder)


    def setup_workspace(self, stim_2_df, mapping, is_fixation, source_name=None, setting='lab'):
        self.jobs.cancel()
        self.setting = setting
        self.stim_dfs = stim_2_df
        self.stim_values = {path: path for path in stim_2_df}
        self.mapping = mapping
        self.is_fixation = is_fixation
        self.source_name = source_name
        self.project_path = None
        self.save_dir = None
        self.base_cache = {}
        self.filtered_cache = {}
        self.aois = {}
        self.aoi_inactive = {}   # stimulus path -> names of the areas ticked off in the AOI panel (left out of the tables)
        self.dataset_fix = None
        self.dataset_sac = None
        self.current_path = None
        self.grouping = None
        self.compare = None
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.update_undo_actions()
        self.similarity_confirmed = set()
        self.min_fix_dur_ms = 0
        self.intervals_path = None
        self.df_events = None
        self.aoi_sizes = {}
        self.aoi_names = {}   # stimulus -> {area: tag} from the AOI-based export, areas nobody fixated included
        self.attributes = None
        self.attributes_path = None
        self.attributes_id_col = None
        self.all_subjects = creapy.natural_sorted(
            pd.concat([df[mapping['subj_index_col']] for df in stim_2_df.values()]).dropna().unique())
        self.derived_grouping = grouping_from_stimulus_names(self.stimulus_names_per_participant()) \
            or grouping_from_participant_names(self.all_subjects)   # condition read off the names, for the rosters
        self.init_main_layout()
        self.setWindowTitle(f"creapy.io - {source_name}" if source_name else "creapy.io")
        self.update_status_dataset()
        self.update_compare_indicator()
        self.set_workspace_actions_enabled(True)
        self.set_setting(setting, render=False)
        self.update_export_aoi_controls()
        self.stats_toolbar.set_groups_available(False)

    def init_main_layout(self):
        self.pending_run = lambda: None
        self.render_timer = QTimer(self)
        self.render_timer.setSingleShot(True)
        self.render_timer.timeout.connect(lambda: self.pending_run())

        self.left_toolbar = QListWidget()
        self.left_toolbar.setObjectName("NavList")
        for name in self.VIEWS:
            self.left_toolbar.addItem(name)
            self.left_toolbar.item(self.left_toolbar.count() - 1).setToolTip(
                widget_utils.rich_tooltip(glossary.VIEW_SUMMARY[name]))
        self.left_toolbar.setFixedWidth(172)
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
        self.visits_toolbar = VisitsToolbar(self.debounced("Visits"))

        self.view_toolbars = [self.fix_heatmap_toolbar, self.fix_scanpath_toolbar, self.sac_scanpath_toolbar,
                              self.sac_heatmap_toolbar, self.rose_toolbar, self.aoi_toolbar,
                              self.time_series_toolbar, self.similarity_toolbar, self.scanpath_compare_toolbar,
                              self.recurrence_toolbar, self.stats_toolbar, self.visits_toolbar]
        self.view_runs = [self.make_runner(name) for name in self.VIEWS]
        for name, toolbar in zip(self.VIEWS, self.view_toolbars):
            toolbar.setObjectName("heatmapToolbar")
            toolbar.setAccessibleName(f"{name} panel")
            toolbar.save_btn.clicked.connect(self.save_image)
            if hasattr(toolbar, 'groups_btn'):
                toolbar.groups_btn.clicked.connect(self.assign_groups)
            if hasattr(toolbar, 'export_btn'):
                toolbar.export_btn.clicked.connect(self.export_table)
        self.apply_advanced_views()
        self.aoi_toolbar.remove_btn.clicked.connect(self.remove_selected_aoi)
        self.aoi_toolbar.clear_btn.clicked.connect(self.clear_aois)
        self.aoi_toolbar.save_aoi_btn.clicked.connect(self.save_aois)
        self.aoi_toolbar.load_aoi_btn.clicked.connect(self.load_aois)
        self.aoi_toolbar.auto_btn.clicked.connect(self.add_hotspot_aoi)
        self.aoi_toolbar.export_aoi_btn.clicked.connect(self.add_export_aois)
        self.aoi_toolbar.mode_selector.currentIndexChanged.connect(lambda *_: self.cancel_drawing())
        self.aoi_toolbar.aoi_list.itemChanged.connect(self.on_aoi_ticked)

        self.right_toolbar_stack = QStackedWidget()
        for toolbar in self.view_toolbars:
            scroll = QScrollArea()
            scroll.setObjectName("PanelScroll")
            toolbar.setMinimumWidth(200)   # follow the panel width (as the former fixed 250 px did), never wider
            scroll.setWidget(toolbar)
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.right_toolbar_stack.addWidget(scroll)

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
        self.right_panel.setObjectName("RightPanel")
        right_layout = QVBoxLayout(self.right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        right_layout.addWidget(header)
        right_layout.addWidget(self.right_toolbar_stack)
        self.right_panel.setFixedWidth(250)

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

        self.toolbar_effect = QGraphicsOpacityEffect(self.right_toolbar_stack)
        self.toolbar_effect.setOpacity(1.0)
        self.right_toolbar_stack.setGraphicsEffect(self.toolbar_effect)
        self.toolbar_fade = QPropertyAnimation(self.toolbar_effect, b"opacity", self)
        self.toolbar_fade.setDuration(140)
        self.toolbar_fade.setStartValue(0.25)
        self.toolbar_fade.setEndValue(1.0)

        self.painter = PainterWidget()
        self.painter.setAccessibleName("canvas")
        self.painter.zoomed.connect(self.on_zoomed)
        self.zoom_log_timer = QTimer(self)
        self.zoom_log_timer.setSingleShot(True)
        self.zoom_log_timer.setInterval(400)
        self.zoom_log_timer.timeout.connect(self.log_zoom)
        self.zoom_hows = set()
        self.table_view = DataFrameView()

        self.main_area = QStackedWidget()
        self.main_area.addWidget(self.painter)
        self.main_area.addWidget(self.table_view)

        self.stimulus_strip = StimulusStrip(list(self.stim_dfs))
        self.stimulus_strip.stimulus_selected.connect(self.on_stimulus_selected)

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

        self.busy_frame = QFrame(self.canvas_area)
        self.busy_frame.setObjectName("BusyPill")
        self.busy_frame.setStyleSheet(
            "QFrame#BusyPill { background-color: #20232b; border: 1px solid #5aa9ff; border-radius: 14px; }"
            "QFrame#BusyPill QLabel { color: #e8e9ed; background: transparent; border: none; }"
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
        self.busy_timer = QTimer(self)
        self.busy_timer.setSingleShot(True)
        self.busy_timer.setInterval(180)
        self.busy_timer.timeout.connect(lambda: self.show_busy(self.busy_pending_text))
        self.busy_pending_text = ""

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.left_toolbar)
        splitter.addWidget(self.right_panel)
        splitter.addWidget(self.canvas_area)
        splitter.setHandleWidth(3)
        splitter.setSizes([172, 250, 900])

        self.setCentralWidget(splitter)

        self.drawing = None
        self.canvas_connections = []

        self.stimulus_strip.select(next(iter(self.stim_dfs)))
        self.left_toolbar.setCurrentRow(0)


    def build_base(self, path):
        max_gap = creapy.MOBILE_MAX_GAP if self.setting == 'mobile' else None
        df_stim = self.filter_min_dur(self.stim_dfs[path])
        if len(df_stim) == 0:
            raise Hint(f"No fixation on {self.stimulus_name(path)} lasts {self.min_fix_dur_ms} ms or longer, so there "
                       "is nothing to show for it. Lower the threshold under Analysis > Minimum Fixation Duration.")
        dataset_fix, dataset_sac = creapy.build_pair(df_stim, path, self.mapping, self.is_fixation, max_gap=max_gap)
        dataset_fix.areas_of_interest = self.aois.setdefault(path, {})
        return dataset_fix, dataset_sac

    def base_datasets(self, path):
        if path not in self.base_cache:
            self.base_cache[path] = self.build_base(path)
        return self.base_cache[path]

    def datasets_for(self, path, subjects=None, t_range=None):
        key = (tuple(subjects) if subjects is not None else None, t_range)
        base_fix, base_sac = self.base_datasets(path)
        if key == (None, None):
            return base_fix, base_sac
        if (path, key) not in self.filtered_cache:
            fix = base_fix.subset(subjects=subjects, t_range=t_range)
            try:
                sac = base_sac.subset(subjects=subjects, t_range=t_range)
            except AssertionError:
                sac = None   # a lone fixation has no saccade; the fixation views still work
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
            except Hint as e:
                self.current_path = path
                self.render_timer.stop()
                self.cancel_drawing()
                self.log.log('hint', view='stimulus', message=str(e))
                self.show_notice(str(e))
                return
            except Exception as e:
                self.log.log_error('load_stimulus', e)
                QMessageBox.critical(
                    self, "Stimulus Failed to Load",
                    "The data for this stimulus could not be loaded.\n\n"
                    "Please check that the column mapping matches your table (e.g., coordinate columns contain "
                    "numbers) and that the image file can be opened.\n\n"
                    f"Technical detail: {e}")
                if self.current_path is not None:
                    self.stimulus_strip.mark(self.current_path)
                return
        self.current_path = path
        base_fix, _ = self.base_cache[path]
        self.filter_bar.set_time_max(base_fix.t_max)
        self.refresh_aoi_controls()
        self.time_series_toolbar.set_curves_available({
            'Pupil Size': (base_fix.pupil_col is not None, "The imported table has no pupil column: re-import and set "
                                                           "the optional field 'Pupil size'."),
            'Viewing Distance': ('distance_mm' in base_fix.df.columns, "No viewing distance in this dataset: Tobii "
                                                                      "glasses Data exports carry it (Gaze point 3D), "
                                                                      "the event-based metrics export does not.")})
        self.log.log('stimulus_selected', stimulus=os.path.basename(path))
        self.refresh_current_datasets()
        self.schedule_current_view(delay=30)

    def refresh_current_datasets(self):
        try:
            self.dataset_fix, self.dataset_sac = self.current_datasets()
            return True
        except Hint:
            return False   # the stimulus is empty under the minimum fixation duration; run_view shows the notice
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


    def schedule_render(self, fn, delay):
        self.pending_run = fn
        self.render_timer.start(delay)

    def schedule_current_view(self, delay):
        row = self.left_toolbar.currentRow()
        if row >= 0:
            self.schedule_render(self.view_runs[row], delay=delay)

    def debounced(self, view_name):
        def request(*_):
            if view_name == self.current_view_name():
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
        self.busy_frame.repaint()

    def show_busy_soon(self, message):
        self.busy_pending_text = message
        self.busy_timer.start()

    def hide_busy(self):
        self.busy_timer.stop()
        if self.busy_frame.isVisible():
            self.busy_fade.start()

    @contextmanager
    def busy_now(self, message):
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
        t0 = time.time()
        try:
            yield
            self.log.log('render', view=view_name, seconds=round(time.time() - t0, 3))
        except Exception as e:  # noqa: BLE001
            self.report_view_error(view_name, e)

    def change_analysis_view(self, index):
        self.render_timer.stop()
        self.cancel_drawing()
        if index < 0:
            return
        self.right_toolbar_stack.setCurrentIndex(index)
        self.panel_title.setText(self.VIEWS[index])
        if not self.explainer_dock.isHidden():
            self.update_explainer()
        self.log.set_view(self.VIEWS[index])
        self.toolbar_fade.stop()
        self.toolbar_fade.start()
        self.schedule_render(self.view_runs[index], delay=160)

    def show_notice(self, text):
        fig = plt.figure(facecolor=DARK_BG)
        fig.text(0.5, 0.5, text, ha='center', va='center', color='#9ba0ab', fontsize=12, wrap=True)
        self.show_figure(fig, None)

    def show_figure(self, fig, caption=None, zoom_key=None):
        self.main_area.setCurrentWidget(self.painter)
        self.painter.set_drag_pan(True)
        self.painter.draw_figure(fig, zoom_key)
        self.painter.set_caption(caption)
        self.current_caption = caption
        plt.close(fig)
        self.current_table = None


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

    def selection_note(self, time=True):
        parts = []
        if self.filter_bar.participants() is not None:
            parts.append(self.filter_bar.selection_label())
        if time and self.filter_bar.t_range() is not None:
            parts.append(self.filter_bar.describe())
        return " · ".join(parts)


    def toolbar_for(self, view_name):
        return self.view_toolbars[self.VIEWS.index(view_name)]

    def make_ctx(self, view_name, params, fix, path=None, subjects='filter', vmax=None):
        participants = self.filter_bar.participants() if subjects == 'filter' else subjects
        path = path or self.current_path
        ctx = {'grouping': self.grouping_for(fix.subjects), 'grouping_all': self.grouping,
               'note': self.selection_note(time=not views.dataset_level(view_name, params)),
               'stim': os.path.basename(path), 'stim_value': str(self.stim_values.get(path, path)),
               'filtered_participants': participants is not None,
               'selected_subject': participants[0] if participants and len(participants) == 1 else None,
               'vmax': vmax, 'setting': self.setting,
               'roster': None}
        if self.zero_rows_enabled():
            ctx['roster'] = list(self.all_subjects) if views.dataset_level(view_name, params) else self.roster_for(path)
            if participants is not None:
                ctx['roster'] = [s for s in ctx['roster'] if s in set(participants)]
            roster_of = {}
            for p in self.stim_dfs:
                roster_of[self.stimulus_name(p)] = roster_of[str(self.stim_values.get(p, p))] = self.roster_for(p)
            ctx['roster_of'] = roster_of
        ctx.update({'names': self.active_aoi_names(path), 'reference': self.aoi_toolbar.get_params()['reference'],
                    'names_of': {self.stimulus_name(p): self.active_aoi_names(p) for p in self.stim_dfs},
                    'all_datasets': self.all_datasets, 'subjects': participants})
        if view_name in self.DATASET_VIEWS:
            ctx.update({'table': self.full_table(), 'mapping': self.mapping, 'events': self.df_events})
        if view_name == 'Statistics':
            ctx['on_measures'] = self.stats_toolbar.set_measures
        if view_name == 'Time Series':
            ctx['on_default_aoi'] = lambda fix_: self.refresh_aoi_controls()
            t_range = self.filter_bar.t_range()
            path = self.current_path
            ctx['subset_fn'] = lambda subs: self.datasets_for(path, list(subs), t_range)
        return ctx

    def panels(self, view_name):
        if not self.compare or view_name not in COMPARABLE_VIEWS \
                or views.dataset_level(view_name, self.toolbar_for(view_name).get_params()):
            return [(None, self.dataset_fix, self.dataset_sac, self.current_path)]
        kind, items = self.compare['kind'], self.compare['items']
        subjects, t_range = self.filter_bar.filter_key()
        panels = []
        if kind == 'groups':
            base_fix, _ = self.base_datasets(self.current_path)
            for name in items:
                members = [s for s in base_fix.subjects if self.grouping and self.grouping.get(s) == name]
                if members:
                    try:
                        panels.append((name, *self.datasets_for(self.current_path, members, t_range), self.current_path))
                    except AssertionError:
                        pass
        elif kind == 'stimuli':
            for path in items:
                if path in self.stim_dfs:
                    try:
                        panels.append((os.path.splitext(os.path.basename(path))[0],
                                       *self.datasets_for(path, subjects, t_range), path))
                    except AssertionError:
                        pass
        else:
            for t0, t1 in items:
                try:
                    panels.append((f"{t0:.1f}–{t1:.1f} s", *self.datasets_for(self.current_path, subjects, (t0, t1)),
                                   self.current_path))
                except AssertionError:
                    pass
        if not panels:
            raise Hint("Nothing to compare for this selection: check the groups / stimuli / time windows "
                       "(Analysis > Compare Side by Side) or reset the filters.")
        return panels

    def without_saccades(self, view_name, panels):
        """Panels this view can draw: those with saccades, when it needs them."""
        if not views.needs_saccades(view_name, self.setting):
            return panels
        kept = [p for p in panels if p[2] is not None]
        if not kept:
            raise Hint("This selection has fixations but no saccade: a participant with a single fixation on the "
                       "stimulus never moved the eyes between two of them here. The fixation heatmap, the fixation "
                       "scanpath, Areas of Interest and Statistics still work for it.")
        return kept

    def run_view(self, view_name):
        if self.dataset_fix is None:
            return
        if self.current_path is not None and self.current_path not in self.base_cache:
            try:
                self.base_datasets(self.current_path)
            except Hint as e:
                self.show_notice(str(e))
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
            panels = self.without_saccades(view_name, self.panels(view_name))
        except Hint as e:
            self.report_view_error(view_name, e)
            return
        ctx = self.make_ctx(view_name, params, self.dataset_fix)
        shared_scale = view_name == 'Fixation Heatmap' and params.get('shared_scale')
        paths = list(self.stim_dfs)

        def work(progress):
            if shared_scale:
                progress(0, 0, "shared colour scale over all stimuli")
                vmax = 0.
                for path in paths:
                    if progress(0, 0, None) is False:
                        raise InterruptedError
                    vmax = max(vmax, self.base_datasets(path)[0].heatmap_max(params['bw_method']))
                ctx['vmax'] = vmax if vmax > 0 else None
            if prepare is not None:
                for _, fix, sac, _ in panels:
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
            done(True)
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

    def panel_roster(self, path, title):
        """Who owes a zero row in one panel of Compare Side by Side: the stimulus roster within the panel's group or
        within the selected participants."""
        if not self.zero_rows_enabled():
            return None
        roster = self.roster_for(path)
        if self.compare['kind'] == 'groups':
            return [s for s in roster if self.grouping.get(s) == title]
        participants = self.filter_bar.participants()
        return roster if participants is None else [s for s in roster if s in set(participants)]

    def draw_into(self, fig, view_name, draw, panels, params, ctx, axes_kind, multi):
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
            caption = None
            for i, (title, fix, sac, path) in enumerate(panels):
                ax = views.new_axes(fig, axes_kind, (n_rows, n_cols, i + 1))
                ctx_panel = dict(ctx, note=None, grouping=self.grouping_for(fix.subjects), panel=title,
                                 names=self.active_aoi_names(path), stim=os.path.basename(path),
                                 roster=self.panel_roster(path, title))
                res = draw(fix, sac, params, ctx_panel, fig, ax)
                if isinstance(res, tuple):
                    res, caption = res
                if isinstance(res, pd.DataFrame):
                    res = res.assign(panel=title)
                    result = res if result is None else pd.concat([result, res], ignore_index=True)
                ax.set_title(title, color='white', fontsize=10, loc='left')
            if caption is not None and isinstance(result, pd.DataFrame):
                by = {'groups': "group", 'stimuli': "stimulus", 'time': "time window"}[self.compare['kind']]
                if view_name == 'Statistics' and params.get('display') == 'Group comparison (table)':
                    result = views.compare_panels_table(result)
                    caption = (f"<b>Compared by {by}</b>: the panels are the groups. {views.COMPARISON_CAPTION}")
                else:
                    caption = f"<b>Compared by {by}</b> (column panel). " + caption
                result = (result, caption)
            fig.suptitle(f"{view_name} · " + {'groups': "by group", 'stimuli': "by stimulus",
                                               'time': "by time window"}[self.compare['kind']]
                         + (f" · {ctx['note']}" if ctx.get('note') and self.compare['kind'] != 'groups' else ""),
                         color='white', fontsize=11, x=0.01, ha='left')
            fig.subplots_adjust(left=0.02, right=0.98, bottom=0.03, top=0.9, wspace=0.08, hspace=0.18)
        return result

    def draw_panels(self, view_name, draw, kind, panels, params, ctx):
        axes_kind = views.axes_kind(view_name, params)
        multi = len(panels) > 1
        with plt.rc_context(DARK_RC if axes_kind != 'image' or multi else {}):
            fig = plt.figure(facecolor=DARK_BG)
            try:
                result = self.draw_into(fig, view_name, draw, panels, params, ctx, axes_kind, multi)
            except BaseException:
                plt.close(fig)
                raise
        if isinstance(result, tuple) and result[1] is not None:
            plt.close(fig)
            self.show_table(result[0], result[1])
            return
        self.show_figure(fig, glossary.figure_caption(view_name, params) if axes_kind != 'image' else None,
                         zoom_key=(view_name, self.current_path, axes_kind, len(panels), params.get('display')))
        self.current_axes_kind = axes_kind
        self.current_table = result[0] if isinstance(result, tuple) else result
        if view_name == 'Areas of Interest' and params['display'] == 'Image with AOIs' and not multi \
                and params['mode'] != 'View only':
            self.connect_drawing(fig.axes[0], params['mode'])

    def confirm_large_similarity(self, params):
        if self.dataset_sac is None:
            return True
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

    def run_visits(self):
        self.run_view("Visits")


    def choose_compare(self):
        if self.dataset_fix is None:
            return
        base_fix, _ = self.base_datasets(self.current_path)
        dialog = CompareDialog(list(self.stim_dfs), self.grouping, base_fix.t_max, parent=self, current=self.compare,
                               allow_time=self.setting != 'mobile')
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
            self.left_toolbar.setCurrentRow(0)
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


    def batch_export(self):
        if self.dataset_fix is None:
            return
        view_name = self.VIEWS[self.left_toolbar.currentRow()]
        folder = QFileDialog.getExistingDirectory(self, "Folder for the Exported Figures / Tables",
                                                  self.start_dir('export'))
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
        if params.get('display'):
            view_slug += '_' + re.sub(r'[^a-z0-9]+', '_', str(params['display']).lower()).strip('_')
        written, skipped = [], []
        tables = []
        vmax = None
        if view_name == 'Fixation Heatmap' and params.get('shared_scale'):
            vmax = max(self.base_datasets(p)[0].heatmap_max(params['bw_method']) for p in paths) or None
        dataset_level = views.dataset_level(view_name, params)
        if dataset_level:
            paths = [self.current_path]
        for i, path in enumerate(paths):
            progress.setValue(i)
            progress.setLabelText(f"{os.path.basename(path)} …")
            QApplication.processEvents()
            if progress.wasCanceled():
                break
            stim_name = os.path.splitext(os.path.basename(path))[0]
            if dataset_level:
                stim_name = 'dataset'
            try:
                fix, sac = self.datasets_for(path, subjects, t_range)
                if sac is None and views.needs_saccades(view_name, self.setting):
                    raise Hint("no saccade in this selection")
                ctx = dict(self.make_ctx(view_name, params, fix, path=path, subjects=subjects, vmax=vmax),
                           stim=stim_name)
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
                    table = self.with_attributes(table)
                    out = os.path.join(folder, f"{stim_name}_{view_slug}.csv")
                    table.to_csv(out, index=False)
                    written.append(out)
                    tables.append(table.assign(stimulus=stim_name) if 'stimulus' not in table.columns else table)
            except Exception as e:  # noqa: BLE001
                skipped.append(f"{stim_name}: {e}")
        if len(tables) > 1:
            out = os.path.join(folder, f"all_stimuli_{view_slug}.csv")
            df_all = pd.concat(tables, ignore_index=True)
            df_all.insert(0, 'stimulus', df_all.pop('stimulus'))
            df_all.to_csv(out, index=False)
            written.append(out)
        progress.setValue(len(paths))
        self.exported_to(folder)
        self.log.log('batch_export', view=view_name, n_files=len(written), n_skipped=len(skipped))
        text = f"{len(written)} file(s) written to\n{folder}"
        if skipped:
            text += "\n\nSkipped:\n" + "\n".join(f"  · {s}" for s in skipped[:8])
        QMessageBox.information(self, "Export Finished", text)


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
        self.painter.set_drag_pan(False)

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
        self.painter.set_drag_pan(True)
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
            return
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
        target = self.aois.setdefault(path, {})
        target.clear()
        target.update(aois)
        if path == self.current_path:
            self.refresh_aoi_controls()
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
        self.refresh_aoi_controls()
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
        self.refresh_aoi_controls()
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
        self.refresh_aoi_controls()
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
            self.refresh_aoi_controls()
            self.schedule_render(self.run_aoi, delay=30)

    def save_aois(self):
        aois = self.aois.get(self.current_path, {})
        if not aois:
            QMessageBox.information(self, "No AOIs", "There are no areas of interest on this stimulus yet.")
            return
        stim_name = os.path.splitext(os.path.basename(self.current_path))[0]
        path, _ = QFileDialog.getSaveFileName(self, "Save AOIs", os.path.join(self.start_dir('export'), f"{stim_name}_aois.json"),
                                              "AOI files (*.json)")
        if not path:
            return
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'stimulus': os.path.basename(self.current_path),
                           'width': self.dataset_fix.width, 'height': self.dataset_fix.height,
                           'aois': [aoi.to_record() for aoi in aois.values()]}, f, indent=2)
        except Exception as e:
            return self.write_failed(path, e)
        self.exported_to(os.path.dirname(path))
        self.log.log('aoi_saved', n=len(aois))

    def load_aois(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load AOIs", self.start_dir('export'), "AOI files (*.json)")
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
        self.refresh_aoi_controls()
        self.schedule_render(self.run_aoi, delay=30)


    def grouping_for(self, subjects):
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
        self.stats_toolbar.set_groups_available(bool(self.grouping))
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
        if self.dataset_fix is None:
            return
        df = self.full_table()   # every stimulus: a column constant per participant (condition ...) is seen for all
        extra = {}
        derived = grouping_from_stimulus_names(self.stimulus_names_per_participant())
        if derived:
            extra["condition (from the snapshot names)"] = pd.Series(derived)
        from_names = grouping_from_participant_names(self.all_subjects)
        if from_names:
            extra["condition (from the participant names)"] = pd.Series(from_names)
        dialog = GroupingDialog(self.all_subjects, df, df[self.mapping['subj_index_col']], grouping=self.grouping,
                                parent=self, attributes=self.attributes, extra=extra or None)
        if dialog.exec():
            self.set_grouping(dialog.get_grouping() or None)
            self.log.log('groups_assigned', grouping=self.grouping)


    def save_image(self):
        fig = self.painter.current_fig
        if fig is None or self.main_area.currentWidget() is not self.painter:
            QMessageBox.information(self, "No Figure", "The current view is a table: use Export Table instead.")
            return
        stim_name = os.path.splitext(os.path.basename(self.current_path))[0]
        view_name = self.left_toolbar.currentItem().text().lower().replace(' ', '_')
        suggestion = os.path.join(self.start_dir('export'), f"{stim_name}_{view_name}.png")
        file_path, chosen = QFileDialog.getSaveFileName(
            self, "Save Figure", suggestion, "PNG image (*.png);;PDF (*.pdf);;SVG (*.svg)")
        if file_path:
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ('.png', '.pdf', '.svg'):
                file_path += '.pdf' if 'PDF' in chosen else ('.svg' if 'SVG' in chosen else '.png')
            try:
                with self.caption_on_figure(fig, self.current_caption, self.current_axes_kind):
                    fig.savefig(file_path, dpi=200, bbox_inches="tight", pad_inches=0, facecolor=fig.get_facecolor())
            except Exception as e:
                return self.write_failed(file_path, e)
            self.exported_to(os.path.dirname(file_path))
            self.log.log('export_image', view=view_name, path=os.path.basename(file_path))

    def write_failed(self, path, error):
        QMessageBox.critical(self, "Could Not Write the File",
                             f"{os.path.basename(path)} could not be written. Close the file if it is open in another "
                             f"program, or choose another folder.\n\nTechnical detail: {error}")

    def export_table(self):
        df = self.with_attributes(self.current_table)
        if df is None:
            QMessageBox.information(self, "No Table",
                                    "This view has no table to export. Tables exist in Statistics, Areas of "
                                    "Interest, Visits, Recurrence, the similarity matrices and the periodogram.")
            return
        stim_name = os.path.splitext(os.path.basename(self.current_path))[0]
        view_name = self.left_toolbar.currentItem().text().lower().replace(' ', '_')
        suggestion = os.path.join(self.start_dir('export'), f"{stim_name}_{view_name}.csv")
        file_path, chosen = QFileDialog.getSaveFileName(
            self, "Export Table", suggestion, "CSV (*.csv);;Excel (*.xlsx)")
        if not file_path:
            return
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in ('.csv', '.xlsx'):
            file_path += '.xlsx' if 'Excel' in chosen else '.csv'
        try:
            if file_path.lower().endswith('.xlsx'):
                df.to_excel(file_path, index=False)
            else:
                df.to_csv(file_path, index=False)
        except Exception as e:
            return self.write_failed(file_path, e)
        self.exported_to(os.path.dirname(file_path))
        self.log.log('export_table', view=view_name, path=os.path.basename(file_path), n_rows=len(df))


def main():
    if '--selftest' in sys.argv:
        return selftest()
    app = QApplication(sys.argv)
    QLocale.setDefault(QLocale(QLocale.English, QLocale.UnitedStates))
    app.setApplicationName("creapy.io")
    app.setOrganizationName("CReA")
    window = MainWindow()

    def report_crash(exc_type, exc, tb):
        window.log.log_crash(exc_type, exc, tb)
        QMessageBox.critical(
            window, "Something Went Wrong",
            "The last action could not be completed. The data is unchanged; try again or reopen the project.\n\n"
            f"Technical detail: {exc_type.__name__}: {exc}")

    sys.excepthook = report_crash
    window.show()
    sys.exit(app.exec())


def selftest():
    import tempfile
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("CREAPY_LOG_DIR", tempfile.mkdtemp(prefix="creapy_selftest_"))
    app = QApplication(sys.argv)
    app.setApplicationName("creapy.io")
    failures = []
    QMessageBox.critical = lambda *a, **k: failures.append(str(a[2])[:300])  # type: ignore
    QMessageBox.information = lambda *a, **k: None  # type: ignore
    QMessageBox.question = lambda *a, **k: QMessageBox.No  # type: ignore
    QtCore.qInstallMessageHandler(lambda mode, ctx, msg: failures.append(msg) if 'Could not parse' in msg else None)
    try:
        window = MainWindow(synchronous=True)
        window.open_example()
        for i, name in enumerate(window.VIEWS):
            t0 = time.time()
            window.left_toolbar.setCurrentRow(i)
            window.view_runs[i]()
            print(f"  {name:20s} {time.time() - t0:5.2f} s")
        window.close()
        selftest_mobile(failures)
    except Exception as e:  # noqa: BLE001
        failures.append(f"{type(e).__name__}: {e}")
    if failures:
        print("SELFTEST FAILED:\n  " + "\n  ".join(failures))
        sys.exit(1)
    print(f"SELFTEST OK: creapy {creapy.__version__}, Python {sys.version.split()[0]}")
    sys.exit(0)


def selftest_mobile(failures):
    import tempfile
    from creapy.examples import make_mobile_example
    global ColumnMappingDialog
    accepted = ColumnMappingDialog
    ColumnMappingDialog = type('Accept', (accepted,), {'exec': lambda self: 1})
    folder = tempfile.mkdtemp(prefix="creapy_selftest_")
    events, aois = make_mobile_example(folder)
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: folder)
    try:
        window = MainWindow(synchronous=True)
        if window.import_tobii(path=events) is False or window.setting != 'mobile':
            failures.append("mobile example: import failed")
            return
        if len(window.all_subjects) != 3 or len(window.stim_dfs) != 4:
            failures.append(f"mobile example: {len(window.all_subjects)} participants, {len(window.stim_dfs)} stimuli")
        if not window.attach_intervals_file(aois, quiet=True):
            failures.append("mobile example: recording clock not attached")
        window.left_toolbar.setCurrentRow(window.VIEWS.index("Areas of Interest"))
        window.aoi_toolbar.all_stimuli_checkbox.setChecked(True)
        window.add_export_aois()
        if any(not window.aois.get(p) for p in window.stim_dfs):
            failures.append("mobile example: areas missing on a stimulus")
        for name in window.MOBILE_VIEWS:
            t0 = time.time()
            i = window.VIEWS.index(name)
            window.left_toolbar.setCurrentRow(i)
            window.view_runs[i]()
            print(f"  {name:20s} {time.time() - t0:5.2f} s  (mobile)")
        window.close()
    finally:
        ColumnMappingDialog = accepted
        shutil.rmtree(folder, ignore_errors=True)


if __name__ == "__main__":
    main()
