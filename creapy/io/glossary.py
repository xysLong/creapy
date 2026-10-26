"""
Every explanatory text of the GUI in one place, so the wording can be reviewed (and translated) without touching
the widgets. Qt-free.

Three layers, cheapest first:
  * TOOLTIPS:   one or two sentences per control, shown on hover. They say what changing the control does to the
                 picture, not what the parameter is called in the literature.
  * EXPLAINERS: one page per view (what it shows, how to read it, the parameters, a reference), shown in the
                 "About this view" panel that the ⓘ button opens and kept while the user works.
  * CAPTIONS:   one line under charts whose axes carry jargon (s_loc, REC %, mm_vector ...), also written into
                 saved figures.

Wording rule: describe effects neutrally ("wider blur merges hot spots"), never recommend a
setting ("use 0.1"). The Fixation Heatmap canvas itself stays untouched (no caption, no participant count).
"""

# ------------------------------------------------------------------------------------------------------------------
# One line per view, for the view list on the left (hover) and the header of the parameter panel
# ------------------------------------------------------------------------------------------------------------------

VIEW_SUMMARY = {
    "Fixation Heatmap": "Where people looked: a smoothed density of fixations, weighted by their duration.",
    "Fixation Scanpath": "The order in which one person looked: numbered circles, sized by fixation duration.",
    "Saccade Scanpath": "All eye movements as arrows from one fixation to the next.",
    "Saccade Heatmap": "Where eye movements of a chosen orientation concentrate (HeatMatch).",
    "Saccade Directions": "Rose diagram: how often the eyes moved in each direction.",
    "Areas of Interest": "Draw regions on the image and count what happened inside them.",
    "Time Series": "How a measure (fixation duration, saccade amplitude, K, pupil ...) changes over viewing time.",
    "Saccade Similarity": "How alike two viewers' eye-movement patterns are (HeatMatch), for every pair.",
    "Scanpath Comparison": "Classic scanpath comparison for every pair: MultiMatch, ScanMatch, cross-recurrence.",
    "Recurrence": "How often a viewer returns to the same spots, and in what pattern (RQA).",
    "Statistics": "One row per participant: counts, means, coefficient K; group tests; AOI metrics.",
}

# ------------------------------------------------------------------------------------------------------------------
# Tooltips, keyed by toolbar and by the attribute name of the control (utils.apply_tooltips sets them)
# ------------------------------------------------------------------------------------------------------------------

STIMULUS_TIPS = {
    'stimulus_opacity_slider': "How strongly the image shows through. 0% hides the image and leaves only the data.",
    'grayscale_checkbox': "Shows the image in grey so the colours of the data are not confused with the colours of "
                          "the artwork.",
}

