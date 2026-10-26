"""0.3.0 library additions: shared colour scale, AOI sequences, generic pairwise results, Tobii extras."""
import numpy as np
import pandas as pd
import pytest
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import creapy
from creapy import FixationData, SaccadeData, AOI, fixations_to_saccades
from creapy.aoi.sequence import aoi_sequence, transition_matrix, show_scarf_plot, show_transition_matrix, \
    first_fixation_order, collapse_runs
from creapy.similarity.heatmatch_result import PairwiseSimilarityResult
from creapy.misc.contours import contour_levels, filled_contour_paths
from creapy.formats.tobii import load_prolab_aoi_metrics_export, aoi_metrics_summary, load_prolab_data_export, \
    load_prolab_data_export_chunked
from tests.conftest import make_prolab_export


def test_contour_paths_match_matplotlib():
    x, y = np.meshgrid(np.linspace(0, 400, 60), np.linspace(0, 300, 50))
    z = np.exp(-((x - 200) ** 2 + (y - 150) ** 2) / 5000) + 0.3 * np.exp(-((x - 50) ** 2 + (y - 50) ** 2) / 3000)
    for n in [3, 10, 20]:
        fig, ax = plt.subplots()
        cs = ax.contourf(x, y, z, levels=n)
        ref = cs.get_paths()
        plt.close(fig)
        lev = contour_levels(z.min(), z.max(), n)
        assert np.allclose(lev, cs.levels)
        got = filled_contour_paths(x, y, z, lev)
        assert len(got) == len(ref)
        for a, b in zip(got, ref):
            assert np.allclose(a.vertices, b.vertices)


