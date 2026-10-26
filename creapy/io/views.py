"""
The views of creapy.io as plain functions, free of Qt: prepare_*(fix, sac, params, ctx, progress) does the slow
numeric work (runs in a worker thread, fills the datasets' caches), draw_*(fix, sac, params, ctx, fig, ax) draws
from those caches on the GUI thread and may return a table (DataFrame). The main window, the compare grid and the
batch export all call the same functions, so a figure looks the same wherever it is produced.

ctx (a dict) carries what a view needs beyond its parameters: 'grouping' (subj -> group, restricted to the
dataset), 'note' (text describing the active filter), 'stim' (stimulus name), 'vmax' (shared heatmap scale or
None), 'dark' (dark theme colours), 'selected_subject' (the one participant of the filter bar, if any).
"""
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches

import creapy
from creapy.stats import participant_table, group_comparison, show_group_boxplot
from creapy.stats.timeseries import value_series, show_smoothed_curve, split_by_group
from creapy.stats.recurrence import participant_rqa, show_recurrence_plot, default_radius
from creapy.stats.spectrum import (participant_periodogram, default_frequencies, show_periodogram, resample_regular,
                                   morlet_scalogram, show_scalogram, dominant_period)
from creapy.aoi.sequence import transition_matrix, show_scarf_plot, show_transition_matrix, first_fixation_order

DARK_BG = '#121212'
DARK_RC = {'text.color': 'white', 'axes.labelcolor': 'white', 'axes.edgecolor': 'white',
           'xtick.color': 'white', 'ytick.color': 'white', 'axes.titlecolor': 'white',
           'boxplot.boxprops.color': 'white', 'boxplot.capprops.color': 'white',
           'boxplot.whiskerprops.color': 'white', 'boxplot.flierprops.markeredgecolor': 'white',
           'legend.facecolor': '#1e2230', 'legend.edgecolor': '#4da3ff'}


GUI_BOXPLOT = {'box_color': '#2b3a55', 'median_color': '#4da3ff', 'point_color': 'white'}  # dark-theme boxplots


class Hint(Exception):
    # Raised by a view when the user has to do something first (assign groups, draw an AOI ...):
    # shown as a friendly information box, not as a failure.
    pass


def title_with_note(ax, text, ctx, **kwargs):
    note = ctx.get('note')
    ax.set_title(text + (f" · {note}" if note else ""), loc='left', fontsize=10, **kwargs)


def group_series(fix, sac, ctx):
    # [(label, fix, sac)]: one entry per group when groups exist and the filter is not already one person/group
    grouping = ctx.get('grouping')
    if not grouping or not ctx.get('per_group', True) or ctx.get('filtered_participants'):
        return [(None, fix, sac)]
    names = creapy.natural_sorted(set(grouping.values()))
    groups = {name: [s for s in fix.subjects if grouping.get(s) == name] for name in names}
    groups = {name: subs for name, subs in groups.items() if subs}
    if not groups:
        return [(None, fix, sac)]
    subset_fn = ctx.get('subset_fn')  # the GUI caches subsets per (stimulus, selection)
    if subset_fn is not None:
        return [(name, *subset_fn(subs)) for name, subs in groups.items()]
    return split_by_group(fix, sac, grouping)


# =====================================================================================================
# Image views
# =====================================================================================================

def prepare_fixation_heatmap(fix, sac, params, ctx, progress):
    fix.prepare_heatmap(bw_method=params['bw_method'], num_levels=params['num_levels'], vmax=ctx.get('vmax'))


def draw_fixation_heatmap(fix, sac, params, ctx, fig, ax):
    params = {k: v for k, v in params.items() if k != 'shared_scale'}
    fix.make_heatmap(ax, vmax=ctx.get('vmax'), **params)


def draw_fixation_scanpath(fix, sac, params, ctx, fig, ax):
    fix.visualize_scanpath(ax, **params)


def draw_saccade_scanpath(fix, sac, params, ctx, fig, ax):
    sac.visualize_scanpaths(ax=ax, **params)


def prepare_saccade_heatmap(fix, sac, params, ctx, progress):
    sac.prepare_heatmap(params['sigma'])


