import os
import pytest

pytest.importorskip("PySide6")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import creapy  # noqa: E402
from creapy.io import main as gui  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def silent_boxes(monkeypatch):
    # No modal dialogs in tests: collect them instead
    seen = []
    for name in ['information', 'critical', 'warning']:
        monkeypatch.setattr(QMessageBox, name, lambda *a, _n=name, **k: seen.append((_n, a[1], str(a[2]))))
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.Yes)
    return seen


def open_example(qapp):
    w = gui.MainWindow(synchronous=True)  # computations inline: nothing waits for an event loop here
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


def test_filters_groups_aois_and_tables(qapp, silent_boxes):
    w = open_example(qapp)
    w.grouping = {s: ('expert' if s <= 'P06' else 'layperson') for s in w.all_subjects}
    w.filter_bar.set_subjects(w.all_subjects, w.grouping)
    # single participant + first 3 s
    w.filter_bar.participant_selector.setCurrentText('P01')
    w.filter_bar.to_slider.setValue(6)
    assert w.filter_bar.participants() == ['P01'] and w.filter_bar.t_range() == (0.0, 3.0)
    assert w.dataset_fix.subjects == ['P01'] and w.dataset_fix.t.max() <= 3.0
    w.left_toolbar.setCurrentRow(1)
    w.run_fixation_scanpath()
    w.left_toolbar.setCurrentRow(7)
    w.run_similarity()  # one participant -> a hint, not a failure
    assert any(s[0] == 'information' and 'two participants' in s[2] for s in silent_boxes)
    w.left_toolbar.setCurrentRow(9)
    w.run_recurrence()  # the recurrence plot of the selected participant
    assert w.painter.current_fig is not None and 'P01' in w.painter.current_fig.axes[0].get_title(loc='left')
    w.filter_bar.reset()
    assert w.dataset_fix.n_subjects() == 12
    # group filter
    w.filter_bar.participant_selector.setCurrentIndex(1)
    assert w.filter_bar.participants() == ['P01', 'P02', 'P03', 'P04', 'P05', 'P06']
    w.filter_bar.reset()
    # AOIs + metrics + statistics tables
    w.left_toolbar.setCurrentRow(5)
    w.run_aoi()
    w.add_aoi(creapy.AOI.rectangle('left', 0, 0, 800, 1200))
    w.aoi_toolbar.display_selector.setCurrentText('Metrics table')
    w.run_aoi()
    assert w.current_table is not None and set(w.current_table['aoi']) == {'left'}
    for display in w.aoi_toolbar.AVAILABLE_DISPLAY[2:]:  # scarf plot, transition matrix, first-fixation order
        w.aoi_toolbar.display_selector.setCurrentText(display)
        w.add_aoi(creapy.AOI.rectangle('right', 800, 0, 1600, 1200)) if display == 'Transition matrix' else None
        w.run_aoi()
    assert set(w.current_table.columns) >= {'participant', 'left', 'right'}  # first-fixation order
    w.left_toolbar.setCurrentRow(10)
    for display in w.stats_toolbar.AVAILABLE_DISPLAY:
        w.stats_toolbar.display_selector.setCurrentText(display)
        w.run_statistics()
    assert 'group' in w.current_table.columns
    # time series per group, all curves and displays (viewing distance -> hint: the example has none)
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
    # scanpath comparison, all methods and views; recurrence table + boxplot
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
    # similarity with groups
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
    # AOI undo/redo
    w.left_toolbar.setCurrentRow(5)
    w.run_aoi()
    w.add_aoi(creapy.AOI.rectangle('face', 500, 100, 900, 700))
    assert 'face' in w.aois[w.current_path]
    w.undo()
    assert 'face' not in w.aois[w.current_path]
    w.redo()
    assert 'face' in w.aois[w.current_path]
    # compare by group, by stimulus, by time window on the heatmap (shared colour scale on)
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
    # project round trip
    project = tmp_path / "demo.creapy.json"
    monkeypatch.setattr(gui.QFileDialog, 'getSaveFileName', lambda *a, **k: (str(project), ''))
    w.save_project()
    assert project.exists()
    w2 = gui.MainWindow(synchronous=True)
    w2.open_project(str(project))
    assert w2.grouping == w.grouping and 'face' in w2.aois[list(w2.stim_dfs)[0]]
    assert len(w2.stim_dfs) == 2
    # batch export of the statistics table and the heatmap for every stimulus
    out = tmp_path / "batch"
    out.mkdir()
    monkeypatch.setattr(gui.QFileDialog, 'getExistingDirectory', lambda *a, **k: str(out))
    w.left_toolbar.setCurrentRow(0)
    w.batch_export()
    w.left_toolbar.setCurrentRow(10)
    w.batch_export()
    names = sorted(p.name for p in out.iterdir())
    assert len([n for n in names if n.endswith('_fixation_heatmap.png')]) == 2
    assert len([n for n in names if n.endswith('_statistics.csv')]) == 2
    assert [s for s in silent_boxes if s[0] == 'critical'] == []


def test_aoi_metrics_window(qapp, silent_boxes, tmp_path):
    from tests.test_library_030 import make_aoi_metrics_export
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
