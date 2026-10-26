# creapy.io - quick start

*Two pages. Open the app, load data, make a figure, export it. Everything else is in the app: hover any control for what it does, click the ⓘ above the parameter panel for what the view shows, and see Help → Quick Guide and Help → The Analyses Explained.*

## 1. Start

Double-click **creapy.io** (installation: `INSTALL_APP.md`). The start screen offers three ways in:

- **Import Fixation Table**: an EyeLink DataViewer *fixation report* (CSV or Excel, one row per fixation).
- **Import Tobii Pro Lab Export**: the `…Metrics_Event-based.tsv` file of your recording (one row per fixation).
  An *AOI-based* metrics export opens as a table with charts per area instead.
- **Open the example dataset**: twelve invented viewers on two drawn pictures. Try every view here first.

Confirm the **column mapping** (pre-filled; check the preview), then point creapy at the **folder with the
images** (Tobii: the snapshot folder; subfolders are searched, names match with or without extension).

## 2. The window

| Left | Middle | Top of the canvas | Right |
|---|---|---|---|
| the **views** | the figure or table | **thumbnails** = stimuli; **Show** bar = participant / group / time window | the **parameters** of the current view |

Parameters stay the same when you switch stimuli, so pictures remain comparable. Long computations run in the
background: the pill over the canvas has a **Cancel** button and the window stays usable.

## 3. The views in one line each

- **Fixation Heatmap**: where people looked, weighted by fixation duration. The *smoothing bandwidth* changes the
  picture more than anything else: try several values. *Same colour scale* makes several heatmaps comparable.
- **Fixation Scanpath**: one viewer's sequence (circles sized by duration, numbered). Pick a participant in *Show*.
- **Saccade Scanpath / Heatmap / Directions**: the eye movements as arrows, an orientation heatmap (HeatMatch), a
  rose diagram of directions.
- **Areas of Interest**: draw rectangles or polygons on the image; read dwell time, fixations, visits and
  time to first fixation per participant; scarf plot (who looked where, when) and transition matrix.
- **Time Series**: fixation duration, saccade amplitude, coefficient K (focal vs. ambient), pupil size or viewing
  distance over the viewing time; one curve per group; periodogram / scalogram for rhythms.
- **Saccade Similarity · Scanpath Comparison**: how alike two viewers are (HeatMatch; MultiMatch, ScanMatch,
  cross-recurrence): matrix, group boxplot with a permutation test, viewer map.
- **Recurrence**: how much a viewer returns to the same spots (recurrence plot, RQA table).
- **Statistics**: one row per participant; group comparison (t-test / ANOVA); boxplots; export CSV/Excel.

## 4. Groups and comparisons

**Analysis → Assign Participants to Groups** (or prefill from a column of your table). Groups then appear in the
*Show* bar, as separate curves, as boxplots, and in the similarity views. **Analysis → Compare Side by Side**
draws the current view once per group, per stimulus or per time window with identical settings.

## 5. Save your work

- **Save as Image** (PNG / PDF / SVG) and **Export Table** (CSV / Excel) are on every panel.
- **File → Export This View for All Stimuli** writes the current view once per picture into a folder.
- **File → Save Project** remembers the table, the images, the groups and the areas of interest; *Open Project*
  resumes later. **Ctrl+Z** undoes AOI edits and group assignments.

## 6. Before you write it up

1. Report the number of participants, the viewing time and **every parameter** a figure depends on (bandwidth,
   colour map, time window).
2. A heatmap is a picture of *these* viewers under *this* setting: not a property of the painting. Look at the
   first 3 seconds and the whole viewing separately; look at two bandwidths.
3. A difference between groups needs a test (Statistics) and an effect size, not two heatmaps.
4. Everything stays on your laptop. Switch on *Logging → Record session log* only if asked to for an evaluation.

*Support: Xingyu Long, xingyu.long@univie.ac.at. Send a screenshot and the file name when something goes wrong.*