def draw_saccade_heatmap(fix, sac, params, ctx, fig, ax):
    sac.make_heatmap(ax=ax, **params)


def draw_rose(fix, sac, params, ctx, fig, ax):
    # ax must be polar
    ax.grid(color='#555a6a', alpha=0.6)
    sac.make_rose_plot(ax=ax, hull_args={'color': 'white', 'lw': 1.2}, **params)
    title_with_note(ax, f"Saccade directions · {sac.n_subjects()} participants", ctx, color='white')


# =====================================================================================================
# Areas of interest
# =====================================================================================================

def prepare_aoi(fix, sac, params, ctx, progress):
    if params['display'] == 'Image with AOIs' and params['underlay'] == 'Fixation heatmap':
        fix.prepare_heatmap(bw_method=0.1, num_levels=20)


def draw_aoi(fix, sac, params, ctx, fig, ax):
    # returns a table for the table displays; the image display draws the AOIs over the chosen underlay
    aois = fix.areas_of_interest
    display = params['display']
    stim = ctx.get('stim', '')
    note = ctx.get('note')
    suffix = f" · {note}" if note else ""
    grouping = ctx.get('grouping')
    if display == 'Metrics table':
        if not aois:
            raise Hint("Draw an area of interest first: choose 'Draw rectangle', then click and drag on the image.")
        df_aoi = fix.aoi_metrics()
        if grouping:
            df_aoi.insert(1, 'group', df_aoi['participant'].astype(object).map(grouping))
        return df_aoi, (f"<b>{stim}</b>: participant × AOI{suffix}. dwell_time in {fix.dur_unit}; "
                        "time_to_first_fixation in s; n_visits = runs of consecutive fixations inside; NaN = never fixated.")
    if display == 'First-fixation order':
        if not aois:
            raise Hint("Draw areas of interest first.")
        df_order = first_fixation_order(fix)
        if grouping:
            df_order.insert(1, 'group', df_order['participant'].astype(object).map(grouping))
        return df_order, (f"<b>{stim}</b>: in which order each participant first looked at the areas "
                          f"(1 = first){suffix}. Empty = never fixated.")
    if display == 'Transition matrix':
        if len(aois) < 2:
            raise Hint("Transitions need at least two areas of interest.")
        matrix = transition_matrix(fix, normalize='row', include_outside=params.get('include_outside', False))
        im = show_transition_matrix(ax, matrix, cmap=params.get('cmap', 'Blues'))
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="share of departures from the row's AOI")
        title_with_note(ax, f"AOI transitions (between visits) · {fix.n_subjects()} participants", ctx)
        fig.tight_layout()
        return matrix.reset_index().rename(columns={'index': 'from'}), None
    if display == 'Scarf plot':
        if not aois:
            raise Hint("Draw areas of interest first: the scarf plot colours every fixation by its area.")
        df_seq = show_scarf_plot(ax, fix)
        title_with_note(ax, f"AOI sequence per participant · {fix.n_subjects()} participants", ctx)
        fig.tight_layout()
        return df_seq, None
    # Image with AOIs
    if params['underlay'] == 'Fixation heatmap':
        fix.make_heatmap(ax, grayscale=params['grayscale'], alpha=0.5, scatter_alpha=0.)
    else:
        fix.plot_setup(ax, bw=params['grayscale'])
        if params['underlay'] == 'Fixation points':
            ax.scatter(fix.fix_x, fix.fix_y, s=4, color='yellow', alpha=0.35)
    palette = plt.get_cmap('tab10')
    for i, (name, aoi) in enumerate(aois.items()):
        aoi.show(ax, color=palette(i % 10), alpha=params['alpha'], label=params['labels'])
    return None


# =====================================================================================================
# Time series + spectrum
# =====================================================================================================

def curve_values(fix, sac, curve):
    # (dataset the values belong to, values aligned with its df, y label): creapy.stats.timeseries.value_series
    # with the GUI's wording for the two optional columns
    if curve == 'Pupil Size' and fix.pupil_col is None:
        raise Hint("The imported table has no pupil column. Re-import and set the optional field "
                   "'Pupil size' to see this curve.")
    if curve == 'Viewing Distance' and 'distance_mm' not in fix.df.columns:
        raise Hint("No viewing distance in this dataset. Tobii glasses Data exports carry it (Gaze point 3D); "
                   "the event-based metrics export does not.")
    return value_series(fix, sac, curve)


