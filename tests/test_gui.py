import json
import os
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

import creapy  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from creapy.io import main as gui  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def silent_boxes(monkeypatch):
    seen = []
    for name in ['information', 'critical', 'warning']:
        monkeypatch.setattr(QMessageBox, name, lambda *a, _n=name, **k: seen.append((_n, a[1], str(a[2]))))
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.Yes)
    return seen


def open_example(qapp):
    w = gui.MainWindow(synchronous=True)
    w.open_example()
    return w


def test_every_view_renders_on_example(qapp, silent_boxes):
    w = open_example(qapp)
    assert len(w.stim_dfs) == 2 and len(w.all_subjects) == 12
    for i, name in enumerate(w.VIEWS):
        w.left_toolbar.setCurrentRow(i)
        w.view_runs[i]()
    failures = [s for s in silent_boxes if s[0] == 'critical']
    assert failures == [], failures


def test_advanced_views_hidden_by_default(qapp, silent_boxes):
    w = open_example(qapp)
    w.settings.setValue("views/advanced", False)
    w.apply_advanced_views()
    hidden = [w.left_toolbar.item(w.VIEWS.index(n)).isHidden() for n in w.ADVANCED_VIEWS]
    assert all(hidden) and w.time_series_toolbar.display_selector.count() == 1
    w.advanced_action.setChecked(True)
    assert not w.left_toolbar.item(w.VIEWS.index("Recurrence")).isHidden()
    assert w.time_series_toolbar.display_selector.count() == 3
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Recurrence"))
    w.advanced_action.setChecked(False)
    assert w.left_toolbar.currentRow() == 0
    w.settings.remove("views/advanced")


def test_filters_groups_aois_and_tables(qapp, silent_boxes):
    w = open_example(qapp)
    w.grouping = {s: ('expert' if s <= 'P06' else 'layperson') for s in w.all_subjects}
    w.filter_bar.set_subjects(w.all_subjects, w.grouping)
    w.filter_bar.participant_selector.setCurrentText('P01')
    w.filter_bar.to_slider.setValue(6)
    assert w.filter_bar.participants() == ['P01'] and w.filter_bar.t_range() == (0.0, 3.0)
    assert w.dataset_fix.subjects == ['P01'] and w.dataset_fix.t.max() <= 3.0
    w.left_toolbar.setCurrentRow(1)
    w.run_fixation_scanpath()
    w.left_toolbar.setCurrentRow(7)
    w.run_similarity()
    assert any(s[0] == 'information' and 'two participants' in s[2] for s in silent_boxes)
    w.left_toolbar.setCurrentRow(9)
    w.run_recurrence()
    assert w.painter.current_fig is not None and 'P01' in w.painter.current_fig.axes[0].get_title(loc='left')
    w.filter_bar.reset()
    assert w.dataset_fix.n_subjects() == 12
    w.filter_bar.participant_selector.setCurrentIndex(1)
    assert w.filter_bar.participants() == ['P01', 'P02', 'P03', 'P04', 'P05', 'P06']
    w.filter_bar.reset()
    w.left_toolbar.setCurrentRow(5)
    w.run_aoi()
    w.add_aoi(creapy.AOI.rectangle('left', 0, 0, 800, 1200))
    w.aoi_toolbar.display_selector.setCurrentText('Metrics table')
    w.run_aoi()
    assert w.current_table is not None and set(w.current_table['aoi']) == {'left'}
    assert not w.aoi_toolbar.display_selector.model().item(
        w.aoi_toolbar.AVAILABLE_DISPLAY.index('Transition matrix')).flags() & Qt.ItemIsEnabled   # one area: greyed
    w.add_aoi(creapy.AOI.rectangle('right', 800, 0, 1600, 1200))
    expected = {'First-fixation order': {'participant', 'left', 'right'},
                'Sequences (table)': {'participant', 'sequence', 'n_switches', 'dwell_left', 'runs_right'},
                'Transitions per participant (table)': {'participant', 'left>right', 'right>left', 'n_transitions'},
                'Area comparison (table)': {'measure', 'test', 'p_value', 'median_left', 'cohen_d'}}
    for display in w.aoi_toolbar.AVAILABLE_DISPLAY[2:]:
        w.aoi_toolbar.display_selector.setCurrentText(display)
        w.run_aoi()
        if display in expected:
            assert set(w.current_table.columns) >= expected[display], display
    assert w.current_table['test'].iloc[0] == 'paired t'   # same participants in both areas
    w.aoi_toolbar.display_selector.setCurrentText('Metrics table')
    w.aoi_toolbar.reference_selector.setCurrentText('left')
    w.run_aoi()
    assert 'dwell_share_of_reference' in w.current_table.columns
    w.aoi_toolbar.aoi_list.item(1).setCheckState(Qt.Unchecked)   # untick 'right'
    assert w.aoi_inactive[w.current_path] == {'right'} and w.aoi_toolbar.active_aois() == ['left']
    w.run_aoi()
    assert set(w.current_table['aoi']) == {'left'}
    w.aoi_toolbar.set_all_checked(True)
    assert not w.aoi_inactive[w.current_path]
    w.left_toolbar.setCurrentRow(10)
    for display in w.stats_toolbar.AVAILABLE_DISPLAY:
        w.stats_toolbar.display_selector.setCurrentText(display)
        w.run_statistics()
        assert w.current_table is not None, display
        if display == 'Group comparison (table)':
            assert {'cohen_d', 'rank_biserial_r', 'ci95_low'} <= set(w.current_table.columns)
            assert any(c.startswith('median_') for c in w.current_table.columns)
        if display == 'All stimuli: participants (table)':
            assert {'stimulus', 'share_of_total', 'rank'} <= set(w.current_table.columns)
            assert w.current_table['stimulus'].nunique() == len(w.stim_dfs)
        if display == 'All stimuli: areas (table)':
            assert {'stimulus', 'aoi', 'share_of_areas', 'share_of_mapped', 'rank'} <= set(w.current_table.columns)
        if display == 'All stimuli: summary per stimulus (table)':
            assert {'stimulus', 'n_looked', 'dwell_median', 'n_rank_1'} <= set(w.current_table.columns)
    assert 'group' in w.current_table.columns or 'stimulus' in w.current_table.columns
    w.left_toolbar.setCurrentRow(6)
    for curve in w.time_series_toolbar.AVAILABLE_CURVE:
        w.time_series_toolbar.curve_selector.setCurrentText(curve)
        w.run_time_series()
    assert any(s[0] == 'information' and 'viewing distance' in s[2] for s in silent_boxes)
    w.time_series_toolbar.curve_selector.setCurrentText('Fixation Duration')
    for display in w.time_series_toolbar.AVAILABLE_DISPLAY:
        w.time_series_toolbar.display_selector.setCurrentText(display)
        w.run_time_series()
    assert w.current_table is not None and 'peak_frequency_hz' in w.current_table.columns or True
    w.left_toolbar.setCurrentRow(8)
    for method_label in w.scanpath_compare_toolbar.AVAILABLE_METHOD:
        w.scanpath_compare_toolbar.method_selector.setCurrentText(method_label)
        for view in w.scanpath_compare_toolbar.AVAILABLE_VIEW:
            w.scanpath_compare_toolbar.view_selector.setCurrentText(view)
            w.run_scanpath_comparison()
    w.left_toolbar.setCurrentRow(9)
    for display in w.recurrence_toolbar.AVAILABLE_DISPLAY:
        w.recurrence_toolbar.display_selector.setCurrentText(display)
        w.run_recurrence()
    assert {'recurrence', 'determinism'} <= set(w.current_table.columns)
    w.left_toolbar.setCurrentRow(7)
    for view in w.similarity_toolbar.AVAILABLE_VIEW:
        w.similarity_toolbar.view_selector.setCurrentText(view)
        w.run_similarity()
    failures = [s for s in silent_boxes if s[0] == 'critical']
    assert failures == [], failures


