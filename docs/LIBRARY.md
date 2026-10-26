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

- `load_fixations(path, mapping=None, **mapping_kwargs)`: Fixation table (CSV/TSV/Excel with one row per fixation, or a Tobii Pro Lab Data export) -> (df, mapping). `mapping` keys: stim_col, subj_index_col, fix_t_col, fix_dur_col, fix_x_col, fix_y_col, optional trial_col, pupil_col. Omitted keys are guessed from the column names.
- `load_saccades(path, mapping=None, **mapping_kwargs)`: Saccade table (one row per saccade) -> (df, mapping) with the sac_* keys of SACCADE_FIELDS.
- `datasets_by_stimulus(df, mapping, stimulus_paths=None, is_fixation=True)`: Split a table into per-stimulus (FixationData, SaccadeData) pairs: {stimulus -> (fix, sac)}. stimulus_paths maps the table's stimulus values to image files when the values are not paths themselves: either a dict {stimulus value -> image path} or a folder to search (file names and stems are matched).
- `build_pair(df_stim, path, mapping, is_fixation=True)`: (FixationData, SaccadeData) of one stimulus from its rows and image path; the second dataset is derived from the first (fixations -> saccades between consecutive fixations, or saccades -> their end points).

### `creapy.gaze.base`

StimulusGaze: what FixationData and SaccadeData share (subsets, AOIs, smoothing)


#### class `StimulusGaze`

Shared base of FixationData and SaccadeData: one stimulus image plus the gaze events of all participants on it. Takes the event table, the image path, the participant column and a time and a value column (fixation duration or saccade amplitude). Times are brought to seconds (time_unit 's', 'ms' or 'us'; guessed from the magnitudes when None) and, for recording-clock timestamps, counted from each participant's first event (see self.t).


- `StimulusGaze(df_stim, path_to_stim, subj_index_col, t_col, v_col, t_min=0, t_max=None, interpolation_grid=(100, 100), interpolation_step=0.01, sigma=5, trial_col=None, img=None, scale=1.0, time_unit=None)`: Initialize self. See help(type(self)) for accurate signature.
- `.n_subjects()`: Number of distinct participants in the table.
- `.subset_rows(subjects=None, t_range=None)`: Boolean row mask over self.df for a participant selection (any iterable of ids) and/or a time window t_range=(t0, t1) in seconds on the dataset's time axis self.t. Both bounds are inclusive; None means no filter.
- `.plot_setup(ax, include_stimulus=True, bw=False, stimulus_alpha=1.0)`: Draw the stimulus into ax as the background of a gaze plot: image pixel coordinates, y pointing down, no ticks. bw=True shows it in grayscale, include_stimulus=False a black canvas of the same size, stimulus_alpha fades it.
- `.make_v_curve_by_time(ax0, ax1, interpolation_step=0.01, sigma=5, n_std=0.05, t_valid=None, color=None, label=None)`: Plot the value (fixation duration or saccade amplitude) over viewing time into ax1: a Gaussian-smoothed mean (sigma and interpolation_step in seconds) with every participant weighted equally, plus a band of n_std standard deviations when 0 < n_std <= 1. The curve is dashed after t_valid (default: the last 5 s, where few participants still contribute). ax0, if not None, gets the stimulus image via plot_setup.
- `.set_top_down_aoi(name, geom)`: Register a hand-drawn area of interest under `name`: geom is a shapely polygon in image array pixels (y down), e.g. AOI.rectangle(...).geom. An existing AOI of the same name is replaced.
- `.remove_aoi(name)`: Drop the AOI called `name`; unknown names are ignored.
- `.show_all_aoi(ax=None)`: Draw every registered AOI over the stimulus, one tab10 colour each. Without ax a new figure is created and shown with plt.show().
- `.gaussian_smooth_irregular(t_new, t_old, v_old, weights_subj, sigma, chunk_size=512)` *(static)*: Gaussian-kernel smoothing of irregularly sampled values v_old at times t_old onto the grid t_new (sigma in the unit of t). weights_subj weights each sample (e.g. 1/n per participant so every viewer counts equally). Returns (m, s): weighted mean and weighted standard deviation per t_new point, NaN where no sample is in reach.


### `creapy.gaze.fixation`

FixationData: heatmaps, scanpaths, AOIs, descriptives, scanpath similarity


#### class `FixationData`