def draw_time_series(fix, sac, params, ctx, fig, ax):
    curve, sigma, n_std = params['curve'], params['sigma'], params['n_std']
    display = params.get('display', 'Curve over time')
    series = group_series(fix, sac, dict(ctx, per_group=params.get('per_group', True)))
    palette = plt.get_cmap('tab10')
    table = None
    if display == 'Curve over time':
        for i, (label, fix_, sac_) in enumerate(series):
            color = palette(i % 10)
            if curve == 'Fixations in AOIs':
                if not fix_.areas_of_interest:
                    fix_.set_bottom_up_aoi()  # default AOI: the most-viewed heatmap regions
                    if ctx.get('on_default_aoi'):
                        ctx['on_default_aoi'](fix_)
                fix_.make_aoi_percentage_curve(None, ax, sigma=sigma, n_std=n_std, color=color if label else None)
                ax.set_ylabel("Share of fixations inside the AOIs")
            else:
                data, values, ylabel = curve_values(fix_, sac_, curve)
                show_smoothed_curve(ax, data, values, sigma, n_std, color, label)
                ax.set_ylabel(ylabel)
                if curve == 'Ambient–Focal (K)':
                    ax.axhline(0, color='#888888', lw=0.8, ls=':')
        ax.set_xlabel("Viewing time (s)")
        title_with_note(ax, f"{curve} · {fix.n_subjects()} participants", ctx)
    elif display == 'Periodogram':
        if curve == 'Fixations in AOIs':
            raise Hint("The periodogram needs a per-fixation value: choose fixation duration, saccade amplitude, "
                       "K, pupil size or viewing distance.")
        ls = []
        for i, (label, fix_, sac_) in enumerate(series):
            data, values, ylabel = curve_values(fix_, sac_, curve)
            df_power = participant_periodogram(data, values=values)
            show_periodogram(ax, df_power, color=palette(i % 10), label=label or 'mean over participants',
                             individual_alpha=0.12 if len(series) == 1 else 0.)
            df_dom = dominant_period(df_power)
            if label:
                df_dom.insert(1, 'group', label)
            ls.append(df_dom)
        ax.set_ylabel("Normalised Lomb–Scargle power")
        title_with_note(ax, f"Rhythm in {curve.lower()} · {fix.n_subjects()} participants", ctx)
        table = pd.concat(ls, ignore_index=True)
    else:  # Scalogram
        if curve == 'Fixations in AOIs':
            raise Hint("The scalogram needs a per-fixation value: choose fixation duration, saccade amplitude, "
                       "K, pupil size or viewing distance.")
        data, values, ylabel = curve_values(fix, sac, curve)
        ok = np.isfinite(values)
        t_new, v_new = resample_regular(data.t.to_numpy()[ok], values[ok], step=0.05, sigma=max(sigma / 4., 0.1),
                                        weights=np.asarray(data.weights_simple)[ok])
        span = max(t_new[-1] - t_new[0], 2.)
        freqs = default_frequencies(span, n=80)
        power = morlet_scalogram(t_new, v_new, freqs)
        mesh = show_scalogram(ax, t_new, freqs, power)
        fig.colorbar(mesh, ax=ax, fraction=0.046, pad=0.04, label="wavelet power")
        ax.set_xlabel("Viewing time (s)")
        title_with_note(ax, f"Time–frequency map of {curve.lower()} (mean curve) · {fix.n_subjects()} participants", ctx)
    if len(series) > 1 and display != 'Scalogram':
        ax.legend(title="Group")
    fig.tight_layout()
    return table


# =====================================================================================================
# Pairwise similarity (HeatMatch saccades, scanpath comparison)
# =====================================================================================================

