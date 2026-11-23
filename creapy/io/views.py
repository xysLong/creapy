import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as patches

import creapy
from creapy.stats import participant_table, group_comparison, show_group_boxplot, participants_over_stimuli
from creapy.stats.timeseries import value_series, show_smoothed_curve, split_by_group
from creapy.stats.recurrence import participant_rqa, show_recurrence_plot, default_radius
from creapy.stats.spectrum import (participant_periodogram, default_frequencies, show_periodogram, resample_regular,
                                   morlet_scalogram, show_scalogram, dominant_period)
from creapy.aoi.sequence import (transition_matrix, show_scarf_plot, show_transition_matrix, first_fixation_order,
                                 aoi_run_sequences, transition_counts)
from creapy.aoi.aoi import LabelAOI
from creapy.stats.descriptives import add_zero_rows
from creapy.stats.visits import (visit_table, episodes, stimulus_totals, stimulus_sequence, session_summary,
                                 show_visit_timeline, has_clock, area_visit_table, aoi_totals_over_stimuli, unit_summary)

DARK_BG = '#121212'
DARK_RC = {'text.color': 'white', 'axes.labelcolor': 'white', 'axes.edgecolor': 'white',
           'xtick.color': 'white', 'ytick.color': 'white', 'axes.titlecolor': 'white',
           'boxplot.boxprops.color': 'white', 'boxplot.capprops.color': 'white',
           'boxplot.whiskerprops.color': 'white', 'boxplot.flierprops.markeredgecolor': 'white',
           'legend.facecolor': '#1e2230', 'legend.edgecolor': '#4da3ff'}


GUI_BOXPLOT = {'box_color': '#2b3a55', 'median_color': '#4da3ff', 'point_color': 'white'}


class Hint(Exception):
    pass


def title_with_note(ax, text, ctx, **kwargs):
    note = ctx.get('note')
    ax.set_title(text + (f" · {note}" if note else ""), loc='left', fontsize=10, **kwargs)


def group_series(fix, sac, ctx):
    grouping = ctx.get('grouping')
    if not grouping or not ctx.get('per_group', True) or ctx.get('filtered_participants'):
        return [(None, fix, sac)]
    names = creapy.natural_sorted(set(grouping.values()))
    groups = {name: [s for s in fix.subjects if grouping.get(s) == name] for name in names}
    groups = {name: subs for name, subs in groups.items() if subs}
    if not groups:
        return [(None, fix, sac)]
    subset_fn = ctx.get('subset_fn')
    if subset_fn is not None:
        return [(name, *subset_fn(subs)) for name, subs in groups.items()]
    return split_by_group(fix, sac, grouping)


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
    ax.grid(color='#555a6a', alpha=0.6)
    sac.make_rose_plot(ax=ax, hull_args={'color': 'white', 'lw': 1.2}, **params)
    title_with_note(ax, f"Saccade directions · {sac.n_subjects()} participants", ctx, color='white')


def active_names(fix, ctx):
    """The ticked areas of this stimulus (ctx['names']), or every area when nothing was ticked off."""
    names = ctx.get('names')
    if names is None:
        return list(fix.areas_of_interest)
    return [n for n in names if n in fix.areas_of_interest]


def reference_of(names, ctx):
    ref = ctx.get('reference')
    return ref if ref in names else None


def prepare_aoi(fix, sac, params, ctx, progress):
    if params['display'] == 'Image with AOIs' and params['underlay'] == 'Fixation heatmap':
        fix.prepare_heatmap(bw_method=0.1, num_levels=20)


