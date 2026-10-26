"""
creapy: eye-tracking visual analytics for the CReA Lab (University of Vienna).

Library layer (no Qt): load a fixation or saccade table, build per-stimulus datasets, draw heatmaps,
scanpaths, saccade heatmaps (HeatMatch), compute AOI metrics, descriptives and similarity scores.
GUI: `creapy-io` on the command line or `python -m creapy.io`.
"""
from creapy.formats import read_table, detect_format, guess_mapping, FIXATION_FIELDS, SACCADE_FIELDS
from creapy.formats import load_prolab_export, load_prolab_data_export, load_prolab_event_export
from creapy.formats import load_prolab_data_export_chunked, load_prolab_aoi_metrics_export, aoi_metrics_summary
from creapy.gaze.base import StimulusGaze
from creapy.gaze.fixation import FixationData
from creapy.gaze.saccade import SaccadeData
from creapy.gaze.convert import fixations_to_saccades, saccades_to_fixations
from creapy.aoi.aoi import AOI
from creapy.aoi.sequence import aoi_sequence, transition_matrix, show_scarf_plot, show_transition_matrix, first_fixation_order
from creapy.stats import coefficient_k, fixation_k, participant_table, group_comparison, show_group_boxplot
from creapy.stats import value_series, show_measure_curve, split_by_group
from creapy.stats import participant_rqa, cross_recurrence_table, show_recurrence_plot
from creapy.stats import participant_periodogram, dominant_period, show_periodogram, morlet_scalogram, show_scalogram
from creapy.similarity.heatmatch_result import PairwiseSimilarityResult, HeatMatchSimilarityResult
from creapy.misc.utils import natural_sorted, find_images
import os

__version__ = "0.3.0"


def load_fixations(path, mapping=None, **mapping_kwargs):
    """
    Fixation table (CSV/TSV/Excel with one row per fixation, or a Tobii Pro Lab Data export) ->
    (df, mapping). `mapping` keys: stim_col, subj_index_col, fix_t_col, fix_dur_col, fix_x_col, fix_y_col,
    optional trial_col, pupil_col. Omitted keys are guessed from the column names.
    """
    df = read_table(path)
    if detect_format(df.columns) in ('tobii_data_export', 'tobii_event_export'):
        df, guessed = load_prolab_export(df)
    else:
        guessed = guess_mapping(df, FIXATION_FIELDS)
    guessed.update(mapping or {})
    guessed.update(mapping_kwargs)
    return df, guessed


def load_saccades(path, mapping=None, **mapping_kwargs):
    """Saccade table (one row per saccade) -> (df, mapping) with the sac_* keys of SACCADE_FIELDS."""
    df = read_table(path)
    guessed = guess_mapping(df, SACCADE_FIELDS)
    guessed.update(mapping or {})
    guessed.update(mapping_kwargs)
    return df, guessed


def datasets_by_stimulus(df, mapping, stimulus_paths=None, is_fixation=True):
    """
    Split a table into per-stimulus (FixationData, SaccadeData) pairs: {stimulus -> (fix, sac)}.
    stimulus_paths maps the table's stimulus values to image files when the values are not paths themselves:
    either a dict {stimulus value -> image path} or a folder to search (file names and stems are matched).
    """
    if isinstance(stimulus_paths, (str, os.PathLike)):
        found = find_images(str(stimulus_paths))
        stimulus_paths = {}
        for stim in df[mapping['stim_col']].unique():
            key = str(stim).lower()  # find_images keys are lower-case names and stems
            stimulus_paths[stim] = found.get(key, found.get(os.path.splitext(key)[0], str(stim)))
    datasets = {}
    for stim, df_stim in df.groupby(mapping['stim_col']):
        path = stimulus_paths[stim] if stimulus_paths is not None else str(stim)
        datasets[stim] = build_pair(df_stim, path, mapping, is_fixation)
    return datasets


def build_pair(df_stim, path, mapping, is_fixation=True):
    """
    (FixationData, SaccadeData) of one stimulus from its rows and image path; the second dataset is derived from
    the first (fixations -> saccades between consecutive fixations, or saccades -> their end points).
    """
    # (FixationData, SaccadeData) of one stimulus. The derived table is built from the first dataset's own rows,
    # which already sit in image-array pixels (normalised Tobii coordinates and downscaled images handled once).
    if is_fixation:
        fix = FixationData(df_stim, path, **mapping)
        df_sac, sac_mapping = fixations_to_saccades(fix.df, fix.mapping)  # t stays in the table's unit
        sac = SaccadeData(df_sac, path, img=fix.img, scale=1., time_unit=fix.time_unit, **sac_mapping)
    else:
        sac = SaccadeData(df_stim, path, **mapping)
        df_fix, fix_mapping = saccades_to_fixations(sac.df, sac.mapping)
        fix = FixationData(df_fix, path, img=sac.img, scale=1., time_unit=sac.time_unit, **fix_mapping)
    return fix, sac
