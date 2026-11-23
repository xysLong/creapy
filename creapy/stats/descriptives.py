import itertools
import warnings
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy import stats as sp_stats
from creapy.misc.utils import natural_sorted


def coefficient_k(fix_dur, next_sac_amp, subj):
    """Ambient-focal coefficient K (Krejtz et al. 2016) per fixation."""
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
    """Amplitude in image pixels of the saccade that follows each fixation."""
    keys = [dataset_fix.subj_index_col] + ([dataset_fix.trial_col] if dataset_fix.trial_col else [])
    grouped = dataset_fix.df.groupby(keys, sort=False)
    next_x = grouped[dataset_fix.mapping['fix_x_col']].shift(-1)
    next_y = grouped[dataset_fix.mapping['fix_y_col']].shift(-1)
    return np.hypot(next_x - dataset_fix.fix_x, next_y - dataset_fix.fix_y).to_numpy(dtype=float)


def fixation_k(dataset_fix):
    """Per-fixation coefficient K (see coefficient_k) aligned with dataset_fix.df, from the fixation table alone."""
    k, _ = coefficient_k(dataset_fix.fix_dur, next_saccade_amplitude(dataset_fix), dataset_fix.subj_index)
    return k


def participant_table(dataset_fix, dataset_sac=None, mobile=False):
    """One row per participant with the fixation descriptives (n_fixations, mean/median duration, spread ...).

    mobile=True is for mobile eye tracking mapped onto snapshots: the trials are the visits of the snapshot, so the
    table gets n_visits and mean_visit_s, and leaves out what depends on the viewer's distance from the wall
    (saccade amplitudes and scanpath length in snapshot pixels, coefficient K)."""
    df_stats = dataset_fix.participant_stats()
    if mobile:
        if dataset_fix.trial_col:
            n_visits = dataset_fix.df.groupby(dataset_fix.subj_index_col, sort=False)[dataset_fix.trial_col].nunique()
        else:
            n_visits = pd.Series(1, index=dataset_fix.subjects)
        df_stats.insert(1, 'n_visits', df_stats['participant'].astype(object).map(n_visits).astype(int))
        df_stats.insert(df_stats.columns.get_loc('viewing_time_s') + 1, 'mean_visit_s',
                        df_stats['viewing_time_s'] / df_stats['n_visits'])
        return df_stats.drop(columns=['scanpath_length_px'])
    if dataset_sac is not None:
        df_sac = dataset_sac.participant_stats()
        df_stats = df_stats.merge(df_sac, on='participant', how='left')
    _, k_subj = coefficient_k(dataset_fix.fix_dur, next_saccade_amplitude(dataset_fix), dataset_fix.subj_index)
    df_stats['coefficient_K'] = df_stats['participant'].astype(object).map(k_subj)
    return df_stats


def participants_over_stimuli(datasets, mobile=False, roster=None):
    """participant_table() of every stimulus in one table: participant x stimulus, with the share of each
    participant's viewing time per stimulus and rank 1 for their longest-viewed stimulus.

    `datasets` maps stimulus -> (FixationData, SaccadeData) (see creapy.datasets_by_stimulus); with a `roster` (a
    list, or a dict stimulus -> participants) those without a fixation on a stimulus get a zero row (looked = False)."""
    ls = []
    for stim, (fix, sac) in datasets.items():
        df_ = participant_table(fix, None if mobile else sac, mobile=mobile)
        if roster is not None:
            from creapy.stats.visits import roster_of
            df_ = add_zero_rows(df_, roster_of(roster, stim), ['n_fixations', 'n_visits', 'viewing_time_s',
                                                               'total_fixation_duration', 'n_saccades'])
        df_.insert(1, 'stimulus', str(stim))
        ls.append(df_)
    df_all = pd.concat(ls, ignore_index=True)
    df_all['participant'] = df_all['participant'].astype(object)
    dwell_col = 'viewing_time_s'
    df_all['share_of_total'] = df_all[dwell_col] / df_all.groupby('participant')[dwell_col].transform('sum').replace(0., np.nan)
    df_all['rank'] = df_all.groupby('participant')[dwell_col].rank(method='min', ascending=False).where(df_all[dwell_col] > 0)
    return df_all


