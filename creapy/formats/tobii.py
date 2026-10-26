import os
import re
import numpy as np
import pandas as pd
from creapy.formats.table import read_table

# Tobii Pro Lab exports, as the CReA Lab meets them (checked against the WOQ Belvedere files, 2026-10-24):
#
# 1. "Data export": one row per gaze SAMPLE, ~300 columns (70 GB for one room of the WOQ study). Newer Pro Lab
#    versions append units to the headers ("Recording timestamp [ms]", "Fixation point X [MCS px]").
#    Glasses recordings mapped onto snapshots carry one column set per snapshot:
#    "Mapped eye movement type [<snapshot>]", "Mapped eye movement type index [<snapshot>]",
#    "Mapped fixation X/Y [<snapshot>]" (snapshot PIXELS), "Width/Height [<snapshot>]".
#    "Fixation point X/Y" is the scene-camera position for glasses (not a stimulus) and the media position for
#    screen-based recordings ("Presented Media name").
# 2. "Metrics export, event-based": one row per EVENT (Fixation / Saccade / Glance) per TOI interval:
#    Recording, Participant, Condition, TOI, Interval, Media, Event_type, Validity, EventIndex, Start, Stop,
#    Duration (ms, from the interval start), AOI (hit), FixationPointX/Y (NORMALISED 0–1 on the Media),
#    Average_pupil_diameter, Saccade_* columns. This is what the team shares: the file most users will get.
# 3. "Metrics export, AOI-based": one row per participant × AOI × interval with dwell/visit/fixation totals;
#    no positions, so nothing to draw. Refused with an explanation (a table view is a later feature).

UNIT_SUFFIX = re.compile(r'\s*\[(?:ms|µs|us|px|mm|MCS px|MCS norm|HUCS mm|HUCS norm|DACS[^\]]*|°/s|°)\]\s*$')

MAPPED_TYPE = re.compile(r'^Mapped eye movement type \[(.+)\]$')
MAPPED_INDEX = re.compile(r'^Mapped eye movement type index \[(.+)\]$')
MAPPED_X = re.compile(r'^Mapped fixation X \[(.+)\]$')
MAPPED_Y = re.compile(r'^Mapped fixation Y \[(.+)\]$')
SNAP_WIDTH = re.compile(r'^Width \[(.+)\]$')
SNAP_HEIGHT = re.compile(r'^Height \[(.+)\]$')

OUTPUT_MAPPING = {'stim_col': 'stimulus', 'subj_index_col': 'participant',
                  'fix_t_col': 't', 'fix_dur_col': 'dur', 'fix_x_col': 'x', 'fix_y_col': 'y',
                  'trial_col': None, 'pupil_col': None, 'time_unit': 'ms'}  # both loaders write t in ms

EVENT_COLUMNS = ['Participant', 'Media', 'Event_type', 'Start', 'Duration', 'FixationPointX', 'FixationPointY']


def strip_units(name):
    """
    Column name without the unit suffix newer Pro Lab versions append ('Recording timestamp [ms]' ->
    'Recording timestamp').
    """
    return UNIT_SUFFIX.sub('', str(name)).strip()


def timestamp_unit(columns):
    """
    'ms' or 'us' from the unit suffix of the 'Recording timestamp' column; None when the header carries no
    unit (the loader then decides from the values).
    """
    # 'ms' | 'us' from the header suffix if present, else None (decided from the values later)
    for col in columns:
        if strip_units(col) == 'Recording timestamp':
            m = re.search(r'\[(ms|µs|us)\]', str(col))
            if m:
                return 'us' if m.group(1) in ('µs', 'us') else 'ms'
    return None


def is_prolab_data_export(columns):
    """
    True if the columns look like a Pro Lab Data export (one row per gaze sample): 'Recording timestamp' and
    'Eye movement type' present, unit suffixes ignored.
    """
    bases = {strip_units(c) for c in columns}
    return 'Recording timestamp' in bases and 'Eye movement type' in bases


def is_prolab_event_export(columns):
    """
    True if all columns of the event-based metrics export are present (Participant, Media, Event_type, Start,
    Duration, FixationPointX, FixationPointY).
    """
    cols = {str(c) for c in columns}
    return set(EVENT_COLUMNS) <= cols