TOOLTIPS = {
    'fix_heatmap': dict(STIMULUS_TIPS, **{
        'contour_opacity_slider': "Transparency of the coloured density layer.",
        'color_selector': "The colour ramp from low to high density. Perceptually uniform maps (viridis, magma) "
                          "show gradual differences; diverging maps (coolwarm) emphasise the extremes.",
        'bw_method_slider': "Smoothing bandwidth of the density estimate, as a share of the image size. Smaller "
                            "values show many small hot spots; larger values merge them into few blurred blobs. "
                            "The hot spots move with this setting, so compare several values.",
        'num_levels_slider': "How many colour bands the density is cut into. More levels give a smoother gradient; "
                             "fewer give clear-cut zones.",
        'from_level_slider': "Hides the lowest density bands so the image shows through where few fixations fell. "
                             "0 colours everything, higher values keep only the densest regions.",
        'shared_scale_checkbox': "Off: each heatmap is scaled to its own peak, so two heatmaps are not comparable by "
                                 "colour. On: the same colour means the same density in every heatmap; the scale is "
                                 "set by the densest stimulus of the dataset.",
        'scatter_opacity_slider': "Transparency of the fixation points drawn on top of the density.",
        'scatter_color_selector': "Colour of the fixation points.",
        'scatter_size_slider': "Size of the fixation points (not related to their duration).",
    }),
    'fix_scanpath': dict(STIMULUS_TIPS, **{
        'numbered_checkbox': "Writes the fixation number into each circle, so the order can be read off.",
        'opacity_slider': "Transparency of circles and connecting lines.",
        'color_selector': "Colour used when one participant is shown. With several participants each gets a "
                          "colour of its own.",
        'size_slider': "Scales the circles. Their area is proportional to the fixation duration, so long fixations "
                       "stay larger than short ones at every setting.",
        'line_width_slider': "Width of the lines connecting consecutive fixations (the saccades).",
    }),
    'sac_scanpath': dict(STIMULUS_TIPS, **{
        'ooi_checkbox': "Keeps only the saccades that run roughly along the orientation set on the dial; all "
                        "others are hidden.",
        'angle_dial': "Orientation of interest: 0° = horizontal, 90° = vertical. Opposite directions count as "
                      "the same orientation.",
        'line_opacity_slider': "Transparency of the arrows. Lower values let dense bundles stand out.",
        'line_color_selector': "Colour of the arrows.",
        'line_width_slider': "Width of the arrows.",
    }),
    'sac_heatmap': dict(STIMULUS_TIPS, **{
        'angle_dial': "Orientation of interest: the heatmap shows where saccades running along this orientation "
                      "concentrate. 0° = horizontal, 90° = vertical. The ring shows the colour of each orientation.",
        'heatmap_opacity_slider': "Transparency of the densest regions; sparser regions are drawn more transparent "
                                  "anyway.",
        'color_selector': "Colour ramp for the saccade density.",
        'heatmap_sigma_slider': "Smoothing of the saccade lines, in image pixels. Larger values turn single lines "
                                "into broad bands.",
        'heatmap_quantile_slider': "Share of the faintest density that is made fully transparent. 0.8 hides the "
                                   "weakest 80% and keeps the densest fifth.",
        'heatmap_degree_slider': "How sharply the opacity rises with density. Below 1 shows faint regions too; "
                                 "above 1 keeps only the strongest bundles.",
    }),
    'rose': {
        'bins_slider': "Number of direction sectors the circle is divided into. More bins resolve finer "
                       "directions but each holds fewer saccades.",
        'fold_checkbox': "Treats opposite directions as one (left = right, up = down), so the diagram shows "
                         "orientations rather than directions.",
        'rays_checkbox': "Draws one bar per direction sector.",
        'hull_checkbox': "Connects the bar tips with a line.",
        'numbers_checkbox': "Writes the percentage of saccades on each bar.",
        'color_selector': "Colour ramp; longer bars get the darker end.",
    },
    'aoi': {
        'mode_selector': "Rectangle: click and drag on the image. Polygon: click the corners, double-click to "
                         "close. View only: the mouse does nothing on the image.",
        'aoi_list': "The areas drawn on this stimulus. Select one to remove it.",
        'remove_btn': "Deletes the selected area (Undo brings it back).",
        'clear_btn': "Deletes all areas of this stimulus (Undo brings them back).",
        'save_aoi_btn': "Writes the areas of this stimulus to a JSON file, to reuse them later or share them.",
        'load_aoi_btn': "Loads areas from a JSON file saved earlier.",
        'auto_btn': "Adds the most-viewed regions of the fixation heatmap as one data-driven area. The result "
                    "depends on the heatmap's smoothing bandwidth.",
        'display_selector': "Image: the areas on the stimulus. Metrics table: dwell time, fixations, visits and "
                            "time to first fixation per participant and area. Scarf plot: each participant's "
                            "sequence of areas over time. Transition matrix: where the gaze went after leaving an "
                            "area. First-fixation order: in which order the areas were first looked at.",
        'underlay_selector': "What is drawn under the areas: the fixation points, the fixation heatmap or nothing.",
        'labels_checkbox': "Writes the name of each area onto the image.",
        'opacity_slider': "Transparency of the area fills.",
        'grayscale_checkbox': STIMULUS_TIPS['grayscale_checkbox'],
    },
    'time_series': {
        'curve_selector': "Which measure is followed over the viewing time. Fixation duration and saccade amplitude "
                          "describe the eye movements; K combines both (positive = focal, negative = ambient); "
                          "pupil size and viewing distance come from the eye tracker; Fixations in AOIs is the "
                          "share of fixations inside the drawn areas.",
        'display_selector': "Curve: the measure smoothed over viewing time. Periodogram: which rhythms (cycles per "
                            "second) the measure shows, one thin line per participant and the mean. Scalogram: the "
                            "same rhythms resolved over time.",
        'per_group_checkbox': "One curve per assigned group instead of one curve for everyone.",
        'sigma_slider': "Smoothing along the time axis, in seconds. Small values follow every bump; large values "
                        "show the trend only.",
        'band_slider': "Width of the shaded band around the mean, as a fraction of the standard deviation between "
                       "participants. 0 hides the band.",
    },
    'similarity': {
        'sigma_slider': "Smoothing of the saccade heatmaps that are compared, in pixels. Larger values forgive "
                        "small positional differences between viewers.",
        'tradeoff_slider': "0 compares only where saccades are dense; 1 compares only how consistently they run "
                           "in the same orientation; values in between mix both.",
        'windows_slider': "Number of overlapping time windows for Similarity over Time. More windows resolve the "
                          "viewing time finer but each holds fewer saccades.",
        'compute_btn': "Starts the pairwise computation with the settings above (it is not run on every change "
                       "because it takes a while).",
        'view_selector': "Matrix: one cell per pair of participants. Boxplot: within-group versus between-group "
                         "similarities with a permutation test. Viewer map: participants placed so that similar "
                         "ones are close. Over time: mean similarity per time window.",
        'score_selector': "Location score s_loc: do the two viewers make saccades in the same places? Direction "
                          "score s_dir: do their saccades run in the same orientations?",
        'color_selector': "Colour ramp of the matrix cells.",
    },
    'scanpath_compare': {
        'method_selector': "MultiMatch aligns two scanpaths and scores five aspects (1 = identical). ScanMatch "
                           "turns scanpaths into letter strings over a grid and aligns them like DNA. "
                           "Cross-recurrence counts how often two viewers fixated the same spots.",
        'grid_slider': "ScanMatch: how finely the image is divided into cells (letters). Finer grids are stricter "
                       "about position.",
        'bin_slider': "ScanMatch: repeats each letter per time bin, so long fixations weigh more. 'per fixation' "
                      "ignores duration.",
        'radius_slider': "Cross-recurrence: two fixations count as the same spot when closer than this share of "
                         "the image diagonal.",
        'compute_btn': "Starts the pairwise computation with the settings above.",
        'view_selector': "Matrix: one cell per pair. Boxplot: within-group versus between-group with a "
                         "permutation test. Viewer map: similar participants close together. Measure overview: all "
                         "five MultiMatch scores at once.",
        'score_selector': "Which score fills the matrix. MultiMatch: vector = shape of the path, direction, "
                          "length of the saccades, position of the fixations, duration of the fixations.",
        'color_selector': "Colour ramp of the matrix cells.",
    },
    'recurrence': {
        'display_selector': "Plot: one participant's recurrence plot (pick the participant in the Show bar). Table: "
                            "the four RQA measures per participant. Boxplot: one measure by group.",
        'radius_slider': "Two fixations recur when they are closer than this share of the image diagonal. Larger "
                         "radii find more recurrences.",
        'min_line_slider': "How many consecutive recurrences form a line. Determinism and laminarity count only "
                           "lines at least this long.",
        'measure_selector': "Recurrence: share of fixation pairs that fall on the same spot. Determinism: share of "
                            "recurrences that are part of repeated sequences. Laminarity: share that are part of "
                            "dwelling in one cluster. CORM: whether returns happen soon after (small) or long after "
                            "(large) the first visit.",
    },
    'stats': {
        'display_selector': "Participants: one row per person. Group comparison: means per group with t-test / "
                            "Mann-Whitney (two groups) or ANOVA (more). AOI metrics: per participant and area. "
                            "Boxplot: one measure by group.",
        'measure_selector': "Which column of the participant table the boxplot shows.",
    },
}

