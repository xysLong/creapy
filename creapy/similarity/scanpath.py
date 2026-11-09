import itertools
import numpy as np
import pandas as pd
from tqdm import tqdm


def scanmatch(path_a, path_b, width, height, grid=(12, 8), temporal_bin=None, gap=0., threshold_share=0.25):
    """ScanMatch similarity of two scanpaths (Cristino et al. 2010), a score in [0, 1]."""
    path_a, path_b = np.asarray(path_a, dtype=float), np.asarray(path_b, dtype=float)
    assert path_a.ndim == 2 and path_a.shape[1] == 3 and path_b.ndim == 2 and path_b.shape[1] == 3
    assert len(path_a) > 0 and len(path_b) > 0
    seq_a = __to_sequence(path_a, width, height, grid, temporal_bin)
    seq_b = __to_sequence(path_b, width, height, grid, temporal_bin)
    sub, max_score = __substitution_matrix(grid, threshold_share)
    score = __needleman_wunsch(seq_a, seq_b, sub, gap)
    return float(np.clip(score / (max_score * max(len(seq_a), len(seq_b))), 0., 1.))


def __to_sequence(path, width, height, grid, temporal_bin):
    n_cols, n_rows = grid
    col = np.clip(np.floor(path[:, 0] / width * n_cols), 0, n_cols - 1).astype(int)
    row = np.clip(np.floor(path[:, 1] / height * n_rows), 0, n_rows - 1).astype(int)
    cells = row * n_cols + col
    if temporal_bin is not None:
        repeats = np.maximum(1, np.round(path[:, 2] / temporal_bin)).astype(int)
        cells = np.repeat(cells, repeats)
    return cells


def __substitution_matrix(grid, threshold_share):
    n_cols, n_rows = grid
    rows, cols = np.divmod(np.arange(n_cols * n_rows), n_cols)
    dist = np.hypot(cols[:, None] - cols[None, :], rows[:, None] - rows[None, :])
    threshold = threshold_share * dist.max()
    assert threshold > 0
    return threshold - dist, threshold


def __needleman_wunsch(seq_a, seq_b, sub, gap):
    n, m = len(seq_a), len(seq_b)
    jj = np.arange(m + 1)
    prev = -gap * jj
    for i in range(1, n + 1):
        base = np.empty(m + 1)
        base[0] = -gap * i
        base[1:] = np.maximum(prev[:-1] + sub[seq_a[i - 1], seq_b], prev[1:] - gap)
        prev = np.maximum.accumulate(base + gap * jj) - gap * jj
    return prev[-1]


MM_MEASURES = ['vector', 'direction', 'length', 'position', 'duration']


def multimatch(path_a, path_b, width, height, amplitude_threshold=None, direction_threshold=None,
               duration_threshold=0.3):
    """MultiMatch similarity of two scanpaths (Dewhurst et al. 2012): dict with the five scores."""
    path_a, path_b = np.asarray(path_a, dtype=float), np.asarray(path_b, dtype=float)
    assert path_a.ndim == 2 and path_a.shape[1] == 3 and path_b.ndim == 2 and path_b.shape[1] == 3
    if len(path_a) < 2 or len(path_b) < 2:
        return {name: np.nan for name in MM_MEASURES}
    diagonal = np.hypot(width, height)
    if amplitude_threshold is None:
        amplitude_threshold = 0.1 * diagonal
    if direction_threshold is None:
        direction_threshold = 45.
    start_a, vec_a, dur_a = __simplify(*__saccades(path_a), amplitude_threshold, np.radians(direction_threshold),
                                       duration_threshold)
    start_b, vec_b, dur_b = __simplify(*__saccades(path_b), amplitude_threshold, np.radians(direction_threshold),
                                       duration_threshold)

    diff = vec_a[:, None, :] - vec_b[None, :, :]
    cost = np.linalg.norm(diff, axis=-1)
    ii, jj = __cheapest_path(cost)

    amp_a, amp_b = np.linalg.norm(vec_a, axis=1), np.linalg.norm(vec_b, axis=1)
    d_vector = cost[ii, jj] / (2 * diagonal)
    d_direction = __angle_between(vec_a[ii], vec_b[jj]) / np.pi
    d_length = np.abs(amp_a[ii] - amp_b[jj]) / diagonal
    d_position = np.linalg.norm(start_a[ii] - start_b[jj], axis=1) / diagonal
    dur_max = np.maximum(dur_a[ii], dur_b[jj])
    with np.errstate(divide='ignore', invalid='ignore'):
        d_duration = np.where(dur_max > 0, np.abs(dur_a[ii] - dur_b[jj]) / dur_max, 0.)
    return {'vector': float(1 - d_vector.mean()),
            'direction': float(1 - d_direction.mean()),
            'length': float(1 - d_length.mean()),
            'position': float(1 - d_position.mean()),
            'duration': float(1 - d_duration.mean())}


