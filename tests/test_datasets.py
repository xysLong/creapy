import numpy as np
import pandas as pd
import pytest
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import creapy
from creapy import FixationData, SaccadeData, AOI, fixations_to_saccades, saccades_to_fixations
from creapy.stats import participant_table, group_comparison, coefficient_k


def test_fixations_to_saccades_matches_loop(fixation_table, fixation_mapping):
    df_sac, sac_mapping = fixations_to_saccades(fixation_table, fixation_mapping)
    # reference: the old row-by-row construction, per participant AND trial; saccades touching the fixation
    # without coordinates are dropped by the vectorized version, so they are skipped here too
    ls = []
    m = fixation_mapping
    for (subj, trial), df_subj in fixation_table.sort_values([m['subj_index_col'], m['trial_col'], m['fix_t_col']]) \
            .groupby([m['subj_index_col'], m['trial_col']]):
        for i in range(len(df_subj) - 1):
            a, b = df_subj.iloc[i], df_subj.iloc[i + 1]
            if np.isnan(a[m['fix_x_col']]) or np.isnan(b[m['fix_x_col']]):
                continue
            ls.append((subj, a[m['fix_t_col']] + a[m['fix_dur_col']], a[m['fix_x_col']], b[m['fix_x_col']]))
    ref = pd.DataFrame(ls, columns=['subj', 't', 'x0', 'x1']).sort_values(['subj', 't']).reset_index(drop=True)
    got = df_sac[['subj', 't', 'x0', 'x1']].sort_values(['subj', 't']).reset_index(drop=True)
    pd.testing.assert_frame_equal(got.astype({'t': float, 'x0': float, 'x1': float}),
                                  ref.astype({'t': float, 'x0': float, 'x1': float}))
    assert 'trial' in df_sac.columns and sac_mapping['trial_col'] == 'trial'
    # no saccade jumps across a trial boundary (24 per viewing, 22 where the NaN fixation sits)
    assert df_sac.groupby(['subj', 'trial']).size().between(22, 24).all()


def test_saccades_to_fixations_roundtrip_shape(fixation_table, fixation_mapping):
    df_sac, sac_mapping = fixations_to_saccades(fixation_table, fixation_mapping)
    sac_mapping = dict(sac_mapping, stim_col='image')
    df_sac['image'] = fixation_table['image'].iloc[0]
    df_fix, fix_mapping = saccades_to_fixations(df_sac, sac_mapping)
    assert fix_mapping['fix_x_col'] == 'x'
    assert df_fix.groupby(['subj', 'trial']).size().between(21, 23).all()