COMMON_TIPS = {
    'save_btn': "Saves the current figure as PNG, PDF or SVG, with the caption line where there is one.",
    'export_btn': "Saves the current table as CSV or Excel.",
    'groups_btn': "Assigns every participant to a group (by name pattern or by hand). Groups split curves, "
                  "boxplots and the similarity tests.",
}

FILTER_TIPS = {
    'participant_selector': "Restricts every view to one participant or one group. Everything else stays the same.",
    'from_slider': "Start of the time window, in seconds from the start of viewing. Only fixations and saccades "
                   "inside the window feed the views.",
    'to_slider': "End of the time window. The first seconds of viewing differ systematically from later viewing.",
    'reset_btn': "Back to all participants and the whole viewing time.",
}

# ------------------------------------------------------------------------------------------------------------------
# Explainers: one HTML page per view for the "About this view" panel
# ------------------------------------------------------------------------------------------------------------------

EXPLAINERS = {
    "Fixation Heatmap": """
<h3>Fixation Heatmap</h3>
<p><b>What it shows.</b> Where the viewers' eyes rested. Every fixation is spread into a small Gaussian blob,
weighted by how long it lasted; the blobs are summed and drawn as coloured bands over the image. Every participant
counts equally, whatever their number of fixations.</p>
<p><b>How to read it.</b> Red (in the default colour map) marks the highest density, blue the lowest; regions
below the lowest shown level are left transparent. By default each heatmap is scaled to its own maximum, so the
reddest spot of a picture that was barely looked at is as red as the reddest spot of a picture that drew everyone.
Tick <i>Same colour scale</i> before comparing two heatmaps by colour.</p>
<p><b>Parameters.</b> <i>Smoothing bandwidth</i> decides the grain of the picture and moves the hot spots;
<i>number of levels</i> and <i>show from level</i> decide how the density is cut into bands and how much of the
image stays visible.</p>
<p><b>Terms.</b> <i>Fixation</i>: a pause of the eye on one spot (typically 150–400 ms). <i>Density</i>: fixation
time per area. <i>Kernel density estimate</i>: the smoothing method behind the picture.</p>
""",
    "Fixation Scanpath": """
<h3>Fixation Scanpath</h3>
<p><b>What it shows.</b> One viewer's fixations in order, as numbered circles connected by lines. The area of a
circle is proportional to the fixation duration.</p>
<p><b>How to read it.</b> Follow the numbers to replay the viewing. Clusters of circles mark regions the viewer
dwelt on; long lines are large saccades. With several participants selected, each gets a colour and the picture
shows whether they took similar routes.</p>
<p><b>Terms.</b> <i>Scanpath</i>: the sequence of fixations and saccades of one viewing. <i>Saccade</i>: the rapid
jump between two fixations, during which little is seen.</p>
""",
    "Saccade Scanpath": """
<h3>Saccade Scanpath</h3>
<p><b>What it shows.</b> Every saccade of the selected viewers as an arrow from the fixation where it started to
the one where it ended.</p>
<p><b>How to read it.</b> Dense bundles of arrows mark routes many viewers took; with <i>orientation of
interest</i> switched on only the saccades along the chosen orientation remain, which brings out, for instance,
the horizontal sweeps across a landscape or the vertical movements along a figure.</p>
<p><b>Terms.</b> <i>Orientation</i>: direction without sign (left-to-right and right-to-left are the same
orientation). <i>Amplitude</i>: the length of a saccade.</p>
""",
    "Saccade Heatmap": """
<h3>Saccade Heatmap (HeatMatch)</h3>
<p><b>What it shows.</b> Where saccades of a chosen orientation concentrate. Each saccade is drawn as a line,
blurred by the smoothing bandwidth and coloured by how closely its orientation matches the one set on the dial;
the result is summed over all viewers.</p>
<p><b>How to read it.</b> Opaque, saturated regions are where many viewers moved their eyes along the chosen
orientation. Turn the dial to see other orientations. The <i>quantile</i> and <i>sensitivity</i> controls decide
how much of the faint density is hidden.</p>
<p><b>Reference.</b> Long, Arató, Kury, Miscenà &amp; Rosenberg (2026), HeatMatch, PACMCGIT 9(2),
doi:10.1145/3803539.</p>
""",
    "Saccade Directions": """
<h3>Saccade Directions (rose diagram)</h3>
<p><b>What it shows.</b> The share of saccades per direction sector. 0° points to the right, 90° upwards.
Every participant is weighted equally.</p>
<p><b>How to read it.</b> Long bars are frequent directions. Most viewings are dominated by horizontal
movements; a strong vertical or diagonal lobe is the interesting finding. <i>Fold opposite directions</i>
merges left with right and up with down, which turns the diagram into one of orientations.</p>
<p><b>Terms.</b> <i>Direction bin</i>: one sector of the circle. <i>Rose diagram</i>: a circular histogram.</p>
""",
    "Areas of Interest": """
<h3>Areas of Interest (AOI)</h3>
<p><b>What it shows.</b> Regions you draw on the image, and what happened inside them: how long the gaze stayed
(<i>dwell time</i>), how many fixations fell inside, how many separate <i>visits</i> there were (a visit is a run
of consecutive fixations inside the area), when the area was first looked at (<i>time to first fixation</i>) and
in which order the areas were first visited.</p>
<p><b>How to read it.</b> The <i>metrics table</i> has one row per participant and area. The <i>scarf plot</i> has
one row per participant with the fixations coloured by area over time, so patterns like "everyone starts at the
face" are visible at a glance. The <i>transition matrix</i> counts where the gaze went after leaving an area
(between visits, so dwelling inside an area is not counted as a transition).</p>
<p><b>Caveats.</b> Results depend entirely on where the borders are drawn; a few pixels decide whether a fixation
counts. Draw areas before looking at the data, or use <i>Add hot spots</i> for a data-driven area and say so.</p>
""",
    "Time Series": """
<h3>Time Series</h3>
<p><b>What it shows.</b> How a measure changes over the viewing time: the mean over participants (each weighted
equally), smoothed along the time axis, with a band for the spread between participants. The dashed tail marks the
last seconds where fewer viewers remain.</p>
<p><b>The measures.</b> <i>Fixation duration</i> and <i>saccade amplitude</i> describe the eye movements
themselves. The <i>ambient–focal coefficient K</i> (Krejtz et al. 2016) combines both: per fixation, standardised
duration minus standardised amplitude of the following saccade; K above 0 means focal viewing (long fixations,
short saccades), below 0 ambient scanning. <i>Pupil size</i> and <i>viewing distance</i> come from the eye
tracker. <i>Fixations in AOIs</i> is the share of fixations inside the drawn areas.</p>
<p><b>Periodogram and scalogram.</b> The periodogram asks whether the measure oscillates with a rhythm: power per
frequency (cycles per second; the top axis gives the period in seconds), one thin line per participant and the
mean. The scalogram shows the same rhythms resolved over time. Both are exploratory tools; a peak needs
replication before it is a finding.</p>
""",
    "Saccade Similarity": """
<h3>Saccade Similarity (HeatMatch)</h3>
<p><b>What it shows.</b> For every pair of participants, how alike their saccade patterns are: the <i>location
score s_loc</i> asks whether they moved their eyes in the same places, the <i>direction score s_dir</i> whether
their saccades ran in the same orientations. Both range from 0 (nothing in common) to 1 (identical).</p>
<p><b>How to read it.</b> The <i>matrix</i> has one cell per pair; brackets mark the groups. The <i>boxplot</i>
compares similarities within groups to those between groups; the permutation test asks whether members of a group
look more alike than chance would produce. The <i>viewer map</i> places participants so that similar ones are close
(multidimensional scaling; the axes have no meaning of their own). <i>Similarity over time</i> shows whether
viewers synchronise early and drift apart later.</p>
<p><b>Reference.</b> Long et al. (2026), HeatMatch, PACMCGIT 9(2), doi:10.1145/3803539.</p>
""",
    "Scanpath Comparison": """
<h3>Scanpath Comparison</h3>
<p><b>What it shows.</b> The classic sequence-based similarity of every pair of scanpaths.</p>
<ul>
<li><b>MultiMatch</b> (Dewhurst et al. 2012) simplifies both scanpaths, aligns them and scores five aspects from
0 to 1: <i>vector</i> (shape), <i>direction</i>, <i>length</i> of the saccades, <i>position</i> of the fixations,
<i>duration</i> of the fixations.</li>
<li><b>ScanMatch</b> (Cristino et al. 2010) turns each scanpath into a string of letters, one per grid cell (and
per time bin if set), and aligns the two strings like DNA sequences; 1 = identical.</li>
<li><b>Cross-recurrence</b> (Anderson et al. 2013) counts how often a fixation of one viewer falls within the
radius of a fixation of the other, as a share of all pairs.</li>
</ul>
<p><b>How to read it.</b> Matrix, group boxplot with permutation test and viewer map as in Saccade Similarity.
<i>Measure overview</i> shows all five MultiMatch scores side by side. Position and duration scores are usually
high for any two viewers of the same picture; differences show in vector and direction.</p>
""",
    "Recurrence": """
<h3>Recurrence (RQA)</h3>
<p><b>What it shows.</b> Whether, and how, a viewer returns to the same spots (Anderson et al. 2013). Two fixations
<i>recur</i> when they fall within the radius of each other. The <i>recurrence plot</i> marks every recurring pair
of fixation indices; the diagonal is the trivial self-match.</p>
<p><b>The measures.</b> <i>Recurrence</i> (REC): share of fixation pairs that recur; high values mean a viewer kept
returning to few spots. <i>Determinism</i> (DET): share of recurrences that form diagonal lines, i.e. repeated
sequences of fixations. <i>Laminarity</i> (LAM): share forming vertical or horizontal lines, i.e. dwelling in one
cluster. <i>CORM</i>: centre of recurrence mass, whether returns happen soon after the first visit (small) or long
after (large).</p>
<p><b>Parameters.</b> The <i>radius</i> decides what counts as the same spot and drives every measure; report it.
<i>Minimum line length</i> decides how many consecutive recurrences form a line.</p>
""",
    "Statistics": """
<h3>Statistics</h3>
<p><b>What it shows.</b> One row per participant: number of fixations, mean fixation duration, number and mean
amplitude of saccades, scanpath length, the ambient–focal coefficient K and more. The <i>group comparison</i>
gives means per group with Welch's t-test and Mann–Whitney U (two groups) or ANOVA (more); the <i>AOI metrics</i>
table repeats the Areas-of-Interest table; the <i>boxplot</i> shows one measure by group.</p>
<p><b>How to read it.</b> Durations are in the unit of your table (EyeLink: ms, Tobii: ms). K above 0 means focal
viewing (long fixations, short saccades), below 0 ambient scanning (Krejtz et al. 2016).</p>
<p><b>Caveats.</b> The tests are exploratory. With a dozen measures, one will be "significant" by chance; correct
for multiple comparisons and report effect sizes.</p>
""",
}