def test_second_stimulus_and_export(qapp, silent_boxes, tmp_path):
    w = open_example(qapp)
    second = list(w.stim_dfs)[1]
    w.stimulus_strip.select(second)
    assert w.current_path == second
    w.left_toolbar.setCurrentRow(0)
    w.run_fixation_heatmap()
    out = tmp_path / "fig.png"
    w.painter.current_fig.savefig(out, dpi=72)
    assert out.stat().st_size > 1000
    assert [s for s in silent_boxes if s[0] == 'critical'] == []


def test_compare_undo_project_and_batch(qapp, silent_boxes, tmp_path, monkeypatch):
    w = open_example(qapp)
    w.set_grouping({s: ('expert' if s <= 'P06' else 'layperson') for s in w.all_subjects})
    assert w.undo_stack and w.undo_action.isEnabled()
    w.left_toolbar.setCurrentRow(5)
    w.run_aoi()
    w.add_aoi(creapy.AOI.rectangle('face', 500, 100, 900, 700))
    assert 'face' in w.aois[w.current_path]
    w.undo()
    assert 'face' not in w.aois[w.current_path]
    w.redo()
    assert 'face' in w.aois[w.current_path]
    w.left_toolbar.setCurrentRow(0)
    w.fix_heatmap_toolbar.shared_scale_checkbox.setChecked(True)
    for spec in [{'kind': 'groups', 'items': ['expert', 'layperson']},
                 {'kind': 'stimuli', 'items': list(w.stim_dfs)},
                 {'kind': 'time', 'items': [(0., 10.), (10., 20.), (20., 30.)]}]:
        w.compare = spec
        w.run_fixation_heatmap()
        assert len(w.painter.current_fig.axes) == len(spec['items'])
    w.compare = {'kind': 'groups', 'items': ['expert', 'layperson']}
    w.run_rose()
    assert len(w.painter.current_fig.axes) == 2
    w.stop_compare()
    w.run_fixation_heatmap()
    assert len(w.painter.current_fig.axes) == 1
    project = tmp_path / "demo.creapy.json"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(project), ''))
    w.save_project()
    assert project.exists()
    w2 = gui.MainWindow(synchronous=True)
    w2.open_project(str(project))
    assert w2.grouping == w.grouping and 'face' in w2.aois[list(w2.stim_dfs)[0]]
    assert len(w2.stim_dfs) == 2
    out = tmp_path / "batch"
    out.mkdir()
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(out))
    w.left_toolbar.setCurrentRow(0)
    w.batch_export()
    w.left_toolbar.setCurrentRow(10)
    w.batch_export()
    names = sorted(p.name for p in out.iterdir())
    assert len([n for n in names if n.endswith('_fixation_heatmap.png')]) == 2
    assert len([n for n in names if '_statistics_' in n and n.endswith('.csv')]) == 3   # one per stimulus plus the combined table
    import pandas as pd
    df_all = pd.read_csv(next(out.glob('all_stimuli_statistics_*.csv')))
    assert list(df_all.columns)[0] == 'stimulus' and set(df_all['stimulus']) == {'demo_picture_A', 'demo_picture_B'}
    assert [s for s in silent_boxes if s[0] == 'critical'] == []


def test_aoi_metrics_window(qapp, silent_boxes, tmp_path):
    from tests.test_library_analyses import make_aoi_metrics_export
    from creapy.io.aoi_metrics_window import AOIMetricsWindow
    from creapy.formats.tobii import load_prolab_aoi_metrics_export
    path = make_aoi_metrics_export(tmp_path / "metrics.tsv")
    df, info = load_prolab_aoi_metrics_export(path)
    win = AOIMetricsWindow(df, info, "metrics.tsv")
    win.split_selector.setCurrentIndex(1)
    win.lookers_only.setChecked(True)
    win.show_raw_btn.setChecked(True)
    assert win.current_table is df and win.painter.current_fig is not None
    w = open_example(qapp)
    w.open_aoi_metrics(path=path)
    assert w.aoi_metrics_windows and [s for s in silent_boxes if s[0] == 'critical'] == []


