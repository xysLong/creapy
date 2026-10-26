from PySide6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser, QDialogButtonBox
from creapy.io import glossary

QUICK_GUIDE = """
<h2>creapy.io in five steps</h2>
<ol>
<li><b>Import a table.</b> One row per fixation (or per saccade), as exported by EyeLink DataViewer
    (fixation / saccade report, CSV or Excel) or by Tobii Pro Lab (<i>Data export</i>, TSV). Any other
    tool works too as long as it exports such a table.</li>
<li><b>Map the columns.</b> creapy guesses which column is the participant, the stimulus, time, duration
    and the coordinates; check the preview and correct if needed. Optional: a trial column (if a participant
    saw the same image more than once) and a pupil column.</li>
<li><b>Locate the images.</b> If the table holds only file names, pick the folder with the stimulus images
    (for Tobii glasses data: the snapshot images). Names are matched case-insensitively, with or without
    extension.</li>
<li><b>Explore.</b> Thumbnails above the canvas switch the stimulus; the list on the left switches the view;
    the panel on the right holds the parameters. Settings persist across stimuli so they stay comparable.</li>
<li><b>Filter and export.</b> The <i>Show</i> bar restricts every view to one participant, one group or a
    time window (e.g. the first 3 seconds). <i>Save as Image</i> exports the figure; tables (statistics,
    AOI metrics) export as CSV or Excel. <i>File &gt; Export This View for All Stimuli</i> writes the current
    view once per stimulus into a folder.</li>
</ol>
<p><b>Projects.</b> <i>File &gt; Save Project</i> remembers the table, the image folder, the column mapping, the
groups and the areas of interest, so you can continue later without redoing the import. <b>Undo</b> (Ctrl+Z)
reverts AOI edits and group assignments. <b>Analysis &gt; Compare Side by Side</b> draws the current view once per
group, stimulus or time window. Long computations run in the background: the window stays usable and the pill
over the canvas has a Cancel button.</p>

<h3>The views</h3>
<ul>
<li><b>Fixation Heatmap</b>: where people looked, weighted by fixation duration; every participant counts
    equally. The <i>smoothing bandwidth</i> decides how coarse the picture is: compare several values before
    drawing conclusions: the hot spots move.</li>
<li><b>Fixation Scanpath</b>: the sequence of fixations of one participant (circles sized by duration,
    numbered). With several participants selected, one colour per person.</li>
<li><b>Saccade Scanpath</b>: all eye movements as arrows; optionally only those along an orientation.</li>
<li><b>Saccade Heatmap</b>: HeatMatch orientation heatmap, where saccades of a given orientation
    concentrate (Long et al. 2026).</li>
<li><b>Saccade Directions</b>: rose diagram of saccade directions (share per direction bin).</li>
<li><b>Areas of Interest</b>: draw rectangles or polygons on the image, then read the table of dwell time,
    number of fixations, visits, time to first fixation per participant and area; scarf plot and transition
    matrix. Save/load AOI sets as JSON.</li>
<li><b>Time Series</b>: how fixation duration, saccade amplitude, the ambient–focal coefficient K, pupil
    size, viewing distance or the share of fixations inside the AOIs change over the viewing time (per group if
    groups are assigned); periodogram and scalogram for rhythms.</li>
<li><b>Saccade Similarity</b>: pairwise HeatMatch similarity of all participants as matrix, group boxplot
    with a permutation test, viewer map, similarity over time.</li>
<li><b>Scanpath Comparison</b>: MultiMatch, ScanMatch and cross-recurrence between all participants, with the
    same matrix / boxplot / viewer-map displays.</li>
<li><b>Recurrence</b>: recurrence plot of one participant and the RQA measures (recurrence, determinism,
    laminarity, CORM) of all.</li>
<li><b>Statistics</b>: one row per participant (fixations, durations, saccades, scanpath length,
    coefficient K ...), group comparison with t-test/ANOVA, AOI metrics. Export as CSV/Excel.</li>
</ul>

<h3>Good habits</h3>
<ul>
<li>A heatmap is a picture of a <i>sample of viewers</i> under <i>one rendering setting</i>, not a
    property of the painting. Report the number of participants, the viewing time and the bandwidth.</li>
<li>Early viewing (first seconds) and later viewing differ systematically: use the time window.</li>
<li>Keep the stimulus image at the resolution the coordinates refer to (the screen or snapshot pixels).</li>
</ul>
"""

