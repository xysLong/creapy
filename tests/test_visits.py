import os
import numpy as np
import pandas as pd
import pytest
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image

import creapy
from creapy.formats.tobii import load_prolab_intervals, attach_intervals
from creapy.aoi.aoi import AOI, LabelAOI
from creapy.aoi.sequence import aoi_run_sequences, transition_matrix
from creapy.stats.visits import visit_table, episodes, stimulus_totals, session_summary, stimulus_sequence, has_clock
from tests.conftest import make_prolab_event_export, make_prolab_aoi_export


@pytest.fixture
def exports(tmp_path):
    for name in ['c1_r1_w1_a', 'c1_r1_w2_a']:
        Image.new('RGB', (400, 300), (90, 90, 90)).save(tmp_path / f"{name}.jpg")
    events = make_prolab_event_export(str(tmp_path / "events.tsv"))
    aois = make_prolab_aoi_export(str(tmp_path / "aois.tsv"))
    return tmp_path, events, aois


def test_event_export_carries_aoi_hits_and_tags(exports):
    tmp_path, events, _ = exports
    df, mapping = creapy.load_fixations(events)
    assert {'aoi_hit', 'aoi_tag'} <= set(df.columns)
    assert df['aoi_hit'].str.contains(',').sum() == 4   # one overlapping-label fixation per participant and medium


def test_label_aois_metrics_and_sequences(exports):
    tmp_path, events, aois = exports
    df, mapping = creapy.load_fixations(events)
    df_iv, sizes, df_ev = load_prolab_intervals(aois)
    df_w1 = df[df['stimulus'] == 'c1_r1_w1_a']
    fix, sac = creapy.build_pair(df_w1, str(tmp_path / "c1_r1_w1_a.jpg"), mapping, max_gap=creapy.MOBILE_MAX_GAP)
    names = fix.set_label_aois('aoi_hit', sizes=sizes)
    assert names == ['Boy', 'Boy_label_id', 'Boy_label_ot']          # _c1 dropped, overlapping labels split
    assert isinstance(fix.areas_of_interest['Boy'], LabelAOI)
    assert list(fix.aoi_mask('Boy')) == [True, False, True] * 2
    assert list(fix.aoi_mask('Boy_label_ot')) == [False, True, False] * 2
    df_aoi = fix.aoi_metrics().set_index(['participant', 'aoi'])
    assert df_aoi.loc[('c1_p001', 'Boy'), 'n_fixations'] == 2
    assert df_aoi.loc[('c1_p001', 'Boy'), 'n_visits'] == 2 and df_aoi.loc[('c1_p001', 'Boy'), 'revisits'] == 1
    assert np.isclose(df_aoi.loc[('c1_p001', 'Boy'), 'dwell_share'], 2 / 3)
    assert np.isclose(df_aoi.loc[('c1_p001', 'Boy'), 'aoi_area_share'], 90_000 * fix.image_scale ** 2 / (400 * 300))
    assert np.isnan(df_aoi.loc[('c1_p001', 'Boy'), 'mean_within_saccade_px'])   # the two Boy fixations are not consecutive
    tags = fix.set_label_aois('aoi_tag')
    assert tags == ['Label_painting_id', 'Label_painting_ot', 'Painting']
    df_runs = aoi_run_sequences(fix, names=['Boy', 'Boy_label_ot'])
    row = df_runs.set_index('participant').loc['c1_p001']
    assert row['sequence'] == 'Boy > Boy_label_ot > Boy' and row['n_switches'] == 2 and row['runs_Boy'] == 2
    df_runs = aoi_run_sequences(fix, names=['Boy', 'Boy_label_ot'], min_run_s=0.25)
    assert df_runs.set_index('participant').loc['c1_p001', 'sequence'] == ''   # every run is one 200 ms fixation
    matrix = transition_matrix(fix, names=['Boy', 'Boy_label_ot'])
    assert np.isclose(matrix.loc['Boy', 'Boy_label_ot'], 1.) and np.isclose(matrix.loc['Boy_label_ot', 'Boy'], 1.)
    fig, ax = plt.subplots()
    from creapy.io.views import show_label_aoi
    show_label_aoi(ax, fix, 'Boy', color='red')
    plt.close(fig)
    rec = fix.areas_of_interest['Boy'].to_record()
    back = AOI.from_record(rec)
    assert isinstance(back, LabelAOI) and back.values == {'Boy_c1'} and back.size == 90_000