def draw_aoi(fix, sac, params, ctx, fig, ax):
    aois = fix.areas_of_interest
    names = active_names(fix, ctx)
    display = params['display']
    stim = ctx.get('stim', '')
    note = ctx.get('note')
    suffix = f" · {note}" if note else ""
    grouping = ctx.get('grouping')
    unit = 'visit' if fix.trial_col else 'viewing'
    if display != 'Image with AOIs' and not names:
        raise Hint("Draw an area of interest first: choose 'Draw rectangle', then click and drag on the image, or add "
                   "the areas of the export. Tick the areas that the tables should use.")
    if display in ('Transition matrix', 'Transitions per participant (table)', 'Area comparison (table)') and len(names) < 2:
        raise Hint("This needs at least two ticked areas.")
    if display == 'Metrics table':
        df_aoi = aoi_table(fix, ctx)
        ref = reference_of(names, ctx)
        return df_aoi, (f"<b>{stim}</b>: participant × area{suffix}. dwell_time in {fix.dur_unit}; dwell_share = share "
                        "of the participant's fixation time on this stimulus"
                        + (f"; dwell_share_of_reference = share of the time inside '{ref}'" if ref else "")
                        + "; dwell_per_area = dwell_share divided by the area's share of the image; "
                        "time_to_first_fixation in s; n_visits = runs of consecutive fixations inside; "
                        "mean_within_saccade_px = mean jump between two fixations inside; hit = fixated at all"
                        + ("; looked = False: no fixation on this stimulus at all." if ctx.get('roster') else "."))
    if display == 'Sequences (table)':
        df_runs = aoi_run_sequences(fix, names=names, min_run_s=params.get('min_run_s', 0.),
                                    bridge_gap_s=params.get('bridge_gap_s', 0.))
        if grouping:
            df_runs.insert(1, 'group', df_runs['participant'].astype(object).map(grouping))
        return df_runs, (f"<b>{stim}</b>: one row per participant and {unit}{suffix}. sequence = the ticked areas as "
                         "runs in viewing order; first_aoi = the area looked at first; n_switches = changes between "
                         f"areas; runs_/dwell_ per area (dwell in {fix.dur_unit}){sequence_rules(params)}.")
    if display == 'Transitions per participant (table)':
        df_tr = transition_counts(fix, names=names, include_outside=params.get('include_outside', False),
                                  min_run_s=params.get('min_run_s', 0.), bridge_gap_s=params.get('bridge_gap_s', 0.))
        if ctx.get('roster'):
            df_tr = add_zero_rows(df_tr, ctx['roster'], [c for c in df_tr.columns if c not in ('participant', 'trial')])
        if grouping or ctx.get('grouping_all'):
            df_tr.insert(1, 'group', df_tr['participant'].astype(object).map(grouping or ctx['grouping_all']))
        return df_tr, (f"<b>{stim}</b>: one row per participant and {unit}{suffix}. Every column 'A>B' counts how often "
                       "a run on B followed a run on A (directional; A>B and B>A differ); n_transitions = all changes "
                       f"between the ticked areas{sequence_rules(params)}"
                       + ("; 'outside' = looks outside every area." if params.get('include_outside') else "."))
    if display == 'Area comparison (table)':
        df_aoi = fix.aoi_metrics(names=names, reference=reference_of(names, ctx))
        columns = [c for c in ('dwell_time', 'dwell_share', 'dwell_share_of_reference', 'n_fixations', 'n_visits',
                               'mean_fixation_duration', 'dwell_per_area', 'time_to_first_fixation')
                   if c in df_aoi.columns and df_aoi[c].notna().any()]
        df_cmp = group_comparison(df_aoi, group_col='aoi', columns=columns, pairwise=True)
        return df_cmp, (f"<b>{stim}</b>: area against area over the same participants{suffix}. Two areas: paired "
                        "t-test and Wilcoxon with Cohen's dz and a 95 % CI of the mean difference; more areas: ANOVA "
                        "and Kruskal-Wallis in the first row of each measure, then every pair. Participants without "
                        "a fixation in an area count with 0 (NaN for time to first fixation). Exploratory: correct "
                        "for the number of tests before reporting.")
    if display == 'First-fixation order':
        df_order = first_fixation_order(fix, names=names)
        if grouping:
            df_order.insert(1, 'group', df_order['participant'].astype(object).map(grouping))
        return df_order, (f"<b>{stim}</b>: in which order each participant first looked at the ticked areas "
                          f"(1 = first){suffix}. Empty = never fixated.")
    if display == 'Transition matrix':
        matrix = transition_matrix(fix, names=names, normalize='row', include_outside=params.get('include_outside', False))
        im = show_transition_matrix(ax, matrix, cmap=params.get('cmap', 'Blues'))
        fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="share of departures from the row's area")
        title_with_note(ax, f"AOI transitions (between runs) · {fix.n_subjects()} participants", ctx)
        fig.tight_layout()
        return matrix.reset_index().rename(columns={'index': 'from'}), None
    if display == 'Scarf plot':
        df_seq = show_scarf_plot(ax, fix, names=names)
        title_with_note(ax, f"AOI sequence per participant · {fix.n_subjects()} participants", ctx)
        fig.tight_layout()
        return df_seq, None
    if params['underlay'] == 'Fixation heatmap':
        fix.make_heatmap(ax, grayscale=params['grayscale'], alpha=0.5, scatter_alpha=0.)
    else:
        fix.plot_setup(ax, bw=params['grayscale'])
        if params['underlay'] == 'Fixation points':
            ax.scatter(fix.fix_x, fix.fix_y, s=4, color='yellow', alpha=0.35)
    palette = plt.get_cmap('tab10')
    for i, (name, aoi) in enumerate(aois.items()):
        ticked = name in names
        alpha = params['alpha'] if ticked else params['alpha'] * 0.3
        if isinstance(aoi, LabelAOI):
            show_label_aoi(ax, fix, name, color=palette(i % 10), alpha=alpha, label=params['labels'] and ticked)
        else:
            aoi.show(ax, color=palette(i % 10), alpha=alpha, label=params['labels'] and ticked)
    return None