def prepare_similarity(fix, sac, params, ctx, progress):
    # Fills the SaccadeData caches; returns nothing (draw_similarity reads the caches again, instantly)
    if sac.n_subjects() < 2:
        raise Hint("Similarity analysis needs saccades from at least two participants: "
                   "select a group or all participants in the Show bar.")
    if params['view'] == 'Similarity over Time':
        span = sac.t_max - sac.t_min
        step = span / (params['n_windows'] + 1)
        sac.compute_heatmatch_similarity_profile(window=2 * step, step=step, sigma=params['sigma'],
                                                 density_coherence_tradeoff=params['density_coherence_tradeoff'],
                                                 verbose=False, progress=progress)
    else:
        result = sac.compute_heatmatch_similarity(sigma=params['sigma'],
                                                  density_coherence_tradeoff=params['density_coherence_tradeoff'],
                                                  verbose=False, progress=progress)
        if params['view'] == 'Group Boxplot' and ctx.get('grouping'):
            result.permutation_test(ctx['grouping'], which=params['which'], verbose=False)


def draw_pairwise(result, profile, view, which, cmap, grouping, fig, ax, label):
    # Shared by the HeatMatch and the scanpath comparison views
    table = None
    if view == 'Similarity Matrix':
        table = result.matshow(which=which, grouping=grouping, ax=ax, cmap=cmap, group_color='white')
        if grouping:
            ax.xaxis.tick_bottom()  # free the top edge for the group brackets
        table = table.reset_index()
    elif view == 'Group Boxplot':
        if not grouping or len(set(grouping.values())) < 2:
            raise Hint("The group boxplot compares similarity within and between groups.\n\n"
                       'Please click "Assign Groups..." first and assign at least two groups.')
        stats = result.permutation_test(grouping, which=which, verbose=False)
        result.show_boxplot(grouping, which=which, ax=ax)
        p_text = "p < 0.001" if stats['p_value'] < 0.001 else f"p = {stats['p_value']:.3f}"
        ax.set_title(f"{label}: within groups {stats['within_mean']:.3f} vs. between groups {stats['between_mean']:.3f}\n"
                     f"{p_text} (one-sided permutation test, {stats['n_permutations']:,} permutations)", fontsize=10)
        table = pd.DataFrame([stats])
    elif view == 'Similarity over Time':
        curves = profile.show_profile(which=which, grouping=grouping, ax=ax)
        table = pd.concat([df_.assign(curve=name) for name, df_ in curves.items()]).reset_index()
    else:  # Viewer Map (MDS)
        result.show_multidimensional_scaling(grouping=grouping, which=which, ax=ax)
        ax.set_title(f"{label}: participants placed by similarity (spectral embedding)", fontsize=10)
    fig.tight_layout()
    return table


def draw_similarity(fix, sac, params, ctx, fig, ax):
    grouping = ctx.get('grouping')
    result = profile = None
    if params['view'] == 'Similarity over Time':
        span = sac.t_max - sac.t_min
        step = span / (params['n_windows'] + 1)
        profile = sac.compute_heatmatch_similarity_profile(window=2 * step, step=step, sigma=params['sigma'],
                                                           density_coherence_tradeoff=params['density_coherence_tradeoff'],
                                                           verbose=False)
    else:
        result = sac.compute_heatmatch_similarity(sigma=params['sigma'],
                                                  density_coherence_tradeoff=params['density_coherence_tradeoff'],
                                                  verbose=False)
    return draw_pairwise(result, profile, params['view'], params['which'], params['cmap'], grouping, fig, ax,
                         label=f"HeatMatch {params['which']}")


SCANPATH_KWARGS = {'multimatch': [], 'scanmatch': ['grid', 'temporal_bin'], 'cross_recurrence': ['radius']}


def scanpath_kwargs(fix, params):
    method = params['method']
    kwargs = {}
    if method == 'scanmatch':
        kwargs['grid'] = (params['grid_cols'], params['grid_rows'])
        kwargs['temporal_bin'] = params['temporal_bin']
    elif method == 'cross_recurrence':
        kwargs['radius'] = float(params['radius_share'] * np.hypot(fix.width, fix.height))
    return kwargs


