"""
A per-fixation value (fixation duration, saccade amplitude, coefficient K, pupil size, viewing distance) as a
smoothed curve over viewing time, for all participants together or per group. This is what the GUI's Time Series
view draws; here it is three plain functions on a FixationData / SaccadeData pair and a matplotlib axes.
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from creapy.gaze.base import StimulusGaze
from creapy.stats.descriptives import fixation_k
from creapy.misc.utils import natural_sorted

# measure key -> label as the GUI shows it (both spellings are accepted everywhere below)
MEASURES = {
    'fixation_duration': "Fixation Duration",
    'saccade_amplitude': "Saccade Amplitude",
    'coefficient_k': "Ambient–Focal (K)",
    'pupil': "Pupil Size",
    'viewing_distance': "Viewing Distance",
}


def measure_key(name):
    """'fixation_duration' or the GUI label 'Fixation Duration' -> 'fixation_duration'; ValueError otherwise."""
    if name in MEASURES:
        return name
    for key, label in MEASURES.items():
        if label == name:
            return key
    raise ValueError(f"Unknown measure: {name!r}; one of {list(MEASURES)}")


def value_series(fix, sac, measure):
    """
    The raw per-event values of one measure: returns (dataset, values, y label), where dataset is `fix` or `sac`
    (saccade amplitude lives in the saccade table) and values is a float array aligned with dataset.df.
    measure: 'fixation_duration', 'saccade_amplitude', 'coefficient_k', 'pupil' or 'viewing_distance'.
    Raises ValueError when the table has no pupil column / no viewing distance (Tobii glasses Data exports only).
    """
    key = measure_key(measure)
    if key == 'fixation_duration':
        return fix, fix.fix_dur.to_numpy(dtype=float), f"Fixation duration ({fix.dur_unit})"
    if key == 'saccade_amplitude':
        assert sac is not None, "saccade amplitude needs the SaccadeData of the stimulus"
        return sac, sac.sac_amp.to_numpy(dtype=float), "Saccade amplitude (table unit)"
    if key == 'coefficient_k':
        return fix, fixation_k(fix), "Coefficient K  (focal ↑ · ambient ↓)"
    if key == 'pupil':
        if fix.pupil_col is None:
            raise ValueError("The table has no pupil column (mapping key 'pupil_col').")
        values = pd.to_numeric(fix.df[fix.pupil_col], errors='coerce').to_numpy(dtype=float)
        return fix, values, "Pupil size (table unit)"
    if key == 'viewing_distance':
        if 'distance_mm' not in fix.df.columns:
            raise ValueError("No viewing distance in this dataset (column 'distance_mm'; Tobii glasses Data exports "
                             "carry it, the event-based metrics export does not).")
        values = pd.to_numeric(fix.df['distance_mm'], errors='coerce').to_numpy(dtype=float) / 10.
        return fix, values, "Viewing distance (cm)"
    raise ValueError(f"Unknown measure: {measure}")


def smoothed_curve(dataset, values, sigma, step=0.05, weights=None):
    """
    Gaussian-smoothed mean of `values` (aligned with dataset.df) over viewing time: returns (t, mean, std) on a
    regular grid from the first to the last event, `step` and `sigma` (kernel width) in seconds. Every participant
    counts equally: the default weights are 1 / number of events of the participant; NaN values are skipped.
    """
    values = np.asarray(values, dtype=float)
    ok = np.isfinite(values)
    if weights is None:
        weights = dataset.weights_simple
    weights = np.asarray(weights, dtype=float)
    t_old = np.asarray(dataset.t, dtype=float)
    t_new = np.arange(dataset.t_min, dataset.t_max + step, step)
    m, s = StimulusGaze.gaussian_smooth_irregular(t_new, t_old[ok], values[ok], weights_subj=weights[ok], sigma=sigma)
    return t_new, m, s


def show_smoothed_curve(ax, dataset, values, sigma, n_std=0.05, color=None, label=None, step=0.05, t_valid=None):
    """
    Draw smoothed_curve(...) on ax: a solid line up to t_valid (default 5 s before the end, after which few
    participants are still viewing and the mean gets unreliable), dashed after it, and a band of ± n_std standard
    deviations when 0 < n_std <= 1. Returns (t, mean).
    """
    t_new, m, s = smoothed_curve(dataset, values, sigma, step=step)
    if t_valid is None:
        t_valid = max(dataset.t_min, dataset.t_max - 5.)
    ax.plot(t_new[t_new <= t_valid], m[t_new <= t_valid], color=color, label=label)
    ax.plot(t_new[t_new > t_valid], m[t_new > t_valid], ls='dashed', color=color)
    if 0. < n_std <= 1.:
        ax.fill_between(t_new, m - n_std * s, m + n_std * s, alpha=0.1, color=color)
    return t_new, m


def show_measure_curve(fix, sac, measure, sigma=2., n_std=0.05, ax=None, color=None, label=None, step=0.05):
    """
    One call for a whole Time Series curve: value_series + show_smoothed_curve with axis labels; with ax=None a
    figure is created and shown. For coefficient K a dotted zero line separates focal (above) from ambient (below).
    Returns (t, mean).
    """
    data, values, ylabel = value_series(fix, sac, measure)
    show = ax is None
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(7, 4))
    out = show_smoothed_curve(ax, data, values, sigma, n_std=n_std, color=color, label=label, step=step)
    if measure_key(measure) == 'coefficient_k':
        ax.axhline(0, color='#888888', lw=0.8, ls=':')
    ax.set_xlabel("Viewing time (s)")
    ax.set_ylabel(ylabel)
    if show:
        ax.figure.tight_layout()
        plt.show()
    return out


def split_by_group(fix, sac, grouping):
    """
    [(group name, fix subset, sac subset)] for the participants of every group, groups in natural order.
    grouping maps participant -> group name; participants without a group are left out, empty groups dropped;
    sac may be None. Draw a curve per entry to compare groups on one axes.
    """
    ls = []
    for name in natural_sorted(set(grouping.values())):
        subs = [s for s in fix.subjects if grouping.get(s) == name]
        if subs:
            ls.append((name, fix.subset(subjects=subs), sac.subset(subjects=subs) if sac is not None else None))
    return ls


if __name__ == '__main__':
    pass
