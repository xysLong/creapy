import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.collections import PolyCollection


OUTSIDE = 'outside'


def aoi_sequence(fix, names=None, include_outside=True):
    """Which AOI each fixation fell into, in viewing order."""
    if names is None:
        names = list(fix.areas_of_interest)
    label = np.full(len(fix.df), OUTSIDE, dtype=object)
    assigned = np.zeros(len(fix.df), dtype=bool)
    for name in names:
        inside = np.asarray(fix.aoi_mask(name)) & ~assigned
        label[inside] = name
        assigned |= inside
    df_seq = pd.DataFrame({'participant': fix.subj_index.to_numpy(),
                           'trial': fix.df[fix.trial_col].to_numpy() if fix.trial_col else 1,
                           'segment': fix.segments(),
                           't': fix.t.to_numpy(), 'clock': fix.viewing_clock().to_numpy(),
                           'dur': fix.fix_dur.to_numpy(), 'aoi': label})
    df_seq['order'] = df_seq.groupby(['participant', 'trial']).cumcount() + 1
    if not include_outside:
        df_seq = df_seq[df_seq['aoi'] != OUTSIDE]
    return df_seq.reset_index(drop=True)


def collapse_runs(df_seq):
    """Merge consecutive fixations in the same AOI into one visit (never across a break, see FixationData.segments)."""
    if len(df_seq) == 0:
        return pd.DataFrame(columns=['participant', 'trial', 'segment', 'aoi', 't_start', 't_end', 'n_fixations', 'dwell'])
    keys = df_seq[['participant', 'trial', 'segment', 'aoi']].astype(object)
    new_run = (keys != keys.shift()).any(axis=1).to_numpy()
    run_id = np.cumsum(new_run)
    df_runs = df_seq.assign(_run=run_id).groupby('_run', sort=False).agg(
        participant=('participant', 'first'), trial=('trial', 'first'), segment=('segment', 'first'),
        aoi=('aoi', 'first'), t_start=('t', 'first'), t_end=('t', 'last'), n_fixations=('aoi', 'size'),
        dwell=('dur', 'sum'))
    return df_runs.reset_index(drop=True)


def transition_matrix(fix, names=None, include_outside=False, normalize='row', per_participant_weight=True):
    """AOI -> AOI transitions between consecutive visits, self-transitions excluded."""
    df_seq = aoi_sequence(fix, names=names, include_outside=include_outside)
    labels = (names if names is not None else list(fix.areas_of_interest)) + ([OUTSIDE] if include_outside else [])
    counts = pd.DataFrame(0., index=labels, columns=labels)
    if len(df_seq) == 0:
        return counts
    df_runs = collapse_runs(df_seq)
    ls = []
    for (subj, trial, _), df_ in df_runs.groupby(['participant', 'trial', 'segment'], sort=False):
        aoi = df_['aoi'].to_numpy()
        if len(aoi) < 2:
            continue
        df_t = pd.DataFrame({'from': aoi[:-1], 'to': aoi[1:]})
        df_t['participant'] = subj
        ls.append(df_t)
    if not ls:
        return counts
    df_trans = pd.concat(ls)
    if per_participant_weight:
        df_trans['w'] = 1. / df_trans.groupby('participant')['from'].transform('size')
    else:
        df_trans['w'] = 1.
    pivot = df_trans.pivot_table(index='from', columns='to', values='w', aggfunc='sum', fill_value=0.)
    counts = counts.add(pivot, fill_value=0.).loc[labels, labels]
    if per_participant_weight:
        counts = counts * df_trans['participant'].nunique()
    if normalize == 'row':
        row_sums = counts.sum(axis=1)
        counts = counts.div(row_sums.where(row_sums > 0, np.nan), axis=0)
    elif normalize == 'all':
        total = counts.to_numpy().sum()
        counts = counts / total if total > 0 else counts
    else:
        assert normalize is None, f"Unknown normalize: {normalize}"
    return counts


def show_transition_matrix(ax, matrix, cmap='Blues', fmt='{:.0%}', text_color_switch=0.6):
    """Draw a transition_matrix() as a heat-table on ax (rows = from, columns = to)."""
    values = matrix.to_numpy(dtype=float)
    im = ax.imshow(np.nan_to_num(values), cmap=cmap, vmin=0, vmax=np.nanmax(values) if np.isfinite(values).any() else 1)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_yticks(range(len(matrix.index)))
    ax.set_xticklabels(matrix.columns, rotation=45, ha='right')
    ax.set_yticklabels(matrix.index)
    ax.set_xlabel("to")
    ax.set_ylabel("from")
    vmax = np.nanmax(values) if np.isfinite(values).any() else 1
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            v = values[i, j]
            if np.isnan(v):
                continue
            ax.text(j, i, fmt.format(v) if fmt else f"{v:.2f}", ha='center', va='center', fontsize=8,
                    color='white' if v > text_color_switch * vmax else 'black')
    return im