Fixations of all participants on one stimulus image. Column names come as parameters (fix_x_col, fix_y_col, fix_t_col, fix_dur_col, subj_index_col, optional trial_col/pupil_col); coordinates end up in pixels of the image array with y down (normalized_xy=True for Tobii's 0-1 positions), durations stay in the table's unit (self.dur_unit, 'ms' or 's', detected). Heatmaps weight fixations by duration and every participant equally; results are cached.


- `FixationData(df_stim, path_to_stim, fix_x_col, fix_y_col, fix_t_col, fix_dur_col, subj_index_col, interpolation_grid=(100, 100), bw_method=0.1, num_levels=20, t_min=0, t_max=None, interpolation_step=0.01, sigma=5, trial_col=None, pupil_col=None, img=None, scale=1.0, normalized_xy=False, time_unit=None, **kwargs)`: Initialize self. See help(type(self)) for accurate signature.
- `.subset(subjects=None, t_range=None)`: A new FixationData with only the selected participants (iterable of ids) and/or time window t_range=(t0, t1) in seconds; AOIs are carried over. Cheap: the image is shared and the heatmap recomputed on demand. Asserts that at least one fixation remains.
- `.heatmap_max(bw_method=0.1)`: Peak density of this dataset's heatmap for the given bw_method, i.e. the `vmax` to pass to make_heatmap of OTHER datasets (stimuli, groups, time windows) so that their colours mean the same thing.
- `.prepare_heatmap(bw_method=0.1, num_levels=20, vmax=None)`: Run the expensive part of make_heatmap (KDE and contouring) into the cache without touching matplotlib, so it can be called from a worker thread; make_heatmap with the same bw_method, num_levels and vmax is then instant.
- `.make_heatmap(ax, bw_method=0.1, num_levels=20, from_level=1, cmap='coolwarm', alpha=0.75, scatter_color=(1, 1, 1), scatter_size=1, scatter_alpha=0.5, stimulus_alpha=1.0, grayscale=False, vmax=None)`: Duration-weighted fixation heatmap over the stimulus in ax: a Gaussian KDE (bw_method = scipy's bandwidth factor) cut into num_levels filled contours, levels below from_level left transparent, every participant with equal total weight. vmax (see heatmap_max) puts several heatmaps on one colour scale; without it colours are normalised to this dataset's own peak. Dots mark the fixations, sized by duration; scatter_size=0 hides them.
- `.visualize_scanpath(ax, subjects=None, numbered=True, color=None, alpha=0.8, size=1.0, line_width=1.5, stimulus_alpha=1.0, grayscale=False, max_numbers=150)`: The textbook scanpath in ax: fixation circles sized by duration, connected in viewing order. One participant gets one colour and fixation numbers (only first and last above max_numbers fixations); several participants get one tab10 colour each and no numbers. subjects defaults to all. Returns the list of participants drawn.
- `.set_bottom_up_aoi(bw_method=0.1, num_levels=20, from_level=1)`: Data-driven AOI: the hot spots of the heatmap, i.e. the union of the contour levels from from_level upwards (same bw_method/num_levels as make_heatmap). Registers it under a name like '0.1_1/20' and returns that name.
- `.make_aoi_percentage_curve(ax0, ax1, interpolation_step=0.01, sigma=5, n_std=0.05, color=None, names=None)`: Plot into ax1 how the share of fixation time inside each AOI evolves over viewing time: Gaussian-smoothed (sigma and interpolation_step in seconds), fixations weighted by duration and every participant equally, with a band of n_std standard deviations when 0 < n_std <= 1. One curve per AOI (restrict with `names`), y axis in percent; ax0, if not None, gets the stimulus image. AOIs added or removed since the last call are picked up.
- `.aoi_metrics(names=None)`: The classic AOI table, one row per participant x AOI (all AOIs, or the given `names`). Columns: participant, aoi, n_fixations, n_visits (runs of consecutive fixations inside), revisits, dwell_time (sum of durations, table unit), dwell_share (of the participant's total), mean_fixation_duration, time_to_first_fixation (s, from the participant's first fixation), first_fixation_rank, aoi_area_share. Non-lookers get zeros and NaN latencies.
- `.participant_stats()`: One row per participant with the usual descriptives. Columns: participant, n_fixations, viewing_time_s, mean_fixation_duration, median_fixation_duration, total_fixation_duration (table unit), scanpath_length_px, mean_x, mean_y, spread_px (image array pixels) and mean_pupil when a pupil column was mapped. Sorted in natural participant order.
- `.compute_scanpath_similarity(method='multimatch', verbose=True, progress=None, **kwargs)`: Pairwise scanpath similarity between all participants: method 'multimatch' (five scores), 'scanmatch' or 'cross_recurrence'; extra kwargs go to the respective algorithm. Returns a PairwiseSimilarityResult (matrix, boxplot by group, permutation test, viewer map), cached per method and kwargs. progress(done, total, text) is an optional callback; returning False from it aborts with InterruptedError.
- `.compute_grid_based_fixation_similarity(grid_sizes=(7,), include_self=False)`: Pairwise fixation similarity on an n x n grid over the image, duration-weighted and with equal weight per participant: a dict grid size (cells per side) -> PairwiseSimilarityResult, or just the result when a single grid size is given. include_self=True also includes each participant's comparison with themselves.


### `creapy.gaze.saccade`

SaccadeData: saccade scanpaths, HeatMatch heatmaps and similarity, rose diagrams


#### class `SaccadeData`

Saccades of all participants on one stimulus image, each a line from (x0, y0) to (x1, y1) in pixels of the image array with y down (normalized_xy=True for Tobii's 0-1 positions). Column names come as parameters (sac_*_col, subj_index_col, optional trial_col). angles_360 holds the direction of each saccade in degrees as seen on screen (0 right, 90 up), angles_180 the orientation folded to [0, 180). Orientation fields and similarities are cached.


- `SaccadeData(df_stim, path_to_stim, sac_x0_col, sac_y0_col, sac_x1_col, sac_y1_col, sac_t_col, sac_amp_col, subj_index_col, t_min=0, t_max=None, interpolation_grid=(200, 200), interpolation_step=0.01, sigma=5, trial_col=None, img=None, scale=1.0, normalized_xy=False, time_unit=None, **kwargs)`: Initialize self. See help(type(self)) for accurate signature.
- `.subset(subjects=None, t_range=None)`: A new SaccadeData with only the selected participants (iterable of ids) and/or time window t_range=(t0, t1) in seconds. Orientation fields are recomputed lazily. Asserts that at least one saccade remains.
- `.participant_stats()`: One row per participant. Columns: participant, n_saccades, mean_saccade_amplitude and median_saccade_amplitude (table unit, usually px or degrees), saccade_rate_per_s, horizontal_share (fraction of saccades within 45 degrees of horizontal). Sorted in natural participant order.
- `.visualize_scanpaths(ax, color=(1, 1, 0), alpha=1.0, width=1, ooi=None, stimulus_alpha=1.0, grayscale=False)`: Draw every saccade as an arrow over the stimulus in ax (one quiver call). color is an RGB tuple, width scales the arrow thickness. ooi, an orientation of interest in degrees (0 horizontal, 90 vertical), fades saccades of other orientations: alpha is multiplied by a sigmoid of the angular similarity. Nothing is returned.
- `.make_heatmap(ax, alpha, sigma, cmap='coolwarm', ooi=90, quantile=0.8, degree=2, stimulus_alpha=1, grayscale=False)`: HeatMatch orientation heatmap (Long et al. 2026) over the stimulus in ax. sigma is the kernel width in pixels of the image array; ooi is the orientation painted warm, in degrees as seen on screen (90 = vertical), the cool end of cmap goes to the perpendicular one; alpha is the base opacity, quantile and degree shape how quickly low density fades out. Slow on big datasets; the field is cached per sigma (see prepare_heatmap).
- `.get_circular_weighted_stats(sigma)`: The orientation field behind the saccade heatmap, computed by heatmatch with kernel width sigma in pixels and cached per sigma. Returns three flat arrays over the interpolation grid (reshape with self.xi.shape): mean orientation in degrees [0, 180) in image (y-down) coordinates, 0 where nothing is in reach; coherence R in [0, 1]; density rho (sums to 1).
- `.make_rose_plot(bins=36, title=None, ax=None, rays=True, num=False, hull=True, hull_args=None, cmap='GnBu', center_symmetric=False, subjects=None)`: Rose diagram of saccade directions in `bins` bins over 360 degrees, every participant weighted equally, bar height = share of saccades (sums to 1); rays, num and hull toggle bars, percent labels and outline. ax must be a polar axes when given, otherwise a figure is made and shown. center_symmetric=True folds directions onto orientations. Returns (xx, yy): bin centres in degrees (0 right, 90 up) and the share per bin.
- `.compute_heatmatch_similarity(sigma=50, density_coherence_tradeoff=0.5, verbose=True, progress=None)`: Pairwise HeatMatch similarity (Long et al. 2026) between all participants, self-pairs included. sigma is the kernel width in pixels, density_coherence_tradeoff in [0, 1] weights the directional score by density (1) or coherence (0). Returns a HeatMatchSimilarityResult over s_loc/s_dir, cached per (sigma, tradeoff). progress(done, total, text) is an optional callback; returning False aborts with InterruptedError (GUI cancel).
- `.compute_heatmatch_similarity_profile(window=None, step=None, sigma=50, density_coherence_tradeoff=0.5, min_saccades=3, verbose=True, progress=None)`: Sliding-window HeatMatch similarity: pairwise s_loc/s_dir per time window, i.e. viewer synchrony over time. window and step in seconds (defaults: a third of the viewing time, half a window); participants with fewer than min_saccades saccades in a window are left out of it. Returns a HeatMatchSimilarityProfile with columns t_center, subject_a, subject_b, s_loc, s_dir, cached per parameter set; progress as in compute_heatmatch_similarity.
- `.prepare_heatmap(sigma)`: Compute the orientation field for `sigma` (pixels) into the cache without drawing, callable from a worker thread; make_heatmap with the same sigma is then quick.

- `report_progress(progress, done, total, text)`: Forward (done, total, text) to a progress callback; a callback that returns False asks for an abort, which is raised as InterruptedError. Shared by the long loops below.

### `creapy.gaze.convert`

fixation table <-> saccade table

- `viewing_keys(column_mapping)`: The columns that identify one continuous viewing: [subj_index_col], plus trial_col when the mapping has one.
- `fixations_to_saccades(df_fixation, column_mapping)`: Derive the saccades between consecutive fixations of ONE stimulus: each fixation becomes a saccade from its own position to the next fixation of the same viewing (the last fixation makes none). Returns (df, mapping): df with columns x0, y0, x1, y1, t (fixation onset + duration, i.e. saccade onset in the table's time unit), subj, trial (only with a trial column), amp (straight-line distance in pixels); mapping has the sac_*_col names for SaccadeData.
- `saccades_to_fixations(df_saccade, column_mapping)`: Reconstruct the fixations between consecutive saccades of ONE stimulus: a fixation sits midway between a saccade's end point and the next saccade's start, lasts from this saccade's onset to the next (dur) and is stamped with this saccade's onset (t); the last saccade of a viewing yields none. Returns (df, mapping): df with columns x, y, t, dur, subj, trial (only with a trial column); mapping has the fix_*_col names for FixationData.

### `creapy.aoi.aoi`

AOI geometry (rectangles, polygons, JSON records)


#### class `AOI`

One area of interest: a named shapely geometry in image pixels (x right, y down). Build it with AOI.rectangle(...) or AOI.polygon(...), or from matplotlib Paths drawn in the GUI (paths=...). Several disconnected parts are fine, they become one MultiPolygon.


- `AOI(name='Unnamed', geom=None, paths=None)`: Initialize self. See help(type(self)) for accurate signature.
- `.area()`: Area of the AOI in square pixels.
- `.contains(points)`: True for each point inside or on the boundary of the AOI. points: shapely point(s), e.g. fix.fix_points; returns one bool or a bool array.
- `.rectangle(name, x0, y0, x1, y1)` *(static)*: Rectangular AOI from two opposite corners (x0, y0), (x1, y1) in pixels; the corner order does not matter.
- `.polygon(name, vertices)` *(static)*: Polygon AOI from a list of (x, y) vertices in pixels, at least three. Self-intersections are repaired with buffer(0).
- `.to_record()`: Dict {'name', 'wkt'} describing the AOI as text (WKT), for saving AOI sets to JSON; see from_record.
- `.from_record(record)` *(static)*: Rebuild an AOI from a to_record() dict.
- `.show(ax, color='yellow', alpha=0.4, label=True)`: Draw the AOI on a matplotlib axes as a translucent patch, with its name at the centroid of the largest part (dashed lines connect further parts). label=False draws the patch alone.


### `creapy.aoi.sequence`

AOI sequences: scarf plot, transition matrix, first-fixation order

- `aoi_sequence(fix, names=None, include_outside=True)`: Which AOI each fixation fell into, in viewing order. One row per fixation with columns participant, trial, t (fixation onset in seconds), dur (duration in the dataset's unit), aoi (AOI name or 'outside') and order (1-based rank within participant and trial). names restricts and orders the AOIs; a fixation inside several overlapping AOIs goes to the first one. include_outside=False drops fixations outside every AOI.
- `collapse_runs(df_seq)`: Merge consecutive fixations in the same AOI into one visit. Takes the output of aoi_sequence and returns one row per visit: participant, trial, aoi, t_start, t_end (onset of the first and last fixation, seconds), n_fixations and dwell (summed duration in the dataset's unit).
- `transition_matrix(fix, names=None, include_outside=False, normalize='row', per_participant_weight=True)`: AOI -> AOI transitions between consecutive VISITS (self-transitions excluded, so a run of fixations inside one AOI counts once). normalize: None (counts), 'row' (share of departures from each AOI), 'all' (share of all transitions). per_participant_weight=True weights every participant's transitions to sum to 1, so a viewer with many fixations does not dominate.
- `show_transition_matrix(ax, matrix, cmap='Blues', fmt='{:.0%}', text_color_switch=0.6)`: Draw a transition_matrix() as a heat-table on ax: rows = from, columns = to, each cell annotated with its value (fmt, default percent; NaN cells stay blank). Returns the AxesImage.
- `aoi_palette(names, include_outside=True)`: Dict AOI name -> RGBA colour (tab10 cycle), plus a grey for 'outside' unless include_outside=False.
- `show_scarf_plot(ax, fix, names=None, subjects=None, colors=None, relative_time=True, outside_alpha=0.35, row_height=0.8)`: Scarf plot: one row per participant, viewing time on x, each fixation a bar coloured by the AOI it fell into (grey = outside every AOI). Several trials of one participant are concatenated in time order.
- `first_fixation_order(fix, names=None)`: In which order each participant first visited the AOIs. One row per participant with one column per AOI holding the rank of its first fixation (1 = looked at first); NaN means the AOI was never fixated.

### `creapy.stats.descriptives`

per-participant table, coefficient K, group comparison, group boxplot

- `coefficient_k(fix_dur, next_sac_amp, subj)`: Ambient–focal coefficient K (Krejtz et al. 2016): per fixation, z(duration) - z(amplitude of the following saccade), both standardized over all fixations of the stimulus; K > 0 = focal (long fixations, short saccades), K < 0 = ambient. Returns the per-fixation K and the per-participant mean.
- `next_saccade_amplitude(dataset_fix)`: Amplitude in image pixels of the saccade that follows each fixation, i.e. the distance to the next fixation of the same participant (and trial), aligned with dataset_fix.df; NaN for the last fixation of each viewing.
- `fixation_k(dataset_fix)`: Per-fixation coefficient K (see coefficient_k) aligned with dataset_fix.df, from the fixation table alone.
- `participant_table(dataset_fix, dataset_sac=None)`: One row per participant with the fixation descriptives (n_fixations, mean/median duration, spread ...), the saccade descriptives when dataset_sac is given (n_saccades, mean amplitude, scanpath length ...) and coefficient_K. The table behind the GUI's Statistics view; durations in dataset_fix.dur_unit, distances in px.
- `group_comparison(df_stats, grouping, columns=None)`: Group means per measure plus a two-sample test (Welch t for two groups, one-way ANOVA for more) and a Mann–Whitney U for two groups. grouping: participant -> group name. Participants without a group are left out.
- `show_group_boxplot(df_values, measure, grouping=None, ax=None, group_col='group', jitter=0.12, seed=0, box_color='#c7d3e6', median_color='#1f5fbf', point_color='#333333')`: Boxplot of one measure by group with every participant as a jittered point: the group boxplot of the GUI's Statistics and Recurrence views. df_values has one row per participant (participant_table, participant_rqa, aoi_metrics ...) and either a `group_col` or a `grouping` (participant -> group) that adds one. Participants without a group are left out. Returns the group names in plotting order.

### `creapy.stats.timeseries`

smoothed curves of a measure over viewing time, per group

- `measure_key(name)`: 'fixation_duration' or the GUI label 'Fixation Duration' -> 'fixation_duration'; ValueError otherwise.
- `value_series(fix, sac, measure)`: The raw per-event values of one measure: returns (dataset, values, y label), where dataset is `fix` or `sac` (saccade amplitude lives in the saccade table) and values is a float array aligned with dataset.df. measure: 'fixation_duration', 'saccade_amplitude', 'coefficient_k', 'pupil' or 'viewing_distance'. Raises ValueError when the table has no pupil column / no viewing distance (Tobii glasses Data exports only).
- `smoothed_curve(dataset, values, sigma, step=0.05, weights=None)`: Gaussian-smoothed mean of `values` (aligned with dataset.df) over viewing time: returns (t, mean, std) on a regular grid from the first to the last event, `step` and `sigma` (kernel width) in seconds. Every participant counts equally: the default weights are 1 / number of events of the participant; NaN values are skipped.
- `show_smoothed_curve(ax, dataset, values, sigma, n_std=0.05, color=None, label=None, step=0.05, t_valid=None)`: Draw smoothed_curve(...) on ax: a solid line up to t_valid (default 5 s before the end, after which few participants are still viewing and the mean gets unreliable), dashed after it, and a band of ± n_std standard deviations when 0 < n_std <= 1. Returns (t, mean).
- `show_measure_curve(fix, sac, measure, sigma=2.0, n_std=0.05, ax=None, color=None, label=None, step=0.05)`: One call for a whole Time Series curve: value_series + show_smoothed_curve with axis labels; with ax=None a figure is created and shown. For coefficient K a dotted zero line separates focal (above) from ambient (below). Returns (t, mean).
- `split_by_group(fix, sac, grouping)`: [(group name, fix subset, sac subset)] for the participants of every group, groups in natural order. grouping maps participant -> group name; participants without a group are left out, empty groups dropped; sac may be None. Draw a curve per entry to compare groups on one axes.

### `creapy.stats.recurrence`

recurrence plots and RQA (Anderson et al. 2013), cross-recurrence

- `recurrence_matrix(xy, radius)`: Boolean (n, n) recurrence matrix of a scanpath: True where fixations i and j lie within radius pixels of each other. xy is an (n, 2) array of x, y in pixels; the diagonal is always True.
- `rqa_measures(xy, radius, min_line=2)`: Recurrence quantification analysis of one scanpath after Anderson et al. 2013. xy is an (n, 2) array of fixation positions in pixels, radius in pixels, min_line the shortest run (in fixations) that counts as a line. Returns a dict with n_fixations, recurrence, determinism, laminarity, corm (all in percent) and n_recurrent_pairs. Fewer than two fixations give NaN measures; no recurrent pair gives recurrence 0 and the other measures NaN.
- `default_radius(fix)`: Default recurrence radius for a dataset: 5 % of the stimulus diagonal in pixels (Anderson et al. used 64 px on 1024-px-wide images).
- `participant_rqa(fix, radius=None, min_line=2)`: RQA measures per participant: DataFrame with columns participant, n_fixations, recurrence, determinism, laminarity, corm, n_recurrent_pairs and radius (see rqa_measures). radius in pixels, default default_radius(fix); min_line in fixations. With a trial column each trial is one scanpath and the rows are means over the participant's trials.
- `cross_recurrence(xy_a, xy_b, radius)`: Cross-recurrence of two scanpaths (each an (n, 2) array of x, y in pixels): the share of fixation pairs across the two that lie within radius pixels, a fraction in [0, 1]. Symmetric and order-free; NaN if either path is empty.
- `cross_recurrence_table(fix, radius=None, verbose=True, progress=None)`: Cross-recurrence for every unordered pair of participants, diagonal included: DataFrame with columns subject_a, subject_b, cross_recurrence. radius in pixels (default default_radius(fix)); each participant's trials are concatenated into one scanpath. progress(done, total, text) may return False to cancel.
- `show_recurrence_plot(ax, xy, radius, color='white')`: Draw the recurrence plot of one scanpath on ax: fixation index on both axes, a square for every recurrent pair on a black background, origin lower-left. xy is an (n, 2) array in pixels, radius in pixels. Returns the boolean recurrence matrix.

### `creapy.stats.spectrum`

Lomb–Scargle periodograms and Morlet scalograms

- `lomb_scargle(t, v, freqs)`: Normalised Lomb-Scargle periodogram of an irregularly sampled series: t in seconds, v the values at those times, freqs in Hz. Returns the power at each frequency as the fraction of variance explained (0..1); all NaN with fewer than four valid samples or a constant series.
- `default_frequencies(t_span, n=200)`: Log-spaced grid of n frequencies in Hz from 2 / t_span (two cycles per viewing) up to 2 Hz, for a viewing of t_span seconds (must be longer than 1 s).
- `participant_periodogram(fix, values=None, freqs=None)`: Lomb-Scargle periodogram per participant. values is a per-fixation series aligned with fix.df (default fixation duration), freqs in Hz (default default_frequencies of the median viewing span). Returns a DataFrame indexed by frequency_hz with one normalised-power column per participant; several trials of one participant are averaged.
- `mean_periodogram(df_power)`: Mean normalised power over the participant columns of a participant_periodogram() table, ignoring NaN; a Series named mean_power.
- `dominant_period(df_power)`: Strongest rhythm per participant from a participant_periodogram() table: DataFrame with columns participant, peak_frequency_hz, peak_period_s (seconds per cycle) and peak_power; all NaN when the periodogram is empty.
- `resample_regular(t, v, step=0.05, sigma=0.3, weights=None)`: Put an irregular series (t in seconds, v) onto a regular grid with spacing step seconds by Gaussian smoothing with sigma seconds (default 0.3 s, about one fixation); gaps the kernel cannot bridge are filled linearly. Returns (t_new, v_new). Needed before morlet_scalogram.
- `morlet_scalogram(t_new, v_new, freqs, w0=6.0)`: Wavelet power of a REGULARLY sampled series (from resample_regular) with a complex Morlet wavelet of parameter w0 (Torrence & Compo 1998). freqs in Hz; returns |W|^2 as an array of shape (len(freqs), len(t_new)), ready for show_scalogram.
- `show_periodogram(ax, df_power, freqs_or_index=None, color=None, label=None, individual_alpha=0.15)`: Plot a participant_periodogram() table on ax: one thin curve per participant, the mean in bold, log frequency axis in Hz with the period in seconds on top. freqs_or_index overrides the table's frequency index; label adds a legend entry (one call per group). Returns nothing.
- `show_scalogram(ax, t_new, freqs, power, cmap='magma')`: Time x frequency map of wavelet power on ax (pcolormesh, log frequency axis): t_new in seconds, freqs in Hz, power from morlet_scalogram. Returns the QuadMesh so a colorbar can be added.

### `creapy.similarity.heatmatch_result`

pairwise similarity results: matrix, boxplot, permutation test, viewer map, overview


#### class `PairwiseSimilarityResult`

Pairwise similarity scores between all subjects viewing one stimulus: any measure that yields one number per subject pair (HeatMatch s_loc/s_dir, MultiMatch, ScanMatch, cross-recurrence ...). The matrix, group boxplot, permutation test and viewer map work for every score column.


- `PairwiseSimilarityResult(df_sim, scores=None)`: Initialize self. See help(type(self)) for accurate signature.
- `.default_score()`: The score column used when `which` is not given (s_dir for HeatMatch, the first column otherwise).
- `.matrix(which=None, grouping=None)`: Symmetric participant x participant DataFrame of one score; with a grouping (participant -> group) the rows and columns are ordered group by group, so same-group pairs form blocks along the diagonal.
- `.matshow(which=None, grouping=None, ax=None, cmap='viridis', group_color='black')`: The similarity matrix as an image with a colour bar; with a grouping, group blocks are framed and labelled. Above 40 participants only every tenth name is written. Returns the matrix DataFrame.
- `.show_boxplot(grouping, which=None, ax=None)`: Boxplots of the pairwise scores within each group and between each pair of groups ('A/B'); grouping maps participant -> group. The within-vs-between question is tested by permutation_test.
- `.permutation_test(grouping, which=None, n_permutations=10000, seed=0, verbose=True)`: One-sided permutation test: are participants more similar within their group than between groups? Statistic = mean within-group score - mean between-group score, group labels shuffled under the null. Returns a dict with which, within_mean, between_mean, observed, p_value, n_permutations (cached per call).
- `.score_overview(grouping=None)`: Mean score over all unordered participant pairs, one row per score column: columns 'measure', 'all pairs' and, with a grouping (participant -> group) of two or more groups, 'within groups' and 'between groups'. For MultiMatch this is the five-dimension summary of the GUI's Measure overview.
- `.show_score_overview(grouping=None, ax=None, strip_prefix='mm_')`: Grouped bar chart of score_overview(): one group of bars per score (all pairs / within / between groups), y from 0 to 1. strip_prefix is removed from the tick labels ('mm_vector' -> 'vector'). Returns the table.
- `.show_multidimensional_scaling(grouping=None, which=None, ax=None)`: Viewer map: each participant as a point in two dimensions (spectral embedding of the similarity matrix), coloured by group when a grouping is given. Near points = similar viewing; the axes carry no unit.


#### class `HeatMatchSimilarityResult`

Pairwise HeatMatch similarity scores (Long et al. 2026): s_loc and s_dir (the default).


- `HeatMatchSimilarityResult(df_sim)`: Initialize self. See help(type(self)) for accurate signature.


#### class `HeatMatchSimilarityProfile`

Sliding-window HeatMatch similarity: pairwise scores per time window (viewer synchrony over time).


- `HeatMatchSimilarityProfile(df_profile, window)`: Initialize self. See help(type(self)) for accurate signature.
- `.curves(which='s_dir', grouping=None)`: {label: DataFrame indexed by window centre (s) with columns mean, std}: one curve 'all pairs' without a grouping, otherwise one per group (within) and one per group pair 'A/B' (between).
- `.show_profile(which='s_dir', grouping=None, ax=None, n_std=0.05)`: Similarity over viewing time: the curves of curves() with a band of ± n_std standard deviations. Returns the curves dict.


### `creapy.similarity.scanpath`

MultiMatch, ScanMatch and cross-recurrence between two scanpaths

- `scanmatch(path_a, path_b, width, height, grid=(12, 8), temporal_bin=None, gap=0.0, threshold_share=0.25)`: ScanMatch similarity of two scanpaths (Cristino et al. 2010), a score in [0, 1]. Each path is an (n, 3) array of x, y in pixels and duration in seconds; width, height is the stimulus size in pixels. The image is split into grid=(columns, rows) cells and the cell sequences are aligned with Needleman-Wunsch (gap penalty gap, substitution threshold threshold_share of the largest cell distance). temporal_bin in seconds repeats a cell once per bin of fixation duration so that duration enters the comparison (None = one letter per fixation).
- `multimatch(path_a, path_b, width, height, amplitude_threshold=None, direction_threshold=None, duration_threshold=0.3)`: MultiMatch similarity of two scanpaths (Dewhurst et al. 2012): dict with the five scores vector, direction, length, position and duration, each in [0, 1] (1 = identical). Paths are (n, 3) arrays of x, y in pixels and duration in seconds; width, height in pixels. Scanpaths are first simplified with amplitude_threshold in pixels (default 10 % of the image diagonal), direction_threshold in degrees (default 45) and duration_threshold in seconds. A path with fewer than two fixations gives all NaN.
- `scanpath_of(fix, subj)`: One participant's scanpath as an (n, 3) array of x, y in pixels and duration in seconds, trials concatenated in viewing order.
- `scanpath_similarity_table(fix, method='multimatch', verbose=True, progress=None, **kwargs)`: Pairwise scanpath similarity between all participants of fix, one row per unordered pair incl. the diagonal. method='multimatch' gives columns subject_a, subject_b, mm_vector, mm_direction, mm_length, mm_position, mm_duration; method='scanmatch' gives subject_a, subject_b, scanmatch. Extra kwargs go to multimatch() or scanmatch(). progress(done, total, text) may return False to cancel.

### `creapy.formats.table`

reading CSV/TSV/Excel robustly

- `sniff_delimiter(path, encoding)`: Guess the column separator of a text table from its header line: tab, ';', ',' or '|', whichever occurs most often (csv.Sniffer only when none of them appears, ',' if even that fails). The counting is there because German Excel exports with ';' and decimal commas fool csv.Sniffer.
- `read_table(path, sheet_name=0)`: Read one table (CSV/TSV/TXT with any common delimiter, or Excel with `sheet_name`) into a DataFrame. utf-8 first, latin-1 as fallback; '.', empty cells, 'NA', 'NaN' and 'None' become NaN (EyeLink DataViewer writes '.' for missing values); decimal commas are converted, numeric-looking text columns are coerced to numbers, column names are stripped and all-empty columns dropped.
- `convert_decimal_commas(df)`: Turn '12,5' into 12.5 in text columns where at least 95 % of the non-empty values become numbers after the swap; other columns stay as they are. Modifies df in place and returns it.
- `coerce_numeric(df)`: Make text columns numeric where at least 95 % of the non-empty values parse as numbers; the rest (e.g. EyeLink's '.') become NaN. Modifies df in place and returns it.
- `numeric_columns(df)`: Names of the columns with a numeric dtype.
- `image_like_columns(df)`: Names of the text columns whose values (the first 200 non-empty ones) mostly end in an image extension (png, jpg, bmp, tif, gif, webp) - candidates for the stimulus column.

### `creapy.formats.detect`

format detection and column-mapping guesses

- `detect_format(columns)`: Classify a table by its column names alone: 'eyelink_fixation', 'eyelink_saccade', 'tobii_event_export', 'tobii_data_export', 'tobii_metrics_export' or 'unknown'. Case-insensitive; no cell values are looked at.
- `guess_mapping(df, fields)`: Best-effort column mapping for `fields` (FIXATION_FIELDS or SACCADE_FIELDS): a dict field key -> column name, None for optional fields without a match. Hints are tried in priority order, numeric fields only take numeric columns, the stimulus prefers image-like columns, required fields fall back to the first unused column. For EyeLink tables whose times exceed 60 the key 'time_unit' = 'ms' is added.
- `validate_mapping(df, mapping, fields)`: Human-readable problems with a mapping as a list of strings (required field unassigned, column missing from df, numeric field with no or mostly non-numeric values, one column used for two required fields); an empty list means the mapping is usable.

### `creapy.formats.tobii`

Tobii Pro Lab exports (Data, event-based metrics, AOI-based metrics)

- `strip_units(name)`: Column name without the unit suffix newer Pro Lab versions append ('Recording timestamp [ms]' -> 'Recording timestamp').
- `timestamp_unit(columns)`: 'ms' or 'us' from the unit suffix of the 'Recording timestamp' column; None when the header carries no unit (the loader then decides from the values).
- `is_prolab_data_export(columns)`: True if the columns look like a Pro Lab Data export (one row per gaze sample): 'Recording timestamp' and 'Eye movement type' present, unit suffixes ignored.
- `is_prolab_event_export(columns)`: True if all columns of the event-based metrics export are present (Participant, Media, Event_type, Start, Duration, FixationPointX, FixationPointY).
- `is_prolab_metrics_export(columns)`: True for an AOI-based metrics export: an 'AOI' column plus 'Total_duration_of_...' / 'Number_of_...' columns, and not an event-based export.
- `load_prolab_export(path_or_df)`: Load a Tobii Pro Lab export (file path or already-read DataFrame), picking load_prolab_event_export or load_prolab_data_export by the columns; returns (df_fixations, mapping). AOI-based metrics exports and tables that are no Pro Lab export raise a ValueError saying what is expected.
- `load_prolab_event_export(path_or_df)`: Event-based metrics export -> one row per fixation: participant, stimulus (= Media / snapshot name), trial (= TOI interval, times restart at each interval), t (ms from the interval start), dur (ms), x, y NORMALISED 0–1 on the medium (the mapping carries normalized_xy=True; FixationData multiplies by the image size), pupil, validity, aoi_hit (Pro Lab's own AOI), condition.
- `load_prolab_data_export(path_or_df)`: Pro Lab Data export -> one row per fixation with the columns participant, stimulus, t (ms), dur (ms), x, y (pixels of the presented medium or snapshot), recording, condition (if present), snapshot_mapped (bool). Returns (df_fixations, mapping) ready for FixationData / the GUI. Screen-based recordings: Fixation point X/Y on the "Presented Media name". Glasses recordings mapped onto snapshots: Mapped fixation X/Y [snapshot]: one fixation table per snapshot, the snapshot name becomes the stimulus (match it to the snapshot image files by name). The scene-camera "Fixation point X/Y" of glasses recordings is NOT a stimulus position and is ignored.
- `collapse_samples(df_samples, keys)`: Collapse gaze samples to one row per fixation, grouped by `keys` (e.g. recording, stimulus, event_index): participant, t (first sample), dur (reported event duration, or the sample span where it is missing), x, y (means), snapshot_mapped, plus pupil and distance_mm means where present. Rows without event_index are dropped.
- `data_export_columns_needed(header)`: The subset of a Data-export header worth reading: the base columns in DATA_EXPORT_BASE_COLUMNS (unit suffixes ignored) plus the per-snapshot 'Mapped ... [snapshot]' and 'Width/Height [snapshot]' columns.
- `load_prolab_data_export_chunked(path, chunksize=250000, progress=None)`: Same result as load_prolab_data_export(path) for huge TSV exports, reading only the needed columns in chunks of `chunksize` rows. A fixation whose samples straddle a chunk boundary is collapsed twice and merged at the end (the Pro Lab fixation point is constant across the samples, so the merge is exact). progress(done_bytes, total_bytes, text) may return False to abort.
- `load_prolab_aoi_metrics_export(path_or_df)`: AOI-based metrics export -> (df, info). df keeps the identifying columns plus every metric column that has a label in AOI_METRIC_LABELS (counts and totals are 0 where Pro Lab left the cell empty: the participant did not look there; latencies stay NaN). info: {'metrics': [column names], 'labels': {column: label}, 'group_columns': [AOI, Media, Condition, ... with 2+ values]}.
- `aoi_metrics_summary(df_aoi, metric, by='AOI', group_col=None)`: Summarise one metric column of the table from load_prolab_aoi_metrics_export over participants: one row per value of `by` (and of `group_col`, e.g. Condition or Media) with the columns mean, sd, median, n and share_looked (fraction of rows with a value > 0, NaN counted as 0).

### `creapy.misc.utils`

natural sorting, image loading, time units, finding stimulus images

- `natural_key(value)`: Sort key that orders embedded numbers numerically ('vp2' before 'vp11'); letters compare lower-case.
- `natural_sorted(values)`: sorted() with natural_key, so 'vp2' comes before 'vp11'.
- `load_stimulus_image(path, max_side=2400)`: Any image Pillow can open -> (uint8 RGB array, scale). Grayscale, palette, CMYK, 16-bit and RGBA all land here (matplotlib's imread returns 2-D arrays for grayscale PNGs and floats for PNGs, which broke `h, w, _ = shape`). Images longer than max_side are downscaled; `scale` (<= 1) is what the ORIGINAL pixel coordinates have to be multiplied by to land on the returned array. JPEGs use Pillow's draft mode, so an 8192 x 5464 snapshot decodes in a fraction of a second instead of ~130 MB of RAM.
- `seconds_from_table_time(t)`: Convert a time column to seconds and report the unit it came in: values above 600,000 are taken as µs ('us'), above 600 as ms, otherwise seconds. Returns (t_in_seconds, unit). Assumes no trial lasts longer than 10 minutes.
- `find_images(folder, max_depth=3)`: Dict lower-case file name AND lower-case stem -> full path for every image (png, jpg, bmp, tif, gif, webp) under `folder`, descending at most max_depth subfolder levels and skipping hidden folders. A name found twice keeps the shallower hit. Tobii snapshot names therefore match with or without extension.

### `creapy.misc.contours`

figure-free contour paths for heatmaps

- `contour_levels(zmin, zmax, num_levels)`: The level boundaries matplotlib would pick for contourf(..., levels=num_levels): MaxNLocator ticks trimmed to the data range. Returns a 1-D array of increasing values.
- `filled_contour_paths(xx, yy, zz, levels)`: Filled-contour polygons without a figure: one matplotlib Path per interval [levels[i], levels[i+1]] (an empty Path where nothing falls into the interval), like QuadContourSet.get_paths(). xx, yy, zz are the grid arrays, levels an increasing sequence of at least two values. Safe to call from a worker thread.

### `creapy.examples`

the synthetic example dataset

- `example_folder()`: Folder holding the example files: the copy shipped with the package, or, when that copy is incomplete, ~/.creapy/example, where they are generated. Nothing is written into the installed package.
- `example_dataset()`: Path of the example fixation CSV (demo_fixations.csv); pictures and table are generated on first call.
- `draw_picture_a(path)`: Paint synthetic picture A (a figure left of centre, a small bright object top right, a horizon line) at 1600 x 1200 px and save it to `path`.
- `draw_picture_b(path)`: Paint synthetic picture B (two figures facing each other, a diagonal, scattered detail) at 1600 x 1200 px and save it to `path`.
- `simulate_viewer(rng, attractors, weights, n_fix, focal, t_total=30.0)`: Simulate one viewer on one picture: a list of dicts with t_start (ms), dur (ms), x, y (px) and pupil, up to n_fix fixations or t_total seconds. `attractors` are (x, y, spread) tuples drawn with `weights`; the first three fixations stay central; focal viewers fixate longer.
- `make_example(folder)`: Write the whole example into `folder`: demo_picture_A.png, demo_picture_B.png, demo_fixations.csv and a README.md. Returns the fixation DataFrame with the columns participant, group, age, trial, image, t_start (ms), dur (ms), x, y (px), pupil.