def test_intervals_give_the_recording_clock(exports):
    tmp_path, events, aois = exports
    df, mapping = creapy.load_fixations(events)
    df_iv, sizes, df_ev = load_prolab_intervals(aois)
    assert len(df_iv) == 8 and any(s.get('Boy_label_ot_c1') == 3_000 for s in sizes.values())
    assert set(df_ev['event']) == {'c1_r1_Start'} and len(df_ev) == 2
    assert np.allclose(sorted(df_ev['t_abs_ms']), [1000, 1000])
    df_abs = attach_intervals(df, df_iv)
    assert df_abs['t_abs'].notna().all() and df_abs.index.equals(df.index)
    first = df_abs[(df_abs['participant'] == 'c1_p001') & (df_abs['stimulus'] == 'c1_r1_w2_a')]['t_abs'].min()
    assert first == 20_000
    df_v = visit_table(df_abs, mapping)
    assert has_clock(df_v) and len(df_v) == 4                       # interval 2 has no fixations
    p2 = df_v[df_v['participant'] == 'c1_p002'].sort_values('order')
    assert list(p2['stimulus']) == ['c1_r1_w2_a', 'c1_r1_w1_a']
    df_ep = episodes(df_v, merge_gap_s=0.)
    assert len(df_ep) == 4 and not df_ep['revisit'].any()
    df_tot = stimulus_totals(df_v, roster=['c1_p001', 'c1_p002', 'c1_p003'], df_episodes=df_ep)
    assert len(df_tot) == 6 and (~df_tot['looked']).sum() == 2
    zero = df_tot[df_tot['participant'] == 'c1_p003']
    assert (zero['dwell_s'] == 0).all() and (zero['n_visits'] == 0).all()
    df_sum = session_summary(df_v, df_ep, df_ev)
    s1 = df_sum.set_index('participant').loc['c1_p001']
    assert np.isclose(s1['span_s'], (20_000 + 480 + 200 - 10_000) / 1000.)
    assert np.isclose(s1['mapped_s'], 2 * 0.68) and np.isclose(s1['event_c1_r1_Start_s'], 1.)
    assert stimulus_sequence(df_ep).set_index('participant').loc['c1_p002', 'sequence'] == 'c1_r1_w2_a > c1_r1_w1_a'
    fig, ax = plt.subplots()
    creapy.show_visit_timeline(ax, df_v, df_events=df_ev)
    plt.close(fig)


def test_revisits_and_merging():
    df_v = pd.DataFrame({'participant': 'A', 'stimulus': ['w1', 'w1', 'w2', 'w1'], 'trial': [1, 2, 1, 3],
                         'n_fixations': 3, 'dwell_s': 1., 't_start_s': [0., 2., 5., 9.], 't_end_s': [1., 3., 6., 10.],
                         'order': [1., 2., 3., 4.]})
    df_ep = episodes(df_v, merge_gap_s=0.)
    assert list(df_ep['episode_of_stimulus']) == [1, 2, 1, 3] and df_ep['revisit'].sum() == 2
    df_ep = episodes(df_v, merge_gap_s=1.)
    assert list(df_ep['stimulus']) == ['w1', 'w2', 'w1'] and df_ep['revisit'].sum() == 1
    assert np.isclose(df_ep.loc[0, 'dwell_s'], 2.) and df_ep.loc[0, 'n_visits'] == 2
    df_ep = episodes(df_v, merge_gap_s=None)
    assert list(df_ep['stimulus']) == ['w1', 'w2', 'w1']
    df_v_no_clock = df_v.assign(t_start_s=np.nan, t_end_s=np.nan)
    assert not has_clock(df_v_no_clock)
    df_tot = stimulus_totals(df_v_no_clock)
    assert df_tot.set_index('stimulus').loc['w1', 'n_visits'] == 3 and df_tot['n_episodes'].isna().all()


