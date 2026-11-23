# creapy.io - quick start

*Two pages. Open the app, load data, make a figure, export it. Everything else is in the app: hover any control for what it does, click the ⓘ above the parameter panel for what the view shows, and see Help → Quick Guide and Help → The Analyses Explained.*

## 1. Start

Double-click **creapy.io** (installation: `INSTALL_APP.md`). The start screen offers:

- **Open a bundle…**: a `.creapy` file (recordings, photos and areas of interest, ready to use; do not
  unzip it). The last bundle stays on the start screen for one-click access.
- **Open a project…**: a project you saved earlier.
- **Example dataset** (link at the bottom): twelve invented viewers on two drawn pictures. Try every view here.
- **Import your own data…**: an EyeLink DataViewer *fixation report* (CSV or Excel, one row per fixation), or
  the `…Metrics_Event-based.tsv` file of a Tobii Pro Lab recording. Confirm the **column mapping** (pre-filled;
  check the preview), then point creapy at the **folder with the images** (Tobii: the snapshot folder;
  subfolders are searched, names match with or without extension). An *AOI-based* metrics export opens as a
  table with charts per area instead.

## 2. The window

| Left | Middle | Top of the canvas | Right |
|---|---|---|---|
| the **views** | the figure or table | **thumbnails** = stimuli; **Show** bar = participant / group / time window | the **parameters** of the current view |

Parameters stay the same when you switch stimuli, so pictures remain comparable. Long computations run in the
background: the pill over the canvas has a **Cancel** button and the window stays usable.

## 3. The views in one line each

The app knows two settings, shown in the status bar: **lab** (a screen, every picture for the same time) and
**museum** (eye-tracking glasses, gaze mapped onto photographs of the walls, every visitor as long as they like).
Views that make no sense in the current setting are greyed out; hover to read why. *Analysis → Recording Setting*
switches.

- **Fixation Heatmap**: where people looked, weighted by fixation duration. The *smoothing bandwidth* changes the
  picture more than anything else: try several values. *Same colour scale* makes several heatmaps comparable.
- **Fixation Scanpath**: one viewer's sequence (circles sized by duration, numbered). Pick a participant in *Show*.
  In the museum setting the line breaks between visits.
- **Saccade Scanpath / Directions**: the eye movements as arrows; a rose diagram of their directions.
- **Areas of Interest**: draw rectangles or polygons on the image, or take the areas of the Tobii export; tick the
  areas you want; read dwell time, fixations, visits and time to first fixation per participant; scarf plot (who
  looked where, when), transition matrix, sequences, area comparison.
- **Statistics**: one row per participant; group comparison with the fitting test and effect size; boxplots;
  tables over all pictures.
- **Visits** (museum): who came to which wall, how often, for how long, in which order; timeline per visitor.
- Lab only: **Saccade Heatmap** (orientation heatmap, HeatMatch), **Time Series** (fixation duration, saccade
  amplitude, coefficient K, pupil size over the viewing time, per group), **Saccade Similarity** (how alike two
  viewers are; matrix, group boxplot with a permutation test). *Analysis → Show Advanced Analyses* adds
  **Scanpath Comparison** (MultiMatch, ScanMatch) and **Recurrence**.

## 4. Groups and comparisons

**Analysis → Assign Participants to Groups** (or prefill from a column of your table). Groups then appear in the
*Show* bar, as separate curves, as boxplots, and in the similarity views. **Analysis → Compare Side by Side**
draws the current view once per group, per stimulus or per time window with identical settings.

## 5. Save your work

- **Save as Image** (PNG / PDF / SVG) is on every panel; **Export Table** (CSV / Excel) on every panel that shows a
  table (also *File → Export Current Table*).
- **File → Export This View for All Stimuli** writes the current view once per picture into a folder.
- **File → Save Project** remembers the table, the images, the groups and the areas of interest; *Open Project*
  resumes later. **Ctrl+Z** (⌘Z on a Mac) undoes AOI edits and group assignments.

## 6. Before you write it up

1. Report the number of participants, the viewing time and **every parameter** a figure depends on (bandwidth,
   colour map, time window).
2. A heatmap is a picture of *these* viewers under *this* setting: not a property of the painting. Look at the
   first 3 seconds and the whole viewing separately; look at two bandwidths.
3. A difference between groups needs a test (Statistics) and an effect size, not two heatmaps.
4. Everything stays on your laptop. The app keeps a session log of what you do in it (not of the gaze data) as a
   text file on your computer; switch it off under *Logging* if you prefer.

*Support: Xingyu Long, xingyu.long@univie.ac.at. When something goes wrong, send a screenshot, the file name and the
zip from Logging → Save Logs for a Bug Report.*