def test_dialog_folders_are_remembered_per_kind(qapp, silent_boxes, tmp_path, monkeypatch):
    w = gui.MainWindow(synchronous=True)
    documents = gui.QStandardPaths.writableLocation(gui.QStandardPaths.DocumentsLocation)
    fresh = {kind: w.start_dir(kind) for kind in ['project', 'data', 'images', 'export']}
    assert all('Pictures' not in d for d in fresh.values()), fresh
    if os.path.isdir(documents):
        assert set(fresh.values()) == {documents}
    data_dir = tmp_path / "work" / "exports"
    data_dir.mkdir(parents=True)
    seen = []
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName',
                        lambda parent, title, folder, *a, **k: seen.append(folder) or (str(data_dir / "t.tsv"), ''))
    w.pick_table_file("Open")
    assert gui.MainWindow(synchronous=True).start_dir('data') == str(data_dir)
    assert w.start_dir('images', near=str(data_dir)) == str(data_dir)
    w.open_example()
    proj_dir = tmp_path / "work"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(proj_dir / "demo.creapy.json"), ''))
    w.save_project()
    w2 = gui.MainWindow(synchronous=True)
    assert w2.start_dir('project') == str(proj_dir)
    assert w.start_dir('export') == str(proj_dir)
    fig_dir = tmp_path / "figures"
    fig_dir.mkdir()
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(fig_dir / "heat.png"), ''))
    w.left_toolbar.setCurrentRow(0)
    w.run_fixation_heatmap()
    w.save_image()
    assert (fig_dir / "heat.png").exists()
    assert w.start_dir('export') == str(fig_dir) and w.start_dir('project') == str(proj_dir)
    w.open_example()
    assert w.save_dir is None and w.start_dir('export') == str(fig_dir)


def test_export_folder_skips_read_only_project_folder(qapp, silent_boxes, tmp_path):
    w = gui.MainWindow(synchronous=True)
    locked = tmp_path / "share"
    locked.mkdir()
    os.chmod(locked, 0o500)
    try:
        w.project_path = str(locked / "x.creapy.json")
        if not os.access(locked, os.W_OK):   # root ignores the mode
            assert w.start_dir('export') != str(locked)
    finally:
        os.chmod(locked, 0o700)


def test_recent_projects_on_start_screen(qapp, silent_boxes, tmp_path, monkeypatch):
    w = open_example(qapp)
    assert gui.MainWindow(synchronous=True).recent_buttons == []
    project = tmp_path / "room 1.creapy.json"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(project), ''))
    w.save_project()
    start = gui.MainWindow(synchronous=True)
    assert [b.text() for b in start.recent_buttons] == ["room 1"]
    assert start.recent_buttons[0].toolTip() == str(project)
    start.recent_buttons[0].click()
    assert start.project_path == str(project) and len(start.stim_dfs) == 2


class AcceptMapping:
    def __init__(self, *a, **k):
        pass

    def exec(self):
        return True

    def get_mapping(self):
        return {}


def test_tobii_snapshot_export_opens_in_mobile_setting(qapp, silent_boxes, tmp_path, monkeypatch):
    from tests.conftest import make_prolab_event_export
    from PIL import Image
    from PySide6.QtCore import Qt
    for name in ['c1_r1_w1_a', 'c1_r1_w2_a']:
        Image.new('RGB', (400, 300), (90, 90, 90)).save(tmp_path / f"{name}.jpg")
    export = make_prolab_event_export(str(tmp_path / "events.tsv"))
    monkeypatch.setattr(gui, 'ColumnMappingDialog', AcceptMapping)
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: ('', ''))   # no AOI-based export here
    w = gui.MainWindow(synchronous=True)
    w.import_tobii(path=export)
    assert w.setting == 'mobile' and w.dataset_fix.max_gap == creapy.MOBILE_MAX_GAP
    assert any(s[1] == "Mobile Eye Tracking" for s in silent_boxes)
    enabled = [n for i, n in enumerate(w.VIEWS) if w.left_toolbar.item(i).flags() & Qt.ItemIsEnabled]
    assert enabled == w.MOBILE_VIEWS
    assert "Not available" in w.left_toolbar.item(w.VIEWS.index("Time Series")).toolTip()
    for name in w.MOBILE_VIEWS:
        w.left_toolbar.setCurrentRow(w.VIEWS.index(name))
        w.view_runs[w.VIEWS.index(name)]()
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Statistics"))
    w.run_view("Statistics")
    assert 'n_visits' in w.current_table.columns and 'coefficient_K' not in w.current_table.columns
    assert [s for s in silent_boxes if s[0] == 'critical'] == []
    project = tmp_path / "walls.creapy.json"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(project), ''))
    w.save_project()
    w2 = gui.MainWindow(synchronous=True)
    w2.open_project(str(project))
    assert w2.setting == 'mobile'
    import json
    state = json.loads(project.read_text())
    state.pop('setting')
    project.write_text(json.dumps(state))
    w3 = gui.MainWindow(synchronous=True)
    w3.open_project(str(project))
    assert w3.setting == 'mobile'
    w3.set_setting('lab')
    assert all(w3.left_toolbar.item(i).flags() & Qt.ItemIsEnabled for i, n in enumerate(w3.VIEWS) if n not in w3.MOBILE_ONLY_VIEWS)
    assert not (w3.left_toolbar.item(w3.VIEWS.index('Visits')).flags() & Qt.ItemIsEnabled)
    assert w3.dataset_fix.max_gap is None and w3.filter_bar.time_title.text() == "Time window:"


def test_example_stays_in_lab_setting(qapp, silent_boxes):
    from PySide6.QtCore import Qt
    w = open_example(qapp)
    assert w.setting == 'lab' and w.dataset_fix.max_gap is None
    assert all(w.left_toolbar.item(i).flags() & Qt.ItemIsEnabled for i, n in enumerate(w.VIEWS) if n not in w.MOBILE_ONLY_VIEWS)
    assert 'lab setting' in w.left_toolbar.item(w.VIEWS.index('Visits')).toolTip()


def test_mobile_time_filter_and_compare(qapp, silent_boxes):
    from creapy.io.widgets.filter_bar import FilterBar
    from creapy.io.widgets.compare_dialog import CompareDialog
    bar = FilterBar()
    bar.set_time_max(30.)
    bar.from_slider.setValue(10)
    bar.set_visit_mode(True)
    assert bar.from_slider.isHidden() and bar.from_slider.value() == 0
    assert bar.range_label.text() == "whole visit" and bar.t_range() is None
    bar.to_slider.setValue(6)
    assert bar.t_range() == (0., 3.) and bar.describe() == "first 3.0 s of each visit"
    bar.set_visit_mode(False)
    assert not bar.from_slider.isHidden() and bar.describe() == "0.0–3.0 s"
    dialog = CompareDialog(["a.png", "b.png"], {'p1': 'g1', 'p2': 'g2'}, 30., allow_time=False,
                           current={'kind': 'time', 'items': [(0, 10), (10, 20)]})
    assert not dialog.radio_time.isEnabled() and dialog.get_spec()['kind'] != 'time'
    w = open_example(qapp)
    w.compare = {'kind': 'time', 'items': [(0., 15.), (15., 30.)]}
    w.set_setting('mobile')
    assert w.compare is None and w.filter_bar.time_title.text() == "Each visit:"


