import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats as sp_stats
from creapy.misc.utils import natural_sorted


def coefficient_k(fix_dur, next_sac_amp, subj):
    """
    Ambient–focal coefficient K (Krejtz et al. 2016): per fixation, z(duration) - z(amplitude of the following
    saccade), both standardized over all fixations of the stimulus; K > 0 = focal (long fixations, short
    saccades), K < 0 = ambient. Returns the per-fixation K and the per-participant mean.
    """
    fix_dur = np.asarray(fix_dur, dtype=float)
    next_sac_amp = np.asarray(next_sac_amp, dtype=float)
    subj = np.asarray(subj)
    ok = np.isfinite(fix_dur) & np.isfinite(next_sac_amp)
    k = np.full(len(fix_dur), np.nan)
    if ok.sum() >= 3 and fix_dur[ok].std() > 0 and next_sac_amp[ok].std() > 0:
        k[ok] = (fix_dur[ok] - fix_dur[ok].mean()) / fix_dur[ok].std() \
                - (next_sac_amp[ok] - next_sac_amp[ok].mean()) / next_sac_amp[ok].std()
    df_k = pd.DataFrame({'subj': subj, 'K': k})
    return k, df_k.groupby('subj', sort=False)['K'].mean()


def next_saccade_amplitude(dataset_fix):
    """
    Amplitude in image pixels of the saccade that follows each fixation, i.e. the distance to the next fixation of
    the same participant (and trial), aligned with dataset_fix.df; NaN for the last fixation of each viewing.
    """
    keys = [dataset_fix.subj_index_col] + ([dataset_fix.trial_col] if dataset_fix.trial_col else [])
    grouped = dataset_fix.df.groupby(keys, sort=False)
    next_x = grouped[dataset_fix.mapping['fix_x_col']].shift(-1)
    next_y = grouped[dataset_fix.mapping['fix_y_col']].shift(-1)
    return np.hypot(next_x - dataset_fix.fix_x, next_y - dataset_fix.fix_y).to_numpy(dtype=float)


def fixation_k(dataset_fix):
    """Per-fixation coefficient K (see coefficient_k) aligned with dataset_fix.df, from the fixation table alone."""
    k, _ = coefficient_k(dataset_fix.fix_dur, next_saccade_amplitude(dataset_fix), dataset_fix.subj_index)
    return k


def participant_table(dataset_fix, dataset_sac=None):
    """
    One row per participant with the fixation descriptives (n_fixations, mean/median duration, spread ...), the
    saccade descriptives when dataset_sac is given (n_saccades, mean amplitude, scanpath length ...) and
    coefficient_K. The table behind the GUI's Statistics view; durations in dataset_fix.dur_unit, distances in px.
    """
    df_stats = dataset_fix.participant_stats()
    if dataset_sac is not None:
        df_sac = dataset_sac.participant_stats()
        df_stats = df_stats.merge(df_sac, on='participant', how='left')
    # K from the fixation table itself: the saccade following fixation i goes to fixation i + 1
    _, k_subj = coefficient_k(dataset_fix.fix_dur, next_saccade_amplitude(dataset_fix), dataset_fix.subj_index)
    df_stats['coefficient_K'] = df_stats['participant'].astype(object).map(k_subj)
    return df_stats


def group_comparison(df_stats, grouping, columns=None):
    """
    Group means per measure plus a two-sample test (Welch t for two groups, one-way ANOVA for more) and a
    Mann–Whitney U for two groups. grouping: participant -> group name. Participants without a group are left out.
    """
    df_ = df_stats.copy()
    df_['group'] = df_['participant'].astype(object).map(grouping)
    df_ = df_[df_['group'].notna()]
    if columns is None:
        columns = [c for c in df_.columns if c not in ('participant', 'group') and pd.api.types.is_numeric_dtype(df_[c])]
    groups = sorted(df_['group'].unique())
    ls = []
    for col in columns:
        row = {'measure': col}
        samples = []
        for g in groups:
            values = df_.loc[df_['group'] == g, col].dropna().to_numpy(dtype=float)
            samples.append(values)
            row[f'mean_{g}'] = values.mean() if len(values) else np.nan
            row[f'sd_{g}'] = values.std(ddof=1) if len(values) > 1 else np.nan
            row[f'n_{g}'] = len(values)
        usable = [v for v in samples if len(v) >= 2]
        if len(usable) == 2 and len(groups) == 2:
            t = sp_stats.ttest_ind(*usable, equal_var=False)
            u = sp_stats.mannwhitneyu(*usable, alternative='two-sided')
            row.update({'test': "Welch t", 'statistic': float(t.statistic), 'p_value': float(t.pvalue),
                        'mann_whitney_U': float(u.statistic), 'mann_whitney_p': float(u.pvalue)})
        elif len(usable) >= 3:
            f = sp_stats.f_oneway(*usable)
            row.update({'test': "one-way ANOVA", 'statistic': float(f.statistic), 'p_value': float(f.pvalue)})
        else:
            row.update({'test': "n/a", 'statistic': np.nan, 'p_value': np.nan})
        ls.append(row)
    return pd.DataFrame.from_records(ls)


def show_group_boxplot(df_values, measure, grouping=None, ax=None, group_col='group', jitter=0.12, seed=0,
                       box_color='#c7d3e6', median_color='#1f5fbf', point_color='#333333'):
    """
    Boxplot of one measure by group with every participant as a jittered point: the group boxplot of the GUI's
    Statistics and Recurrence views. df_values has one row per participant (participant_table, participant_rqa,
    aoi_metrics ...) and either a `group_col` or a `grouping` (participant -> group) that adds one. Participants
    without a group are left out. Returns the group names in plotting order.
    """
    df_ = df_values.copy()
    if grouping is not None:
        df_[group_col] = df_['participant'].astype(object).map(grouping)
    assert group_col in df_.columns, "no groups: pass grouping (participant -> group) or a table with a group column"
    names = natural_sorted(df_[group_col].dropna().unique())
    assert names, "no participant has a group"
    data = [df_.loc[df_[group_col] == g, measure].dropna().to_numpy(dtype=float) for g in names]
    show = ax is None
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(5, 5))
    ax.boxplot(data, tick_labels=[f"{g} (n={len(d)})" for g, d in zip(names, data)], patch_artist=True,
               boxprops={'facecolor': box_color}, medianprops={'color': median_color})
    rng = np.random.default_rng(seed)
    for i, d in enumerate(data, start=1):
        ax.scatter(i + rng.uniform(-jitter, jitter, len(d)), d, s=18, color=point_color, alpha=0.7, zorder=3)
    ax.set_ylabel(measure)
    if show:
        ax.figure.tight_layout()
        plt.show()
    return names


if __name__ == '__main__':
    pass