def is_prolab_metrics_export(columns):
    """
    True for an AOI-based metrics export: an 'AOI' column plus 'Total_duration_of_...' / 'Number_of_...'
    columns, and not an event-based export.
    """
    cols = [str(c) for c in columns]
    return 'AOI' in cols and any(c.startswith('Total_duration_of') or c.startswith('Number_of_') for c in cols) \
        and not is_prolab_event_export(cols)


def load_prolab_export(path_or_df):
    """
    Load a Tobii Pro Lab export (file path or already-read DataFrame), picking load_prolab_event_export or
    load_prolab_data_export by the columns; returns (df_fixations, mapping). AOI-based metrics exports and
    tables that are no Pro Lab export raise a ValueError saying what is expected.
    """
    # Whichever Pro Lab export it is -> (df_fixations, mapping); see the two loaders below
    df_raw = read_table(path_or_df) if isinstance(path_or_df, str) else path_or_df
    if is_prolab_event_export(df_raw.columns):
        return load_prolab_event_export(df_raw)
    if is_prolab_data_export(df_raw.columns):
        return load_prolab_data_export(df_raw)
    if is_prolab_metrics_export(df_raw.columns):
        raise ValueError("This is a Tobii Pro Lab *AOI-based metrics* export (one row per AOI and interval, no "
                         "fixation positions). creapy needs the *event-based* metrics export (one row per fixation, "
                         "with FixationPointX/Y) or the *Data export* (one row per gaze sample).")
    raise ValueError("The table does not look like a Tobii Pro Lab export: neither the event-based metrics columns "
                     "(Participant, Media, Event_type, Start, Duration, FixationPointX/Y) nor the Data-export columns "
                     "('Recording timestamp', 'Eye movement type') are present.")


# ---------------------------------------------------------------------------------------------------------------
# Event-based metrics export
# ---------------------------------------------------------------------------------------------------------------

def load_prolab_event_export(path_or_df):
    """
    Event-based metrics export -> one row per fixation: participant, stimulus (= Media / snapshot name),
    trial (= TOI interval, times restart at each interval), t (ms from the interval start), dur (ms),
    x, y NORMALISED 0–1 on the medium (the mapping carries normalized_xy=True; FixationData multiplies by the
    image size), pupil, validity, aoi_hit (Pro Lab's own AOI), condition.
    """
    df = read_table(path_or_df) if isinstance(path_or_df, str) else path_or_df
    if not is_prolab_event_export(df.columns):
        raise ValueError("Not an event-based Pro Lab metrics export (expected the columns "
                         + ", ".join(EVENT_COLUMNS) + ").")
    is_fix = df['Event_type'].astype(str).str.lower() == 'fixation'
    df_ = df[is_fix]
    out = pd.DataFrame({
        'participant': df_['Participant'].astype(str),
        'stimulus': df_['Media'].astype(str),
        'trial': pd.to_numeric(df_['Interval'], errors='coerce') if 'Interval' in df_.columns else 1,
        't': pd.to_numeric(df_['Start'], errors='coerce'),  # ms from the interval start, same unit as dur
        'dur': pd.to_numeric(df_['Duration'], errors='coerce'),
        'x': pd.to_numeric(df_['FixationPointX'], errors='coerce'),
        'y': pd.to_numeric(df_['FixationPointY'], errors='coerce'),
    })
    for src, dst in [('Average_pupil_diameter', 'pupil'), ('Validity', 'validity'), ('AOI', 'aoi_hit'),
                     ('Condition', 'condition'), ('Recording', 'recording'), ('TOI', 'toi'),
                     ('Hit_proportion', 'hit_proportion')]:
        if src in df_.columns:
            out[dst] = df_[src].values
    out = out.dropna(subset=['x', 'y', 't', 'dur'])
    out = out[out['stimulus'].notna() & (out['stimulus'] != 'nan')]
    out = out.sort_values(['participant', 'stimulus', 'trial', 't']).reset_index(drop=True)
    if len(out) == 0:
        raise ValueError("The export contains no fixation rows with a position.")
    mapping = dict(OUTPUT_MAPPING, trial_col='trial', pupil_col='pupil' if 'pupil' in out.columns else None,
                   normalized_xy=True)
    return out, mapping


# ---------------------------------------------------------------------------------------------------------------
# Data export (gaze samples)
# ---------------------------------------------------------------------------------------------------------------

