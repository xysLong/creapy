import pandas as pd
from creapy.formats.table import numeric_columns, image_like_columns

# The fields creapy needs for each data type: key -> (label shown in the GUI, required?, name hints).
# Hints are matched case-insensitively as substrings; the first column matching the first hint wins,
# then the second hint, etc. EyeLink DataViewer names come first, then Tobii Pro Lab, then generic words.
FIXATION_FIELDS = {
    'stim_col': ('Stimulus (image name or path)', True,
                 ['image', 'stimulus', 'presented media name', 'snapshot', 'picture', 'painting', 'media']),
    'subj_index_col': ('Participant', True,
                       ['recording_session_label', 'participant name', 'participant', 'subject', 'subj', 'vp', 'pp',
                        'recording name']),
    'fix_t_col': ('Fixation start time', True,
                  ['current_fix_start', 'fixation start', 'recording timestamp', 'start_time', 'onset', 'start',
                   'timestamp', 'time']),
    'fix_dur_col': ('Fixation duration', True,
                    ['current_fix_duration', 'gaze event duration', 'fixation duration', 'duration', 'dur']),
    'fix_x_col': ('Fixation X', True,
                  ['current_fix_x', 'fixation point x', 'fix_x', 'fixation x', 'x_px', 'x']),
    'fix_y_col': ('Fixation Y', True,
                  ['current_fix_y', 'fixation point y', 'fix_y', 'fixation y', 'y_px', 'y']),
    'trial_col': ('Trial (optional)', False,
                  ['trial_index', 'trial', 'block', 'timeline', 'toi']),
    'pupil_col': ('Pupil size (optional)', False,
                  ['current_fix_pupil', 'pupil diameter', 'pupil']),
}

SACCADE_FIELDS = {
    'stim_col': ('Stimulus (image name or path)', True,
                 ['image', 'stimulus', 'presented media name', 'snapshot', 'picture', 'painting', 'media']),
    'subj_index_col': ('Participant', True,
                       ['recording_session_label', 'participant name', 'participant', 'subject', 'subj', 'vp', 'pp',
                        'recording name']),
    'sac_t_col': ('Saccade start time', True,
                  ['current_sac_start_time', 'start_time', 'saccade start', 'onset', 'timestamp', 'time']),
    'sac_amp_col': ('Saccade amplitude', True,
                    ['current_sac_amplitude', 'amplitude', 'amp']),
    'sac_x0_col': ('Saccade start X', True, ['current_sac_start_x', 'start_x', 'x0', 'start x']),
    'sac_y0_col': ('Saccade start Y', True, ['current_sac_start_y', 'start_y', 'y0', 'start y']),
    'sac_x1_col': ('Saccade end X', True, ['current_sac_end_x', 'end_x', 'x1', 'end x']),
    'sac_y1_col': ('Saccade end Y', True, ['current_sac_end_y', 'end_y', 'y1', 'end y']),
    'trial_col': ('Trial (optional)', False, ['trial_index', 'trial', 'block', 'timeline', 'toi']),
}

NUMERIC_FIELDS = ['fix_t_col', 'fix_dur_col', 'fix_x_col', 'fix_y_col', 'pupil_col',
                  'sac_t_col', 'sac_amp_col', 'sac_x0_col', 'sac_y0_col', 'sac_x1_col', 'sac_y1_col']


def detect_format(columns):
    """
    Classify a table by its column names alone: 'eyelink_fixation', 'eyelink_saccade', 'tobii_event_export',
    'tobii_data_export', 'tobii_metrics_export' or 'unknown'. Case-insensitive; no cell values are looked at.
    """
    # 'eyelink_fixation' | 'eyelink_saccade' | 'tobii_event_export' | 'tobii_data_export' | 'tobii_metrics_export' | 'unknown'
    cols = [str(c).lower() for c in columns]
    joined = ' | '.join(cols)
    if 'current_fix_x' in joined and 'current_fix_y' in joined:
        return 'eyelink_fixation'
    if 'current_sac_start_x' in joined and 'current_sac_end_x' in joined:
        return 'eyelink_saccade'
    if {'participant', 'media', 'event_type', 'start', 'duration', 'fixationpointx', 'fixationpointy'} <= set(cols):
        return 'tobii_event_export'
    if 'eye movement type' in joined and 'recording timestamp' in joined:
        return 'tobii_data_export'
    if any(c.startswith('total_duration_of') or c.startswith('number_of_') for c in cols) and 'aoi' in cols:
        return 'tobii_metrics_export'
    return 'unknown'