def prepare_scanpath_comparison(fix, sac, params, ctx, progress):
    if fix.n_subjects() < 2:
        raise Hint("Scanpath comparison needs at least two participants: select a group or all participants.")
    result = fix.compute_scanpath_similarity(method=params['method'], verbose=False, progress=progress,
                                             **scanpath_kwargs(fix, params))
    if params['view'] == 'Group Boxplot' and ctx.get('grouping') and len(set(ctx['grouping'].values())) >= 2:
        result.permutation_test(ctx['grouping'], which=params['which'] if params['which'] in result.scores
                                else result.default_score(), verbose=False)


def draw_scanpath_comparison(fix, sac, params, ctx, fig, ax):
    result = fix.compute_scanpath_similarity(method=params['method'], verbose=False, **scanpath_kwargs(fix, params))
    which = params['which'] if params['which'] in result.scores else result.default_score()
    labels = {'multimatch': 'MultiMatch', 'scanmatch': 'ScanMatch', 'cross_recurrence': 'Cross-recurrence'}
    if params['view'] == 'Measure overview' and params['method'] == 'multimatch':
        # the five MultiMatch dimensions side by side: mean over all pairs (and within/between groups if any)
        df_over = result.show_score_overview(grouping=ctx.get('grouping'), ax=ax)
        df_over['measure'] = df_over['measure'].str.replace('mm_', '', regex=False)
        ax.set_title("MultiMatch: the five dimensions of scanpath similarity", fontsize=10)
        fig.tight_layout()
        return df_over
    return draw_pairwise(result, None, params['view'] if params['view'] != 'Measure overview' else 'Similarity Matrix',
                         which, params['cmap'], ctx.get('grouping'), fig, ax, label=f"{labels[params['method']]} {which}")


# =====================================================================================================
# Recurrence
# =====================================================================================================

def draw_recurrence(fix, sac, params, ctx, fig, ax):
    radius = float(params['radius_share'] * np.hypot(fix.width, fix.height))
    grouping = ctx.get('grouping')
    stim = ctx.get('stim', '')
    if params['display'] == 'Recurrence plot (one participant)':
        subjects = fix.subjects
        subj = ctx.get('selected_subject') if ctx.get('selected_subject') in subjects else subjects[0]
        mask = (fix.subj_index == subj).to_numpy()
        xy = np.column_stack([fix.fix_x[mask].to_numpy(), fix.fix_y[mask].to_numpy()])
        show_recurrence_plot(ax, xy, radius)
        from creapy.stats.recurrence import rqa_measures
        m = rqa_measures(xy, radius, min_line=params['min_line'])
        ax.set_title(f"Recurrence plot of {subj} · REC {m['recurrence']:.1f} %, DET {m['determinism']:.0f} %, "
                     f"LAM {m['laminarity']:.0f} %, CORM {m['corm']:.0f} · radius {radius:.0f} px"
                     + (" (select one participant in the Show bar to change)" if len(subjects) > 1 else ""),
                     fontsize=9, loc='left')
        fig.tight_layout()
        return None
    df_rqa = participant_rqa(fix, radius=radius, min_line=params['min_line'])
    if grouping:
        df_rqa.insert(1, 'group', df_rqa['participant'].astype(object).map(grouping))
    if params['display'] == 'RQA table':
        return df_rqa, (f"<b>{stim}</b>: recurrence quantification per participant (Anderson et al. 2013), radius "
                        f"{radius:.0f} px, minimum line {params['min_line']}. recurrence = % of fixation pairs "
                        "that re-visit a location; determinism = % of recurrences in repeated sequences; "
                        "laminarity = % in dwell clusters; corm = how late revisits happen (0–100).")
    # Boxplot by group
    if not grouping or len(set(grouping.values())) < 2:
        raise Hint("Assign participants to at least two groups first (Analysis > Assign Participants to Groups).")
    measure = params['measure']
    show_group_boxplot(df_rqa, measure, ax=ax, **GUI_BOXPLOT)
    title_with_note(ax, f"{measure} by group · {stim}", ctx)
    fig.tight_layout()
    return df_rqa


# =====================================================================================================
# Statistics
# =====================================================================================================