def load_prolab_data_export(path_or_df):
    """
    Pro Lab Data export -> one row per fixation with the columns participant, stimulus, t (ms), dur (ms), x, y
    (pixels of the presented medium or snapshot), recording, condition (if present), snapshot_mapped (bool).
    Returns (df_fixations, mapping) ready for FixationData / the GUI.

    Screen-based recordings: Fixation point X/Y on the "Presented Media name".
    Glasses recordings mapped onto snapshots: Mapped fixation X/Y [snapshot]: one fixation table per snapshot,
    the snapshot name becomes the stimulus (match it to the snapshot image files by name). The scene-camera
    "Fixation point X/Y" of glasses recordings is NOT a stimulus position and is ignored.
    """
    df_raw = read_table(path_or_df) if isinstance(path_or_df, str) else path_or_df
    original_columns = list(df_raw.columns)
    if is_prolab_metrics_export(original_columns) or is_prolab_event_export(original_columns):
        raise ValueError("This is a Tobii Pro Lab *metrics* export, not the Data export (one row per gaze sample).")
    if not is_prolab_data_export(original_columns):
        raise ValueError("The table does not look like a Tobii Pro Lab Data export: the columns "
                         "'Recording timestamp' and 'Eye movement type' are missing.")

    unit = timestamp_unit(original_columns)
    df = df_raw.copy()
    df.columns = [strip_units(c) for c in original_columns]

    participant_col = 'Participant name' if 'Participant name' in df.columns else 'Recording name'
    assert participant_col in df.columns, "Neither 'Participant name' nor 'Recording name' found."
    recording_col = 'Recording name' if 'Recording name' in df.columns else participant_col

    t = pd.to_numeric(df['Recording timestamp'], errors='coerce')
    if unit is None:
        # Pro Lab defaults to ms; µs exports show up as implausibly large numbers (> 1e8 for a 100 s recording)
        unit = 'us' if t.max() > 1e8 else 'ms'
    t_ms = t / (1e3 if unit == 'us' else 1.)  # ms, the same unit as the event durations

    # the event duration column changed its name across Pro Lab versions
    dur_col = next((c for c in ['Gaze event duration', 'Eye movement event duration'] if c in df.columns), None)
    dur_ms = pd.to_numeric(df[dur_col], errors='coerce') if dur_col else pd.Series(np.nan, index=df.index)

    extras = {}
    for col in ['Condition', 'Timeline name', 'Presented Stimulus name', 'Validity left', 'Validity right']:
        if col in df.columns:
            extras[col] = df[col]

    # Per-sample measures averaged over the fixation: pupil diameter and, for glasses, the viewing distance =
    # length of the 3D gaze vector (scene-camera coordinates, mm): ~2000 mm in front of a museum painting
    sample_measures = {}
    pupil_col = next((c for c in ['Pupil diameter filtered', 'Pupil diameter left', 'Pupil diameter right']
                      if c in df.columns), None)
    if pupil_col:
        sample_measures['pupil'] = pd.to_numeric(df[pupil_col], errors='coerce')
    if {'Gaze point 3D X', 'Gaze point 3D Y', 'Gaze point 3D Z'} <= set(df.columns):
        xyz = np.column_stack([pd.to_numeric(df[c], errors='coerce') for c in
                               ['Gaze point 3D X', 'Gaze point 3D Y', 'Gaze point 3D Z']])
        distance = pd.Series(np.sqrt(np.nansum(xyz ** 2, axis=1)), index=df.index).where(~np.isnan(xyz).all(axis=1))
        # the 3D estimate fails on some samples (hundreds of metres); nothing in a museum room is 20 m away
        sample_measures['distance_mm'] = distance.where(distance < 20_000)

    snapshots = {}
    for col in df.columns:
        for regex, key in [(MAPPED_TYPE, 'type'), (MAPPED_INDEX, 'index'), (MAPPED_X, 'x'), (MAPPED_Y, 'y'),
                           (SNAP_WIDTH, 'width'), (SNAP_HEIGHT, 'height')]:
            m = regex.match(str(col))
            if m:
                snapshots.setdefault(m.group(1), {})[key] = col
    mapped_snapshots = {name: cols for name, cols in snapshots.items() if {'type', 'x', 'y'} <= set(cols)}

    ls = []
    # ---------- screen-based: Fixation point X/Y on the presented medium ----------
    screen_based = 'Presented Media name' in df.columns and not mapped_snapshots
    if screen_based and 'Fixation point X' in df.columns and 'Fixation point Y' in df.columns:
        is_fix = df['Eye movement type'].astype(str).str.lower() == 'fixation'
        df_fix = pd.DataFrame({
            'participant': df[participant_col].astype(str),
            'recording': df[recording_col].astype(str),
            'stimulus': df['Presented Media name'].astype(str),
            'event_index': pd.to_numeric(df['Eye movement type index'], errors='coerce'),
            't': t_ms, 'dur': dur_ms,
            'x': pd.to_numeric(df['Fixation point X'], errors='coerce'),
            'y': pd.to_numeric(df['Fixation point Y'], errors='coerce'),
            **sample_measures,
        })[is_fix.to_numpy()]
        df_fix['snapshot_mapped'] = False
        ls.append(collapse_samples(df_fix, ['recording', 'stimulus', 'event_index']))

    # ---------- glasses: fixations mapped onto snapshots ----------
    media_sizes = {}
    for snapshot, cols in mapped_snapshots.items():
        is_fix = df[cols['type']].astype(str).str.lower() == 'fixation'
        if 'width' in cols and 'height' in cols:
            media_sizes[snapshot] = (float(pd.to_numeric(df[cols['width']], errors='coerce').max()),
                                     float(pd.to_numeric(df[cols['height']], errors='coerce').max()))
        if not is_fix.any():
            continue
        index_col = cols.get('index', 'Eye movement type index')
        df_snap = pd.DataFrame({
            'participant': df[participant_col].astype(str),
            'recording': df[recording_col].astype(str),
            'stimulus': snapshot,
            'event_index': pd.to_numeric(df[index_col], errors='coerce'),
            't': t_ms, 'dur': dur_ms,
            'x': pd.to_numeric(df[cols['x']], errors='coerce'),
            'y': pd.to_numeric(df[cols['y']], errors='coerce'),
            **sample_measures,
        })[is_fix.to_numpy()]
        df_snap['snapshot_mapped'] = True
        ls.append(collapse_samples(df_snap, ['recording', 'stimulus', 'event_index']))

    if not ls:
        raise ValueError("No fixations found. The Data export needs either 'Fixation point X/Y' plus 'Presented "
                         "Media name' (screen-based recordings) or 'Mapped fixation X/Y [snapshot]' columns "
                         "(glasses recordings mapped onto snapshots).")
    df_out = pd.concat(ls).reset_index(drop=True)
    for col, values in extras.items():
        # per-recording constants (condition, timeline) are carried over by recording
        per_rec = pd.Series(values.values, index=df[recording_col].astype(str).values).groupby(level=0).first()
        df_out[col.lower().replace(' ', '_')] = df_out['recording'].map(per_rec)
    df_out = df_out.dropna(subset=['x', 'y', 't']).sort_values(['participant', 'stimulus', 't']).reset_index(drop=True)
    df_out['unit_timestamp'] = unit
    df_out.attrs['media_sizes'] = media_sizes  # snapshot -> (width, height) in px, when the export carries them
    return df_out, dict(OUTPUT_MAPPING, pupil_col='pupil' if 'pupil' in df_out.columns else None)