FORMATS = """
<h2>Supported data formats</h2>
<h3>EyeLink DataViewer</h3>
<p><b>Fixation report</b> with at least <code>RECORDING_SESSION_LABEL</code>, <code>CURRENT_FIX_X</code>,
<code>CURRENT_FIX_Y</code>, <code>CURRENT_FIX_START</code>, <code>CURRENT_FIX_DURATION</code> and a column
naming the stimulus image (a trial variable such as <code>image</code>). <code>TRIAL_INDEX</code> and
<code>CURRENT_FIX_PUPIL</code> are picked up as optional columns. Missing values written as '.' are handled.</p>
<p><b>Saccade report</b> with <code>CURRENT_SAC_START_X/Y</code>, <code>CURRENT_SAC_END_X/Y</code>,
<code>CURRENT_SAC_START_TIME</code>, <code>CURRENT_SAC_AMPLITUDE</code>, the participant and the stimulus
column.</p>
<p>Times may be in milliseconds (raw reports) or seconds; creapy detects the unit.</p>

<h3>Tobii Pro Lab</h3>
<p><b>Event-based metrics export</b> (Analyze &gt; Metrics export, <i>event-based</i>; TSV, one row per fixation,
saccade or glance). This is the file the lab usually shares (e.g. the Belvedere WOQ rooms). creapy keeps the
fixation rows: <i>Media</i> becomes the stimulus (the snapshot), <i>FixationPointX/Y</i> (0–1 on the medium) are
scaled to the snapshot image, <i>Start</i>/<i>Duration</i> are ms from the start of each interval of the time of
interest, and every interval counts as one trial (times restart per interval). <i>Average_pupil_diameter</i> and
the Pro Lab <i>AOI</i> hit are carried along. The <b>AOI-based</b> metrics export has no positions and cannot be
visualised.</p>
<p><b>AOI-based metrics export</b> (one row per participant × interval × AOI, no positions): opens as a table
window with a bar chart per AOI (<i>File &gt; Open Tobii AOI Metrics Table</i>): mean dwell time, visits, fixations,
time to first fixation, split by Media or Condition, exportable.</p>
<p><b>Data export</b> (Analyze &gt; Data export; TSV, one row per gaze sample; can be tens of gigabytes: files
above 1.5 GB are read in chunks with only the needed columns, about a minute per gigabyte). Include the columns
<i>Recording timestamp, Participant name, Eye movement type, Eye movement type index, Gaze event duration</i>
and</p>
<ul>
<li>for <b>screen-based</b> recordings: <i>Fixation point X/Y</i> (media coordinates) and
    <i>Presented Media name</i>;</li>
<li>for <b>glasses</b> recordings mapped onto snapshots: <i>Mapped eye movement type</i> and
    <i>Mapped fixation X/Y</i> for every snapshot. Each snapshot becomes one stimulus; point creapy at the
    folder with the snapshot images when asked.</li>
</ul>
<p>creapy collapses the samples into one row per fixation and carries the mean pupil diameter and, for glasses,
the viewing distance (length of the 3D gaze vector) per fixation. Timestamps in ms or µs are both fine; decimal
commas are handled.</p>

<h3>Any other tool</h3>
<p>Export one row per fixation with participant, stimulus, start time, duration, x and y, as CSV
(comma, semicolon or tab separated) or Excel, and map the columns in the import dialog.</p>

<h3>Stimulus images</h3>
<p>Coordinates are interpreted as pixels of the image you provide. Use the images at the resolution they were
shown (or the snapshot files of the Pro Lab project). PNG, JPEG, BMP and TIFF are supported; very large images
(museum snapshots of 8000 px) are downscaled on loading and the coordinates with them. When asked for the image
folder, pick the top folder: subfolders are searched, and names match with or without the extension.</p>
"""