def sequence_rules(params):
    rules = []
    if params.get('min_run_s'):
        rules.append(f"runs under {params['min_run_s']:g} s dropped")
    if params.get('bridge_gap_s'):
        rules.append(f"looks outside up to {params['bridge_gap_s']:g} s bridged")
    return f"; {', '.join(rules)}" if rules else ""


def show_label_aoi(ax, fix, name, color, alpha=0.35, label=True):
    import matplotlib.patheffects as pe
    from shapely import MultiPoint
    mask = fix.aoi_mask(name)
    if not mask.any():
        return
    xx, yy = fix.fix_x.to_numpy()[mask], fix.fix_y.to_numpy()[mask]
    ax.scatter(xx, yy, s=6, color=color, alpha=min(1., alpha + 0.3), edgecolor='none', zorder=3)
    if mask.sum() >= 3:
        hull = MultiPoint(np.column_stack([xx, yy])).convex_hull
        if hull.geom_type == 'Polygon':
            hx, hy = hull.exterior.xy
            ax.fill(hx, hy, color=color, alpha=alpha * 0.5, lw=1.2, edgecolor=color, zorder=2)
    if label:
        ax.text(float(np.median(xx)), float(np.median(yy)), name, ha='center', va='center', color='black',
                fontsize=8, path_effects=[pe.Stroke(linewidth=3, foreground='white', alpha=0.8), pe.Normal()],
                zorder=4)


def aoi_table(fix, ctx):
    names = active_names(fix, ctx)
    df_aoi = fix.aoi_metrics(names=names, reference=reference_of(names, ctx))
    if ctx.get('roster'):
        df_aoi = add_zero_rows(df_aoi, ctx['roster'], ['n_fixations', 'n_visits', 'revisits', 'dwell_time'], per='aoi')
        df_aoi['hit'] = df_aoi['hit'].eq(True)
    grouping = ctx.get('grouping') or ctx.get('grouping_all')
    if grouping:
        df_aoi.insert(1, 'group', df_aoi['participant'].astype(object).map(grouping))
    return df_aoi


def all_datasets(ctx, progress=None):
    """Every stimulus of the dataset as {stimulus name -> (fix, sac)}, built on demand through ctx['all_datasets']."""
    fn = ctx.get('all_datasets')
    if fn is None:
        raise Hint("This table runs over every stimulus of the dataset and is only available in the application.")
    return fn(progress)


def names_of(ctx, fixes):
    """stimulus -> ticked areas, for tables over every stimulus."""
    chosen = ctx.get('names_of') or {}
    return {stim: [n for n in chosen.get(stim, list(fix.areas_of_interest)) if n in fix.areas_of_interest]
            for stim, (fix, _) in fixes.items()}


def area_rosters(ctx, roster):
    """area -> participants owing a zero row: the rosters of every stimulus that carries the ticked area."""
    members = {}
    for stim, names in names_of(ctx, all_datasets(ctx)).items():
        subjects = set(ctx['roster_of'].get(stim, roster))
        for name in names:
            members.setdefault(name, set()).update(subjects)
    return {name: [s for s in roster if s in subjects] for name, subjects in members.items()}