def collapse_samples(df_samples, keys):
    """
    Collapse gaze samples to one row per fixation, grouped by `keys` (e.g. recording, stimulus, event_index):
    participant, t (first sample), dur (reported event duration, or the sample span where it is missing),
    x, y (means), snapshot_mapped, plus pupil and distance_mm means where present. Rows without event_index
    are dropped.
    """
    # Many gaze samples per fixation -> one row: first timestamp, the reported event duration, mean position
    # (Pro Lab repeats the fixation point on every sample, so the mean equals that value; NaN-safe).
    df_ = df_samples.dropna(subset=['event_index'])
    grouped = df_.groupby(keys, sort=False)
    aggs = dict(participant=('participant', 'first'), t=('t', 'min'), t_end=('t', 'max'),
                dur=('dur', 'first'), x=('x', 'mean'), y=('y', 'mean'),
                snapshot_mapped=('snapshot_mapped', 'first'))
    for col in ['pupil', 'distance_mm']:
        if col in df_.columns:
            aggs[col] = (col, 'mean')
    df_fix = grouped.agg(**aggs).reset_index()
    # No event-duration column exported -> fall back to the sample span (last sample start, so slightly short)
    missing = df_fix['dur'].isna()
    df_fix.loc[missing, 'dur'] = df_fix.loc[missing, 't_end'] - df_fix.loc[missing, 't']
    return df_fix.drop(columns=['t_end'])  # event_index stays: Pro Lab's fixation number within the recording


