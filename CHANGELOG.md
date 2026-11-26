# Changelog

## Unreleased

- Zoom: the mouse wheel or a trackpad pinch zooms the figure at the pointer (up to 20 times), a drag or a two-finger
  scroll on the trackpad moves around, a double-click shows the whole figure; the same through + and − in the
  figure's corner and View > Zoom In / Zoom Out / Show Whole Figure (Ctrl+Plus, Ctrl+Minus, Ctrl+0). The zoom stays
  while the parameters of the same view and stimulus change and resets with another view or stimulus. Polar plots
  and colour bars are not zoomed; drawing an area keeps its clicks (the wheel still zooms). Save as Image saves the
  visible part.

Fixes
- Opening a lab dataset showed the Visits table instead of the selected view: a setting change in a panel that is
  not on screen no longer triggers a render.
- Opening a project renders the selected view once, after the areas, the clock and the participant table are in
  place, instead of once halfway and once at the end.

## 0.2.1 (2026-11-24)

Session log
- The app keeps a session log by default (Logging menu, status bar indicator): views and the time spent in each,
  parameters, filters, areas, clicks, hovers, key presses, wheel steps, dialogs with their answers, file dialogs
  (file names only), exports, errors and the program versions, one JSON line per event in a text file on the user's
  computer. Logging > Save Logs for a Bug Report packs the files into one zip archive. The log holds no gaze data.

Fixes
- Visits with the unit Areas gives every area the roster of the stimuli that carry it (zero rows for the participants
  of that condition only) and lists ticked areas nobody fixated.
- A participant with a single fixation on a stimulus (hence no saccade) can be selected in the Show bar; the
  saccade views explain instead of resetting the filter, the fixation views work.
- A minimum fixation duration that leaves a stimulus empty shows a notice instead of the previous stimulus's data.
- Identifier columns of Tobii exports (Participant, Media, AOI, Ungrouped and the like) are read as text, so an
  area named by a number keeps its name and a fixation inside two numbered areas ("2497,2501") is not turned into
  one decimal number.
- Export This View for All Stimuli names its files after the view and the display, so two displays of one view
  exported into the same folder no longer overwrite each other.
- Compare Side by Side over stimuli is stored with relative paths and survives a moved or renamed bundle folder.

## 0.2.0 (2026-11-23)

Look and feel
- One typeface for the whole app: Lato (bundled, SIL Open Font License, see `creapy/io/style/fonts/OFL.txt`), with
  a single application stylesheet (`creapy/io/theme.py`) shared by every window and dialog: neutral buttons, one
  accent, drawn combo arrows and check marks, slim scroll bars, styled table headers, menus and tooltips.
- Start screen rebuilt as a centred page: Open a bundle / Open a project, the last bundle's projects as tiles,
  recent projects (without those of the bundle) as tiles with their folder, import cards on a second page.
- A bundle is one file: Open a bundle takes a `.creapy` file (a zip archive of ready-made projects), unpacks it once
  into creapy's local data folder (reused while the file is unchanged; a damaged file gives a message and leaves nothing behind) and opens the single project directly or lists the rooms.

Fixes and packaging
- Text columns are recognised under pandas 3 as well (decimal commas in Tobii exports were no longer converted and
  every fixation row was dropped); pandas is pinned below 3 for this release.
- The stylesheet survives an installation path with non-ASCII characters (icon urls are quoted).
- The desktop app keeps matplotlib's font cache between starts (about 15 s faster start-up).
- The self-test also imports a small mobile export with decimal commas, attaches its recording clock and renders
  every mobile view, and fails on a stylesheet parse error.
- Statistics greys its group displays while no groups are assigned.
- Zero rows respect the selection: a participant or group chosen in the Show bar, and each panel of Compare Side by
  Side, only list their own participants (a group comparison over panels no longer pairs everyone with everyone).
- The condition read off the snapshot or participant names keeps deciding the zero rows after other groups are
  assigned.
- Area sizes from the AOI-based export are kept per stimulus (the same area name on several snapshots no longer
  takes the largest size everywhere); an untagged area is still listed.
- Area comparisons over the same participants stay paired when a measure is missing for some of them.
- Save as Image, Export Table and Save AOIs report a file that could not be written; any other unexpected error
  shows a message instead of failing silently.
- A project first saved from inside an unpacked bundle is offered in the user's own folder, so a new download of the
  bundle cannot discard it.