def test_fixation_data_handles_ms_shuffle_and_nan(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    assert fix.time_unit == 'ms' and fix.dur_unit == 'ms'
    assert fix.t.max() < 60  # converted to seconds
    assert fix.subjects == ['vp1', 'vp2', 'vp10']  # natural order
    assert len(fix.df) == len(fixation_table) - 1  # the NaN coordinate row is dropped
    assert fix.pupil_col == 'CURRENT_FIX_PUPIL'
    # sorted by time within participant+trial
    for _, df_ in fix.df.groupby(['RECORDING_SESSION_LABEL', 'TRIAL_INDEX']):
        assert df_['CURRENT_FIX_START'].is_monotonic_increasing


def test_grayscale_image_loads(fixation_table, fixation_mapping, gray_image):
    df = fixation_table.assign(image=gray_image)
    fix = FixationData(df, gray_image, **fixation_mapping)
    assert fix.img.shape == (300, 400, 3)
    fig, ax = plt.subplots()
    fix.make_heatmap(ax)
    plt.close(fig)


def test_subset_by_participant_and_time(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    sub = fix.subset(subjects=['vp1'], t_range=(0, 2))
    assert sub.subjects == ['vp1']
    assert sub.t.max() <= 2.0 and len(sub.df) < len(fix.df)
    assert sub.t_max == fix.t_max  # the time axis is kept so curves stay comparable
    with pytest.raises(AssertionError):
        fix.subset(subjects=['nobody'])


def test_saccade_data_and_rose(fixation_table, fixation_mapping):
    df_sac, sac_mapping = fixations_to_saccades(fixation_table, fixation_mapping)
    sac = SaccadeData(df_sac, fixation_table['image'].iloc[0], **sac_mapping)
    assert sac.subjects == ['vp1', 'vp2', 'vp10']
    fig = plt.figure()
    ax = fig.add_subplot(projection='polar')
    xx, yy = sac.make_rose_plot(ax=ax, bins=12)
    assert len(xx) == 12 and np.isclose(yy.sum(), 1.)
    xx, yy = sac.make_rose_plot(ax=ax, bins=12, center_symmetric=True, subjects=['vp1'])
    assert np.isclose(yy.sum(), 1.)
    plt.close(fig)
    sub = sac.subset(subjects=['vp1', 'vp2'])
    assert sub.n_subjects() == 2
    stats = sub.participant_stats()
    assert list(stats['participant']) == ['vp1', 'vp2'] and stats['n_saccades'].min() > 0


def test_aoi_metrics_and_records(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    fix.set_top_down_aoi('left', AOI.rectangle('left', 0, 0, 200, 300).geom)
    fix.set_top_down_aoi('tri', AOI.polygon('tri', [(200, 0), (400, 0), (400, 300)]).geom)
    df_aoi = fix.aoi_metrics()
    assert set(df_aoi['aoi']) == {'left', 'tri'} and len(df_aoi) == 2 * 3
    left = df_aoi[df_aoi['aoi'] == 'left']
    assert (left['dwell_share'] <= 1).all() and (left['n_fixations'] >= 0).all()
    assert np.isclose(left['aoi_area_share'].iloc[0], 0.5)
    rec = fix.areas_of_interest['tri'].to_record()
    assert AOI.from_record(rec).area() == pytest.approx(fix.areas_of_interest['tri'].area())
    # the whole image: every fixation inside the image counts
    fix.set_top_down_aoi('all', AOI.rectangle('all', 0, 0, 400, 300).geom)
    df_all = fix.aoi_metrics(names=['all'])
    assert np.allclose(df_all['dwell_share'], 1.)


def test_participant_table_and_groups(fixation_table, fixation_mapping):
    fix = FixationData(fixation_table, fixation_table['image'].iloc[0], **fixation_mapping)
    df_sac, sac_mapping = fixations_to_saccades(fixation_table, fixation_mapping)
    sac = SaccadeData(df_sac, fixation_table['image'].iloc[0], img=fix.img, **sac_mapping)
    df_stats = participant_table(fix, sac)
    assert list(df_stats['participant']) == ['vp1', 'vp2', 'vp10']
    assert {'n_fixations', 'mean_fixation_duration', 'n_saccades', 'coefficient_K', 'mean_pupil'} <= set(df_stats.columns)
    assert df_stats['coefficient_K'].notna().all()
    cmp = group_comparison(df_stats, {'vp1': 'A', 'vp2': 'B', 'vp10': 'A'})
    assert 'mean_A' in cmp.columns and (cmp['test'] == 'n/a').all()  # too few per group for a test
    k, k_subj = coefficient_k([100, 300, 200, 400], [50, 10, 30, 10], ['a', 'a', 'b', 'b'])
    assert k_subj['b'] > k_subj['a']  # longer fixations + shorter saccades = more focal


def test_example_dataset_builds(example_csv):
    df, mapping = creapy.load_fixations(example_csv)
    assert df['participant'].nunique() == 12 and df['image'].nunique() == 2
    assert mapping['subj_index_col'] == 'participant' and mapping['stim_col'] == 'image'


def test_subset_keeps_coordinates_on_downscaled_images(fixation_table, fixation_mapping, tmp_path):
    # an 8k-style image is downscaled on loading; a participant subset must not scale the coordinates again
    from PIL import Image
    big = tmp_path / "big.jpg"
    Image.new('RGB', (4800, 3200), (100, 100, 100)).save(big, quality=60)
    df = fixation_table.assign(image=str(big))
    df['CURRENT_FIX_X'] = df['CURRENT_FIX_X'] * 12  # spread over the 4800 px width
    df['CURRENT_FIX_Y'] = df['CURRENT_FIX_Y'] * 10
    fix = FixationData(df, str(big), **fixation_mapping)
    assert fix.width == 2400 and fix.scale == pytest.approx(0.5)
    assert fix.fix_x.max() == pytest.approx(df['CURRENT_FIX_X'].max() * 0.5)
    sub = fix.subset(subjects=['vp1'])
    assert sub.fix_x.max() == pytest.approx(fix.fix_x[fix.subj_index == 'vp1'].max())
    sub_t = fix.subset(t_range=(0, 3))
    assert sub_t.fix_x.max() <= fix.width and sub_t.fix_x.max() > fix.width * 0.3
    # normalised Tobii coordinates land on the array once, subsets keep them
    df_norm = fixation_table.assign(image=str(big))
    df_norm['CURRENT_FIX_X'] = df_norm['CURRENT_FIX_X'] / 400.
    df_norm['CURRENT_FIX_Y'] = df_norm['CURRENT_FIX_Y'] / 300.
    fix_n = FixationData(df_norm, str(big), normalized_xy=True, **fixation_mapping)
    assert fix_n.fix_x.max() == pytest.approx(df_norm['CURRENT_FIX_X'].max() * 2400)
    assert fix_n.subset(subjects=['vp2']).fix_x.max() == pytest.approx(fix_n.fix_x[fix_n.subj_index == 'vp2'].max())
    df_sac, sm = fixations_to_saccades(fix_n.df, fix_n.mapping)
    sac = SaccadeData(df_sac, str(big), img=fix_n.img, scale=1., **sm)
    assert sac.sac_x0.max() <= fix_n.width
    assert sac.subset(subjects=['vp1']).sac_x0.max() <= fix_n.width