# ------------------------------------------------------------------------------------------------------------------
# Captions under charts whose axes carry jargon (not for image views; the heatmap canvas stays untouched)
# ------------------------------------------------------------------------------------------------------------------

SCORE_CAPTIONS = {
    's_loc': "s_loc = location similarity: 1 when two viewers make their saccades in the same places, 0 when nowhere "
             "in common",
    's_dir': "s_dir = direction similarity: 1 when two viewers' saccades run in the same orientations",
    'mm_vector': "MultiMatch vector = similarity of the scanpath shapes after alignment (1 = identical)",
    'mm_direction': "MultiMatch direction = similarity of saccade directions of aligned fixations (1 = identical)",
    'mm_length': "MultiMatch length = similarity of saccade lengths of aligned fixations (1 = identical)",
    'mm_position': "MultiMatch position = similarity of fixation positions of aligned fixations (1 = identical)",
    'mm_duration': "MultiMatch duration = similarity of fixation durations of aligned fixations (1 = identical)",
    'scanmatch': "ScanMatch score = alignment of the two letter strings, 1 = identical",
    'cross_recurrence': "Cross-recurrence = share of fixation pairs of two viewers that fall within the radius",
}

PAIRWISE_VIEW_CAPTIONS = {
    "Similarity Matrix": "One cell per pair of participants; brackets mark the groups.",
    "Group Boxplot": "Within = pairs from the same group, between = pairs from different groups; p from a "
                     "permutation test of the within–between difference.",
    "Viewer Map (MDS)": "Multidimensional scaling: similar participants are placed close together; the axes have "
                        "no meaning of their own.",
    "Similarity over Time": "Mean pairwise similarity per overlapping time window.",
    "Measure overview": "All five MultiMatch scores; position and duration are usually high for any two viewers "
                        "of the same picture.",
}

