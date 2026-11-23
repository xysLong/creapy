import itertools
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from tqdm import tqdm


def recurrence_matrix(xy, radius):
    """Boolean (n, n) recurrence matrix of a scanpath: True where fixations i and j lie within radius pixels."""
    xy = np.asarray(xy, dtype=float).reshape(-1, 2)
    return cdist(xy, xy) <= radius


def _line_points(mask, min_line):
    mask = np.concatenate([[False], np.asarray(mask, dtype=bool), [False]])
    edges = np.flatnonzero(np.diff(mask.astype(int)))
    lengths = edges[1::2] - edges[::2]
    return int(lengths[lengths >= min_line].sum())


def rqa_measures(xy, radius, min_line=2):
    """Recurrence quantification analysis of one scanpath after Anderson et al. 2013."""
    xy = np.asarray(xy, dtype=float).reshape(-1, 2)
    n = len(xy)
    nan_row = {'n_fixations': n, 'recurrence': np.nan, 'determinism': np.nan, 'laminarity': np.nan,
               'corm': np.nan, 'n_recurrent_pairs': 0}
    if n < 2:
        return nan_row
    rec = np.triu(recurrence_matrix(xy, radius), k=1)
    r = int(rec.sum())
    if r == 0:
        return dict(nan_row, recurrence=0.)

    d_l = sum(_line_points(np.diagonal(rec, offset=k), min_line) for k in range(1, n))
    v_l = sum(_line_points(rec[:j, j], min_line) for j in range(1, n))
    h_l = sum(_line_points(rec[i, i + 1:], min_line) for i in range(n - 1))
    ii, jj = np.nonzero(rec)

    return {'n_fixations': n,
            'recurrence': 100. * 2 * r / (n * (n - 1)),
            'determinism': 100. * d_l / r,
            'laminarity': 100. * (h_l + v_l) / (2 * r),
            'corm': 100. * np.sum(jj - ii) / ((n - 1) * r),
            'n_recurrent_pairs': r}


def default_radius(fix):
    """Default recurrence radius for a dataset: 5 % of the stimulus diagonal in pixels."""
    return 0.05 * np.hypot(fix.width, fix.height)


def participant_rqa(fix, radius=None, min_line=2):
    """RQA measures per participant, one row each."""
    if radius is None:
        radius = default_radius(fix)
    keys = [fix.subj_index_col] + ([fix.trial_col] if fix.trial_col else [])
    ls = []
    for key, df_ in fix.df.groupby(keys, sort=False):
        subj = key[0] if isinstance(key, tuple) else key
        xy = np.column_stack([fix.fix_x[df_.index].to_numpy(), fix.fix_y[df_.index].to_numpy()])
        ls.append(dict(participant=subj, **rqa_measures(xy, radius, min_line=min_line)))
    df_trials = pd.DataFrame.from_records(ls)
    df_rqa = df_trials.groupby('participant', sort=False).mean().reset_index()
    df_rqa['radius'] = radius
    df_rqa['participant'] = pd.Categorical(df_rqa['participant'], categories=fix.subjects, ordered=True)
    return df_rqa.sort_values('participant').reset_index(drop=True)


def cross_recurrence(xy_a, xy_b, radius):
    """Cross-recurrence of two scanpaths (each an (n, 2) array of x, y in pixels)."""
    xy_a = np.asarray(xy_a, dtype=float).reshape(-1, 2)
    xy_b = np.asarray(xy_b, dtype=float).reshape(-1, 2)
    if len(xy_a) == 0 or len(xy_b) == 0:
        return np.nan
    return float(np.mean(cdist(xy_a, xy_b) <= radius))


def cross_recurrence_table(fix, radius=None, verbose=True, progress=None):
    """Cross-recurrence for every unordered pair of participants, diagonal included."""
    if radius is None:
        radius = default_radius(fix)
    xy_subj = {}
    for subj in fix.subjects:
        mask = (fix.subj_index == subj).to_numpy()
        xy_subj[subj] = np.column_stack([fix.fix_x[mask].to_numpy(), fix.fix_y[mask].to_numpy()])
    combos = list(itertools.combinations_with_replacement(fix.subjects, 2))
    ls = []
    for i, (a, b) in enumerate(tqdm(combos, desc="Cross-recurrence", disable=not verbose)):
        if progress is not None and i % 20 == 0 and progress(i, len(combos), "cross-recurrence pairs") is False:
            raise InterruptedError("Computation cancelled.")
        ls.append({'subject_a': a, 'subject_b': b, 'cross_recurrence': cross_recurrence(xy_subj[a], xy_subj[b], radius)})
    return pd.DataFrame.from_records(ls, columns=['subject_a', 'subject_b', 'cross_recurrence'])


def show_recurrence_plot(ax, xy, radius, color='white'):
    """Draw the recurrence plot of one scanpath on ax: fixation index on both axes."""
    rec = recurrence_matrix(xy, radius)
    n = len(rec)
    ii, jj = np.nonzero(rec)
    ax.set_facecolor('black')
    ax.scatter(jj, ii, s=max(4., (180. / max(n, 1)) ** 2), marker='s', color=color, linewidths=0)
    ax.set_xlim([-0.5, n - 0.5])
    ax.set_ylim([-0.5, n - 0.5])
    ax.set_aspect('equal')
    ax.set_xlabel('Fixation index')
    ax.set_ylabel('Fixation index')
    return rec


if __name__ == '__main__':
    pass
