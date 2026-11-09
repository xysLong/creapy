# Changelog

## 0.1.1 (2026-11)

- Scanpath Comparison, Recurrence and the periodogram and scalogram displays of Time Series are advanced analyses,
  hidden until switched on under Analysis > Show Advanced Analyses (remembered between sessions).
- Desktop apps are built on the macos-15 runner.

## 0.1.0 (2026-11)

First public release: the `creapy` library and the `creapy.io` desktop app.

Input
- Fixation and saccade tables (CSV, TSV, Excel) from any eye tracker, with a column-mapping dialog, format
  detection for EyeLink DataViewer reports, delimiter and decimal-comma sniffing, time and duration unit detection.
- Tobii Pro Lab exports: Data export (screen-based, or glasses recordings mapped onto snapshots), event-based
  metrics export, AOI-based metrics export (table window with bar charts). Large Data exports are read in chunks.
- Stimulus images are found by name in a folder (subfolders included); very large images are downscaled on load.

Views
- Fixation Heatmap, Fixation Scanpath, Saccade Scanpath, Saccade Heatmap (HeatMatch orientation coding),
  Saccade Directions, Areas of Interest (drawn on the canvas; metrics, scarf plot, transition matrix,
  first-fixation order), Time Series (fixation duration, saccade amplitude, coefficient K, pupil size, viewing
  distance, AOI share; periodogram and scalogram), Saccade Similarity (HeatMatch), Scanpath Comparison
  (MultiMatch, ScanMatch, cross-recurrence), Recurrence (RQA), Statistics (descriptives, group tests, export).
- Filter bar (participant, group, time window) for every view, groups with permutation tests, projects,
  undo and redo, Compare Side by Side, Export This View for All Stimuli, PNG/PDF/SVG and CSV/XLSX export.
- Every view runs in a worker thread with progress and cancel; tooltips, per-view explanations and a Quick Guide;
  an opt-in session log; a synthetic example dataset.

Library
- `load_fixations`, `load_saccades`, `datasets_by_stimulus`; `FixationData` and `SaccadeData` with subsets,
  heatmaps, scanpaths, AOIs, similarity results; `creapy.stats` (descriptives, time series, recurrence, spectrum),
  `creapy.similarity`, `creapy.aoi`, `creapy.formats`. Every public callable has a docstring; the reference is
  `docs/LIBRARY.md`, the tutorial `tutorial.ipynb`.
- Saccade orientation fields and HeatMatch similarity come from the `heatmatch` package.

Packaging
- `pip install creapy` for the library, `pip install "creapy[gui]"` adds the app (`creapy-io`).
- Double-click bundles for macOS and Windows built with PyInstaller (`packaging/`), self-tested on build.