CURVE_CAPTIONS = {
    "Fixation Duration": "Mean fixation duration of all participants (each weighted equally), smoothed over viewing "
                         "time; band = spread between participants; dashed tail = fewer viewers remain.",
    "Saccade Amplitude": "Mean saccade amplitude (length of the eye movements), smoothed over viewing time; "
                         "dashed tail = fewer viewers remain.",
    "Ambient–Focal (K)": "Coefficient K (Krejtz et al. 2016): above 0 = focal viewing (long fixations, short "
                         "saccades), below 0 = ambient scanning.",
    "Pupil Size": "Mean pupil size as recorded by the eye tracker (unit of the table); also reacts to brightness.",
    "Viewing Distance": "Distance between the eyes and the fixated point, from the eye tracker's 3D gaze vector.",
    "Fixations in AOIs": "Share of fixations that fall inside the drawn areas of interest at each moment.",
}

RQA_CAPTIONS = {
    "Recurrence plot (one participant)": "Each dot: fixations i and j fell within the radius of each other. Diagonal "
                                         "lines = repeated sequences, vertical/horizontal lines = dwelling in one "
                                         "cluster.",
    "RQA table": "REC = share of recurring fixation pairs, DET = share in repeated sequences, LAM = share in dwelling, "
                 "CORM = centre of recurrence mass (early vs late returns); Anderson et al. 2013.",
    "Boxplot by group": None,  # filled from the measure
}