def visits_of(ctx, params, progress=None):
    subjects = ctx.get('subjects')
    if params.get('unit') == 'areas':
        fixes = all_datasets(ctx, progress)
        per_stim = names_of(ctx, fixes)
        if not any(per_stim.values()):
            raise Hint("No area is ticked on any stimulus. Draw areas in the view Areas of Interest or add the areas "
                       "of the export there (tick 'On every stimulus').")
        df_visits = area_visit_table({stim: fix for stim, (fix, _) in fixes.items()}, names=per_stim)
        if subjects is not None:
            df_visits = df_visits[df_visits['participant'].isin(list(subjects))]
        if len(df_visits) == 0:
            raise Hint("The selected participants never fixated a ticked area.")
        return df_visits
    df_all, mapping = ctx['table'], ctx['mapping']
    if subjects is not None:
        df_all = df_all[df_all[mapping['subj_index_col']].isin(list(subjects))]
    if len(df_all) == 0:
        raise Hint("The selected participants have no fixations in this dataset.")
    return visit_table(df_all, mapping)


def prepare_visits(fix, sac, params, ctx, progress):
    if params.get('unit') == 'areas':
        fixes = all_datasets(ctx, progress)
        per_stim = names_of(ctx, fixes)
        for i, (stim, (fix_, _)) in enumerate(fixes.items()):
            if progress(i, len(fixes), f"areas of {stim}") is False:
                raise InterruptedError
            for name in per_stim[stim]:
                fix_.aoi_mask(name)   # warms the label cache