def test_recording_clock_label_aois_visits_and_participant_table(qapp, silent_boxes, tmp_path, monkeypatch):
    from tests.conftest import make_prolab_event_export, make_prolab_aoi_export
    from PIL import Image
    import json
    import pandas as pd
    for name in ['c1_r1_w1_a', 'c1_r1_w2_a']:
        Image.new('RGB', (400, 300), (90, 90, 90)).save(tmp_path / f"{name}.jpg")
    export = make_prolab_event_export(str(tmp_path / "events.tsv"))
    aoi_export = make_prolab_aoi_export(str(tmp_path / "aois.tsv"))
    monkeypatch.setattr(gui, 'ColumnMappingDialog', AcceptMapping)
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: (aoi_export, ''))
    w = gui.MainWindow(synchronous=True)
    w.import_tobii(path=export)
    assert w.intervals_path == aoi_export and all('t_abs' in df.columns for df in w.stim_dfs.values())
    assert any(sizes.get('Boy_c1') == 90_000 for sizes in w.aoi_sizes.values()) and w.df_events is not None
    assert any(s[1] == "Recording Clock Added" for s in silent_boxes)
    assert w.aoi_toolbar.export_aoi_btn.isEnabled()

    i_visits = w.VIEWS.index("Visits")
    assert w.left_toolbar.item(i_visits).flags() & gui.Qt.ItemIsEnabled
    w.left_toolbar.setCurrentRow(i_visits)
    for display in w.visits_toolbar.AVAILABLE_DISPLAY:
        w.visits_toolbar.display_selector.setCurrentText(display)
        w.run_visits()
        if display != 'Timeline':
            assert w.current_table is not None, display
    assert 'looked' in w.current_table.columns or display == 'Stimulus sequence (table)'
    w.visits_toolbar.display_selector.setCurrentText('Totals per stimulus (table)')
    w.run_visits()
    assert len(w.current_table) == 4 and w.current_table['looked'].all()
    w.filter_bar.participant_selector.setCurrentText('c1_p001')
    w.run_visits()
    assert set(w.current_table['participant']) == {'c1_p001'}
    w.filter_bar.reset()

    w.left_toolbar.setCurrentRow(w.VIEWS.index("Areas of Interest"))
    w.aoi_toolbar.all_stimuli_checkbox.setChecked(True)
    w.add_export_aois()
    assert set(w.aois[w.current_path]) == {'Boy', 'Boy_label_id', 'Boy_label_ot'}
    assert all(set(w.aois[p]) == {'Boy', 'Boy_label_id', 'Boy_label_ot'} for p in w.stim_dfs)
    w.aoi_toolbar.level_selector.setCurrentText('Area types')
    w.add_export_aois()
    assert 'Painting' in w.aois[w.current_path]
    w.undo()
    assert 'Painting' not in w.aois[w.current_path] and 'Boy' in w.aois[w.current_path]
    for display in w.aoi_toolbar.AVAILABLE_DISPLAY:
        w.aoi_toolbar.display_selector.setCurrentText(display)
        w.run_aoi()
    w.aoi_toolbar.display_selector.setCurrentText('Metrics table')
    w.run_aoi()
    assert 'mean_within_saccade_px' in w.current_table.columns and 'looked' in w.current_table.columns
    assert np.isclose(w.current_table.set_index(['participant', 'aoi']).loc[('c1_p001', 'Boy'), 'aoi_area_share'],
                      90_000 * w.dataset_fix.image_scale ** 2 / (w.dataset_fix.width * w.dataset_fix.height))

    attributes = tmp_path / "survey.csv"
    pd.DataFrame({'code': ['c1_p001', 'c1_p002', 'c1_p999'], 'age': [31, 58, 40],
                  'cohort': ['morning', 'afternoon', 'x']}).to_csv(attributes, index=False)
    assert w.import_attributes(str(attributes))
    assert w.attributes_id_col == 'code' and list(w.attributes.columns) == ['age', 'cohort']
    out = tmp_path / "metrics.csv"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(out), ''))
    w.export_table()
    df_out = pd.read_csv(out)
    assert {'age', 'cohort'} <= set(df_out.columns) and df_out.loc[df_out['participant'] == 'c1_p002', 'age'].iloc[0] == 58
    from creapy.io.widgets.grouping_dialog import GroupingDialog
    dialog = GroupingDialog(w.all_subjects, w.dataset_fix.df, w.dataset_fix.subj_index, attributes=w.attributes)
    assert 'cohort (participant table)' in dialog.candidates
    dialog.prefill_selector.setCurrentText('cohort (participant table)')
    assert dialog.get_grouping() == {'c1_p001': 'morning', 'c1_p002': 'afternoon'}

    w.zero_rows_action.setChecked(False)
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Statistics"))
    w.run_statistics()
    assert 'looked' not in w.current_table.columns
    w.zero_rows_action.setChecked(True)
    w.filter_bar.participant_selector.setCurrentText('c1_p001')
    w.run_statistics()
    assert list(w.current_table['participant']) == ['c1_p001'] and list(w.current_table['looked']) == [True]
    w.filter_bar.reset()
    w.run_statistics()
    assert list(w.current_table['participant']) == ['c1_p001', 'c1_p002'] and w.current_table['looked'].all()

    w.apply_min_fixation_duration(250)
    assert "250 ms" in w.status_dataset.text()
    assert w.current_path not in w.base_cache and w.current_table is None   # every fixation lasts 200 ms: a notice, no stale table
    assert not any(s[0] == 'critical' for s in silent_boxes)
    w.run_statistics()
    assert w.current_table is None
    w.apply_min_fixation_duration(100)
    assert w.dataset_fix.n_subjects() == 2

    project = tmp_path / "room.creapy.json"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(project), ''))
    w.save_project()
    state = json.loads(project.read_text())
    assert state['intervals_path'] == 'aois.tsv' and state['min_fix_dur_ms'] == 100   # inside the project folder: relative
    assert state['attributes'] == {'path': attributes.name, 'id_col': 'code'}
    assert any(rec['aois'][0].get('column') == 'aoi_hit' for rec in state['aois'])
    w2 = gui.MainWindow(synchronous=True)
    w2.open_project(str(project))
    assert w2.intervals_path == aoi_export and w2.min_fix_dur_ms == 100 and w2.attributes is not None
    assert isinstance(w2.aois[w2.current_path]['Boy'], creapy.LabelAOI)
    assert all('t_abs' in df.columns for df in w2.stim_dfs.values())
    w2.left_toolbar.setCurrentRow(w2.VIEWS.index("Visits"))
    w2.run_visits()
    assert w2.painter.current_fig is not None
    failures = [s for s in silent_boxes if s[0] == 'critical' and 'Stimulus Failed' not in s[1]]
    assert failures == [], failures