def guess_mapping(df, fields):
    """
    Best-effort column mapping for `fields` (FIXATION_FIELDS or SACCADE_FIELDS): a dict field key -> column
    name, None for optional fields without a match. Hints are tried in priority order, numeric fields only take
    numeric columns, the stimulus prefers image-like columns, required fields fall back to the first unused
    column. For EyeLink tables whose times exceed 60 the key 'time_unit' = 'ms' is added.
    """
    # Best-effort column mapping for the GUI dialog: hints in priority order, numeric fields must be numeric,
    # the stimulus column prefers image-like values. Optional fields may map to None.
    columns = list(df.columns)
    lower = {col: str(col).lower() for col in columns}
    numeric = set(numeric_columns(df))
    image_like = image_like_columns(df)
    mapping = {}
    taken = set()
    for key, (_, required, hints) in fields.items():
        chosen = None
        if key == 'stim_col' and image_like:
            chosen = image_like[0]
        else:
            for hint in hints:
                for col in columns:
                    if col in taken:
                        continue
                    if key in NUMERIC_FIELDS and col not in numeric:
                        continue
                    name = lower[col]
                    if name == hint or (len(hint) > 2 and hint in name) or (len(hint) <= 2 and name == hint):
                        chosen = col
                        break
                if chosen is not None:
                    break
        if chosen is None and required:
            # fall back to the first unused column of the right kind so every combo has a value
            candidates = [c for c in columns if c not in taken and (key not in NUMERIC_FIELDS or c in numeric)]
            chosen = candidates[0] if candidates else columns[0]
        mapping[key] = chosen
        if chosen is not None:
            taken.add(chosen)
    t_key = 'fix_t_col' if 'fix_t_col' in fields else 'sac_t_col'
    if detect_format(columns).startswith('eyelink') and mapping.get(t_key) is not None:
        t_max = pd.to_numeric(df[mapping[t_key]], errors='coerce').max()
        if t_max > 60:  # DataViewer reports are in ms; preprocessed tables (seconds, < 60) keep the heuristic
            mapping['time_unit'] = 'ms'
    return mapping


def validate_mapping(df, mapping, fields):
    """
    Human-readable problems with a mapping as a list of strings (required field unassigned, column missing
    from df, numeric field with no or mostly non-numeric values, one column used for two required fields);
    an empty list means the mapping is usable.
    """
    # Human-readable problems with a mapping, [] if it is usable
    problems = []
    for key, (label, required, _) in fields.items():
        col = mapping.get(key)
        if col is None:
            if required:
                problems.append(f"'{label}' has no column assigned.")
            continue
        if col not in df.columns:
            problems.append(f"'{label}': column '{col}' does not exist in the table.")
            continue
        if key in NUMERIC_FIELDS:
            as_num = pd.to_numeric(df[col], errors='coerce')
            if as_num.notna().sum() == 0:
                problems.append(f"'{label}': column '{col}' contains no numbers.")
            elif as_num.notna().mean() < 0.5:
                problems.append(f"'{label}': column '{col}' is mostly non-numeric.")
    required_cols = [mapping[k] for k, (_, req, _) in fields.items() if req and mapping.get(k) is not None]
    if len(set(required_cols)) < len(required_cols):
        problems.append("The same column is assigned to more than one required field.")
    return problems


if __name__ == '__main__':
    pass