def draw_visits(fix, sac, params, ctx, fig, ax):
    display = params['display']
    note = ctx.get('note')
    suffix = f" · {note}" if note else ""
    grouping = ctx.get('grouping_all') or ctx.get('grouping')
    areas = params.get('unit') == 'areas'
    unit, units = ('area', 'areas') if areas else ('stimulus', 'stimuli')
    df_visits = visits_of(ctx, params)
    clock = has_clock(df_visits)
    needs_clock = display in ('Timeline', 'Episodes (table)', 'Stimulus sequence (table)')
    if needs_clock and not clock:
        raise Hint("This export restarts its clock with every visit, so the order of visits across stimuli is "
                   "unknown.\n\nAnalysis > Add Recording Clock loads the AOI-based metrics export of the same "
                   "Pro Lab project, which states when every visit started. Totals per stimulus and the session "
                   "summary work without it.")
    df_episodes = episodes(df_visits, merge_gap_s=params.get('merge_gap_s', 0.)) if clock else None
    roster = ctx.get('roster')
    if ctx.get('subjects') is not None and roster:
        roster = [s for s in roster if s in set(ctx['subjects'])]
    df_events = ctx.get('events') if params.get('show_events', True) else None

    def with_group(df_):
        if grouping and 'participant' in df_.columns:
            df_.insert(1, 'group', df_['participant'].astype(object).map(grouping))
        return df_

    gap = params.get('merge_gap_s', 0.)
    gap_text = "joined whatever the pause" if gap is None else f"joined when paused at most {gap:g} s"
    area_note = (" Areas: a visit is a run of consecutive fixations inside a ticked area, on any snapshot (column "
                 "snapshot)." if areas else "")
    if display == 'Visits (table)':
        return with_group(df_visits), (f"One row per participant, {unit} and visit{suffix}. dwell_s = fixation time "
                                       "inside the visit; t_start_s / t_end_s on the recording clock"
                                       + ("" if clock else " (NaN: no clock attached)") + "; order = rank of the "
                                       f"visit in the participant's recording.{area_note}")
    if display == 'Episodes (table)':
        return with_group(df_episodes), (f"One row per stay at a {unit}{suffix}: consecutive visits of the same "
                                         f"{unit} {gap_text}. episode_of_stimulus 2 = first return; revisit = a "
                                         f"stay after a stay at another {unit}.{area_note}")
    if display in ('Totals per stimulus (table)', 'Summary per stimulus (table)'):
        roster_by_stim = roster
        if roster and ctx.get('roster_of'):
            kept = set(roster)
            roster_by_stim = area_rosters(ctx, roster) if areas else \
                {stim: [s_ for s_ in subs if s_ in kept] for stim, subs in ctx['roster_of'].items()}
        df_tot = stimulus_totals(df_visits, roster=roster_by_stim, df_episodes=df_episodes)
        if display == 'Summary per stimulus (table)':
            df_sum = unit_summary(df_tot)
            return df_sum, (f"One row per {unit}{suffix}: n_looked / share_looked = participants with a fixation on it"
                            + (" (of every participant of the dataset)" if roster else "")
                            + "; dwell_median / dwell_mean in s over everyone, *_looked over those who looked; "
                            "n_revisits_mean and share_revisited need the recording clock; n_rank_1 = for how many "
                            f"participants this was the longest-looked {unit}; share_of_total_dwell = its share of "
                            f"all fixation time on the listed {units}.{area_note}")
        return with_group(df_tot), (f"One row per participant and {unit}{suffix}. dwell_s = total fixation time; "
                                    "share_of_mapped = share of the participant's fixation time over all listed "
                                    f"{units}; rank 1 = the participant's longest-looked {unit}; n_visits = visits in "
                                    "the export; n_episodes / n_revisits / first_episode_s / later_episodes_s need "
                                    "the recording clock" + (f" (visits {gap_text})" if clock else " (NaN without it)")
                                    + ("; looked = False: never fixated (zeros)." if roster else ".") + area_note)
    if display == 'Session summary (table)':
        df_sum = session_summary(df_visits, df_episodes, df_events, roster=roster)
        return with_group(df_sum), (f"One row per participant{suffix}. span_s = first to last fixation mapped on any "
                                    f"{unit} of this dataset; mapped_s = time inside the visits; unmapped_s = the "
                                    "rest (walking, other walls, people); event_*_s = logged events where the export "
                                    f"carries them.{area_note}")
    if display == 'Stimulus sequence (table)':
        df_seq = stimulus_sequence(df_episodes)
        return with_group(df_seq), (f"One row per participant{suffix}: the {units} in the order of the stays "
                                    f"(visits {gap_text}); n_revisits = stays at a {unit} seen before.{area_note}")
    subjects = ctx.get('subjects') or creapy.natural_sorted(df_visits['participant'].unique())
    highlight = ctx.get('stim_value') if params.get('highlight') and not areas else None
    show_visit_timeline(ax, df_visits, subjects=list(subjects), relative=params.get('relative', True),
                        df_events=df_events, highlight=highlight)
    title_with_note(ax, f"Visits of {units} on the recording clock · {len(subjects)} participants", ctx)
    fig.tight_layout()
    return with_group(df_visits)


def curve_values(fix, sac, curve):
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
                    fix_.set_bottom_up_aoi()
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
    else:
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


def prepare_similarity(fix, sac, params, ctx, progress):
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
    table = None
    if view == 'Similarity Matrix':
        table = result.matshow(which=which, grouping=grouping, ax=ax, cmap=cmap, group_color='white')
        if grouping:
            ax.xaxis.tick_bottom()
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
    else:
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
        df_over = result.show_score_overview(grouping=ctx.get('grouping'), ax=ax)
        df_over['measure'] = df_over['measure'].str.replace('mm_', '', regex=False)
        ax.set_title("MultiMatch: the five dimensions of scanpath similarity", fontsize=10)
        fig.tight_layout()
        return df_over
    return draw_pairwise(result, None, params['view'] if params['view'] != 'Measure overview' else 'Similarity Matrix',
                         which, params['cmap'], ctx.get('grouping'), fig, ax, label=f"{labels[params['method']]} {which}")


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
    if not grouping or len(set(grouping.values())) < 2:
        raise Hint("Assign participants to at least two groups first (Analysis > Assign Participants to Groups).")
    measure = params['measure']
    show_group_boxplot(df_rqa, measure, ax=ax, **GUI_BOXPLOT)
    title_with_note(ax, f"{measure} by group · {stim}", ctx)
    fig.tight_layout()
    return df_rqa


ALL_STIMULI_DISPLAYS = ["All stimuli: participants (table)", "All stimuli: areas (table)",
                        "All stimuli: summary per stimulus (table)"]


