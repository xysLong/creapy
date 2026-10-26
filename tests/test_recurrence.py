import numpy as np
import pandas as pd
import pytest
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from creapy import FixationData
from creapy.stats.recurrence import (recurrence_matrix, rqa_measures, participant_rqa, cross_recurrence,
                                     cross_recurrence_table, show_recurrence_plot, default_radius)


def test_recurrence_matrix_is_symmetric_with_true_diagonal():
    xy = np.array([[0, 0], [10, 0], [0, 1], [50, 50]], dtype=float)
    rec = recurrence_matrix(xy, radius=5)
    assert rec.shape == (4, 4) and rec.dtype == bool
    assert np.array_equal(rec, rec.T)
    assert rec.diagonal().all()
    assert rec[0, 2] and not rec[0, 1] and not rec[0, 3]


def test_two_recurrent_pairs_on_one_diagonal():
    # exactly (0, 2) and (1, 3) recur: R = 2, both on the offset-2 diagonal -> one diagonal line of length 2
    xy = np.array([[0, 0], [100, 0], [0, 1], [100, 1]], dtype=float)
    m = rqa_measures(xy, radius=5)
    assert m['n_fixations'] == 4 and m['n_recurrent_pairs'] == 2
    assert np.isclose(m['recurrence'], 100. * 2 * 2 / (4 * 3))  # 33.3 %
    assert np.isclose(m['determinism'], 100.)
    assert np.isclose(m['laminarity'], 0.)
    assert np.isclose(m['corm'], 100. * (2 + 2) / (3 * 2))  # 66.7


def test_repeated_scanpath_gives_full_determinism():
    # A B C A B C: pairs (0,3), (1,4), (2,5) form one diagonal line of length 3
    abc = np.array([[0, 0], [100, 0], [0, 100]], dtype=float)
    xy = np.vstack([abc, abc])
    m = rqa_measures(xy, radius=5)
    assert m['n_recurrent_pairs'] == 3
    assert np.isclose(m['recurrence'], 100. * 6 / 30)
    assert np.isclose(m['determinism'], 100.)
    assert np.isclose(m['laminarity'], 0.)
    assert np.isclose(m['corm'], 100. * 9 / (5 * 3))


def test_dwelling_on_one_location_gives_laminarity():
    # A A A B: pairs (0,1), (0,2), (1,2); vertical line in column 2 and horizontal line in row 0, both of length 2
    xy = np.array([[0, 0], [1, 0], [0, 1], [200, 200]], dtype=float)
    m = rqa_measures(xy, radius=5)
    assert m['n_recurrent_pairs'] == 3
    assert m['laminarity'] > 0
    assert np.isclose(m['laminarity'], 100. * (2 + 2) / (2 * 3))
    assert np.isclose(m['determinism'], 100. * 2 / 3)  # (0,1),(1,2) on the first diagonal


def test_min_line_filters_short_lines():
    xy = np.array([[0, 0], [100, 0], [0, 1], [100, 1]], dtype=float)
    assert np.isclose(rqa_measures(xy, radius=5, min_line=2)['determinism'], 100.)
    assert np.isclose(rqa_measures(xy, radius=5, min_line=3)['determinism'], 0.)


def test_degenerate_inputs():
    m = rqa_measures(np.array([[0, 0]], dtype=float), radius=5)
    assert m['n_fixations'] == 1 and m['n_recurrent_pairs'] == 0
    assert all(np.isnan(m[k]) for k in ['recurrence', 'determinism', 'laminarity', 'corm'])
    m = rqa_measures(np.array([[0, 0], [100, 100], [200, 200]], dtype=float), radius=5)  # no recurrence
    assert m['recurrence'] == 0 and m['n_recurrent_pairs'] == 0
    assert all(np.isnan(m[k]) for k in ['determinism', 'laminarity', 'corm'])


def test_cross_recurrence_symmetric_and_bounded():
    rng = np.random.default_rng(3)
    xy_a = rng.uniform(0, 100, size=(20, 2))
    xy_b = rng.uniform(0, 100, size=(15, 2))
    c_ab = cross_recurrence(xy_a, xy_b, radius=10)
    assert np.isclose(c_ab, cross_recurrence(xy_b, xy_a, radius=10))
    assert 0 <= c_ab <= 1
    assert cross_recurrence(xy_a, xy_a, radius=1000) == 1.
    assert cross_recurrence(xy_a, xy_b + 10_000, radius=10) == 0.


def test_participant_rqa_on_fixture(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    df_rqa = participant_rqa(fix)
    assert list(df_rqa['participant'].astype(object)) == fix.subjects  # natural order: vp1, vp2, vp10
    assert len(df_rqa) == 3
    for col in ['n_fixations', 'recurrence', 'determinism', 'laminarity', 'corm', 'n_recurrent_pairs', 'radius']:
        assert col in df_rqa.columns
    assert df_rqa['recurrence'].between(0, 100).all()
    assert np.isclose(df_rqa['radius'].iloc[0], 0.05 * np.hypot(400, 300))
    # trials are averaged: 25 fixations per trial (24 where the NaN sits), never the 50 of the pooled participant
    assert df_rqa['n_fixations'].between(24, 25).all()
    df_fixed = participant_rqa(fix, radius=30, min_line=3)
    assert (df_fixed['radius'] == 30).all()


def test_cross_recurrence_table_columns_and_pairs(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    df_cr = cross_recurrence_table(fix, verbose=False)
    assert list(df_cr.columns) == ['subject_a', 'subject_b', 'cross_recurrence']
    assert len(df_cr) == 6  # 3 participants -> 3 pairs + 3 diagonal entries
    diag = df_cr[df_cr['subject_a'] == df_cr['subject_b']]
    assert len(diag) == 3 and (diag['cross_recurrence'] > 0).all()
    assert df_cr['cross_recurrence'].between(0, 1).all()


def test_show_recurrence_plot_on_agg():
    rng = np.random.default_rng(1)
    xy = rng.uniform(0, 400, size=(30, 2))
    fig, ax = plt.subplots(1, 1, figsize=(4, 4))
    rec = show_recurrence_plot(ax, xy, radius=40)
    fig.canvas.draw()
    assert rec.shape == (30, 30)
    assert ax.get_xlabel() == 'Fixation index'
    plt.close(fig)