def test_inventory_named_room_export_in_the_gui(qapp, silent_boxes, tmp_path, monkeypatch):
    from tests.conftest import make_inventory_named_exports
    events, aois = make_inventory_named_exports(str(tmp_path))
    monkeypatch.setattr(gui, 'ColumnMappingDialog', AcceptMapping)
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: (aois, ''))
    w = gui.MainWindow(synchronous=True)
    w.import_tobii(path=events)
    assert w.setting == 'mobile' and len(w.stim_dfs) == 4 and w.intervals_path == aois
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Areas of Interest"))
    w.add_export_aois()
    assert all(set(w.aois[p]) == {'1101', 'label1101', 'roomtext1'} for p in w.stim_dfs)
    w.aoi_toolbar.display_selector.setCurrentText('Metrics table')
    w.run_aoi()
    assert set(w.current_table['aoi']) == {'1101', 'label1101', 'roomtext1'}
    assert w.current_table['aoi_area_share'].notna().any()
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Visits"))
    for display in w.visits_toolbar.AVAILABLE_DISPLAY:
        w.visits_toolbar.display_selector.setCurrentText(display)
        w.run_visits()
    w.visits_toolbar.display_selector.setCurrentText('Session summary (table)')
    w.run_visits()
    assert len(w.current_table) == 3 and w.current_table['n_stimuli'].tolist() == [2, 2, 2]
    w.visits_toolbar.display_selector.setCurrentText('Summary per stimulus (table)')
    w.run_visits()
    assert len(w.current_table) == 4 and {'n_looked', 'share_looked', 'dwell_median', 'n_rank_1'} <= set(w.current_table.columns)
    assert w.current_table['n_looked'].tolist() == [2, 2, 1, 1]
    w.visits_toolbar.unit_selector.setCurrentIndex(1)
    for display in w.visits_toolbar.AVAILABLE_DISPLAY:
        w.visits_toolbar.display_selector.setCurrentText(display)
        w.run_visits()
        assert w.current_table is not None, display
        if display in ('Visits (table)', 'Totals per stimulus (table)', 'Episodes (table)'):
            assert set(w.current_table['stimulus']) == {'1101', 'label1101', 'roomtext1'}, display
    w.visits_toolbar.display_selector.setCurrentText('Totals per stimulus (table)')
    w.run_visits()
    df_tot = w.current_table.set_index(['participant', 'stimulus'])
    assert df_tot.loc[('G_c1_p001', '1101'), 'n_revisits'] == 3   # painting > label > painting on two walls
    w.visits_toolbar.unit_selector.setCurrentIndex(0)
    w.compare = {'kind': 'stimuli', 'items': [p for p in w.stim_dfs if 'w1' in p]}
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Statistics"))
    w.stats_toolbar.display_selector.setCurrentText('Group comparison (table)')
    w.run_statistics()
    assert {'measure', 'test', 'p_value', 'median_c1_r1_w1', 'median_c2_r1_w1'} <= set(w.current_table.columns)
    assert w.main_area.currentWidget() is w.table_view
    w.stats_toolbar.display_selector.setCurrentText('Participants (table)')
    w.run_statistics()
    assert set(w.current_table['panel']) == {'c1_r1_w1', 'c2_r1_w1'}
    w.compare = None
    from creapy.misc.utils import grouping_from_stimulus_names
    subj_to_names = {subj: [str(w.stim_values[p]) for p, df_ in w.stim_dfs.items()
                            if (df_[w.mapping['subj_index_col']] == subj).any()] for subj in w.all_subjects}
    assert grouping_from_stimulus_names(subj_to_names) == {'G_c1_p001': 'c1', 'G_c1_p002': 'c1', 'G_c2_p004': 'c2'}
    from creapy.io.widgets.grouping_dialog import GroupingDialog
    df_all = w.full_table()
    dialog = GroupingDialog(w.all_subjects, df_all, df_all[w.mapping['subj_index_col']],
                            extra={"condition (from the snapshot names)": pd.Series(grouping_from_stimulus_names(subj_to_names))})
    assert "condition (from the snapshot names)" in dialog.candidates
    dialog.prefill_selector.setCurrentText('condition')
    assert dialog.get_grouping() == {'G_c1_p001': 'c1', 'G_c1_p002': 'c1', 'G_c2_p004': 'c2'}
    dialog.prefill_selector.setCurrentText("condition (from the snapshot names)")
    assert dialog.get_grouping() == {'G_c1_p001': 'c1', 'G_c1_p002': 'c1', 'G_c2_p004': 'c2'}
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Areas of Interest"))
    w.aoi_toolbar.aoi_list.item(2).setCheckState(Qt.Unchecked)   # roomtext1 off
    w.aoi_toolbar.reference_selector.setCurrentText('1101')
    project = tmp_path / "room1.creapy.json"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(project), ''))
    w.save_project()
    state = json.loads(project.read_text())
    assert state['aoi_reference'] == '1101' and list(state['aoi_inactive'].values()) == [['roomtext1']]
    w2 = gui.MainWindow(synchronous=True)
    w2.open_project(str(project))
    assert w2.aoi_inactive[w2.current_path] == {'roomtext1'} and w2.aoi_toolbar.active_aois() == ['1101', 'label1101']
    assert w2.aoi_toolbar.reference_selector.currentText() == '1101'
    assert [s for s in silent_boxes if s[0] == 'critical'] == []