def aoi_palette(names, include_outside=True):
    """Dict AOI name -> RGBA colour (tab10 cycle), plus a grey for 'outside' unless include_outside=False."""
    palette = plt.get_cmap('tab10')
    colors = {name: palette(i % 10) for i, name in enumerate(names)}
    if include_outside:
        colors[OUTSIDE] = (0.35, 0.35, 0.38, 1.)
    return colors


def show_scarf_plot(ax, fix, names=None, subjects=None, colors=None, relative_time=True, outside_alpha=0.35,
                    row_height=0.8):
    """Scarf plot: one row per participant, viewing time on x."""
    df_seq = aoi_sequence(fix, names=names, include_outside=True)
    if names is None:
        names = list(fix.areas_of_interest)
    if colors is None:
        colors = aoi_palette(names)
    if subjects is None:
        subjects = list(fix.subjects)
    dur_s = df_seq['dur'] / (1000. if fix.dur_unit == 'ms' else 1.)
    df_seq = df_seq.assign(dur_s=dur_s.to_numpy())
    row_of = {subj: row for row, subj in enumerate(subjects)}
    df_plot = df_seq[df_seq['participant'].isin(row_of)]
    if relative_time:
        t_start = df_plot['clock']   # trials / visits laid end to end, see FixationData.viewing_clock
    else:
        t_start = df_plot['t']
    rows = df_plot['participant'].map(row_of).to_numpy(dtype=float)
    x0 = t_start.to_numpy(dtype=float)
    x1 = x0 + df_plot['dur_s'].to_numpy(dtype=float)
    y0 = rows - row_height / 2
    y1 = rows + row_height / 2
    verts = np.stack([np.column_stack([x0, y0]), np.column_stack([x1, y0]),
                      np.column_stack([x1, y1]), np.column_stack([x0, y1])], axis=1)
    rgba = np.array([colors.get(a, (0.5, 0.5, 0.5, 1.)) for a in df_plot['aoi']], dtype=float)
    rgba[df_plot['aoi'].to_numpy() == OUTSIDE, 3] = outside_alpha
    ax.add_collection(PolyCollection(verts, facecolors=rgba, edgecolors='none'))
    ax.set_xlim(0, float(x1.max()) if len(x1) else 1.)
    if len(subjects) <= 40:
        ax.set_yticks(range(len(subjects)))
        ax.set_yticklabels([str(s) for s in subjects], fontsize=7 if len(subjects) > 30 else 9)
    else:
        step = 10 if len(subjects) <= 200 else 25
        ax.set_yticks(range(0, len(subjects), step))
        ax.set_yticklabels([str(subjects[i]) for i in range(0, len(subjects), step)], fontsize=7)
        ax.set_ylabel(f"participants ({len(subjects)})")
    ax.set_ylim(len(subjects) - 0.4, -0.6)
    ax.set_xlabel("Viewing time (s)")
    handles = [Patch(color=colors[name], label=name) for name in names] + \
              [Patch(color=colors[OUTSIDE], alpha=outside_alpha, label=OUTSIDE)]
    ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(1.01, 1.), fontsize=8, frameon=False)
    return df_seq


def aoi_run_sequences(fix, names=None, min_run_s=0., bridge_gap_s=0.):
    """Per participant and trial: the order of the areas looked at, as runs ("A > L > A"), with switches and dwell.

    Runs are consecutive fixations in one area. Looks outside every area shorter than bridge_gap_s do not break a
    run (so a glance off the label and back counts as one run of reading); runs shorter than min_run_s (dwell) are
    dropped as glances. Dwell is in the unit of the table; n_switches counts changes between different areas."""
    if names is None:
        names = list(fix.areas_of_interest)
    df_runs, pairs = filtered_runs(fix, names, min_run_s=min_run_s, bridge_gap_s=bridge_gap_s, include_outside=False)
    by_pair = dict(list(df_runs.groupby(['participant', 'trial'], sort=False))) if len(df_runs) else {}
    ls = []
    for subj, trial in pairs:
        runs = by_pair.get((subj, trial), df_runs.iloc[0:0])
        aoi = runs['aoi'].tolist()
        row = {'participant': subj, 'trial': trial,
               'first_aoi': aoi[0] if aoi else np.nan,
               'sequence': ' > '.join(aoi),
               'n_runs': len(aoi),
               'n_switches': int(np.sum(np.array(aoi[1:]) != np.array(aoi[:-1]))) if len(aoi) > 1 else 0}
        for name in names:
            hits = runs[runs['aoi'] == name]
            row[f'runs_{name}'] = int(len(hits))
            row[f'dwell_{name}'] = float(hits['dwell'].sum())
        ls.append(row)
    return pd.DataFrame.from_records(ls)


