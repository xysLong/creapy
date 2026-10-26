# Changelog

## Unreleased

Packaging for PyPI
- `pyproject.toml`: SPDX license expression (`license = "MIT"`, `license-files`) instead of the deprecated table and
  classifier; `setuptools>=77`. The wheel passes `twine check` and installs without Qt (`pip install creapy`).
- README: install instructions as they read on PyPI; links to `docs/` and screenshots are absolute so they render
  outside the repository.
- `creapy.examples`: the shipped example files are read in place and never regenerated inside the installed package;
  when they are missing they are generated into `~/.creapy/example`.
- The hard-coded development table in `creapy/io/main.py` is gone; set `CREAPY_DEV_TABLE=<fixation table>` to open
  a file at start and print tracebacks.

## 0.3.0 (2026-10-24): performance, user experience, analysis options

Performance
- Every view is split into a numeric *prepare* step and a *draw* step (`creapy/io/views.py`). The prepare step
  runs in a worker thread (`creapy/io/worker.py`): the window stays responsive, the pill over the canvas shows
  progress and has a **Cancel** button (HeatMatch similarity, scanpath comparison and the shared colour scale
  report progress and stop at the next check). Tests and the self-test run synchronously.
- Fixation heatmaps are contoured with `contourpy` directly (identical polygons to `contourf`, no figure, thread-safe).
- Dataset constructors no longer compute the default KDE and curves eagerly; subsets (participant, group, time
  window) are cheap, and group subsets are cached by the GUI. On a museum-room export (157 participants, 23k
  fixations on one wall): Time Series 24 s → 2 s, scarf plot 14 s → 0.3 s, import 25 s → 10 s.
- Scarf plot drawn as one collection; similarity matrices and scarf plots stay readable with 150+ participants.
- Tobii Data exports above 1.5 GB are read in chunks with only the ~20 needed columns
  (`load_prolab_data_export_chunked`; verified identical to the whole-file path on 400k real rows, 3× faster), with
  a cancellable progress dialog.

Explanations (for users who do not know the jargon)
- Every control of every view has a **tooltip** that says what changing it does to the picture (hover the slider,
  its title or the combo box); the view list and the Show bar too. All texts live in `creapy/io/glossary.py`.
- An **ⓘ button** above the parameter panel (also `Help > About This View`, Shift+F1) opens a dock panel with one
  page per view (what it shows, how to read it, the parameters, a reference) that stays open and follows the
  view. Openings are logged (`explainer`). The same pages are appended to `Help > The Analyses Explained`.
- Charts whose axes carry jargon (s_loc, MultiMatch scores, REC/DET/LAM/CORM, periodogram, K ...) get a one-line
  **caption** under the canvas, also written into saved figures. Image views (heatmaps, scanpaths, AOI image) stay
  untouched.

Library (the DHd 2026 promise: the app for non-programmers, the library for everyone who wants more)
- **Every public class, method and function has a docstring** (121 callables; a test fails when one is missing),
  so `help()` and Jupyter's `?` explain parameters, units and return values. `docs/LIBRARY.md`: design rules,
  quickstart, a table mapping every app view to its library calls, and the API reference generated from the
  docstrings by `docs/make_library_reference.py`.
- **Parity**: the computations that lived only in the GUI are now library functions and the GUI calls them:
  `creapy/stats/timeseries.py` (`value_series`, `smoothed_curve`, `show_smoothed_curve`, `show_measure_curve`,
  `split_by_group`: the Time Series view), `fixation_k` / `next_saccade_amplitude` and `show_group_boxplot`
  (descriptives; the Statistics and Recurrence boxplots), `PairwiseSimilarityResult.score_overview` /
  `show_score_overview` (the MultiMatch measure overview). `views.py` holds no analysis code of its own.
- `datasets_by_stimulus(df, mapping, "image_folder/")` finds the stimulus images itself (names or stems,
  case-insensitive) instead of requiring a dict. The example dataset falls back to `~/.creapy/example` when the
  package is read-only and PySide6 is not installed, so a `pip install creapy` without `[gui]` works end to end
  (tested: wheel built, installed into a fresh venv without Qt, quickstart run).
- Grid similarity: `include_self` keyword (compare every participant with themselves too) on
  `compute_grid_based_fixation_similarity` and the `FixationGrid` methods.

User experience
- **Projects** (`File > Save / Open Project`, recent list): table path, image folder, column mapping, groups, AOIs
  and the current view are remembered; no gaze data in the file.
- **Undo / Redo** (Ctrl+Z / Ctrl+Shift+Z) for AOI edits and group assignments.
- **Compare Side by Side** (`Analysis`): the current image view once per group, per stimulus or per time window
  in one figure with identical settings: also the multi-stimulus overview.
- **Export This View for All Stimuli** (`File`): the current view and parameters for every stimulus into a
  folder (PNG, plus CSV for table views), with progress and cancel.
- **Same colour scale** checkbox on the fixation heatmap (off by default, logged):
  one density scale across stimuli, groups and time windows; densities above it saturate.
- Tobii **AOI-based metrics exports** open as a table window with bar charts per AOI (mean ± SD, split by Media /
  Condition, lookers only, export) instead of being refused.
- Help: new page *The Analyses Explained*; Quick Guide and Formats updated; start screen gets *Open a project*.
- Two-page hand-out `docs/QUICKSTART.md` / `.pdf`, library tutorial `tutorial.ipynb`, screenshots in `docs/screenshots/`.

Analysis options
- **Areas of Interest**: scarf plot (participants × time coloured by AOI), visit-based transition matrix,
  first-fixation order table; `n_visits` / `revisits` in the metrics table.