# ---------------------------------------------------------------------------------------------------------------
# Data export, chunked (the WOQ room files are 70 GB: read_table would need that much RAM)
# ---------------------------------------------------------------------------------------------------------------

DATA_EXPORT_BASE_COLUMNS = ['Recording timestamp', 'Participant name', 'Recording name', 'Eye movement type',
                            'Eye movement type index', 'Gaze event duration', 'Eye movement event duration',
                            'Presented Media name', 'Fixation point X', 'Fixation point Y', 'Condition',
                            'Timeline name', 'Presented Stimulus name', 'Pupil diameter filtered',
                            'Pupil diameter left', 'Pupil diameter right', 'Gaze point 3D X', 'Gaze point 3D Y',
                            'Gaze point 3D Z']


def data_export_columns_needed(header):
    """
    The subset of a Data-export header worth reading: the base columns in DATA_EXPORT_BASE_COLUMNS (unit
    suffixes ignored) plus the per-snapshot 'Mapped ... [snapshot]' and 'Width/Height [snapshot]' columns.
    """
    # Of the ~300 export columns only these ~20 (+ the per-snapshot mapped columns) matter
    keep = []
    for col in header:
        base = strip_units(col)
        if base in DATA_EXPORT_BASE_COLUMNS or any(r.match(str(col)) for r in
                                                   [MAPPED_TYPE, MAPPED_INDEX, MAPPED_X, MAPPED_Y, SNAP_WIDTH, SNAP_HEIGHT]):
            keep.append(col)
    return keep


def load_prolab_data_export_chunked(path, chunksize=250_000, progress=None):
    """
    Same result as load_prolab_data_export(path) for huge TSV exports, reading only the needed columns in chunks
    of `chunksize` rows. A fixation whose samples straddle a chunk boundary is collapsed twice and merged at the
    end (the Pro Lab fixation point is constant across the samples, so the merge is exact). progress(done_bytes,
    total_bytes, text) may return False to abort.
    """
    from creapy.formats.table import sniff_delimiter, MISSING_VALUES, convert_decimal_commas, coerce_numeric
    encoding = 'utf-8-sig'
    try:
        sep = sniff_delimiter(path, encoding)
    except UnicodeDecodeError:
        encoding = 'latin-1'
        sep = sniff_delimiter(path, encoding)
    header = list(pd.read_csv(path, sep=sep, encoding=encoding, nrows=0).columns)
    usecols = data_export_columns_needed(header)
    assert usecols, "None of the Data-export columns were found in the header."
    total = os.path.getsize(path)
    ls = []
    mapping = None
    reader = pd.read_csv(path, sep=sep, encoding=encoding, usecols=usecols, na_values=MISSING_VALUES,
                         keep_default_na=True, chunksize=chunksize, low_memory=False)
    done_rows = 0
    for df_chunk in reader:
        df_chunk = coerce_numeric(convert_decimal_commas(df_chunk))
        df_chunk.columns = [str(c).strip() for c in df_chunk.columns]
        try:
            df_fix, mapping = load_prolab_data_export(df_chunk)
            ls.append(df_fix)
        except ValueError:
            pass  # a chunk without a single fixation (saccades only / unmapped stretch)
        done_rows += len(df_chunk)
        if progress is not None:
            # the file is too large to count lines first; bytes done are estimated from the chunk's share of rows
            if progress(done_rows, total, f"{done_rows:,} samples read") is False:
                raise InterruptedError("Import cancelled.")
    if not ls:
        raise ValueError("No fixations found in the Data export.")
    df_all = pd.concat(ls, ignore_index=True)
    # a fixation split across two chunks appears twice (same recording, stimulus and Pro Lab event index)
    keys = ['recording', 'stimulus', 'event_index']
    aggs = {'participant': 'first', 't': 'min', 'dur': 'first', 'x': 'mean', 'y': 'mean', 'snapshot_mapped': 'first'}
    for col in ['pupil', 'distance_mm', 'condition', 'timeline_name', 'presented_stimulus_name', 'unit_timestamp']:
        if col in df_all.columns:
            aggs[col] = 'first'
    df_out = df_all.groupby(keys, sort=False).agg(aggs).reset_index()
    df_out = df_out.sort_values(['participant', 'stimulus', 't']).reset_index(drop=True)
    return df_out, mapping