def test_heatmap_shared_scale(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    vmax = fix.heatmap_max(bw_method=0.2)
    assert vmax > 0
    sub = fix.subset(subjects=['vp1'])
    fig, ax = plt.subplots()
    sub.make_heatmap(ax, bw_method=0.2, num_levels=8, vmax=vmax)  # saturates where denser than the whole group
    sub.make_heatmap(ax, bw_method=0.2, num_levels=8)
    plt.close(fig)
    assert (0.2, 8, vmax) in sub.cache_heatmap_contour and (0.2, 8, None) in sub.cache_heatmap_contour
    assert len(sub.cache_heatmap_contour[(0.2, 8, vmax)]) == 8
    sub.prepare_heatmap(bw_method=0.3, num_levels=5)
    assert (0.3, 5, None) in sub.cache_heatmap_contour


def test_aoi_sequences_transitions_and_scarf(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    fix.set_top_down_aoi('left', AOI.rectangle('left', 0, 0, 200, 300).geom)
    fix.set_top_down_aoi('right', AOI.rectangle('right', 200, 0, 400, 300).geom)
    df_seq = aoi_sequence(fix)
    assert len(df_seq) == len(fix.df) and set(df_seq['aoi']) <= {'left', 'right', 'outside'}
    assert (df_seq['aoi'] != 'outside').all()  # the two AOIs cover the image
    df_runs = collapse_runs(df_seq)
    assert (df_runs['n_fixations'] >= 1).all() and df_runs['dwell'].sum() == pytest.approx(fix.fix_dur.sum())
    m = transition_matrix(fix, normalize='row')
    assert list(m.index) == ['left', 'right'] and np.allclose(m.sum(axis=1), 1.)
    assert m.loc['left', 'left'] == 0  # visits collapse self-transitions
    counts = transition_matrix(fix, normalize=None, per_participant_weight=False)
    assert counts.to_numpy().sum() == len(df_runs) - df_runs.groupby(['participant', 'trial']).ngroups
    df_metrics = fix.aoi_metrics()
    assert {'n_visits', 'revisits'} <= set(df_metrics.columns) and (df_metrics['revisits'] >= 0).all()
    order = first_fixation_order(fix)
    assert set(order.columns) == {'participant', 'left', 'right'} and order[['left', 'right']].min().min() == 1
    fig, (ax0, ax1) = plt.subplots(1, 2)
    show_scarf_plot(ax0, fix)
    show_transition_matrix(ax1, m)
    plt.close(fig)


def test_pairwise_result_generic_scores():
    rows = [('a', 'a', 1., 1.), ('a', 'b', .5, .2), ('a', 'c', .4, .1), ('b', 'b', 1., 1.), ('b', 'c', .6, .3),
            ('c', 'c', 1., 1.)]
    df = pd.DataFrame(rows, columns=['subject_a', 'subject_b', 'scanmatch', 'mm_vector'])
    res = PairwiseSimilarityResult(df)
    assert res.scores == ['scanmatch', 'mm_vector'] and res.default_score() == 'scanmatch'
    m = res.matrix()
    assert m.loc['a', 'b'] == m.loc['b', 'a'] == .5
    m2 = res.matrix(which='mm_vector', grouping={'a': 'X', 'b': 'X', 'c': 'Y'})
    assert list(m2.index) == ['a', 'b', 'c'] and m2.loc['b', 'c'] == .3
    with pytest.raises(AssertionError):
        res.matrix(which='s_dir')
    stats = res.permutation_test({'a': 'X', 'b': 'X', 'c': 'Y'}, n_permutations=50, verbose=False)
    assert stats['which'] == 'scanmatch' and 0 < stats['p_value'] <= 1
    fig, ax = plt.subplots()
    res.matshow(ax=ax, grouping={'a': 'X', 'b': 'X', 'c': 'Y'})
    res.show_boxplot({'a': 'X', 'b': 'X', 'c': 'Y'}, ax=ax)
    plt.close(fig)


def test_heatmatch_progress_cancel(fixation_table, fixation_mapping):
    df_sac, sm = fixations_to_saccades(fixation_table, fixation_mapping)
    sac = SaccadeData(df_sac, fixation_table['image'].iloc[0], **sm)
    seen = []
    res = sac.compute_heatmatch_similarity(sigma=100, verbose=False, progress=lambda d, n, txt: seen.append(txt))
    assert res.scores == ['s_dir', 's_loc'] and seen and 'orientation fields' in seen[0]
    with pytest.raises(InterruptedError):
        sac.compute_heatmatch_similarity(sigma=150, verbose=False, progress=lambda d, n, txt: False)


def make_aoi_metrics_export(path):
    ls = []
    for p in ['p1', 'p2', 'p3']:
        for media, aois in [('wall_a', ['face', 'label']), ('wall_b', ['vase'])]:
            for aoi in aois:
                looked = not (p == 'p3' and aoi == 'label')
                ls.append({'Recording': p, 'Participant': p, 'Condition': 'c1', 'TOI': media, 'Interval': 1,
                           'Media': media, 'AOI': aoi, 'AOI_size': 1000, 'Ungrouped': 'Painting',
                           'Duration_of_interval': 5000, 'Start_of_interval': 0,
                           'Total_duration_of_fixations': '1200,5' if looked else '', 'Number_of_fixations': 4 if looked else '',
                           'Time_to_first_fixation': 300 if looked else '', 'Total_duration_of_Visit': 1500 if looked else '',
                           'Number_of_Visits': 2 if looked else '', 'Average_pupil_diameter': '3,2' if looked else ''})
    pd.DataFrame.from_records(ls).to_csv(path, sep='\t', index=False)
    return str(path)


def test_aoi_metrics_export(tmp_path):
    path = make_aoi_metrics_export(tmp_path / "Raum X Metrics_AOI-based.tsv")
    assert creapy.detect_format(creapy.read_table(path).columns) == 'tobii_metrics_export'
    df, info = load_prolab_aoi_metrics_export(path)
    assert info['n_participants'] == 3 and 'Total_duration_of_fixations' in info['metrics']
    assert df.loc[(df['Participant'] == 'p3') & (df['AOI'] == 'label'), 'Number_of_fixations'].iloc[0] == 0
    assert df.loc[(df['Participant'] == 'p3') & (df['AOI'] == 'label'), 'Time_to_first_fixation'].isna().all()
    assert df['Total_duration_of_fixations'].max() == pytest.approx(1200.5)
    summary = aoi_metrics_summary(df, 'Total_duration_of_fixations', by='AOI', group_col='Media')
    assert set(summary.columns) == {'AOI', 'Media', 'mean', 'sd', 'median', 'n', 'share_looked'}
    assert summary.loc[summary['AOI'] == 'label', 'share_looked'].iloc[0] == pytest.approx(2 / 3)
    with pytest.raises(ValueError):
        load_prolab_aoi_metrics_export(pd.DataFrame({'a': [1]}))


def test_data_export_distance_and_chunked(tmp_path):
    path = make_prolab_export(tmp_path / "export.tsv", snapshots=True)
    df_raw = creapy.read_table(path)
    df_raw['Gaze point 3D X'] = 100.
    df_raw['Gaze point 3D Y'] = 0.
    df_raw['Gaze point 3D Z'] = 2000.
    df_raw['Pupil diameter filtered'] = 3.5
    df_raw.to_csv(path, sep='\t', index=False)
    df, mapping = load_prolab_data_export(df_raw)
    assert mapping['pupil_col'] == 'pupil' and df['pupil'].eq(3.5).all()
    assert df['distance_mm'].round(1).eq(round(np.hypot(100, 2000), 1)).all()
    df_chunked, mapping2 = load_prolab_data_export_chunked(path, chunksize=7)  # chunks split fixations on purpose
    assert len(df_chunked) == len(df)
    merged = df.merge(df_chunked, on=['participant', 'stimulus', 't'], suffixes=('', '_c'))
    assert len(merged) == len(df) and np.allclose(merged['x'], merged['x_c']) and np.allclose(merged['dur'], merged['dur_c'])
