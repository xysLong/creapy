import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.collections import PolyCollection

# AOI sequences: which area each fixation falls into, in viewing order. Feeds the transition matrix, the scarf plot
# (participants x time, coloured by AOI: Richardson & Dale 2005 / the Tobii "AOI sequence chart") and the
# visit/revisit counts. A fixation inside several overlapping AOIs is assigned to the FIRST one in the dict order.

OUTSIDE = 'outside'


def aoi_sequence(fix, names=None, include_outside=True):
    """
    Which AOI each fixation fell into, in viewing order. One row per fixation with columns participant, trial,
    t (fixation onset in seconds), dur (duration in the dataset's unit), aoi (AOI name or 'outside') and order
    (1-based rank within participant and trial). names restricts and orders the AOIs; a fixation inside several
    overlapping AOIs goes to the first one. include_outside=False drops fixations outside every AOI.
    """
    # One row per fixation: participant, trial, order, t (s), dur, aoi (name or 'outside')
    if names is None:
        names = list(fix.areas_of_interest)
    label = np.full(len(fix.df), OUTSIDE, dtype=object)
    assigned = np.zeros(len(fix.df), dtype=bool)
    for name in names:
        inside = np.asarray(fix.areas_of_interest[name].contains(fix.fix_points)) & ~assigned
        label[inside] = name
        assigned |= inside
    df_seq = pd.DataFrame({'participant': fix.subj_index.to_numpy(),
                           'trial': fix.df[fix.trial_col].to_numpy() if fix.trial_col else 1,
                           't': fix.t.to_numpy(), 'dur': fix.fix_dur.to_numpy(), 'aoi': label})
    df_seq['order'] = df_seq.groupby(['participant', 'trial']).cumcount() + 1
    if not include_outside:
        df_seq = df_seq[df_seq['aoi'] != OUTSIDE]
    return df_seq.reset_index(drop=True)


def collapse_runs(df_seq):
    """
    Merge consecutive fixations in the same AOI into one visit. Takes the output of aoi_sequence and returns one
    row per visit: participant, trial, aoi, t_start, t_end (onset of the first and last fixation, seconds),
    n_fixations and dwell (summed duration in the dataset's unit).
    """
    # Consecutive fixations in the same AOI -> one visit: participant, trial, aoi, t_start, t_end, n_fixations, dwell
    ls = []
    for (subj, trial), df_ in df_seq.groupby(['participant', 'trial'], sort=False):
        aoi = df_['aoi'].to_numpy()
        new_run = np.r_[True, aoi[1:] != aoi[:-1]]
        run_id = np.cumsum(new_run)
        for _, df_run in df_.groupby(run_id, sort=False):
            ls.append({'participant': subj, 'trial': trial, 'aoi': df_run['aoi'].iloc[0],
                       't_start': float(df_run['t'].iloc[0]), 't_end': float(df_run['t'].iloc[-1]),
                       'n_fixations': int(len(df_run)), 'dwell': float(df_run['dur'].sum())})
    return pd.DataFrame.from_records(ls)


def transition_matrix(fix, names=None, include_outside=False, normalize='row', per_participant_weight=True):
    """
    AOI -> AOI transitions between consecutive VISITS (self-transitions excluded, so a run of fixations inside one
    AOI counts once). normalize: None (counts), 'row' (share of departures from each AOI), 'all' (share of all
    transitions). per_participant_weight=True weights every participant's transitions to sum to 1, so a viewer
    with many fixations does not dominate.
    """
    df_seq = aoi_sequence(fix, names=names, include_outside=include_outside)
    labels = (names if names is not None else list(fix.areas_of_interest)) + ([OUTSIDE] if include_outside else [])
    counts = pd.DataFrame(0., index=labels, columns=labels)
    if len(df_seq) == 0:
        return counts
    df_runs = collapse_runs(df_seq)
    ls = []
    for (subj, trial), df_ in df_runs.groupby(['participant', 'trial'], sort=False):
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
        counts = counts * df_trans['participant'].nunique()  # back to "number of transitions"-like scale
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
    """
    Draw a transition_matrix() as a heat-table on ax: rows = from, columns = to, each cell annotated with its
    value (fmt, default percent; NaN cells stay blank). Returns the AxesImage.
    """
    # Heat-table of the transition matrix with the value written into each cell
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
    """
    Scarf plot: one row per participant, viewing time on x, each fixation a bar coloured by the AOI it fell into
    (grey = outside every AOI). Several trials of one participant are concatenated in time order.
    """
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
        t_start = df_plot['t'] - df_plot.groupby('participant')['t'].transform('min')
    else:
        t_start = df_plot['t']
    rows = df_plot['participant'].map(row_of).to_numpy(dtype=float)
    x0 = t_start.to_numpy(dtype=float)
    x1 = x0 + df_plot['dur_s'].to_numpy(dtype=float)
    y0 = rows - row_height / 2
    y1 = rows + row_height / 2
    # one PolyCollection for all fixations (23k bars as separate artists took 14 s to draw)
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
        # 157 participant names would overprint: label every tenth row
        step = 10 if len(subjects) <= 200 else 25
        ax.set_yticks(range(0, len(subjects), step))
        ax.set_yticklabels([str(subjects[i]) for i in range(0, len(subjects), step)], fontsize=7)
        ax.set_ylabel(f"participants ({len(subjects)})")
    ax.set_ylim(len(subjects) - 0.4, -0.6)  # first participant on top
    ax.set_xlabel("Viewing time (s)")
    handles = [Patch(color=colors[name], label=name) for name in names] + \
              [Patch(color=colors[OUTSIDE], alpha=outside_alpha, label=OUTSIDE)]
    ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(1.01, 1.), fontsize=8, frameon=False)
    return df_seq


def first_fixation_order(fix, names=None):
    """
    In which order each participant first visited the AOIs. One row per participant with one column per AOI
    holding the rank of its first fixation (1 = looked at first); NaN means the AOI was never fixated.
    """
    # Which AOI was looked at first, second, ... per participant (rank of the first visit; NaN = never)
    df_seq = aoi_sequence(fix, names=names, include_outside=False)
    if names is None:
        names = list(fix.areas_of_interest)
    ls = []
    for subj in fix.subjects:
        df_ = df_seq[df_seq['participant'] == subj]
        firsts = df_.groupby('aoi')['t'].min().sort_values()
        rank = {name: i + 1 for i, name in enumerate(firsts.index)}
        row = {'participant': subj}
        row.update({name: rank.get(name, np.nan) for name in names})
        ls.append(row)
    return pd.DataFrame.from_records(ls)


if __name__ == '__main__':
    pass