def dataset_level(view_name, params):
    """True when the view's current display runs over every stimulus of the dataset, not the selected one."""
    return view_name == 'Visits' or (view_name == 'Statistics' and params.get('display') in ALL_STIMULI_DISPLAYS)


def prepare_statistics(fix, sac, params, ctx, progress):
    if params.get('display') not in ALL_STIMULI_DISPLAYS:
        return
    fixes = all_datasets(ctx, progress)
    if params.get('display') == 'All stimuli: areas (table)':
        per_stim = names_of(ctx, fixes)
        for i, (stim, (fix_, _)) in enumerate(fixes.items()):
            if progress(i, len(fixes), f"areas of {stim}") is False:
                raise InterruptedError
            if per_stim[stim]:
                fix_.aoi_metrics(names=per_stim[stim], reference=reference_of(per_stim[stim], ctx))   # warms the cache


def participant_rows(fix, sac, ctx):
    mobile = ctx.get('setting') == 'mobile'
    df_stats = participant_table(fix, None if mobile else sac, mobile=mobile)
    if ctx.get('roster'):
        df_stats = add_zero_rows(df_stats, ctx['roster'], ['n_fixations', 'n_visits', 'viewing_time_s',
                                                           'total_fixation_duration', 'n_saccades'])
    return df_stats


def draw_statistics(fix, sac, params, ctx, fig, ax):
    grouping = ctx.get('grouping')
    stim = ctx.get('stim', '')
    note = ctx.get('note')
    suffix = f" · {note}" if note else ""
    mobile = ctx.get('setting') == 'mobile'
    display = params['display']
    if display in ALL_STIMULI_DISPLAYS:
        return statistics_over_stimuli(display, ctx, suffix)
    df_stats = participant_rows(fix, sac, ctx)
    if ctx.get('roster'):
        grouping = ctx.get('grouping_all') or grouping
    if ctx.get('panel') and display == 'Group comparison (table)':
        df_stats.insert(1, 'group', ctx['panel'])   # the panels are the groups; main combines and tests them
        return df_stats, "panel"
    if grouping:
        df_stats.insert(1, 'group', df_stats['participant'].astype(object).map(grouping))
    measures = [c for c in df_stats.columns if c not in ('participant', 'group', 'looked')]
    if ctx.get('on_measures'):
        ctx['on_measures'](measures)
    if display == 'Participants (table)':
        if mobile:
            return df_stats, (f"<b>{stim}</b>: one row per participant{suffix}. n_visits = separate visits of this "
                              f"snapshot; viewing_time_s = time on the snapshot summed over the visits; durations in "
                              f"{fix.dur_unit}; positions and spread in snapshot pixels.")
        return df_stats, (f"<b>{stim}</b>: one row per participant{suffix}. Durations in {fix.dur_unit}, "
                          "distances in pixels.")
    if display == 'Group comparison (table)':
        if not grouping:
            raise Hint("Assign participants to groups first (Analysis > Assign Participants to Groups), or compare "
                       "stimuli with Analysis > Compare Side by Side: then the stimuli are the groups.")
        df_cmp = group_comparison(df_stats, grouping, columns=measures)
        return df_cmp, (f"<b>{stim}</b>: {COMPARISON_CAPTION}{suffix}")
    if display == 'AOI metrics (table)':
        if not active_names(fix, ctx):
            raise Hint("Draw or add areas of interest first (view 'Areas of Interest') and tick them.")
        df_aoi = aoi_table(fix, ctx)
        return df_aoi, (f"<b>{stim}</b>: participant × area{suffix}. dwell_time in {fix.dur_unit}; "
                        "time_to_first_fixation in s from the participant's first fixation"
                        + (" (visits counted one after another)" if mobile else "") + "; hit = fixated at all.")
    if not grouping:
        raise Hint("Assign participants to groups first (Analysis > Assign Participants to Groups).")
    measure = params['measure'] if params['measure'] in measures else measures[0]
    show_group_boxplot(df_stats, measure, ax=ax, **GUI_BOXPLOT)
    title_with_note(ax, f"{measure} by group · {stim}", ctx)
    fig.tight_layout()
    return df_stats