- Compare Side by Side skips a group without eye movements on the stimulus instead of showing nothing, and the
  tables over all stimuli are no longer repeated once per panel; their note no longer claims a time window.
- The Visits title spells "stimuli".

Mobile eye tracking
- Recording setting (lab / mobile), inferred from Tobii exports, switchable under Analysis > Recording Setting:
  scanpaths and saccades break between visits and at pauses, the time filter means the first seconds of each visit,
  views that assume a fixed viewing time are greyed out with the reason, Statistics counts visits.
- Areas from the export: the AOI hits a Tobii Pro Lab event-based export carries per fixation (and their tags) become
  areas of interest without drawing, on one or on every stimulus; once the recording clock is attached, the areas the
  AOI-based export lists for a stimulus but nobody fixated are created too (`aoi_names_by_stimulus`), so they appear
  as zero rows; a fixation that the export places in several
  overlapping areas counts for each; the export's AOI sizes feed the area share.
- Recording clock: Analysis > Add Recording Clock loads the AOI-based metrics export of the same project and places
  every visit on the recording clock (the event-based export restarts its times per interval).
- New view Visits (mobile only): timeline of all visits per participant, visit and episode tables (consecutive visits
  joined up to a chosen pause), totals per participant and stimulus with zero rows for non-viewers, session summary
  (span, mapped and unmapped time, logged events), stimulus sequence.
- Areas of Interest: Sequences table (runs of areas per participant and visit, first area, switches, dwell per area,
  with a minimum run length and a bridgeable gap) and the mean within-area saccade length in the metrics table.
- Visits can count the visits of areas instead of snapshots (a visit is a run of fixations inside a ticked area, on
  any snapshot), so returns to a painting after another painting are counted wherever the paintings hang; a summary
  per stimulus (how many looked, median dwell, returns, how often it was the longest looked) and, in the totals, each
  participant's share and rank.
- The displays that need the recording clock are greyed out with the reason until the clock is added.

General
- Analysis > Import Participant Table joins a per-participant CSV/Excel table (survey, condition, codes) on the
  participant name: appended to every exported table and offered as prefill for the groups.
- Analysis > Minimum Fixation Duration drops short fixations before anything is computed.
- Analysis > Keep Non-Viewers as Zero Rows (on by default): the participant, AOI and totals tables list every
  participant of the dataset, with zeros and looked = False for those without a fixation on the stimulus.
- Export This View for All Stimuli also writes one combined table over all stimuli.
- Areas of Interest: the areas have a tick that decides whether the tables, sequences and transitions use them (the
  rest stays faint on the image), a reference area for the dwell shares (a detail as a share of its painting), dwell
  per area share, a hit column, directional transition counts per participant (label>painting apart from
  painting>label), an area-against-area comparison with paired tests, and looks outside the areas as an optional
  station of the transitions. Displays that need one or two areas are greyed out with the reason.
- Statistics: the group comparison reports n, mean, SD and median per group with the fitting test and effect size
  (Welch t and Mann-Whitney with Cohen's d, rank-biserial r and a 95 % CI; paired t and Wilcoxon when both groups
  hold the same participants; ANOVA and Kruskal-Wallis for more groups). Compare Side by Side now applies to the
  Statistics tables: the stimuli, groups or time windows become the groups of the test. Three new tables run over
  every stimulus of the dataset: participants with shares and ranks, areas, and a summary per stimulus.
- Zero rows follow the condition: when every viewer of a stimulus belongs to one group (assigned, or read off the
  snapshot or participant names), only that group's participants get zero rows on it.
- The group prefill offers the condition read off the snapshot names (c1_..., c2_...) and off the participant names.
- Curves of Time Series that the imported table cannot feed (pupil size, viewing distance) are greyed out with the
  reason instead of failing.
- Faster area tables (the per-area statistics and the run detection are vectorised; areas and their fixations are cached).
- Areas named by bare numbers keep their names when the table reader turns the column into
  numbers; the group prefill looks at every stimulus of the dataset, so a condition column with one value per
  stimulus is offered.
- File dialogs remember one folder per kind; the start screen lists the last projects.
- Start screen in two steps: the front page opens a bundle (ready-made projects, listed as one click
  per project) or a project and shows the last bundle and the recent projects; the import cards for own data sit behind
  "Import your own data". A single project in a bundle opens directly.
- Portable projects: files inside the project's folder are stored with relative paths, and a file that moved is
  searched by name below the project folder, so a bundle folder can be copied or renamed without the image dialog.

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
