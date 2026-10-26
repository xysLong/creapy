import numpy as np
import pandas as pd

# Fixation table <-> saccade table for ONE stimulus. The old loops over df.iloc[i] / iloc[i + 1] were O(n) Python
# per row; groupby + shift does the same in a few vectorized calls (several hundred times faster on a
# 20k-row report) and no longer asserts sorted input: rows are sorted by time within each viewing.


def viewing_keys(column_mapping):
    """The columns that identify one continuous viewing: [subj_index_col], plus trial_col when the mapping has one."""
    keys = [column_mapping['subj_index_col']]
    trial_col = column_mapping.get('trial_col')
    if trial_col is not None:
        keys.append(trial_col)
    return keys


def fixations_to_saccades(df_fixation, column_mapping):
    """Derive the saccades between consecutive fixations of ONE stimulus: each fixation becomes a saccade from its own
    position to the next fixation of the same viewing (the last fixation makes none). Returns (df, mapping): df with
    columns x0, y0, x1, y1, t (fixation onset + duration, i.e. saccade onset in the table's time unit), subj, trial
    (only with a trial column), amp (straight-line distance in pixels); mapping has the sac_*_col names for SaccadeData.
    """
    stim_col = column_mapping.get('stim_col')
    subj_index_col = column_mapping['subj_index_col']
    fix_x_col = column_mapping['fix_x_col']
    fix_y_col = column_mapping['fix_y_col']
    fix_t_col = column_mapping['fix_t_col']
    fix_dur_col = column_mapping['fix_dur_col']
    if stim_col is not None and stim_col in df_fixation.columns:
        assert df_fixation[stim_col].nunique() == 1, "fixations_to_saccades expects the rows of ONE stimulus"
    keys = viewing_keys(column_mapping)
    df_ = df_fixation.sort_values(keys + [fix_t_col]).reset_index(drop=True)
    grouped = df_.groupby(keys, sort=False)
    df = pd.DataFrame({
        'x0': df_[fix_x_col].to_numpy(dtype=float),
        'y0': df_[fix_y_col].to_numpy(dtype=float),
        'x1': grouped[fix_x_col].shift(-1).to_numpy(dtype=float),
        'y1': grouped[fix_y_col].shift(-1).to_numpy(dtype=float),
        't': (df_[fix_t_col] + df_[fix_dur_col]).to_numpy(dtype=float),  # saccade onset = fixation offset
        'subj': df_[subj_index_col].to_numpy(),
    })
    if len(keys) > 1:
        df['trial'] = df_[keys[1]].to_numpy()
    # the last fixation of a viewing has no following saccade; fixations without coordinates make no saccade either
    df = df.dropna(subset=['x0', 'y0', 'x1', 'y1']).reset_index(drop=True)
    df['amp'] = np.sqrt((df.x1 - df.x0) ** 2 + (df.y1 - df.y0) ** 2)
    mapping = {'sac_x0_col': 'x0', 'sac_y0_col': 'y0',
               'sac_x1_col': 'x1', 'sac_y1_col': 'y1',
               'sac_t_col': 't', 'sac_amp_col': 'amp',
               'subj_index_col': 'subj',
               'trial_col': 'trial' if len(keys) > 1 else None}
    return df, mapping


def saccades_to_fixations(df_saccade, column_mapping):
    """Reconstruct the fixations between consecutive saccades of ONE stimulus: a fixation sits midway between a
    saccade's end point and the next saccade's start, lasts from this saccade's onset to the next (dur) and is stamped
    with this saccade's onset (t); the last saccade of a viewing yields none. Returns (df, mapping): df with columns
    x, y, t, dur, subj, trial (only with a trial column); mapping has the fix_*_col names for FixationData.
    """
    stim_col = column_mapping.get('stim_col')
    subj_index_col = column_mapping['subj_index_col']
    sac_x0_col = column_mapping['sac_x0_col']
    sac_y0_col = column_mapping['sac_y0_col']
    sac_x1_col = column_mapping['sac_x1_col']
    sac_y1_col = column_mapping['sac_y1_col']
    sac_t_col = column_mapping['sac_t_col']
    if stim_col is not None and stim_col in df_saccade.columns:
        assert df_saccade[stim_col].nunique() == 1, "saccades_to_fixations expects the rows of ONE stimulus"
    keys = viewing_keys(column_mapping)
    df_ = df_saccade.sort_values(keys + [sac_t_col]).reset_index(drop=True)
    grouped = df_.groupby(keys, sort=False)
    next_x0 = grouped[sac_x0_col].shift(-1).to_numpy(dtype=float)
    next_y0 = grouped[sac_y0_col].shift(-1).to_numpy(dtype=float)
    next_t = grouped[sac_t_col].shift(-1).to_numpy(dtype=float)
    # The fixation between two saccades: midway between this saccade's end and the next one's start
    df = pd.DataFrame({
        'x': (df_[sac_x1_col].to_numpy(dtype=float) + next_x0) / 2,
        'y': (df_[sac_y1_col].to_numpy(dtype=float) + next_y0) / 2,
        't': df_[sac_t_col].to_numpy(dtype=float),  # the saccade's own onset, as in the original implementation
        'dur': next_t - df_[sac_t_col].to_numpy(dtype=float),
        'subj': df_[subj_index_col].to_numpy(),
    })
    if len(keys) > 1:
        df['trial'] = df_[keys[1]].to_numpy()
    df = df.dropna(subset=['x', 'y', 'dur']).reset_index(drop=True)
    mapping = {'fix_x_col': 'x', 'fix_y_col': 'y',
               'fix_t_col': 't', 'fix_dur_col': 'dur',
               'subj_index_col': 'subj',
               'trial_col': 'trial' if len(keys) > 1 else None}
    return df, mapping


if __name__ == '__main__':
    pass
