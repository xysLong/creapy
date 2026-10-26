import itertools
import numpy as np
import pandas as pd
from scipy.spatial.distance import cdist
from tqdm import tqdm


# Recurrence quantification analysis of fixation sequences after
# Anderson, Bischof, Laidlaw, Risko & Kingstone (2013), Behav Res Methods 45:842-856.
# Two fixations recur when they lie within `radius` pixels of each other; the measures describe the
# upper triangle (i < j) of the symmetric recurrence matrix, exactly as in the paper.


def recurrence_matrix(xy, radius):
    """
    Boolean (n, n) recurrence matrix of a scanpath: True where fixations i and j lie within radius pixels of
    each other. xy is an (n, 2) array of x, y in pixels; the diagonal is always True.
    """
    # xy: (n, 2) array of fixation positions -> boolean (n, n) matrix, r_ij = dist(i, j) <= radius
    xy = np.asarray(xy, dtype=float).reshape(-1, 2)
    return cdist(xy, xy) <= radius


def _line_points(mask, min_line):
    # number of True entries of a 1-D boolean mask that sit in runs of length >= min_line
    mask = np.concatenate([[False], np.asarray(mask, dtype=bool), [False]])
    edges = np.flatnonzero(np.diff(mask.astype(int)))  # run starts at even positions, ends at odd ones
    lengths = edges[1::2] - edges[::2]
    return int(lengths[lengths >= min_line].sum())


def rqa_measures(xy, radius, min_line=2):
    """
    Recurrence quantification analysis of one scanpath after Anderson et al. 2013. xy is an (n, 2) array of
    fixation positions in pixels, radius in pixels, min_line the shortest run (in fixations) that counts as a line.
    Returns a dict with n_fixations, recurrence, determinism, laminarity, corm (all in percent) and
    n_recurrent_pairs. Fewer than two fixations give NaN measures; no recurrent pair gives recurrence 0 and the
    other measures NaN.
    """
    xy = np.asarray(xy, dtype=float).reshape(-1, 2)
    n = len(xy)
    nan_row = {'n_fixations': n, 'recurrence': np.nan, 'determinism': np.nan, 'laminarity': np.nan,
               'corm': np.nan, 'n_recurrent_pairs': 0}
    if n < 2:
        return nan_row
    rec = np.triu(recurrence_matrix(xy, radius), k=1)  # strict upper triangle, i < j
    r = int(rec.sum())
    if r == 0:
        return dict(nan_row, recurrence=0.)

    # diagonal lines: every diagonal above the main one
    d_l = sum(_line_points(np.diagonal(rec, offset=k), min_line) for k in range(1, n))
    # vertical lines (column j, rows < j) and horizontal lines (row i, columns > i); the paper counts both
    # in the upper triangle and divides by 2R
    v_l = sum(_line_points(rec[:j, j], min_line) for j in range(1, n))
    h_l = sum(_line_points(rec[i, i + 1:], min_line) for i in range(n - 1))
    ii, jj = np.nonzero(rec)

    return {'n_fixations': n,
            'recurrence': 100. * 2 * r / (n * (n - 1)),
            'determinism': 100. * d_l / r,
            'laminarity': 100. * (h_l + v_l) / (2 * r),
            'corm': 100. * np.sum(jj - ii) / ((n - 1) * r),  # 0 = refixations right away, 100 = far apart in time
            'n_recurrent_pairs': r}


def default_radius(fix):
    """
    Default recurrence radius for a dataset: 5 % of the stimulus diagonal in pixels (Anderson et al. used 64 px
    on 1024-px-wide images).
    """
    # Anderson et al. used 64 px on 1024-px-wide stimuli, i.e. roughly 5 % of the image diagonal;
    # scaling with the diagonal keeps the measures comparable across differently sized images
    return 0.05 * np.hypot(fix.width, fix.height)


def participant_rqa(fix, radius=None, min_line=2):
    """
    RQA measures per participant: DataFrame with columns participant, n_fixations, recurrence, determinism,
    laminarity, corm, n_recurrent_pairs and radius (see rqa_measures). radius in pixels, default
    default_radius(fix); min_line in fixations. With a trial column each trial is one scanpath and the rows are
    means over the participant's trials.
    """
    # One row per participant. With a trial column the measures are computed per trial (one scanpath each)
    # and then averaged over the participant's trials, so n_fixations etc. are per-trial means.
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
    """
    Cross-recurrence of two scanpaths (each an (n, 2) array of x, y in pixels): the share of fixation pairs
    across the two that lie within radius pixels, a fraction in [0, 1]. Symmetric and order-free; NaN if
    either path is empty.
    """
    # share of (i, j) pairs across the two scanpaths within radius, a fraction in [0, 1]; symmetric and
    # order-free (it only asks whether the two viewers looked at the same places, not when)
    xy_a = np.asarray(xy_a, dtype=float).reshape(-1, 2)
    xy_b = np.asarray(xy_b, dtype=float).reshape(-1, 2)
    if len(xy_a) == 0 or len(xy_b) == 0:
        return np.nan
    return float(np.mean(cdist(xy_a, xy_b) <= radius))


def cross_recurrence_table(fix, radius=None, verbose=True, progress=None):
    """
    Cross-recurrence for every unordered pair of participants, diagonal included: DataFrame with columns
    subject_a, subject_b, cross_recurrence. radius in pixels (default default_radius(fix)); each participant's
    trials are concatenated into one scanpath. progress(done, total, text) may return False to cancel.
    """
    # all unordered participant pairs incl. the diagonal, one scanpath per participant (trials concatenated);
    # progress(done, total, text) may return False to abort
    if radius is None:
        radius = default_radius(fix)
    xy_subj = {}  # subject -> (n, 2) array
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
    """
    Draw the recurrence plot of one scanpath on ax: fixation index on both axes, a square for every recurrent
    pair on a black background, origin lower-left. xy is an (n, 2) array in pixels, radius in pixels. Returns
    the boolean recurrence matrix.
    """
    # the recurrence plot: fixation index on both axes, recurrent pairs as squares, origin lower-left
    rec = recurrence_matrix(xy, radius)
    n = len(rec)
    ii, jj = np.nonzero(rec)
    ax.set_facecolor('black')
    # marker side ~ one cell, so dense plots look like imshow and sparse ones stay legible
    ax.scatter(jj, ii, s=max(4., (180. / max(n, 1)) ** 2), marker='s', color=color, linewidths=0)
    # ax.imshow(rec, cmap='gray', origin='lower', interpolation='nearest')
    ax.set_xlim([-0.5, n - 0.5])
    ax.set_ylim([-0.5, n - 0.5])
    ax.set_aspect('equal')
    ax.set_xlabel('Fixation index')
    ax.set_ylabel('Fixation index')
    return rec


if __name__ == '__main__':
    pass