ANALYSES = """
<h2>The analyses explained</h2>
<p>Every view answers one question. The parameter on the right changes the picture: compare settings before you
conclude anything, and report the setting you used.</p>

<h3>Where did people look?</h3>
<p><b>Fixation Heatmap.</b> A smoothed density of fixations, weighted by their duration, each participant counting
equally. The <i>smoothing bandwidth</i> is the one setting that changes the picture most: small values show many
small hot spots, large values one blurred blob. By default every heatmap is scaled to its own peak, so two heatmaps
are <i>not</i> comparable by colour; tick <i>Same colour scale</i> to compare stimuli, groups or time windows
honestly (densities above the shared maximum saturate).</p>
<p><b>Areas of Interest.</b> Draw the regions you care about and read dwell time, number of fixations, visits
(runs of consecutive fixations inside), time to first fixation and first-fixation rank per participant. The
<i>scarf plot</i> shows every participant's sequence of areas over time; the <i>transition matrix</i> shows where
the gaze went after leaving an area (between visits, so a dwell inside an area counts once).</p>

<h3>How did people look?</h3>
<p><b>Scanpaths</b> show one viewer's sequence (circles sized by duration). <b>Saccade Scanpath / Heatmap /
Directions</b> show the eye movements themselves: all saccades as arrows, where saccades of a given orientation
concentrate (HeatMatch, Long et al. 2026), and the distribution of directions (rose diagram).</p>
<p><b>Ambient–focal coefficient K</b> (Krejtz et al. 2016): per fixation, standardised duration minus standardised
amplitude of the following saccade. K &gt; 0 = focal (long fixations, short saccades), K &lt; 0 = ambient
(scanning). Available as a per-participant value (Statistics) and as a curve over viewing time (Time Series).</p>
<p><b>Recurrence</b> (Anderson et al. 2013): two fixations recur when they fall within a radius of each other.
<i>Recurrence</i> measures how much a viewer returns to the same spots, <i>determinism</i> how often whole sequences
repeat, <i>laminarity</i> how much they dwell in clusters, <i>CORM</i> whether returns come early or late. The
recurrence plot of one participant shows all of this at a glance.</p>

<h3>How do viewers or groups differ?</h3>
<p><b>Statistics.</b> One row per participant; group comparison with Welch's t-test and Mann–Whitney U (two groups)
or ANOVA (more); boxplots. Exploratory: with many measures, correct for multiple comparisons before reporting.</p>
<p><b>Saccade Similarity</b> (HeatMatch): how alike two participants' saccade patterns are, in location
(<i>s_loc</i>) and direction (<i>s_dir</i>). <b>Scanpath Comparison</b>: the classic sequence-based measures:
MultiMatch (Dewhurst et al. 2012: shape, direction, length, position, duration of aligned scanpaths),
ScanMatch (Cristino et al. 2010: scanpaths as letter strings over a grid, aligned like DNA sequences),
cross-recurrence (how often two viewers fixated the same spots). All four produce a participant × participant
matrix, a group boxplot with a permutation test (are participants more similar within their group than between
groups?), and a viewer map that places similar participants close together.</p>
<p><b>Compare Side by Side</b> (Analysis menu) draws the current image view once per group, stimulus or time
window with identical settings.</p>

<h3>How does viewing change over time?</h3>
<p><b>Time Series.</b> The curve of fixation duration, saccade amplitude, K, pupil size or viewing distance over the
viewing time (smoothed; the dashed tail marks the last 5 s where fewer viewers remain), or the share of fixations
inside the AOIs. <i>Periodogram</i>: does the value oscillate with a rhythm? Lomb–Scargle power per frequency
(cycles per second; the top axis gives the period in seconds), one thin line per participant and the mean.
<i>Scalogram</i>: the same rhythms resolved over time (Morlet wavelets on the mean curve). <b>Similarity over
Time</b> (in Saccade Similarity) shows whether viewers synchronise early and drift apart later.</p>

<h3>Good habits</h3>
<ul>
<li>Report the number of participants, the viewing time, and every parameter value a figure depends on.</li>
<li>Try the first 3 seconds and the full viewing separately; early and late viewing differ systematically.</li>
<li>A difference between groups needs a test and an effect size, not two heatmaps.</li>
</ul>
"""
ANALYSES += glossary.view_by_view_html()

ABOUT = """
<h2>creapy.io</h2>
<p>Eye-tracking visual analytics for art history and empirical aesthetics.<br>
CReA Lab (Lab for Cognitive Research in Art History), Department of Art History, University of Vienna.</p>
<p>Lead developer: Xingyu Long (xingyu.long@univie.ac.at). Saccade heatmaps and similarity scores are computed by
the <b>HeatMatch</b> package (Long, Arató, Kury, Miscenà &amp; Rosenberg 2026, PACMCGIT 9(2),
doi:10.1145/3803539).</p>
<p>Please cite: Long, X. &amp; Rosenberg, R. (2026). Perspektiven für ein anfängerfreundliches Tool zur
Eye-Tracking-Datenvisualisierung in der kognitiven Kunstgeschichte. <i>DHd 2026 Book of Abstracts</i>,
606–607. doi:10.5281/zenodo.18703017</p>
<p><b>Session log.</b> If you switch on <i>Logging &gt; Record session log</i>, creapy writes which views and
parameter values you used to a text file on this computer only (see <i>Logging &gt; Open log folder</i>).
Nothing is sent anywhere; you can delete the files at any time.</p>
"""


class HelpDialog(QDialog):

    def __init__(self, title, html, parent=None, size=(720, 640)):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(html)
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
        self.resize(*size)