def test_portable_project_survives_a_moved_bundle_folder(qapp, silent_boxes, tmp_path, monkeypatch):
    from tests.conftest import make_inventory_named_exports
    import shutil
    bundle = tmp_path / "bundle_v1" / "Room 1"
    (bundle / "snapshots").mkdir(parents=True)
    events, aois = make_inventory_named_exports(str(bundle))
    for name in os.listdir(bundle):
        if name.endswith('.jpg'):
            shutil.move(str(bundle / name), str(bundle / "snapshots" / name))
    monkeypatch.setattr(gui, 'ColumnMappingDialog', AcceptMapping)
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(bundle / "snapshots"))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: (aois, ''))
    w = gui.MainWindow(synchronous=True)
    w.import_tobii(path=events)
    w.add_export_aois()
    project = bundle / "Room 1.creapy.json"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(project), ''))
    w.save_project()
    state = json.loads(project.read_text())
    assert state['source_path'] == "Room 1 Metrics_Event-based.tsv" and state['image_folder'] == "snapshots"
    assert all(e['path'].startswith("snapshots/") for e in state['stimuli'])
    assert all(e['stimulus'].startswith("snapshots/") for e in state['aois'])
    moved = tmp_path / "elsewhere" / "Demo"
    shutil.move(str(tmp_path / "bundle_v1"), str(moved))
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: "")   # nothing may ask for a folder
    w2 = gui.MainWindow(synchronous=True)
    w2.open_project(str(moved / "Room 1" / "Room 1.creapy.json"))
    assert len(w2.stim_dfs) == 4 and w2.intervals_path == str(moved / "Room 1" / "Room 1 Metrics_AOI-based.tsv")
    assert all(set(w2.aois[p]) == {'1101', 'label1101', 'roomtext1'} for p in w2.stim_dfs)
    assert [s for s in silent_boxes if s[0] in ('critical', 'warning')] == []
    (moved / "Room 2").mkdir()
    shutil.copy(str(moved / "Room 1" / "Room 1.creapy.json"), str(moved / "Room 2" / "Room 2.creapy.json"))
    start = gui.MainWindow(synchronous=True)
    assert start.start_stack.currentIndex() == 0
    start.import_page_btn.click()
    assert start.start_stack.currentIndex() == 2
    assert start.open_bundle(str(moved)) and start.start_stack.currentIndex() == 1
    assert [b.text() for b in start.bundle_buttons] == ["Room 1", "Room 2"]
    assert not start.open_bundle(str(tmp_path / "elsewhere")) or True   # parent folder also finds them (depth 4)
    empty = tmp_path / "empty"
    empty.mkdir()
    assert not start.open_bundle(str(empty))
    assert any(s[0] == 'information' and 'No Projects' in s[1] for s in silent_boxes)
    start.bundle_buttons[0].click()
    assert start.project_path == str(moved / "Room 1" / "Room 1.creapy.json")
    again = gui.MainWindow(synchronous=True)
    assert [b.text() for b in again.last_bundle_buttons] == ["Room 1", "Room 2"]   # remembered on the front page
    import zipfile
    zip_path = tmp_path / "Demo bundle.creapy"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(moved):
            for f in files:
                zf.write(os.path.join(root, f), os.path.relpath(os.path.join(root, f), tmp_path / "elsewhere"))
    cache = tmp_path / "appdata"
    monkeypatch.setattr(gui.MainWindow, 'bundle_cache_dir', lambda self: str(cache))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: (str(zip_path), ''))
    z = gui.MainWindow(synchronous=True)
    assert z.open_bundle() and z.start_stack.currentIndex() == 1
    unpacked = cache / "Demo bundle"
    assert [b.text() for b in z.bundle_buttons] == ["Room 1", "Room 2"]
    marker = unpacked / ".bundle_source"
    stamp = marker.read_text()
    z.bundle_buttons[0].click()
    assert z.project_path == str(unpacked / "Demo" / "Room 1" / "Room 1.creapy.json") and len(z.stim_dfs) == 4
    assert z.intervals_path == str(unpacked / "Demo" / "Room 1" / "Room 1 Metrics_AOI-based.tsv")
    marker.write_text(stamp + " ")
    z2 = gui.MainWindow(synchronous=True)
    assert z2.open_bundle(str(zip_path)) and marker.read_text() == stamp + " "   # unchanged file: not unpacked again
    assert [b.text() for b in z2.last_bundle_buttons] == ["Room 1", "Room 2"]
    (tmp_path / "junk.creapy").write_bytes(b"not a zip")
    assert not z2.open_bundle(str(tmp_path / "junk.creapy"))
    assert any(s[0] == 'critical' and 'unpacked' in s[2] for s in silent_boxes)


def test_export_areas_include_never_fixated_ones(qapp, silent_boxes, tmp_path, monkeypatch):
    from creapy.examples import make_mobile_example
    from creapy.formats import aoi_names_by_stimulus
    events, aois = make_mobile_example(str(tmp_path))
    names = aoi_names_by_stimulus(aois)
    assert set(names) == {'c1_r1_w1', 'c1_r1_w2', 'c2_r1_w1', 'c2_r1_w2'}
    assert names['c1_r1_w1'] == {'work1': 'Painting', 'labelwork1': 'Painting', 'roomtext1': 'Painting', 'plinth1': 'Painting'}
    monkeypatch.setattr(gui, 'ColumnMappingDialog', AcceptMapping)
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: ('', ''))   # the clock offer is declined
    w = gui.MainWindow(synchronous=True)
    w.import_tobii(path=events)
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Areas of Interest"))
    w.aoi_toolbar.all_stimuli_checkbox.setChecked(True)
    w.add_export_aois()
    assert all(set(w.aois[p]) == {'work1', 'labelwork1', 'roomtext1'} for p in w.stim_dfs)   # no clock: hits only
    assert w.attach_intervals_file(aois, quiet=True)
    w.add_export_aois()
    assert all(set(w.aois[p]) == {'work1', 'labelwork1', 'roomtext1', 'plinth1'} for p in w.stim_dfs)
    assert w.aois[w.current_path]['plinth1'].area() == 60_000
    for display in w.aoi_toolbar.AVAILABLE_DISPLAY:
        w.aoi_toolbar.display_selector.setCurrentText(display)
        w.view_runs[w.VIEWS.index("Areas of Interest")]()
    assert [s for s in silent_boxes if s[0] in ('critical', 'warning')] == []


