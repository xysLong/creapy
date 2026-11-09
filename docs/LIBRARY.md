# The creapy library

creapy has two faces, as announced at DHd 2026: **`creapy.io`**, the desktop app for art historians and other
researchers who do not program (maximal ease of use), and **`creapy`**, the Python library underneath it (maximal
analytical depth and flexibility). Everything the app shows is a library call. The app adds only what a window
needs: file dialogs, sliders, the worker thread, project files, the session log.

This document is for the second audience: people who know some Python and want more than the app offers, say their
own figure layouts, statistics beyond the built-in tests, batch processing of many datasets, or a notebook that
documents an analysis. `tutorial.ipynb` in the repository walks through the same material on the example dataset;
`demo_similarity.ipynb` covers the similarity workflow in depth.

## Install

```bash
pip install creapy          # once on PyPI (planned with the public release); until then:
pip install "creapy @ git+https://github.com/xysLong/creapy.git"
pip install "creapy[gui]"   # adds PySide6 for the desktop app
```

The library needs no Qt: numpy, pandas, scipy, matplotlib, shapely, scikit-learn, Pillow, openpyxl and
[heatmatch](https://pypi.org/project/heatmatch/) (PyPI). Python 3.10 or newer.

## Design rules (what "flexible" means here)

- **Every plot takes a matplotlib `ax`** (or creates one when `ax=None`) and returns what it drew or computed:
  the heatmap array, the matrix, the curves. Compose your own figures with `plt.subplots`.
- **Every table is a pandas DataFrame** with plain column names: `participant_table`, `aoi_metrics`,
  `participant_rqa`, `participant_periodogram`, `score_overview`, `group_comparison` ... Feed them to seaborn,
  statsmodels, pingouin, R via `to_csv`.
- **Datasets are per stimulus**: a `FixationData` and a `SaccadeData` (one derived from the other). `.subset(
  subjects=..., t_range=...)` returns a new dataset for a participant selection or time window in seconds; the GUI's
  Show bar is nothing else.
- **Groups are a dict** `participant -> group name`. Pass it to `matshow`, `show_boxplot`, `permutation_test`,
  `group_comparison`, `show_group_boxplot`, `split_by_group`.
- **Coordinates are image pixels, y down**; times in seconds relative to the trial start; durations in the unit of
  the table (`fix.dur_unit`). Participants are weighted equally in every aggregate (`weights_simple`).
- **Slow computations are cached on the dataset** (heatmaps per bandwidth, orientation fields per sigma,
  similarity results per parameter set) and accept `progress` / `verbose` where they take long.

## Quickstart

```python
import creapy, matplotlib.pyplot as plt

df, mapping = creapy.load_fixations("fixation_report.csv")      # EyeLink report, Tobii export or any table
datasets = creapy.datasets_by_stimulus(df, mapping)             # {stimulus -> (FixationData, SaccadeData)}
fix, sac = datasets["painting.png"]
grouping = {p: ("expert" if p.startswith("E") else "novice") for p in fix.subjects}

fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(12, 5))
fix.make_heatmap(ax0, bw_method=0.1, cmap="inferno")
fix.subset(t_range=(0, 3)).visualize_scanpath(ax1, subjects=fix.subjects[:3])

df_stats = creapy.participant_table(fix, sac)                   # one row per participant, incl. coefficient K
print(creapy.group_comparison(df_stats, grouping))
creapy.show_group_boxplot(df_stats, "coefficient_K", grouping)
creapy.show_measure_curve(fix, sac, "fixation_duration", sigma=2)   # the Time Series view
mm = fix.compute_scanpath_similarity("multimatch")
print(mm.score_overview(grouping)); mm.permutation_test(grouping)
```

## What the app shows, as library calls

| View in creapy.io | Library |
|---|---|
| Fixation Heatmap | `fix.make_heatmap(ax, bw_method, cmap, ...)`; shared scale: `fix.heatmap_max(...)` → `vmax` |
| Fixation Scanpath | `fix.visualize_scanpath(ax, subjects=...)` |
| Saccade Scanpath | `sac.visualize_scanpaths(ax, ...)` |
| Saccade Heatmap | `sac.make_heatmap(ax, sigma, orientation, ...)` (HeatMatch) |
| Saccade Directions | `sac.make_rose_plot(ax=polar_ax, ...)`, `sac.get_circular_weighted_stats()` |
| Areas of Interest | `creapy.AOI.rectangle/polygon`, `fix.set_top_down_aoi`, `fix.set_bottom_up_aoi`, `fix.aoi_metrics()`, `creapy.show_scarf_plot`, `creapy.transition_matrix`, `creapy.first_fixation_order` |
| Time Series | `creapy.show_measure_curve(fix, sac, measure)`, `creapy.split_by_group`, `fix.make_aoi_percentage_curve`; periodogram `creapy.participant_periodogram` + `show_periodogram` + `dominant_period`; scalogram `resample_regular` + `morlet_scalogram` + `show_scalogram` |
| Saccade Similarity | `sac.compute_heatmatch_similarity(sigma)` → `.matshow / .show_boxplot / .permutation_test / .show_multidimensional_scaling`; over time: `sac.compute_heatmatch_similarity_profile(...)` → `.show_profile` |
| Scanpath Comparison | `fix.compute_scanpath_similarity("multimatch" / "scanmatch" / "cross_recurrence")` → same methods + `.score_overview / .show_score_overview` |
| Recurrence | `creapy.show_recurrence_plot`, `creapy.participant_rqa`, `creapy.cross_recurrence_table`, `creapy.show_group_boxplot` |
| Statistics | `creapy.participant_table`, `creapy.group_comparison`, `fix.aoi_metrics()`, `creapy.show_group_boxplot` |
| Show bar (participant / group / time window) | `fix.subset(subjects=..., t_range=...)`, same for `sac` |
| Compare Side by Side / Export for All Stimuli | a `for` loop over `datasets.items()` and `plt.subplots(...)` |
| Import dialog | `creapy.load_fixations(path, mapping)`, `creapy.load_saccades`, `creapy.guess_mapping`, the Tobii loaders |

## API reference

Generated from the docstrings by `docs/make_library_reference.py`; `help(obj)` in Python shows the same text.


### `creapy`

top level: loading tables, building datasets, re-exports of everything below

- `load_fixations(path, mapping=None, **mapping_kwargs)`: Fixation table (CSV/TSV/Excel with one row per fixation, or a Tobii Pro Lab Data export) -> (df, mapping).
- `load_saccades(path, mapping=None, **mapping_kwargs)`: Saccade table (one row per saccade) -> (df, mapping) with the sac_* keys of SACCADE_FIELDS.
- `datasets_by_stimulus(df, mapping, stimulus_paths=None, is_fixation=True)`: Split a table into per-stimulus (FixationData, SaccadeData) pairs: {stimulus -> (fix, sac)}.
- `build_pair(df_stim, path, mapping, is_fixation=True)`: (FixationData, SaccadeData) of one stimulus from its rows and image path.

### `creapy.gaze.base`

StimulusGaze: what FixationData and SaccadeData share (subsets, AOIs, smoothing)


#### class `StimulusGaze`

Shared base of FixationData and SaccadeData: one stimulus image plus the gaze events of all participants.


- `StimulusGaze(df_stim, path_to_stim, subj_index_col, t_col, v_col, t_min=0, t_max=None, interpolation_grid=(100, 100), interpolation_step=0.01, sigma=5, trial_col=None, img=None, scale=1.0, time_unit=None)`: Initialize self. See help(type(self)) for accurate signature.
- `.n_subjects()`: Number of distinct participants in the table.
- `.subset_rows(subjects=None, t_range=None)`: Boolean row mask over self.df for a participant selection.
- `.plot_setup(ax, include_stimulus=True, bw=False, stimulus_alpha=1.0)`: Draw the stimulus into ax as the background of a gaze plot: image pixel coordinates, y pointing down.
- `.make_v_curve_by_time(ax0, ax1, interpolation_step=0.01, sigma=5, n_std=0.05, t_valid=None, color=None, label=None)`: Plot the value (fixation duration or saccade amplitude) over viewing time into ax1.
- `.set_top_down_aoi(name, geom)`: Register a hand-drawn area of interest under `name`: geom is a shapely polygon in image array pixels.
- `.remove_aoi(name)`: Drop the AOI called `name`; unknown names are ignored.
- `.show_all_aoi(ax=None)`: Draw every registered AOI over the stimulus, one tab10 colour each.
- `.gaussian_smooth_irregular(t_new, t_old, v_old, weights_subj, sigma, chunk_size=512)` *(static)*: Gaussian-kernel smoothing of irregularly sampled values v_old at times t_old onto the grid t_new.


### `creapy.gaze.fixation`

FixationData: heatmaps, scanpaths, AOIs, descriptives, scanpath similarity


#### class `FixationData`

Fixations of all participants on one stimulus image.


- `FixationData(df_stim, path_to_stim, fix_x_col, fix_y_col, fix_t_col, fix_dur_col, subj_index_col, interpolation_grid=(100, 100), bw_method=0.1, num_levels=20, t_min=0, t_max=None, interpolation_step=0.01, sigma=5, trial_col=None, pupil_col=None, img=None, scale=1.0, normalized_xy=False, time_unit=None, **kwargs)`: Initialize self. See help(type(self)) for accurate signature.
- `.subset(subjects=None, t_range=None)`: A new FixationData with only the selected participants.
- `.heatmap_max(bw_method=0.1)`: Peak density of this dataset's heatmap for the given bw_method.
- `.prepare_heatmap(bw_method=0.1, num_levels=20, vmax=None)`: Run the expensive part of make_heatmap (KDE and contouring) into the cache without touching matplotlib.
- `.make_heatmap(ax, bw_method=0.1, num_levels=20, from_level=1, cmap='coolwarm', alpha=0.75, scatter_color=(1, 1, 1), scatter_size=1, scatter_alpha=0.5, stimulus_alpha=1.0, grayscale=False, vmax=None)`: Duration-weighted fixation heatmap over the stimulus in ax: a Gaussian KDE.
- `.visualize_scanpath(ax, subjects=None, numbered=True, color=None, alpha=0.8, size=1.0, line_width=1.5, stimulus_alpha=1.0, grayscale=False, max_numbers=150)`: The textbook scanpath in ax: fixation circles sized by duration, connected in viewing order.
- `.set_bottom_up_aoi(bw_method=0.1, num_levels=20, from_level=1)`: Data-driven AOI: the hot spots of the heatmap above a contour level.
- `.make_aoi_percentage_curve(ax0, ax1, interpolation_step=0.01, sigma=5, n_std=0.05, color=None, names=None)`: Plot into ax1 how the share of fixation time inside each AOI evolves over viewing time.
- `.aoi_metrics(names=None)`: The classic AOI table, one row per participant x AOI (all AOIs, or the given `names`).
- `.participant_stats()`: One row per participant with the usual descriptives.
- `.compute_scanpath_similarity(method='multimatch', verbose=True, progress=None, **kwargs)`: Pairwise scanpath similarity between all participants: 'multimatch', 'scanmatch' or 'cross_recurrence'.
- `.compute_grid_based_fixation_similarity(grid_sizes=(7,), include_self=False)`: Pairwise fixation similarity on an n x n grid over the image.


### `creapy.gaze.saccade`

SaccadeData: saccade scanpaths, HeatMatch heatmaps and similarity, rose diagrams


#### class `SaccadeData`

Saccades of all participants on one stimulus image, each a line from (x0, y0) to (x1, y1).


- `SaccadeData(df_stim, path_to_stim, sac_x0_col, sac_y0_col, sac_x1_col, sac_y1_col, sac_t_col, sac_amp_col, subj_index_col, t_min=0, t_max=None, interpolation_grid=(200, 200), interpolation_step=0.01, sigma=5, trial_col=None, img=None, scale=1.0, normalized_xy=False, time_unit=None, **kwargs)`: Initialize self. See help(type(self)) for accurate signature.
- `.subset(subjects=None, t_range=None)`: A new SaccadeData with only the selected participants and/or time window.
- `.participant_stats()`: One row per participant.
- `.visualize_scanpaths(ax, color=(1, 1, 0), alpha=1.0, width=1, ooi=None, stimulus_alpha=1.0, grayscale=False)`: Draw every saccade as an arrow over the stimulus in ax (one quiver call).
- `.make_heatmap(ax, alpha, sigma, cmap='coolwarm', ooi=90, quantile=0.8, degree=2, stimulus_alpha=1, grayscale=False)`: HeatMatch orientation heatmap (Long et al. 2026) over the stimulus in ax.
- `.get_circular_weighted_stats(sigma)`: The orientation field behind the saccade heatmap, computed by heatmatch with kernel width sigma.
- `.make_rose_plot(bins=36, title=None, ax=None, rays=True, num=False, hull=True, hull_args=None, cmap='GnBu', center_symmetric=False, subjects=None)`: Rose diagram of saccade directions in `bins` bins over 360 degrees, every participant weighted equally.
- `.compute_heatmatch_similarity(sigma=50, density_coherence_tradeoff=0.5, verbose=True, progress=None)`: Pairwise HeatMatch similarity (Long et al. 2026) between all participants, self-pairs included.
- `.compute_heatmatch_similarity_profile(window=None, step=None, sigma=50, density_coherence_tradeoff=0.5, min_saccades=3, verbose=True, progress=None)`: Sliding-window HeatMatch similarity: pairwise s_loc/s_dir per time window.
- `.prepare_heatmap(sigma)`: Compute the orientation field for `sigma` (pixels) into the cache without drawing.

- `report_progress(progress, done, total, text)`: Forward (done, total, text) to a progress callback; a callback that returns False asks for an abort.

### `creapy.gaze.convert`

fixation table <-> saccade table

- `viewing_keys(column_mapping)`: The columns that identify one continuous viewing: [subj_index_col], plus trial_col when the mapping has one.
- `fixations_to_saccades(df_fixation, column_mapping)`: Derive the saccades between consecutive fixations of ONE stimulus.
- `saccades_to_fixations(df_saccade, column_mapping)`: Reconstruct the fixations between consecutive saccades of ONE stimulus.

### `creapy.aoi.aoi`

AOI geometry (rectangles, polygons, JSON records)


#### class `AOI`

One area of interest: a named shapely geometry in image pixels (x right, y down).


- `AOI(name='Unnamed', geom=None, paths=None)`: Initialize self. See help(type(self)) for accurate signature.
- `.area()`: Area of the AOI in square pixels.
- `.contains(points)`: True for each point inside or on the boundary of the AOI.
- `.rectangle(name, x0, y0, x1, y1)` *(static)*: Rectangular AOI from two opposite corners (x0, y0), (x1, y1) in pixels.
- `.polygon(name, vertices)` *(static)*: Polygon AOI from a list of (x, y) vertices in pixels, at least three.
- `.to_record()`: Dict {'name', 'wkt'} describing the AOI as text (WKT), for saving AOI sets to JSON; see from_record.
- `.from_record(record)` *(static)*: Rebuild an AOI from a to_record() dict.
- `.show(ax, color='yellow', alpha=0.4, label=True)`: Draw the AOI on a matplotlib axes as a translucent patch.


### `creapy.aoi.sequence`

AOI sequences: scarf plot, transition matrix, first-fixation order

- `aoi_sequence(fix, names=None, include_outside=True)`: Which AOI each fixation fell into, in viewing order.
- `collapse_runs(df_seq)`: Merge consecutive fixations in the same AOI into one visit.
- `transition_matrix(fix, names=None, include_outside=False, normalize='row', per_participant_weight=True)`: AOI -> AOI transitions between consecutive visits, self-transitions excluded.
- `show_transition_matrix(ax, matrix, cmap='Blues', fmt='{:.0%}', text_color_switch=0.6)`: Draw a transition_matrix() as a heat-table on ax (rows = from, columns = to).
- `aoi_palette(names, include_outside=True)`: Dict AOI name -> RGBA colour (tab10 cycle), plus a grey for 'outside' unless include_outside=False.
- `show_scarf_plot(ax, fix, names=None, subjects=None, colors=None, relative_time=True, outside_alpha=0.35, row_height=0.8)`: Scarf plot: one row per participant, viewing time on x.
- `first_fixation_order(fix, names=None)`: In which order each participant first visited the AOIs.

### `creapy.stats.descriptives`

per-participant table, coefficient K, group comparison, group boxplot

- `coefficient_k(fix_dur, next_sac_amp, subj)`: Ambient-focal coefficient K (Krejtz et al. 2016) per fixation.
- `next_saccade_amplitude(dataset_fix)`: Amplitude in image pixels of the saccade that follows each fixation.
- `fixation_k(dataset_fix)`: Per-fixation coefficient K (see coefficient_k) aligned with dataset_fix.df, from the fixation table alone.
- `participant_table(dataset_fix, dataset_sac=None)`: One row per participant with the fixation descriptives (n_fixations, mean/median duration, spread ...).
- `group_comparison(df_stats, grouping, columns=None)`: Group means per measure plus a two-sample test (Welch t, Mann-Whitney or ANOVA).
- `show_group_boxplot(df_values, measure, grouping=None, ax=None, group_col='group', jitter=0.12, seed=0, box_color='#c7d3e6', median_color='#1f5fbf', point_color='#333333')`: Boxplot of one measure by group with every participant as a jittered point.

### `creapy.stats.timeseries`

smoothed curves of a measure over viewing time, per group

- `measure_key(name)`: 'fixation_duration' or the GUI label 'Fixation Duration' -> 'fixation_duration'; ValueError otherwise.
- `value_series(fix, sac, measure)`: The raw per-event values of one measure: returns (dataset, values, y label).
- `smoothed_curve(dataset, values, sigma, step=0.05, weights=None)`: Gaussian-smoothed mean of `values` over viewing time: returns (t, mean, std) on a regular grid.
- `show_smoothed_curve(ax, dataset, values, sigma, n_std=0.05, color=None, label=None, step=0.05, t_valid=None)`: Draw smoothed_curve(...) on ax, dashed after t_valid, with a band of n_std standard deviations.
- `show_measure_curve(fix, sac, measure, sigma=2.0, n_std=0.05, ax=None, color=None, label=None, step=0.05)`: One call for a whole Time Series curve: value_series + show_smoothed_curve with axis labels.
- `split_by_group(fix, sac, grouping)`: [(group name, fix subset, sac subset)] for the participants of every group, groups in natural order.

### `creapy.stats.recurrence`

recurrence plots and RQA (Anderson et al. 2013), cross-recurrence

- `recurrence_matrix(xy, radius)`: Boolean (n, n) recurrence matrix of a scanpath: True where fixations i and j lie within radius pixels.
- `rqa_measures(xy, radius, min_line=2)`: Recurrence quantification analysis of one scanpath after Anderson et al. 2013.
- `default_radius(fix)`: Default recurrence radius for a dataset: 5 % of the stimulus diagonal in pixels.
- `participant_rqa(fix, radius=None, min_line=2)`: RQA measures per participant, one row each.
- `cross_recurrence(xy_a, xy_b, radius)`: Cross-recurrence of two scanpaths (each an (n, 2) array of x, y in pixels).
- `cross_recurrence_table(fix, radius=None, verbose=True, progress=None)`: Cross-recurrence for every unordered pair of participants, diagonal included.
- `show_recurrence_plot(ax, xy, radius, color='white')`: Draw the recurrence plot of one scanpath on ax: fixation index on both axes.

### `creapy.stats.spectrum`

Lomb–Scargle periodograms and Morlet scalograms

- `lomb_scargle(t, v, freqs)`: Normalised Lomb-Scargle periodogram of an irregularly sampled series: t in seconds.
- `default_frequencies(t_span, n=200)`: Log-spaced grid of n frequencies in Hz from 2 / t_span (two cycles per viewing) up to 2 Hz.
- `participant_periodogram(fix, values=None, freqs=None)`: Lomb-Scargle periodogram per participant.
- `mean_periodogram(df_power)`: Mean normalised power over the participant columns of a participant_periodogram() table, ignoring NaN.
- `dominant_period(df_power)`: Strongest rhythm per participant from a participant_periodogram() table.
- `resample_regular(t, v, step=0.05, sigma=0.3, weights=None)`: Put an irregular series (t in seconds, v) onto a regular grid by Gaussian smoothing.
- `morlet_scalogram(t_new, v_new, freqs, w0=6.0)`: Wavelet power of a REGULARLY sampled series (from resample_regular) with a complex Morlet wavelet.
- `show_periodogram(ax, df_power, freqs_or_index=None, color=None, label=None, individual_alpha=0.15)`: Plot a participant_periodogram() table on ax: one thin curve per participant, the mean in bold.
- `show_scalogram(ax, t_new, freqs, power, cmap='magma')`: Time x frequency map of wavelet power on ax (pcolormesh, log frequency axis): t_new in seconds.

### `creapy.similarity.heatmatch_result`

pairwise similarity results: matrix, boxplot, permutation test, viewer map, overview


#### class `PairwiseSimilarityResult`

Pairwise similarity scores between all subjects viewing one stimulus.


- `PairwiseSimilarityResult(df_sim, scores=None)`: Initialize self. See help(type(self)) for accurate signature.
- `.default_score()`: The score column used when `which` is not given (s_dir for HeatMatch, the first column otherwise).
- `.matrix(which=None, grouping=None)`: Symmetric participant x participant DataFrame of one score.
- `.matshow(which=None, grouping=None, ax=None, cmap='viridis', group_color='black')`: The similarity matrix as an image with a colour bar.
- `.show_boxplot(grouping, which=None, ax=None)`: Boxplots of the pairwise scores within each group and between each pair of groups ('A/B').
- `.permutation_test(grouping, which=None, n_permutations=10000, seed=0, verbose=True)`: One-sided permutation test: are participants more similar within their group than between groups?
- `.score_overview(grouping=None)`: Mean score over all unordered participant pairs, one row per score column.
- `.show_score_overview(grouping=None, ax=None, strip_prefix='mm_')`: Grouped bar chart of score_overview(): one group of bars per score.
- `.show_multidimensional_scaling(grouping=None, which=None, ax=None)`: Viewer map: each participant as a point in two dimensions.


#### class `HeatMatchSimilarityResult`

Pairwise HeatMatch similarity scores (Long et al. 2026): s_loc and s_dir (the default).


- `HeatMatchSimilarityResult(df_sim)`: Initialize self. See help(type(self)) for accurate signature.


#### class `HeatMatchSimilarityProfile`

Sliding-window HeatMatch similarity: pairwise scores per time window (viewer synchrony over time).


- `HeatMatchSimilarityProfile(df_profile, window)`: Initialize self. See help(type(self)) for accurate signature.
- `.curves(which='s_dir', grouping=None)`: {label: DataFrame indexed by window centre (s) with columns mean, std}.
- `.show_profile(which='s_dir', grouping=None, ax=None, n_std=0.05)`: Similarity over viewing time: the curves of curves() with a band of ± n_std standard deviations.


### `creapy.similarity.scanpath`

MultiMatch, ScanMatch and cross-recurrence between two scanpaths

- `scanmatch(path_a, path_b, width, height, grid=(12, 8), temporal_bin=None, gap=0.0, threshold_share=0.25)`: ScanMatch similarity of two scanpaths (Cristino et al. 2010), a score in [0, 1].
- `multimatch(path_a, path_b, width, height, amplitude_threshold=None, direction_threshold=None, duration_threshold=0.3)`: MultiMatch similarity of two scanpaths (Dewhurst et al. 2012): dict with the five scores.
- `scanpath_of(fix, subj)`: One participant's scanpath as an (n, 3) array of x, y in pixels and duration in seconds.
- `scanpath_similarity_table(fix, method='multimatch', verbose=True, progress=None, **kwargs)`: Pairwise scanpath similarity between all participants of fix, one row per unordered pair incl. the diagonal.

### `creapy.formats.table`

reading CSV/TSV/Excel robustly

- `sniff_delimiter(path, encoding)`: Guess the column separator of a text table from its header line: tab, ';', ',' or '|'.
- `read_table(path, sheet_name=0)`: Read one table (CSV/TSV/TXT with any common delimiter, or Excel with `sheet_name`) into a DataFrame.
- `convert_decimal_commas(df)`: Turn '12,5' into 12.5 in text columns that are numeric apart from the decimal comma.
- `coerce_numeric(df)`: Make text columns numeric where at least 95 % of the non-empty values parse as numbers.
- `numeric_columns(df)`: Names of the columns with a numeric dtype.
- `image_like_columns(df)`: Names of the text columns whose values (the first 200 non-empty ones) mostly end in an image extension.

### `creapy.formats.detect`

format detection and column-mapping guesses

- `detect_format(columns)`: Classify a table by its column names alone (EyeLink fixation or saccade report, Tobii export, generic).
- `guess_mapping(df, fields)`: Best-effort column mapping for `fields` (FIXATION_FIELDS or SACCADE_FIELDS).
- `validate_mapping(df, mapping, fields)`: Human-readable problems with a mapping, as a list of strings; empty when the mapping is usable.

### `creapy.formats.tobii`

Tobii Pro Lab exports (Data, event-based metrics, AOI-based metrics)

- `strip_units(name)`: Column name without the unit suffix newer Pro Lab versions append.
- `timestamp_unit(columns)`: 'ms' or 'us' from the unit suffix of the 'Recording timestamp' column.
- `is_prolab_data_export(columns)`: True if the columns look like a Pro Lab Data export (one row per gaze sample).
- `is_prolab_event_export(columns)`: True if the columns of a Pro Lab event-based metrics export are present.
- `is_prolab_metrics_export(columns)`: True for an AOI-based metrics export: an 'AOI' column plus 'Total_duration_of_...' / 'Number_of_...'.
- `load_prolab_export(path_or_df)`: Load a Tobii Pro Lab export (file path or already-read DataFrame).
- `load_prolab_event_export(path_or_df)`: Event-based metrics export -> one row per fixation with participant, stimulus, trial, t, dur, x, y.
- `load_prolab_data_export(path_or_df)`: Pro Lab Data export -> one row per fixation with the columns participant, stimulus, t (ms), dur (ms), x, y.
- `collapse_samples(df_samples, keys)`: Collapse gaze samples to one row per fixation, grouped by `keys` (e.g. recording, stimulus, event_index).
- `data_export_columns_needed(header)`: The subset of a Data-export header worth reading: the base columns in DATA_EXPORT_BASE_COLUMNS.
- `load_prolab_data_export_chunked(path, chunksize=250000, progress=None)`: Same result as load_prolab_data_export(path) for huge TSV exports.
- `load_prolab_aoi_metrics_export(path_or_df)`: AOI-based metrics export -> (df, info).
- `aoi_metrics_summary(df_aoi, metric, by='AOI', group_col=None)`: Summarise one metric column of the table from load_prolab_aoi_metrics_export over participants.

### `creapy.misc.utils`

natural sorting, image loading, time units, finding stimulus images

- `natural_key(value)`: Sort key that orders embedded numbers numerically ('vp2' before 'vp11'); letters compare lower-case.
- `natural_sorted(values)`: sorted() with natural_key, so 'vp2' comes before 'vp11'.
- `load_stimulus_image(path, max_side=2400)`: Any image Pillow can open -> (uint8 RGB array, scale).
- `seconds_from_table_time(t)`: Convert a time column to seconds and report the unit it came in: values above 600,000 are taken as µs.
- `find_images(folder, max_depth=3)`: Dict lower-case file name and stem -> full path for every image in a folder, subfolders included.

### `creapy.misc.contours`

figure-free contour paths for heatmaps

- `contour_levels(zmin, zmax, num_levels)`: The level boundaries matplotlib would pick for contourf(..., levels=num_levels).
- `filled_contour_paths(xx, yy, zz, levels)`: Filled-contour polygons without a figure: one matplotlib Path per interval [levels[i], levels[i+1]].

### `creapy.examples`

the synthetic example dataset

- `example_folder()`: Folder holding the example files.
- `example_dataset()`: Path of the example fixation CSV (demo_fixations.csv); pictures and table are generated on first call.
- `draw_picture_a(path)`: Paint synthetic picture A.
- `draw_picture_b(path)`: Paint synthetic picture B.
- `simulate_viewer(rng, attractors, weights, n_fix, focal, t_total=30.0)`: Simulate one viewer on one picture: a list of dicts with t_start (ms), dur (ms), x, y (px) and pupil.
- `make_example(folder)`: Write the whole example (two pictures, fixation table, README) into `folder`.