def draw_statistics(fix, sac, params, ctx, fig, ax):
    grouping = ctx.get('grouping')
    stim = ctx.get('stim', '')
    note = ctx.get('note')
    suffix = f" · {note}" if note else ""
    df_stats = participant_table(fix, sac)
    if grouping:
        df_stats.insert(1, 'group', df_stats['participant'].astype(object).map(grouping))
    measures = [c for c in df_stats.columns if c not in ('participant', 'group')]
    if ctx.get('on_measures'):
        ctx['on_measures'](measures)
    display = params['display']
    if display == 'Participants (table)':
        return df_stats, (f"<b>{stim}</b>: one row per participant{suffix}. Durations in {fix.dur_unit}, "
                          "distances in pixels.")
    if display == 'Group comparison (table)':
        if not grouping:
            raise Hint("Assign participants to groups first (Analysis > Assign Participants to Groups).")
        df_cmp = group_comparison(df_stats, grouping, columns=measures)
        return df_cmp, (f"<b>{stim}</b>: group means ± SD and tests per measure{suffix}. "
                        "Two groups: Welch t-test and Mann–Whitney U; more: one-way ANOVA. "
                        "Exploratory: correct for multiple comparisons before reporting.")
    if display == 'AOI metrics (table)':
        if not fix.areas_of_interest:
            raise Hint("Draw areas of interest first (view 'Areas of Interest').")
        df_aoi = fix.aoi_metrics()
        if grouping:
            df_aoi.insert(1, 'group', df_aoi['participant'].astype(object).map(grouping))
        return df_aoi, (f"<b>{stim}</b>: participant × AOI{suffix}. dwell_time in {fix.dur_unit}; "
                        "time_to_first_fixation in s from the participant's first fixation; NaN = never fixated.")
    # Boxplot by group
    if not grouping:
        raise Hint("Assign participants to groups first (Analysis > Assign Participants to Groups).")
    measure = params['measure'] if params['measure'] in measures else measures[0]
    show_group_boxplot(df_stats, measure, ax=ax, **GUI_BOXPLOT)
    title_with_note(ax, f"{measure} by group · {stim}", ctx)
    fig.tight_layout()
    return df_stats


# =====================================================================================================
# Registry
# =====================================================================================================

# name -> (prepare or None, draw, kind) ; kind: 'image' (stimulus axes, no frame), 'plot' (dark axes), 'polar'
VIEW_SPECS = {
    "Fixation Heatmap": (prepare_fixation_heatmap, draw_fixation_heatmap, 'image'),
    "Fixation Scanpath": (None, draw_fixation_scanpath, 'image'),
    "Saccade Scanpath": (None, draw_saccade_scanpath, 'image'),
    "Saccade Heatmap": (prepare_saccade_heatmap, draw_saccade_heatmap, 'image'),
    "Saccade Directions": (None, draw_rose, 'polar'),
    "Areas of Interest": (prepare_aoi, draw_aoi, 'aoi'),
    "Time Series": (None, draw_time_series, 'plot'),
    "Saccade Similarity": (prepare_similarity, draw_similarity, 'plot'),
    "Scanpath Comparison": (prepare_scanpath_comparison, draw_scanpath_comparison, 'plot'),
    "Recurrence": (None, draw_recurrence, 'plot'),
    "Statistics": (None, draw_statistics, 'plot'),
}

# Views whose figure can be laid out as a grid of panels (compare mode / multi-stimulus overview)
COMPARABLE_VIEWS = ["Fixation Heatmap", "Fixation Scanpath", "Saccade Scanpath", "Saccade Heatmap",
                    "Saccade Directions", "Areas of Interest"]


def axes_kind(view, params):
    kind = VIEW_SPECS[view][2]
    if kind == 'aoi':
        return 'image' if params.get('display') == 'Image with AOIs' else 'plot'
    return kind


def new_axes(fig, kind, position=(1, 1, 1)):
    if kind == 'polar':
        ax = fig.add_subplot(*position, projection='polar')
        ax.set_facecolor(DARK_BG)
    elif kind == 'plot':
        ax = fig.add_subplot(*position)
        ax.set_facecolor(DARK_BG)
    else:
        ax = fig.add_subplot(*position)
        ax.axis('off')
    return ax