def test_zero_rows_in_participant_and_aoi_tables(exports):
    tmp_path, events, _ = exports
    df, mapping = creapy.load_fixations(events)
    df_w1 = df[(df['stimulus'] == 'c1_r1_w1_a') & (df['participant'] == 'c1_p001')]
    fix, sac = creapy.build_pair(df_w1, str(tmp_path / "c1_r1_w1_a.jpg"), mapping, max_gap=creapy.MOBILE_MAX_GAP)
    df_stats = creapy.add_zero_rows(creapy.participant_table(fix, mobile=True), ['c1_p001', 'c1_p002'],
                                    ['n_fixations', 'n_visits', 'viewing_time_s'])
    assert list(df_stats['participant']) == ['c1_p001', 'c1_p002'] and list(df_stats['looked']) == [True, False]
    assert df_stats.loc[1, 'n_fixations'] == 0 and np.isnan(df_stats.loc[1, 'mean_fixation_duration'])
    fix.set_label_aois('aoi_hit')
    df_aoi = creapy.add_zero_rows(fix.aoi_metrics(), ['c1_p001', 'c1_p002'], ['n_fixations', 'dwell_time'], per='aoi')
    assert len(df_aoi) == 6 and set(df_aoi[df_aoi['participant'] == 'c1_p002']['aoi']) == set(fix.areas_of_interest)
    assert (df_aoi[df_aoi['participant'] == 'c1_p002']['dwell_time'] == 0).all()


def test_inventory_named_areas_survive_numeric_coercion(tmp_path):
    from creapy.aoi.aoi import split_labels, clean_label
    from tests.conftest import make_inventory_named_exports
    from creapy.gaze.fixation import labels_in_column
    assert clean_label(1101.0) == '1101' and clean_label('1101.0') == '1101' and clean_label('Lg11') == 'Lg11'
    assert split_labels('1101,label1101') == {'1101', 'label1101'} and split_labels(1102.0) == {'1102'}
    assert labels_in_column(pd.Series([1101.0, np.nan, 1102.0])) == ['1101', '1102']
    events, aois = make_inventory_named_exports(str(tmp_path))
    df, mapping = creapy.load_fixations(events)
    assert set(df['condition']) == {'c1', 'c2'} and df['stimulus'].nunique() == 4
    df_iv, sizes, df_ev = load_prolab_intervals(aois)
    assert sizes['c1_r1_w1'] == {'1101': 1_200_000., 'label1101': 20_000., 'roomtext1': 150_000.}
    df = attach_intervals(df, df_iv)
    assert df['t_abs'].notna().all()
    fix, sac = creapy.build_pair(df[df['stimulus'] == 'c2_r1_w1'], str(tmp_path / "c2_r1_w1.jpg"), mapping,
                                 max_gap=creapy.MOBILE_MAX_GAP)
    assert fix.width == 2400 and np.isclose(fix.image_scale, 0.6)         # 4000 px snapshot downscaled
    names = fix.set_label_aois('aoi_hit', sizes=sizes)
    assert names == ['1101', 'label1101', 'roomtext1']                      # no suffix to strip, natural order
    df_aoi = fix.aoi_metrics().set_index('aoi')
    assert df_aoi.loc['1101', 'n_fixations'] == 2 and df_aoi.loc['label1101', 'n_fixations'] == 2
    assert np.isclose(df_aoi.loc['1101', 'aoi_area_share'], 1_200_000 * 0.6 ** 2 / (2400 * 960))
    tags = fix.set_label_aois('aoi_tag')
    assert tags == ['Label', 'Painting', 'Roomtext']
    df_runs = aoi_run_sequences(fix, names=['1101', 'label1101'])
    assert df_runs['sequence'].iloc[0] == '1101 > label1101 > 1101'
    df_v = visit_table(df, mapping)
    df_ep = episodes(df_v)
    assert len(df_ep) == 6 and not df_ep['revisit'].any()
    df_tot = stimulus_totals(df_v, roster=sorted(df['participant'].unique()), df_episodes=df_ep)
    assert len(df_tot) == 12 and (~df_tot['looked']).sum() == 6           # c1 visitors never on c2 walls and vice versa