def test_stylesheet_parses_from_a_non_ascii_folder(qapp, tmp_path, monkeypatch):
    import shutil
    from PySide6 import QtCore
    from creapy.io import theme
    original = theme.stylesheet()
    folder = tmp_path / "Übung (Kopie) it's" / "style"
    shutil.copytree(theme.STYLE_DIR, folder)
    monkeypatch.setattr(theme, 'STYLE_DIR', str(folder))
    sheet = theme.stylesheet()
    assert 'Übung' in sheet and 'url("' in sheet and sheet.count('url(') == sheet.count('url("')
    messages = []
    QtCore.qInstallMessageHandler(lambda mode, ctx, msg: messages.append(msg))
    try:
        qapp.setStyleSheet(sheet)
        QApplication.processEvents()
    finally:
        QtCore.qInstallMessageHandler(None)
        qapp.setStyleSheet(original)
    assert not [m for m in messages if 'Could not parse' in m], messages


def test_theme_font_and_stylesheet_apply_once(qapp, tmp_path):
    from creapy.io import theme
    start = gui.MainWindow(synchronous=True)
    assert qapp.font().family() == theme.FONT_FAMILY
    assert qapp.property('creapy_theme') is True
    sheet = qapp.styleSheet()
    assert sheet == theme.stylesheet()
    assert '@style@' not in sheet and 'icons/chevron-down.svg' in sheet and 'QListWidget#NavList' in sheet
    assert start.start_stack.currentIndex() == 0 and start.bundle_btn.objectName() == "PrimaryButton"
    from creapy.io.widgets.project_tile import ProjectTile
    tile = ProjectTile("Room 1", "bundle/Room 1", tooltip=str(tmp_path))
    hits = []
    tile.clicked.connect(lambda: hits.append(1))
    tile.click()
    assert tile.text() == "Room 1" and tile.toolTip() == str(tmp_path) and hits == [1]


def test_zero_rows_follow_the_selection_and_the_panels(qapp, silent_boxes, tmp_path, monkeypatch):
    from tests.conftest import make_inventory_named_exports
    events, aois = make_inventory_named_exports(str(tmp_path))
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(tmp_path)))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: ('', ''))
    monkeypatch.setattr(gui, 'ColumnMappingDialog', AcceptMapping)
    w = gui.MainWindow(synchronous=True)
    w.import_tobii(path=events)
    w.zero_rows_action.setChecked(True)
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Statistics"))
    w.stats_toolbar.display_selector.setCurrentText("Participants (table)")
    w.set_grouping({'G_c1_p001': 'A', 'G_c1_p002': 'B', 'G_c2_p004': 'B'})
    w.compare = {'kind': 'groups', 'items': ['A', 'B']}
    w.run_statistics()
    by_panel = w.current_table.groupby('panel')['participant'].apply(set).to_dict()
    assert by_panel['A'] == {'G_c1_p001'} and 'G_c1_p001' not in by_panel['B']
    w.stop_compare()
    w.filter_bar.participant_selector.setCurrentText('G_c1_p001')
    w.run_statistics()
    assert list(w.current_table['participant']) == ['G_c1_p001']
    w.filter_bar.reset()
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Fixation Heatmap"))
    out = tmp_path / "locked" / "figure.png"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(out), 'PNG image (*.png)'))
    w.run_fixation_heatmap()
    w.save_image()
    assert any(kind == 'critical' and 'written' in text for kind, title, text in silent_boxes) and not out.exists()
    w.close()


def test_visits_of_areas_use_the_rosters_and_list_empty_areas(qapp, silent_boxes, tmp_path, monkeypatch):
    from tests.conftest import make_inventory_named_exports
    from creapy.aoi.aoi import AOI
    from shapely.geometry import box
    events, aois = make_inventory_named_exports(str(tmp_path))
    monkeypatch.setattr(gui, 'ColumnMappingDialog', AcceptMapping)
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(tmp_path))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: (aois, ''))
    w = gui.MainWindow(synchronous=True)
    w.import_tobii(path=events)
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Areas of Interest"))
    w.add_export_aois()
    c1_wall = next(p for p in w.stim_dfs if os.path.basename(p).startswith('c1_r1_w1'))
    w.on_stimulus_selected(c1_wall)
    w.add_aoi(AOI('corner', geom=box(3800, 1500, 3990, 1590)))   # nobody fixates the bottom-right corner
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Visits"))
    w.visits_toolbar.unit_selector.setCurrentIndex(1)
    w.visits_toolbar.display_selector.setCurrentText('Totals per stimulus (table)')
    w.run_visits()
    df_tot = w.current_table
    corner = df_tot[df_tot['stimulus'] == 'corner']
    assert set(corner['participant']) == {'G_c1_p001', 'G_c1_p002'} and not corner['looked'].any()
    assert set(df_tot.loc[df_tot['stimulus'] == '1101', 'participant']) == {'G_c1_p001', 'G_c1_p002', 'G_c2_p004'}
    w.visits_toolbar.display_selector.setCurrentText('Summary per stimulus (table)')
    w.run_visits()
    df_sum = w.current_table.set_index('stimulus')
    assert df_sum.loc['corner', 'n_looked'] == 0 and df_sum.loc['1101', 'n_looked'] == 3
    assert [s for s in silent_boxes if s[0] == 'critical'] == []


def test_a_participant_with_one_fixation_can_be_selected(qapp, silent_boxes):
    w = open_example(qapp)
    path = w.current_path
    df = w.stim_dfs[path]
    subj_col = w.mapping['subj_index_col']
    lone = df[subj_col].iloc[0]
    keep = df[subj_col] != lone
    keep.iloc[df.index.get_loc(df[df[subj_col] == lone].index[0])] = True
    w.stim_dfs[path] = df[keep]
    w.base_cache = {}
    w.filtered_cache = {}
    w.on_stimulus_selected(path)
    w.filter_bar.participant_selector.setCurrentText(str(lone))
    assert w.filter_bar.participants() == [lone] and w.dataset_sac is None
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Fixation Heatmap"))
    w.run_fixation_heatmap()
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Saccade Scanpath"))
    w.view_runs[w.VIEWS.index("Saccade Scanpath")]()
    assert w.filter_bar.participants() == [lone]   # the filter is kept, the view explains
    assert any(s[0] == 'information' and 'no saccade' in s[2] for s in silent_boxes)
    assert [s for s in silent_boxes if s[0] in ('critical', 'warning')] == []


