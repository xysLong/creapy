import numpy as np
import pandas as pd
import pytest
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import creapy
from creapy.aoi.sequence import first_fixation_order, show_scarf_plot

MAPPING = {'stim_col': 'image', 'subj_index_col': 'subj', 'fix_t_col': 't', 'fix_dur_col': 'dur',
           'fix_x_col': 'x', 'fix_y_col': 'y', 'trial_col': 'trial', 'time_unit': 'ms'}


@pytest.fixture
def visits(small_image):
    ls = [('A', 1, 0, 50), ('A', 1, 240, 100), ('A', 1, 1000, 300), ('A', 2, 0, 300), ('A', 2, 240, 110),
          ('B', 1, 0, 200), ('B', 1, 240, 210)]
    return pd.DataFrame([{'subj': s, 'trial': tr, 't': t, 'dur': 200, 'x': x, 'y': 150, 'image': small_image}
                         for s, tr, t, x in ls])


def pair(df, max_gap=None):
    return creapy.build_pair(df, df['image'].iloc[0], MAPPING, max_gap=max_gap)


def add_aois(fix):
    fix.set_top_down_aoi("right", creapy.AOI.rectangle("right", 280, 0, 320, 300).geom)
    fix.set_top_down_aoi("second", creapy.AOI.rectangle("second", 105, 0, 115, 300).geom)


def test_segments_break_at_trials_and_long_pauses(visits):
    fix, sac = pair(visits)
    assert list(fix.segments()) == [1, 1, 1, 2, 2, 3, 3]
    fix_m, sac_m = pair(visits, max_gap=creapy.MOBILE_MAX_GAP)
    assert list(fix_m.segments()) == [1, 1, 2, 3, 3, 4, 4]
    assert len(sac.df) == 4 and len(sac_m.df) == 3   # no saccade across the 560 ms pause
    assert fix_m.subset(subjects=['A']).max_gap == creapy.MOBILE_MAX_GAP


def test_viewing_clock_lays_visits_end_to_end(visits):
    fix, _ = pair(visits)
    assert np.allclose(fix.viewing_clock().to_numpy(), [0, .24, 1., 1.2, 1.44, 0, .24])


def test_aoi_metrics_count_visits_and_first_fixation_over_the_clock(visits):
    fix, _ = pair(visits, max_gap=creapy.MOBILE_MAX_GAP)
    add_aois(fix)
    df_aoi = fix.aoi_metrics().set_index(['participant', 'aoi'])
    assert df_aoi.loc[('A', 'right'), 'n_visits'] == 2           # end of visit 1, start of visit 2
    assert np.isclose(df_aoi.loc[('A', 'right'), 'time_to_first_fixation'], 1.)
    assert np.isclose(df_aoi.loc[('A', 'second'), 'time_to_first_fixation'], 1.44)
    order = first_fixation_order(fix).set_index('participant')
    assert order.loc['A', 'right'] == 1 and order.loc['A', 'second'] == 2


def test_scarf_plot_does_not_overlap_visits(visits):
    fix, _ = pair(visits)
    add_aois(fix)
    fig, ax = plt.subplots()
    show_scarf_plot(ax, fix)
    starts = sorted(np.asarray(ax.collections[0].get_paths()[i].vertices[0, 0]) for i in range(5))
    plt.close(fig)
    assert np.allclose(starts, [0, .24, 1., 1.2, 1.44])


def test_participant_table_mobile(visits):
    fix, sac = pair(visits, max_gap=creapy.MOBILE_MAX_GAP)
    df_lab = creapy.participant_table(fix, sac)
    df_mob = creapy.participant_table(fix, mobile=True).set_index('participant')
    assert {'coefficient_K', 'scanpath_length_px', 'n_saccades'} <= set(df_lab.columns)
    assert not {'coefficient_K', 'scanpath_length_px', 'n_saccades'} & set(df_mob.columns)
    assert df_mob.loc['A', 'n_visits'] == 2 and df_mob.loc['B', 'n_visits'] == 1
    assert np.isclose(df_mob.loc['A', 'viewing_time_s'], 1.64)
    assert np.isclose(df_mob.loc['A', 'mean_visit_s'], 0.82)


def test_scanpath_line_breaks(visits):
    fix, _ = pair(visits, max_gap=creapy.MOBILE_MAX_GAP)
    fig, ax = plt.subplots()
    fix.visualize_scanpath(ax, subjects=['A'])
    xs = ax.lines[0].get_xdata()
    plt.close(fig)
    assert np.isnan(xs).sum() == 2 and len(xs) == 7


def test_data_export_visits_restart_time():
    from creapy.formats.tobii import split_into_visits, VISIT_GAP_MS
    df = pd.DataFrame({'participant': 'V1', 'recording': ['R1'] * 4 + ['R2'], 'stimulus': 'Wall',
                       't': [1000., 1300., 1600 + VISIT_GAP_MS + 1000, 1600 + VISIT_GAP_MS + 1300, 50.],
                       'dur': 200., 'x': 1., 'y': 1.})
    out = split_into_visits(df)
    assert list(out['visit']) == [1, 1, 2, 2, 3]
    assert list(out['t']) == [0., 300., 0., 300., 0.]


def test_data_export_loaders_mark_visits(tmp_path):
    from tests.conftest import make_prolab_export
    from creapy.formats.tobii import load_prolab_data_export, load_prolab_data_export_chunked
    path = make_prolab_export(str(tmp_path / "glasses.tsv"), snapshots=True)
    df, mapping = load_prolab_data_export(path)
    df_c, mapping_c = load_prolab_data_export_chunked(path, chunksize=7)
    assert mapping['trial_col'] == 'visit' and mapping_c['trial_col'] == 'visit'
    key = ['participant', 'stimulus', 'visit', 't']
    pd.testing.assert_frame_equal(df.sort_values(key)[key].reset_index(drop=True),
                                  df_c.sort_values(key)[key].reset_index(drop=True), check_dtype=False)
    assert (df.groupby(['participant', 'stimulus', 'visit'])['t'].min() == 0).all()