- **Scanpath Comparison** view: MultiMatch (Dewhurst et al. 2012; five dimensions), ScanMatch (Cristino et al.
  2010; grid, temporal binning) and cross-recurrence (Anderson et al. 2013) between all participants, with the
  matrix / group boxplot + permutation test / viewer map displays of the HeatMatch view and a five-dimension
  overview. `PairwiseSimilarityResult` generalises the HeatMatch result to any score.
- **Recurrence** view: recurrence plot of one participant, RQA table (recurrence, determinism, laminarity, CORM),
  boxplot by group.
- **Time Series**: viewing distance (Tobii glasses Data export, from the 3D gaze point), periodogram
  (Lomb–Scargle per participant + mean, period axis) and scalogram (Morlet wavelets) for rhythms.
- Library: `creapy.stats.recurrence`, `creapy.stats.spectrum`, `creapy.similarity.scanpath`, `creapy.aoi.sequence`,
  `FixationData.compute_scanpath_similarity`, `heatmap_max` / `vmax`, `prepare_heatmap`;
  `load_prolab_aoi_metrics_export`, `aoi_metrics_summary`; pupil and `distance_mm` per fixation from Data exports.
- 65 tests.

## 0.2.1 (2026-10-24): tested against real Tobii Pro Lab glasses exports

- **Tobii Pro Lab event-based metrics export** (the file the lab shares, one row per fixation/saccade/glance)
  is now a first-class input: `creapy.formats.tobii.load_prolab_event_export` keeps the fixation rows, uses
  `Media` as the stimulus, scales the normalised `FixationPointX/Y` to the snapshot image, treats each TOI
  interval as a trial (times restart per interval), carries pupil, validity and the Pro Lab AOI hit.
  Verified on `Raum 1 c1 Metrics_Event-based.tsv` (157 participants, 8 snapshots): coordinates identical to
  the Data export's mapped pixels, AOI hits land on the painted AOIs.
- Data-export loader: ignores the glasses scene-camera `Fixation point X/Y` (only snapshot-mapped fixations
  are stimuli), uses `Eye movement event duration` when `Gaze event duration` is absent, records snapshot
  sizes; verified on the first 200k rows of the 70 GB `Raum 1 Data export.tsv`.
- Loaders write times in ms (same unit as durations) and declare `time_unit` in the mapping; EyeLink reports
  are declared ms too, so a short recording can no longer be misread as seconds.
- 8k-pixel snapshot JPEGs are downscaled on loading (JPEG draft mode, long side 2400 px) and the
  coordinates with them; participant/time subsets no longer re-apply the factor (bug found on real data).
- Stimulus folder search is recursive and matches names with or without extension (WOQ keeps snapshots in
  `Wandansichten/Raum N` and `Werkansichten/Raum N`).
- Similarity on more than 60 participants asks before computing (12,000 pairs take minutes).
- Tests: synthetic event export, scene-camera rows, downscale/subset regression, and a real-share module
  (`tests/test_woq_share.py`, skipped when the share is not mounted). 28 tests.

## 0.2.0 (2026-10-24): packaging, import, data handling, new views

Packaging and structure
- `pyproject.toml` with real dependencies (HeatMatch from PyPI); `pip install -e ".[gui]"` is a complete install.
- GUI moved from `app/` to `creapy/io/`; `creapy-io` console command and `python -m creapy.io`; assets resolved
  relative to the package, so the app starts from any working directory.
- Public library API in `creapy/__init__.py` (`load_fixations`, `load_saccades`, `datasets_by_stimulus`, ...).
- Test suite (`tests/`, pytest): formats, conversions, datasets, offscreen GUI.

Import
- Robust table reader: `,` `;` tab, decimal commas, Excel, EyeLink `.` missing values, numeric coercion.
- Format detection (EyeLink fixation/saccade report, Tobii Pro Lab data/metrics export) with better column guesses.
- **Tobii Pro Lab Data export loader** (`creapy.formats.tobii`): screen-based (Fixation point X/Y on the presented
  medium) and glasses recordings mapped onto snapshots (one stimulus per snapshot); unit suffixes, ms/µs timestamps,
  decimal commas handled; metrics exports refused with an explanation.
- Column-mapping dialog with optional fields (trial, pupil), table preview, validation.
- Stimulus files matched with or without extension (snapshot names).

Data handling
- Rows sorted by time within participant (and trial) instead of asserting sorted input; missing coordinates dropped
  and counted; grayscale/palette/CMYK images load; time units s/ms/µs and duration units detected.
- Vectorized fixation ⇄ saccade conversion (hundreds of times faster), trial-aware.
- `subset(subjects, t_range)` on both dataset classes; natural participant ordering (vp1, vp2, vp11).

New analyses and views
- Fixation Scanpath (numbered circles), Saccade Directions (rose diagram), Areas of Interest (draw rectangles /
  polygons on the canvas, metrics table, JSON save/load, data-driven hot-spot AOI), Statistics (per-participant
  descriptives incl. scanpath length and coefficient K, group comparison with Welch t / Mann–Whitney / ANOVA,
  AOI metrics, boxplot by group).
- Time Series: ambient–focal coefficient K, pupil size, share of fixations in AOIs, one curve per group.
- Filter bar: participant / group / time window applied to every view.
- Menus, status bar, Quick Guide, Supported Data Formats, About; figure export as PNG/PDF/SVG; table export CSV/XLSX.
- Opt-in session log with parameter values (`creapy/io/session_log.py`), visible indicator, off by default.
- Every view guarded: no traceback reaches the user; user guidance appears as information, not as failure.

Removed
- `setup.py`, the legacy `visualize_orientation_field` leftover, the deprecated `matplotlib.cm.get_cmap` calls.