def add_zero_rows(df_table, roster, zero_columns, per=None):
    """Append a row per participant of `roster` missing from df_table, with 0 in zero_columns and NaN elsewhere.

    The column `looked` (True / False) says whether the participant appears in the data; `per` names a column such
    as 'aoi' whose values are repeated for every missing participant (one zero row per area)."""
    present = set(df_table['participant'].astype(object))
    missing = [s for s in roster if s not in present]
    df_ = df_table.copy()
    df_.insert(1, 'looked', True)
    if not missing:
        return df_
    if per is not None and per in df_.columns:
        values = list(pd.unique(df_[per]))
        rows = [{'participant': s, per: v} for s in missing for v in values]
    else:
        rows = [{'participant': s} for s in missing]
    zeros = {col: 0 for col in zero_columns if col in df_.columns}
    df_zero = pd.DataFrame.from_records([dict(row, looked=False, **zeros) for row in rows])
    df_out = pd.concat([df_, df_zero], ignore_index=True)
    order = {s: i for i, s in enumerate(natural_sorted(df_out['participant'].astype(object).unique()))}
    keys = ['participant'] + ([per] if per is not None and per in df_out.columns else [])
    df_out['_o'] = df_out['participant'].astype(object).map(order)
    return df_out.sort_values(['_o'] + keys[1:], kind='stable').drop(columns='_o').reset_index(drop=True)


def group_comparison(df_stats, grouping=None, columns=None, group_col='group', pairwise=False):
    """Per measure: n, mean, SD and median per group, plus the fitting test with an effect size.

    `grouping` maps participant -> group; without it the table's `group_col` is used (so a table with one row per
    participant and area can be compared area against area). Two groups: Welch t and Mann-Whitney U with Cohen's d,
    the rank-biserial r and a 95 % CI of the mean difference; when both groups hold exactly the same participants
    (two areas, two time windows) the paired t-test and Wilcoxon are used instead, with Cohen's dz. Three or more
    groups: one-way ANOVA and Kruskal-Wallis; pairwise=True adds one row per pair of groups."""
    df_ = df_stats.copy()
    if grouping is not None:
        df_[group_col] = df_['participant'].astype(object).map(grouping)
    assert group_col in df_.columns, "no groups: pass grouping (participant -> group) or a table with a group column"
    df_ = df_[df_[group_col].notna()]
    if columns is None:
        columns = [c for c in df_.columns if c not in ('participant', group_col, 'looked', 'stimulus', 'aoi', 'trial')
                   and pd.api.types.is_numeric_dtype(df_[c])]
    groups = natural_sorted(df_[group_col].unique())
    members = {g: df_.loc[df_[group_col] == g, 'participant'].astype(str) for g in groups}
    same = {(g1, g2): members[g1].is_unique and len(members[g1]) > 1 and set(members[g1]) == set(members[g2])
            for g1 in groups for g2 in groups}   # pairing decided on the full tables, not the complete cases
    ls = []
    warnings.simplefilter('ignore')   # constant samples make scipy warn; the NaN / inf statistic says it all
    for col in columns:
        row = {'measure': col}
        samples = {}
        for g in groups:
            df_g = df_.loc[df_[group_col] == g, ['participant', col]].dropna(subset=[col])
            values = df_g[col].to_numpy(dtype=float)
            samples[g] = df_g
            row[f'n_{g}'] = len(values)
            row[f'mean_{g}'] = values.mean() if len(values) else np.nan
            row[f'sd_{g}'] = values.std(ddof=1) if len(values) > 1 else np.nan
            row[f'median_{g}'] = float(np.median(values)) if len(values) else np.nan
        usable = {g: df_g for g, df_g in samples.items() if len(df_g) >= 2}
        if len(groups) == 2 and len(usable) == 2:
            row.update(two_sample_test(*usable.values(), col, paired=same[tuple(usable)]))
        elif len(usable) >= 3:
            values = [df_g[col].to_numpy(dtype=float) for df_g in usable.values()]
            f = safe_test(sp_stats.f_oneway, *values)
            kw = safe_test(sp_stats.kruskal, *values)
            row.update({'test': "one-way ANOVA", 'statistic': f[0], 'p_value': f[1], 'kruskal_H': kw[0], 'kruskal_p': kw[1]})
        else:
            row.update({'test': "n/a", 'statistic': np.nan, 'p_value': np.nan})
        ls.append(row)
        if pairwise and len(groups) > 2:
            for g1, g2 in itertools.combinations(groups, 2):
                if g1 not in usable or g2 not in usable:
                    continue
                pair = {'measure': f"{col}: {g1} vs {g2}"}
                for g in (g1, g2):
                    pair.update({k: row[k] for k in (f'n_{g}', f'mean_{g}', f'sd_{g}', f'median_{g}')})
                pair.update(two_sample_test(usable[g1], usable[g2], col, paired=same[(g1, g2)]))
                ls.append(pair)
    warnings.resetwarnings()
    return pd.DataFrame.from_records(ls)