COMPARISON_CAPTION = ("n, mean, SD and median per group and the test per measure. Two groups of different people: "
                      "Welch t-test and Mann-Whitney U with Cohen's d, the rank-biserial r and a 95 % CI of the mean "
                      "difference; two groups of the same people: paired t-test and Wilcoxon with Cohen's dz; three or "
                      "more: one-way ANOVA and Kruskal-Wallis. Exploratory: correct for the number of tests before "
                      "reporting.")


def statistics_over_stimuli(display, ctx, suffix):
    fixes = all_datasets(ctx)
    mobile = ctx.get('setting') == 'mobile'
    roster = ctx.get('roster')
    grouping = ctx.get('grouping_all')
    subjects = ctx.get('subjects')

    def finish(df_):
        if subjects is not None and 'participant' in df_.columns:
            df_ = df_[df_['participant'].astype(object).isin(list(subjects))].reset_index(drop=True)
        if grouping and 'participant' in df_.columns:
            df_.insert(1, 'group', df_['participant'].astype(object).map(grouping))
        return df_

    if display == 'All stimuli: areas (table)':
        per_stim = names_of(ctx, fixes)
        if not any(per_stim.values()):
            raise Hint("No area is ticked on any stimulus. Draw areas in the view Areas of Interest or add the areas "
                       "of the export there (tick 'On every stimulus').")
        df_all = aoi_totals_over_stimuli({stim: fix for stim, (fix, _) in fixes.items()}, names=per_stim,
                                         roster=ctx.get('roster_of') if roster else None, reference=ctx.get('reference'))
        return finish(df_all), ("Every ticked area of every stimulus, one row per participant, stimulus and area"
                                f"{suffix}. share_of_areas = share of the participant's fixation time over all listed "
                                "areas; share_of_mapped = share of all their fixations on any stimulus; rank 1 = the "
                                "participant's longest-looked area; dwell_per_area = share per share of image"
                                + ("; looked = False: no fixation on that stimulus (zeros for the participants of "
                                   "that stimulus's condition when groups or the snapshot names tell it, else for "
                                   "everyone)." if roster else "."))
    df_all = participants_over_stimuli(fixes, mobile=mobile, roster=ctx.get('roster_of') if roster else None)
    dwell_col = 'viewing_time_s'
    if display == 'All stimuli: participants (table)':
        return finish(df_all), (f"One row per participant and stimulus{suffix}. {dwell_col} is the viewing time the "
                                "shares and ranks use: share_of_total = share of the participant's time over all "
                                "stimuli, rank 1 = their longest-viewed stimulus"
                                + ("; looked = False: no fixation on that stimulus (zeros)." if roster else "."))
    df_sum = unit_summary(finish(df_all), dwell_col=dwell_col)
    return df_sum, (f"One row per stimulus{suffix}: n_looked / share_looked = participants with a fixation on it"
                    + (" (of every participant of the dataset)" if roster else "") + f"; dwell_* = {dwell_col} over "
                    "everyone, *_looked over those who looked; n_rank_1 = for how many participants this was the "
                    "longest-viewed stimulus; share_of_total_dwell = its share of all viewing time in the dataset.")


def compare_panels_table(df_all):
    """Statistics compared side by side: the panels (stimuli, groups or time windows) become the groups of the test."""
    columns = [c for c in df_all.columns if c not in ('participant', 'group', 'looked', 'panel', 'stimulus')
               and pd.api.types.is_numeric_dtype(df_all[c])]
    return group_comparison(df_all, group_col='panel', columns=columns)


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
    "Statistics": (prepare_statistics, draw_statistics, 'plot'),
    "Visits": (prepare_visits, draw_visits, 'plot'),
}

SACCADE_VIEWS = ["Saccade Scanpath", "Saccade Heatmap", "Saccade Directions", "Saccade Similarity", "Time Series"]


def needs_saccades(view, setting='lab'):
    """True when the view cannot be drawn without saccades (a lone fixation on a stimulus has none)."""
    return view in SACCADE_VIEWS or (view == "Statistics" and setting != 'mobile')


COMPARABLE_VIEWS = ["Fixation Heatmap", "Fixation Scanpath", "Saccade Scanpath", "Saccade Heatmap",
                    "Saccade Directions", "Areas of Interest", "Statistics"]


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