RQA_MEASURE_CAPTIONS = {
    'recurrence': "Recurrence (REC): share of fixation pairs that fall on the same spot (within the radius).",
    'determinism': "Determinism (DET): share of recurrences that are part of repeated fixation sequences.",
    'laminarity': "Laminarity (LAM): share of recurrences that are part of dwelling in one cluster.",
    'corm': "CORM: centre of recurrence mass; small = returns soon after the first visit, large = long after.",
}


def figure_caption(view, params):
    # One plain-text line for the chart of `view` drawn with `params`, or None when the view needs none
    # (image views: heatmaps, scanpaths, the AOI image)
    if view == "Saccade Directions":
        return ("Share of saccades per direction sector (0° = to the right, 90° = upwards); every participant "
                "weighted equally." + (" Opposite directions folded together." if params.get('center_symmetric')
                                       else ""))
    if view == "Time Series":
        display = params.get('display', 'Curve over time')
        base = CURVE_CAPTIONS.get(params.get('curve'), "")
        if display == 'Periodogram':
            return ("Lomb–Scargle periodogram: power per frequency (cycles per second; top axis = period in "
                    "seconds), thin lines = participants, thick = mean. A peak means the measure oscillates with "
                    "that rhythm.")
        if display == 'Scalogram':
            return "Morlet scalogram of the mean curve: which rhythms (y) are present at which moment (x)."
        return base or None
    if view in ("Saccade Similarity", "Scanpath Comparison"):
        parts = [SCORE_CAPTIONS.get(params.get('which'), ""), PAIRWISE_VIEW_CAPTIONS.get(params.get('view'), "")]
        if params.get('view') == 'Measure overview':
            parts = [PAIRWISE_VIEW_CAPTIONS['Measure overview']]
        return " ".join(p for p in parts if p) or None
    if view == "Recurrence":
        display = params.get('display')
        if display == "Boxplot by group":
            return RQA_MEASURE_CAPTIONS.get(params.get('measure'))
        return RQA_CAPTIONS.get(display)
    if view == "Statistics" and params.get('display') == "Boxplot by group":
        measure = params.get('measure', '')
        if measure.lower().startswith('k') or 'coefficient' in measure.lower():
            return CURVE_CAPTIONS["Ambient–Focal (K)"]
        return f"{measure} per participant, one box per group (median, quartiles, whiskers = 1.5 IQR)."
    if view == "Areas of Interest":
        display = params.get('display')
        if display == "Scarf plot":
            return "One row per participant; each fixation is a bar coloured by the area it fell in, grey = outside."
        if display == "Transition matrix":
            return ("Row = area the gaze left, column = area it entered next; counted between visits, so dwelling "
                    "inside an area is not a transition.")
        return None
    return None


def view_by_view_html():
    # The explainers concatenated, appended to the "Analyses explained" help page so both share one text
    return "<h2>View by view</h2>" + "".join(EXPLAINERS[view] for view in VIEW_SUMMARY)