def __saccades(path):
    start = path[:-1, :2]
    vec = path[1:, :2] - path[:-1, :2]
    dur = path[:-1, 2]
    return start, vec, dur


def __angle_between(u, v):
    cross = u[:, 0] * v[:, 1] - u[:, 1] * v[:, 0]
    dot = (u * v).sum(axis=1)
    return np.abs(np.arctan2(cross, dot))


def __simplify(start, vec, dur, amp_thr, dir_thr, dur_thr):
    start, vec, dur = start.copy(), vec.copy(), dur.copy()
    while len(vec) > 1:
        amp = np.linalg.norm(vec, axis=1)
        angle = __angle_between(vec[:-1], vec[1:])
        short = (amp[:-1] < amp_thr) & (amp[1:] < amp_thr)
        similar = angle < dir_thr
        mergeable = (short | similar) & (dur[1:] < dur_thr)
        if not mergeable.any():
            break
        ls_start, ls_vec, ls_dur = [], [], []
        i = 0
        while i < len(vec):
            if i < len(vec) - 1 and mergeable[i]:
                ls_start.append(start[i])
                ls_vec.append(vec[i] + vec[i + 1])
                ls_dur.append(dur[i] + dur[i + 1])
                i += 2
            else:
                ls_start.append(start[i])
                ls_vec.append(vec[i])
                ls_dur.append(dur[i])
                i += 1
        start, vec, dur = np.array(ls_start), np.array(ls_vec), np.array(ls_dur)
    return start, vec, dur


def __cheapest_path(cost):
    n, m = cost.shape
    D = np.empty_like(cost)
    D[0] = np.cumsum(cost[0])
    for i in range(1, n):
        base = np.empty(m)
        base[0] = D[i - 1, 0]
        base[1:] = np.minimum(D[i - 1, 1:], D[i - 1, :-1])
        c = np.cumsum(cost[i])
        c_prev = np.concatenate([[0.], c[:-1]])
        D[i] = c + np.minimum.accumulate(base - c_prev)
    i, j = n - 1, m - 1
    path = [(i, j)]
    while i > 0 or j > 0:
        candidates = []
        if i > 0 and j > 0:
            candidates.append((D[i - 1, j - 1], i - 1, j - 1))
        if i > 0:
            candidates.append((D[i - 1, j], i - 1, j))
        if j > 0:
            candidates.append((D[i, j - 1], i, j - 1))
        _, i, j = min(candidates)
        path.append((i, j))
    path = np.array(path[::-1])
    return path[:, 0], path[:, 1]


def scanpath_of(fix, subj):
    """One participant's scanpath as an (n, 3) array of x, y in pixels and duration in seconds."""
    mask = (fix.subj_index == subj).to_numpy()
    assert mask.any(), f"Unknown subject: {subj}"
    dur_s = fix.fix_dur[mask].to_numpy(dtype=float) / (1000. if fix.dur_unit == 'ms' else 1.)
    return np.column_stack([fix.fix_x[mask].to_numpy(dtype=float), fix.fix_y[mask].to_numpy(dtype=float), dur_s])


def scanpath_similarity_table(fix, method='multimatch', verbose=True, progress=None, **kwargs):
    """Pairwise scanpath similarity between all participants of fix, one row per unordered pair incl. the diagonal."""
    if method not in ['scanmatch', 'multimatch']:
        raise ValueError(f"Unsupported method: {method}")
    paths = {subj: scanpath_of(fix, subj) for subj in fix.subjects}
    pairs = list(itertools.combinations_with_replacement(fix.subjects, 2))
    ls = []
    for i, (subj_a, subj_b) in enumerate(tqdm(pairs, desc=f"Scanpath similarity ({method})", disable=not verbose)):
        if progress is not None and i % 20 == 0 and progress(i, len(pairs), f"{method} pairs") is False:
            raise InterruptedError("Computation cancelled.")
        row = {'subject_a': subj_a, 'subject_b': subj_b}
        if method == 'scanmatch':
            row['scanmatch'] = scanmatch(paths[subj_a], paths[subj_b], fix.width, fix.height, **kwargs)
        else:
            sims = multimatch(paths[subj_a], paths[subj_b], fix.width, fix.height, **kwargs)
            row.update({f"mm_{name}": sims[name] for name in MM_MEASURES})
        ls.append(row)
    return pd.DataFrame.from_records(ls)


if __name__ == '__main__':
    rng = np.random.default_rng(0)
    p = np.column_stack([rng.uniform(0, 400, 20), rng.uniform(0, 300, 20), rng.uniform(0.1, 0.4, 20)])
    print(scanmatch(p, p, 400, 300), scanmatch(p, p[::-1], 400, 300))
    print(multimatch(p, p[::-1], 400, 300))
