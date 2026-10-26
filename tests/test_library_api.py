"""
The library promise (DHd 2026): everything the GUI shows is reachable as a plain, documented, Qt-free library call.
"""
import inspect
import importlib
import os
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pytest

import creapy
from creapy.examples import example_dataset

PUBLIC_MODULES = ['creapy', 'creapy.gaze.base', 'creapy.gaze.fixation', 'creapy.gaze.saccade', 'creapy.gaze.convert',
                  'creapy.aoi.aoi', 'creapy.aoi.sequence', 'creapy.stats.descriptives', 'creapy.stats.timeseries',
                  'creapy.stats.recurrence', 'creapy.stats.spectrum', 'creapy.similarity.heatmatch_result',
                  'creapy.similarity.scanpath', 'creapy.formats.table', 'creapy.formats.detect', 'creapy.formats.tobii',
                  'creapy.misc.utils', 'creapy.misc.contours', 'creapy.examples']


@pytest.fixture(scope='module')
def example():
    path = example_dataset()
    df, mapping = creapy.load_fixations(path)
    datasets = creapy.datasets_by_stimulus(df, mapping, stimulus_paths=os.path.dirname(path))  # folder search
    fix, sac = datasets['demo_picture_A.png']
    grouping = {s: ('expert' if s <= 'P06' else 'layperson') for s in fix.subjects}
    return fix, sac, grouping


def test_every_public_callable_has_a_docstring():
    missing = []
    for module_name in PUBLIC_MODULES:
        module = importlib.import_module(module_name)
        for name, obj in vars(module).items():
            if name.startswith('_') or getattr(obj, '__module__', None) != module_name:
                continue
            if inspect.isfunction(obj):
                if not obj.__doc__:
                    missing.append(f"{module_name}.{name}")
            elif inspect.isclass(obj):
                if not obj.__doc__:
                    missing.append(f"{module_name}.{name}")
                for mname, member in vars(obj).items():
                    if mname.startswith('_'):
                        continue
                    fn = member.__func__ if isinstance(member, (staticmethod, classmethod)) else member
                    if inspect.isfunction(fn) and not fn.__doc__:
                        missing.append(f"{module_name}.{name}.{mname}")
    assert not missing, "public API without docstring:\n" + "\n".join(missing)


def test_library_imports_without_qt(tmp_path):
    # A library-only install (pip install creapy, no [gui]) must import and run the quickstart with PySide6 absent
    import subprocess
    code = """
import sys
sys.modules['PySide6'] = None  # makes every 'import PySide6' raise ImportError
import creapy
from creapy.examples import example_dataset
import os
path = example_dataset()
df, mapping = creapy.load_fixations(path)
fix, sac = next(iter(creapy.datasets_by_stimulus(df, mapping, stimulus_paths=os.path.dirname(path)).values()))
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig, ax = plt.subplots(); fix.make_heatmap(ax, bw_method=0.1)
print(len(creapy.participant_table(fix, sac)))
"""
    out = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, timeout=600)
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "12"


def test_time_series_functions(example):
    fix, sac, grouping = example
    from creapy.stats.timeseries import value_series, smoothed_curve, show_smoothed_curve, MEASURES
    for measure in ['fixation_duration', 'saccade_amplitude', 'coefficient_k', 'pupil', 'Fixation Duration']:
        data, values, ylabel = value_series(fix, sac, measure)
        assert len(values) == len(data.df) and ylabel
        t, m, s = smoothed_curve(data, values, sigma=2.)
        assert len(t) == len(m) == len(s) and np.isfinite(m).sum() > 0
    with pytest.raises(ValueError):
        value_series(fix, sac, 'viewing_distance')  # the synthetic data has none
    with pytest.raises(ValueError):
        value_series(fix, sac, 'nonsense')
    fig, ax = plt.subplots()
    for name, fix_g, sac_g in creapy.split_by_group(fix, sac, grouping):
        t, m = creapy.show_measure_curve(fix_g, sac_g, 'coefficient_k', sigma=2., ax=ax, label=name)
        assert fix_g.n_subjects() == 6
    assert len(ax.get_lines()) >= 4  # solid + dashed per group (+ zero line)
    plt.close(fig)
    # the per-fixation K of the library equals what participant_table aggregates
    k = creapy.fixation_k(fix)
    df_stats = creapy.participant_table(fix, sac)
    k_first = pd.Series(k).groupby(fix.subj_index.to_numpy()).mean()[df_stats['participant'].iloc[0]]
    assert np.isclose(k_first, df_stats['coefficient_K'].iloc[0])


def test_group_boxplot_and_score_overview(example):
    fix, sac, grouping = example
    df_stats = creapy.participant_table(fix, sac)
    fig, ax = plt.subplots()
    names = creapy.show_group_boxplot(df_stats, 'coefficient_K', grouping, ax=ax)
    assert names == ['expert', 'layperson']
    assert [t.get_text() for t in ax.get_xticklabels()] == ['expert (n=6)', 'layperson (n=6)']
    plt.close(fig)
    with pytest.raises(AssertionError):
        creapy.show_group_boxplot(df_stats, 'coefficient_K', ax=ax)  # no groups at all
    mm = fix.compute_scanpath_similarity('multimatch', verbose=False)
    df_over = mm.score_overview(grouping)
    assert list(df_over.columns) == ['measure', 'all pairs', 'within groups', 'between groups']
    assert len(df_over) == len(mm.scores) and df_over['all pairs'].between(0, 1).all()
    assert list(mm.score_overview().columns) == ['measure', 'all pairs']
    fig, ax = plt.subplots()
    df_bars = mm.show_score_overview(grouping, ax=ax)
    assert len(ax.patches) == 3 * len(mm.scores)
    assert ax.get_xticklabels()[0].get_text() == mm.scores[0].replace('mm_', '')
    plt.close(fig)


def test_reference_generator_runs(tmp_path):
    import runpy, os, shutil
    src = os.path.join(os.path.dirname(__file__), '..', 'docs', 'make_library_reference.py')
    assert os.path.exists(src)
    # run it against a copy so the repo file is only rewritten on purpose
    shutil.copy(src, tmp_path / 'make_library_reference.py')
    runpy.run_path(str(tmp_path / 'make_library_reference.py'), run_name='__main__')
    text = (tmp_path / 'LIBRARY.md').read_text(encoding='utf-8')
    assert '### `creapy.stats.timeseries`' in text and 'show_measure_curve' in text