def test_transition_counts_area_visits_and_totals_over_stimuli(tmp_path):
    from tests.conftest import make_inventory_named_exports
    from creapy.aoi.sequence import transition_counts
    from creapy.stats.visits import area_visit_table, aoi_totals_over_stimuli, unit_summary
    from creapy.stats import group_comparison, participants_over_stimuli
    events, aois = make_inventory_named_exports(str(tmp_path))
    df, mapping = creapy.load_fixations(events)
    df_iv, sizes, _ = load_prolab_intervals(aois)
    df = attach_intervals(df, df_iv)
    fixes, pairs = {}, {}
    for stim, df_s in df.groupby('stimulus'):
        fix, sac = creapy.build_pair(df_s, str(tmp_path / f"{stim}.jpg"), mapping, max_gap=creapy.MOBILE_MAX_GAP)
        fix.set_label_aois('aoi_hit', sizes=sizes)
        fixes[stim], pairs[stim] = fix, (fix, sac)
    fix = fixes['c1_r1_w1']
    df_tr = transition_counts(fix, names=['1101', 'label1101'])
    assert df_tr.set_index('participant').loc['G_c1_p001', ['1101>label1101', 'label1101>1101']].tolist() == [1, 1]
    df_tr = transition_counts(fix, names=['1101', 'label1101'], include_outside=True)
    assert 'outside>roomtext1' not in df_tr.columns and df_tr['1101>outside'].tolist() == [1, 1]
    df_m = fix.aoi_metrics(reference='1101')
    assert df_m.set_index('aoi').loc['roomtext1', 'dwell_share_of_reference'].tolist() == [0.5, 0.5]
    assert df_m['hit'].all() and (df_m['dwell_per_area'] > 0).all()
    df_v = area_visit_table(fixes, names=['1101', 'label1101'])
    assert set(df_v['stimulus']) == {'1101', 'label1101'} and has_clock(df_v)
    df_ep = episodes(df_v, merge_gap_s=0.)
    df_tot = stimulus_totals(df_v, roster=sorted(df['participant'].unique()), df_episodes=df_ep)
    row = df_tot.set_index(['participant', 'stimulus']).loc[('G_c1_p001', '1101')]
    assert row['n_visits'] == 4 and row['n_revisits'] == 3 and row['rank'] == 1 and row['share_of_mapped'] == 0.5
    df_sum = unit_summary(df_tot)
    assert df_sum.set_index('stimulus').loc['1101', 'n_looked'] == 3
    df_all = aoi_totals_over_stimuli(fixes, roster=sorted(df['participant'].unique()))
    idx = df_all.set_index(['participant', 'stimulus', 'aoi'])
    assert idx.loc[('G_c1_p001', 'c1_r1_w1', '1101'), 'share_of_areas'] == 0.2
    assert not idx.loc[('G_c1_p001', 'c2_r1_w1', '1101'), 'looked'] and idx.loc[('G_c1_p001', 'c2_r1_w1', '1101'), 'dwell_time'] == 0
    df_area_sum = unit_summary(df_all, unit_col='aoi', dwell_col='dwell_time')
    assert set(df_area_sum.columns) >= {'stimulus', 'aoi', 'n_looked', 'share_of_total_dwell'}
    df_p = participants_over_stimuli(pairs, mobile=True, roster=sorted(df['participant'].unique()))
    assert df_p.set_index(['participant', 'stimulus']).loc[('G_c2_p004', 'c1_r1_w1'), 'looked'] == False  # noqa: E712
    assert (df_p.groupby('participant')['share_of_total'].sum().round(6) == 1).all()
    cmp_ = group_comparison(df_p, {'G_c1_p001': 'c1', 'G_c1_p002': 'c1', 'G_c2_p004': 'c2'}, columns=['viewing_time_s'])
    assert cmp_['test'].iloc[0] == 'Welch t' and {'median_c1', 'cohen_d', 'rank_biserial_r', 'ci95_low'} <= set(cmp_.columns)
    paired = group_comparison(fix.aoi_metrics(names=['1101', 'label1101']), group_col='aoi', columns=['dwell_time'])
    assert paired['test'].iloc[0] == 'paired t' and 'wilcoxon_p' in paired.columns