# ---------------------------------------------------------------------------------------------------------------
# AOI-based metrics export (one row per participant x interval x AOI; dwell/visit/fixation totals, no positions)
# ---------------------------------------------------------------------------------------------------------------

AOI_METRIC_LABELS = {
    'Total_duration_of_fixations': 'Total fixation duration (ms)',
    'Number_of_fixations': 'Number of fixations',
    'Average_duration_of_fixations': 'Mean fixation duration (ms)',
    'Time_to_first_fixation': 'Time to first fixation (ms)',
    'Duration_of_first_fixation': 'Duration of first fixation (ms)',
    'Total_duration_of_Visit': 'Total visit duration / dwell time (ms)',
    'Number_of_Visits': 'Number of visits',
    'Average_duration_of_Visit': 'Mean visit duration (ms)',
    'Time_to_first_Visit': 'Time to first visit (ms)',
    'Total_duration_of_Glances': 'Total glance duration (ms)',
    'Number_of_Glances': 'Number of glances',
    'Average_pupil_diameter': 'Mean pupil diameter (mm)',
    'Number_of_saccades_in_AOI': 'Number of saccades in AOI',
}
AOI_ID_COLUMNS = ['Recording', 'Participant', 'Condition', 'TOI', 'Interval', 'Media', 'AOI', 'AOI_size',
                  'Ungrouped', 'Duration_of_interval', 'Start_of_interval']


def load_prolab_aoi_metrics_export(path_or_df):
    """
    AOI-based metrics export -> (df, info). df keeps the identifying columns plus every metric column that has a
    label in AOI_METRIC_LABELS (counts and totals are 0 where Pro Lab left the cell empty: the participant did not
    look there; latencies stay NaN). info: {'metrics': [column names], 'labels': {column: label},
    'group_columns': [AOI, Media, Condition, ... with 2+ values]}.
    """
    df = read_table(path_or_df) if isinstance(path_or_df, str) else path_or_df.copy()
    if not is_prolab_metrics_export(df.columns):
        raise ValueError("Not a Tobii Pro Lab AOI-based metrics export (expected an 'AOI' column and "
                         "'Total_duration_of_…' / 'Number_of_…' columns).")
    ids = [c for c in AOI_ID_COLUMNS if c in df.columns]
    metrics = [c for c in AOI_METRIC_LABELS if c in df.columns]
    assert metrics, "No known metric columns found."
    df_out = df[ids + metrics].copy()
    for col in metrics:
        df_out[col] = pd.to_numeric(df_out[col], errors='coerce')
        if col.startswith(('Total_', 'Number_')):
            df_out[col] = df_out[col].fillna(0.)
    group_columns = [c for c in ['AOI', 'Media', 'Condition', 'Ungrouped', 'TOI', 'Interval', 'Participant']
                     if c in df_out.columns and df_out[c].nunique() >= 2]
    info = {'metrics': metrics, 'labels': {c: AOI_METRIC_LABELS[c] for c in metrics}, 'group_columns': group_columns,
            'n_participants': int(df_out['Participant'].nunique()) if 'Participant' in df_out.columns else None}
    return df_out, info


def aoi_metrics_summary(df_aoi, metric, by='AOI', group_col=None):
    """
    Summarise one metric column of the table from load_prolab_aoi_metrics_export over participants: one row
    per value of `by` (and of `group_col`, e.g. Condition or Media) with the columns mean, sd, median, n and
    share_looked (fraction of rows with a value > 0, NaN counted as 0).
    """
    # Mean, SD, n and median of one metric per AOI (and per group column, e.g. Condition or Media) over participants
    keys = [by] + ([group_col] if group_col and group_col != by else [])
    grouped = df_aoi.groupby(keys, sort=False)[metric]
    df_sum = grouped.agg(['mean', 'std', 'median', 'count']).reset_index()
    df_sum.columns = keys + ['mean', 'sd', 'median', 'n']
    df_sum['share_looked'] = grouped.apply(lambda v: float((v.fillna(0) > 0).mean())).to_numpy()
    return df_sum


if __name__ == '__main__':
    pass