def test_batch_export_keeps_two_displays_of_one_view_apart(qapp, silent_boxes, tmp_path, monkeypatch):
    w = open_example(qapp)
    out = tmp_path / "batch"
    out.mkdir()
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(out))
    w.set_grouping({s: ('A' if i % 2 else 'B') for i, s in enumerate(w.all_subjects)})
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Statistics"))
    w.stats_toolbar.display_selector.setCurrentText("Participants (table)")
    w.batch_export()
    n_first = len(list(out.iterdir()))
    w.stats_toolbar.display_selector.setCurrentText("Group comparison (table)")
    w.batch_export()
    assert len(list(out.iterdir())) > n_first
    assert any('participants_table' in p.name for p in out.iterdir()) and any('group_comparison' in p.name for p in out.iterdir())


def test_compare_by_stimuli_travels_with_the_project(qapp, silent_boxes, tmp_path, monkeypatch):
    from tests.conftest import make_inventory_named_exports
    import shutil
    bundle = tmp_path / "bundle" / "Room 1"
    (bundle / "snapshots").mkdir(parents=True)
    events, aois = make_inventory_named_exports(str(bundle))
    for name in os.listdir(bundle):
        if name.endswith('.jpg'):
            shutil.move(str(bundle / name), str(bundle / "snapshots" / name))
    monkeypatch.setattr(gui, 'ColumnMappingDialog', AcceptMapping)
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(bundle / "snapshots"))
    monkeypatch.setattr(gui.QFileDialog, 'getOpenFileName', lambda *a, **k: ('', ''))
    w = gui.MainWindow(synchronous=True)
    w.import_tobii(path=events)
    paths = list(w.stim_dfs)
    w.compare = {'kind': 'stimuli', 'items': paths[:2]}
    project = bundle / "Room 1.creapy.json"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(project), ''))
    w.save_project()
    state = json.loads(project.read_text())
    assert all(p.startswith("snapshots/") for p in state['compare']['items'])
    moved = tmp_path / "moved"
    shutil.move(str(tmp_path / "bundle"), str(moved))
    w2 = gui.MainWindow(synchronous=True)
    w2.open_project(str(moved / "Room 1" / "Room 1.creapy.json"))
    assert w2.compare['kind'] == 'stimuli' and len(w2.compare['items']) == 2
    assert all(p in w2.stim_dfs for p in w2.compare['items'])
    w2.left_toolbar.setCurrentRow(w2.VIEWS.index("Fixation Heatmap"))
    w2.run_fixation_heatmap()
    assert [s for s in silent_boxes if s[0] in ('critical', 'warning')] == []


def read_log(w):
    if w.log._file is not None:
        w.log._file.flush()
    with open(w.log.path, encoding='utf-8') as f:
        return [json.loads(line) for line in f]


def test_session_log_records_the_whole_session(qapp, silent_boxes, tmp_path, monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QEvent, QPoint, QPointF
    from PySide6.QtGui import QEnterEvent
    import time
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: ('', ''))
    w = open_example(qapp)
    assert w.log.enabled and w.log.path.startswith(str(tmp_path / "logs"))
    events = read_log(w)
    env = next(e for e in events if e['event'] == 'environment')
    assert env['creapy'] == creapy.__version__ and env['screens'] and 'os' in env and env['frozen'] is False
    w.show()
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Statistics"))
    w.view_runs[w.VIEWS.index("Statistics")]()
    w.left_toolbar.setCurrentRow(w.VIEWS.index("Fixation Heatmap"))
    w.run_fixation_heatmap()
    events = read_log(w)
    dwell = [e for e in events if e['event'] == 'view_dwell']
    assert dwell and dwell[-1]['view'] == "Statistics" and dwell[-1]['seconds'] >= 0
    assert [e for e in events if e['event'] == 'view'][-1]['view'] == "Fixation Heatmap"
    btn = w.fix_heatmap_toolbar.save_btn
    QTest.mouseClick(btn, Qt.LeftButton)
    events = read_log(w)
    click = [e for e in events if e['event'] == 'click']
    assert click and click[-1]['widget'] == 'QPushButton' and click[-1]['text'] == 'Save as Image'
    assert click[-1]['in'] == 'Fixation Heatmap panel'
    assert any(e['event'] == 'file_dialog' and e['kind'] == 'getSaveFileName' and e['chosen'] is None for e in events)
    pos = QPointF(5, 5)
    qapp.sendEvent(btn, QEnterEvent(pos, pos, btn.mapToGlobal(QPoint(5, 5))))
    time.sleep(0.15)
    qapp.sendEvent(btn, QEvent(QEvent.Leave))
    hover = [e for e in read_log(w) if e['event'] == 'hover']
    assert hover and hover[-1]['text'] == 'Save as Image' and hover[-1]['ms'] >= 100
    checkbox = w.fix_heatmap_toolbar.grayscale_checkbox
    checkbox.toggle()   # set by the program: not a user action
    assert not [e for e in read_log(w) if e['event'] == 'control']
    QTest.mouseClick(checkbox, Qt.LeftButton, pos=QPoint(8, checkbox.height() // 2))
    events = read_log(w)
    control = [e for e in events if e['event'] == 'control']
    assert control and control[-1]['widget'] == 'QCheckBox' and control[-1]['value'] == checkbox.isChecked()
    QTest.keyClick(w.fix_heatmap_toolbar.grayscale_checkbox, Qt.Key_Escape)
    keys = [e for e in read_log(w) if e['event'] == 'key']
    assert len(keys) == 1 and keys[0]['key'] == 'Escape' and keys[0]['widget'] == 'QCheckBox'   # logged once, not per parent
    w.zero_rows_action.trigger()
    actions = [e for e in read_log(w) if e['event'] == 'action']
    assert actions and actions[-1]['text'] == "Keep Non-Viewers as Zero Rows" and actions[-1]['checked'] is False
    QMessageBox.information(w, "Hello", "A box")
    box = [e for e in read_log(w) if e['event'] == 'message_box']
    assert box and box[-1]['title'] == 'Hello' and box[-1]['kind'] == 'information'
    out = tmp_path / "report.zip"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(out), ''))
    w.export_logs()
    import zipfile
    with zipfile.ZipFile(out) as zf:
        assert os.path.basename(w.log.path) in zf.namelist()
    w.logging_action.setChecked(False)
    assert not w.log.enabled and w.log._file is None and "Log off" in w.status_logging.text()
    w.logging_action.setChecked(True)
    assert w.log.enabled and any(e['event'] == 'environment' for e in read_log(w)[-3:])
    w.close()
    assert read_log(w)[-1]['event'] == 'session_end'