def test_condition_from_stimulus_names():
    from creapy.misc.utils import grouping_from_stimulus_names, condition_token
    assert condition_token('c1_r1_w2_a.jpg') == 'c1' and condition_token('Boy_c2') == 'c2'
    assert condition_token('Room 4 wall 3.jpg') is None and condition_token('c1_c2_mixed') is None
    assert grouping_from_stimulus_names({'a': ['c1_w1', 'c1_w2'], 'b': ['c2_w1']}) == {'a': 'c1', 'b': 'c2'}
    assert grouping_from_stimulus_names({'a': ['c1_w1', 'c2_w2'], 'b': ['c2_w1']}) is None   # a: tie, one token left
    assert grouping_from_stimulus_names({'a': ['c1_w1', 'c1_w1', 'c2_w2'], 'b': ['c2_w1']}) == {'a': 'c1', 'b': 'c2'}
    assert grouping_from_stimulus_names({'a': ['c1_w1'], 'b': ['c1_w1']}) is None            # one condition only
    from creapy.misc.utils import grouping_from_participant_names
    assert grouping_from_participant_names(['M_c1_p001', 'M_c2_p004', 'x']) == {'M_c1_p001': 'c1', 'M_c2_p004': 'c2'}


def test_paired_test_survives_missing_values_and_sizes_follow_the_stimulus(tmp_path):
    from creapy.stats import group_comparison
    from creapy.formats.tobii import load_prolab_intervals
    df = pd.DataFrame({'participant': list('abcdef') * 2, 'aoi': ['work'] * 6 + ['label'] * 6,
                       'dwell': [1., 2., 3., 4., 5., 6., 2., 2., 4., 3., 7., 5.],
                       'latency': [1., np.nan, 3., 4., 5., 6., 2., 2., np.nan, 3., 7., 5.]})
    cmp_ = group_comparison(df, group_col='aoi', columns=['dwell', 'latency']).set_index('measure')
    assert cmp_.loc['dwell', 'test'] == 'paired t' and cmp_.loc['latency', 'test'] == 'paired t'
    assert cmp_.loc['latency', 'n_work'] == 5 and cmp_.loc['latency', 'n_label'] == 5
    df_other = df.assign(participant=[*'abcdef', *'ghijkl'])
    assert group_comparison(df_other, group_col='aoi', columns=['dwell']).iloc[0]['test'] == 'Welch t'
    rows = [{'Participant': 'p1', 'Media': m, 'Interval': 1, 'Start_of_interval': 0, 'AOI': 'socket', 'AOI_size': s,
             'Ungrouped': t} for m, s, t in [('w1', 100, 'Socket'), ('w2', 900, np.nan)]]
    _, sizes, _ = load_prolab_intervals(pd.DataFrame(rows))
    assert sizes == {'w1': {'socket': 100.}, 'w2': {'socket': 900.}}
    from creapy.formats.tobii import aoi_names_by_stimulus
    assert aoi_names_by_stimulus(pd.DataFrame(rows)) == {'w1': {'socket': 'Socket'}, 'w2': {'socket': ''}}