def filtered_runs(fix, names, min_run_s=0., bridge_gap_s=0., include_outside=False):
    """collapse_runs() of the whole dataset with the glance and bridging rules applied, adjacent same-area runs merged.

    Returns (runs, pairs): pairs lists every (participant, trial) of the dataset, including those left without a run."""
    df_seq = aoi_sequence(fix, names=names, include_outside=True)
    pairs = list(df_seq[['participant', 'trial']].drop_duplicates().itertuples(index=False, name=None))
    to_s = 1000. if fix.dur_unit == 'ms' else 1.
    runs = collapse_runs(df_seq)
    if bridge_gap_s > 0:
        runs = runs[~((runs['aoi'] == OUTSIDE) & (runs['dwell'] / to_s <= bridge_gap_s))]
    if not include_outside:
        runs = runs[runs['aoi'] != OUTSIDE]
    if min_run_s > 0:
        runs = runs[(runs['dwell'] / to_s >= min_run_s) | (runs['aoi'] == OUTSIDE)]
    if len(runs) == 0:
        return runs.reset_index(drop=True), pairs
    keys = runs[['participant', 'trial', 'aoi']].astype(object)
    new_run = (keys != keys.shift()).any(axis=1).to_numpy()
    merged = runs.assign(_run=np.cumsum(new_run)).groupby('_run', sort=False).agg(
        participant=('participant', 'first'), trial=('trial', 'first'), segment=('segment', 'first'),
        aoi=('aoi', 'first'), t_start=('t_start', 'min'), t_end=('t_end', 'max'),
        n_fixations=('n_fixations', 'sum'), dwell=('dwell', 'sum'))
    return merged.reset_index(drop=True), pairs


def transition_counts(fix, names=None, include_outside=False, min_run_s=0., bridge_gap_s=0.):
    """Per participant and trial: how often the gaze went from each area to each other area (one column per pair).

    Counts the changes between consecutive runs (see aoi_run_sequences for min_run_s and bridge_gap_s), so
    'label>painting' is the number of times a look at the painting followed a run on the label. Returns in viewing
    order, directional: 'A>B' and 'B>A' are different columns. include_outside adds the looks outside every area
    as a station of their own."""
    if names is None:
        names = list(fix.areas_of_interest)
    stations = list(names) + ([OUTSIDE] if include_outside else [])
    directions = [(a, b) for a in stations for b in stations if a != b]
    df_runs, pairs = filtered_runs(fix, names, min_run_s=min_run_s, bridge_gap_s=bridge_gap_s, include_outside=include_outside)
    by_pair = dict(list(df_runs.groupby(['participant', 'trial'], sort=False))) if len(df_runs) else {}
    ls = []
    for subj, trial in pairs:
        aoi = by_pair[(subj, trial)]['aoi'].tolist() if (subj, trial) in by_pair else []
        row = {'participant': subj, 'trial': trial, 'n_transitions': max(len(aoi) - 1, 0)}
        counts = {pair: 0 for pair in directions}
        for a, b in zip(aoi[:-1], aoi[1:]):
            if (a, b) in counts:
                counts[(a, b)] += 1
        row.update({f'{a}>{b}': n for (a, b), n in counts.items()})
        ls.append(row)
    return pd.DataFrame.from_records(ls)


def merge_adjacent_runs(df_runs):
    """Merge consecutive rows of a collapse_runs() table that fall in the same area (after dropping rows between)."""
    if len(df_runs) < 2:
        return df_runs.reset_index(drop=True)
    aoi = df_runs['aoi'].to_numpy()
    run_id = np.cumsum(np.r_[True, aoi[1:] != aoi[:-1]])
    df_ = df_runs.groupby(run_id, sort=False).agg(participant=('participant', 'first'), trial=('trial', 'first'),
                                                  segment=('segment', 'first'), aoi=('aoi', 'first'),
                                                  t_start=('t_start', 'min'), t_end=('t_end', 'max'),
                                                  n_fixations=('n_fixations', 'sum'), dwell=('dwell', 'sum'))
    return df_.reset_index(drop=True)


def first_fixation_order(fix, names=None):
    """In which order each participant first visited the AOIs."""
    df_seq = aoi_sequence(fix, names=names, include_outside=False)
    if names is None:
        names = list(fix.areas_of_interest)
    ls = []
    for subj in fix.subjects:
        df_ = df_seq[df_seq['participant'] == subj]
        firsts = df_.groupby('aoi')['clock'].min().sort_values()
        rank = {name: i + 1 for i, name in enumerate(firsts.index)}
        row = {'participant': subj}
        row.update({name: rank.get(name, np.nan) for name in names})
        ls.append(row)
    return pd.DataFrame.from_records(ls)


if __name__ == '__main__':
    pass