def safe_test(test, *samples, **kwargs):
    """(statistic, p) of a scipy test, or (NaN, NaN) where the data leave it undefined (constant values, no pairs)."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            result = test(*samples, **kwargs)
        return float(result.statistic), float(result.pvalue)
    except ValueError:
        return np.nan, np.nan


def two_sample_test(df_a, df_b, col, paired=None):
    """Welch t + Mann-Whitney (independent groups) or paired t + Wilcoxon (same participants), with effect sizes.

    paired=None decides from the rows given; True pairs the participants present in both tables (complete cases)."""
    a = df_a[col].to_numpy(dtype=float)
    b = df_b[col].to_numpy(dtype=float)
    pa, pb = df_a['participant'].astype(str), df_b['participant'].astype(str)
    if paired is None:
        paired = len(a) == len(b) and len(a) > 1 and pa.is_unique and set(pa) == set(pb)
    if paired:
        sa, sb = df_a.set_index(pa)[col], df_b.set_index(pb)[col]
        common = sa.index.intersection(sb.index)
        a, b = sa.reindex(common).to_numpy(dtype=float), sb.reindex(common).to_numpy(dtype=float)
    if paired and len(a) < 2:
        paired = False
        a, b = df_a[col].to_numpy(dtype=float), df_b[col].to_numpy(dtype=float)
    if paired:
        diff = a - b
        t = safe_test(sp_stats.ttest_rel, a, b)
        w_stat, w_p = safe_test(sp_stats.wilcoxon, a, b)
        sd = diff.std(ddof=1)
        se = sd / np.sqrt(len(diff))
        half = sp_stats.t.ppf(0.975, len(diff) - 1) * se
        return {'test': "paired t", 'statistic': t[0], 'p_value': t[1],
                'wilcoxon_W': w_stat, 'wilcoxon_p': w_p,
                'mean_difference': float(diff.mean()), 'ci95_low': float(diff.mean() - half),
                'ci95_high': float(diff.mean() + half), 'cohen_d': float(diff.mean() / sd) if sd > 0 else np.nan}
    t = safe_test(sp_stats.ttest_ind, a, b, equal_var=False)
    u = safe_test(sp_stats.mannwhitneyu, a, b, alternative='two-sided')
    pooled = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1)) / (len(a) + len(b) - 2))
    se = np.sqrt(a.var(ddof=1) / len(a) + b.var(ddof=1) / len(b))
    dof = se ** 4 / ((a.var(ddof=1) / len(a)) ** 2 / (len(a) - 1) + (b.var(ddof=1) / len(b)) ** 2 / (len(b) - 1)) \
        if se > 0 else 1
    half = sp_stats.t.ppf(0.975, dof) * se
    return {'test': "Welch t", 'statistic': t[0], 'p_value': t[1], 'mann_whitney_U': u[0], 'mann_whitney_p': u[1],
            'mean_difference': float(a.mean() - b.mean()), 'ci95_low': float(a.mean() - b.mean() - half),
            'ci95_high': float(a.mean() - b.mean() + half),
            'cohen_d': float((a.mean() - b.mean()) / pooled) if pooled > 0 else np.nan,
            'rank_biserial_r': float(2 * u[0] / (len(a) * len(b)) - 1) if np.isfinite(u[0]) else np.nan}


def show_group_boxplot(df_values, measure, grouping=None, ax=None, group_col='group', jitter=0.12, seed=0,
                       box_color='#c7d3e6', median_color='#1f5fbf', point_color='#333333'):
    """Boxplot of one measure by group with every participant as a jittered point."""
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
