import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.collections import PolyCollection
from creapy.misc.utils import natural_sorted


def visit_table(df, mapping):
    """One row per participant, stimulus and visit (trial): fixations, dwell_s and, with t_abs, start and end (s) on the recording clock.

    `df` is the whole fixation table of a mobile recording (all stimuli), `mapping` its column mapping. Without a
    trial column every participant has one visit per stimulus. t_start_s / t_end_s are NaN unless the table carries
    t_abs (see creapy.formats.tobii.attach_intervals); order is the rank of the visit in the participant's
    recording and needs t_abs too."""
    subj_col, stim_col = mapping['subj_index_col'], mapping['stim_col']
    trial_col = mapping.get('trial_col')
    df_ = pd.DataFrame({'participant': df[subj_col].to_numpy(), 'stimulus': df[stim_col].astype(str).to_numpy(),
                        'trial': df[trial_col].to_numpy() if trial_col and trial_col in df.columns else 1,
                        'dur': pd.to_numeric(df[mapping['fix_dur_col']], errors='coerce').to_numpy(),
                        't_abs': pd.to_numeric(df['t_abs'], errors='coerce').to_numpy() if 't_abs' in df.columns else np.nan})
    to_s = 1000. if np.nanmedian(df_['dur']) > 5 else 1.
    df_['end'] = df_['t_abs'] + df_['dur']
    grouped = df_.groupby(['participant', 'stimulus', 'trial'], sort=False)
    df_visits = grouped.agg(n_fixations=('dur', 'size'), dwell=('dur', 'sum'), t_start=('t_abs', 'min'),
                            t_end=('end', 'max')).reset_index()
    df_visits['dwell_s'] = df_visits['dwell'] / to_s
    df_visits['t_start_s'] = df_visits['t_start'] / 1000.
    df_visits['t_end_s'] = df_visits['t_end'] / 1000.
    df_visits = df_visits.drop(columns=['dwell', 't_start', 't_end'])
    df_visits['order'] = df_visits.groupby('participant')['t_start_s'].rank(method='first')
    df_visits = df_visits.sort_values(['participant', 't_start_s', 'stimulus', 'trial'], na_position='last')
    return df_visits.reset_index(drop=True)


def has_clock(df_visits):
    """True when the visits carry start times on the recording clock (t_abs was attached)."""
    return 't_start_s' in df_visits.columns and df_visits['t_start_s'].notna().any()


def episodes(df_visits, merge_gap_s=0.):
    """Visits in recording order, merged into episodes: one episode = one stay at a stimulus.

    Two visits of the same stimulus join one episode when no other stimulus was looked at in between and the pause
    between them is at most merge_gap_s (None: whatever the pause). episode_no counts a participant's episodes,
    episode_of_stimulus the episodes at that stimulus (2 = first return), revisit = episode_of_stimulus > 1. Needs
    the recording clock."""
    assert has_clock(df_visits), "episodes need the recording clock (t_start_s): attach the interval times first"
    ls = []
    for subj, df_ in df_visits.dropna(subset=['t_start_s']).sort_values('t_start_s').groupby('participant', sort=False):
        stim = df_['stimulus'].to_numpy()
        start = df_['t_start_s'].to_numpy(dtype=float)
        end = df_['t_end_s'].to_numpy(dtype=float)
        new = np.ones(len(df_), dtype=bool)
        for i in range(1, len(df_)):
            same = stim[i] == stim[i - 1]
            new[i] = not (same and (merge_gap_s is None or start[i] - end[i - 1] <= merge_gap_s))
        ep_id = np.cumsum(new)
        df_ep = df_.assign(ep=ep_id).groupby('ep', sort=False).agg(
            participant=('participant', 'first'), stimulus=('stimulus', 'first'), n_visits=('trial', 'size'),
            n_fixations=('n_fixations', 'sum'), dwell_s=('dwell_s', 'sum'),
            t_start_s=('t_start_s', 'min'), t_end_s=('t_end_s', 'max')).reset_index(drop=True)
        df_ep['episode_no'] = np.arange(1, len(df_ep) + 1)
        df_ep['episode_of_stimulus'] = df_ep.groupby('stimulus').cumcount() + 1
        ls.append(df_ep)
    if not ls:
        return pd.DataFrame(columns=['participant', 'stimulus', 'n_visits', 'n_fixations', 'dwell_s', 't_start_s',
                                     't_end_s', 'episode_no', 'episode_of_stimulus', 'revisit'])
    df_episodes = pd.concat(ls, ignore_index=True)
    df_episodes['revisit'] = df_episodes['episode_of_stimulus'] > 1
    return df_episodes


def stimulus_totals(df_visits, roster=None, df_episodes=None):
    """Participant x stimulus: total dwell_s, fixations, visits, episodes and revisits; zero rows for a roster.

    `roster` lists every participant of the dataset: those who never looked at a stimulus get a row with zeros
    (looked = False), which keeps them in the denominators; a dict stimulus -> participants gives every stimulus its
    own roster (the visitors of its condition). Episodes and revisits are filled from df_episodes
    (see episodes()); without the recording clock they are NaN. share_of_mapped is the stimulus's share of the
    participant's fixation time over all stimuli, rank 1 the longest-looked stimulus of that participant."""
    df_tot = df_visits.groupby(['participant', 'stimulus'], sort=False).agg(
        n_visits=('trial', 'size'), n_fixations=('n_fixations', 'sum'), dwell_s=('dwell_s', 'sum'),
        first_visit_s=('t_start_s', 'min')).reset_index()
    if df_episodes is not None and len(df_episodes):
        df_ep = df_episodes.groupby(['participant', 'stimulus'], sort=False).agg(
            n_episodes=('episode_no', 'size'), n_revisits=('revisit', 'sum'),
            first_episode_s=('dwell_s', 'first')).reset_index()
        df_ep['later_episodes_s'] = df_episodes[df_episodes['revisit']].groupby(['participant', 'stimulus'])['dwell_s'] \
            .sum().reindex(pd.MultiIndex.from_frame(df_ep[['participant', 'stimulus']])).fillna(0.).to_numpy()
        df_tot = df_tot.merge(df_ep, on=['participant', 'stimulus'], how='left')
    else:
        df_tot['n_episodes'] = np.nan
        df_tot['n_revisits'] = np.nan
    df_tot['looked'] = True
    if roster is not None:
        stimuli = set(df_visits['stimulus'].unique()) | (set(roster) if isinstance(roster, dict) else set())
        full = pd.DataFrame.from_records([{'participant': subj, 'stimulus': stim} for stim in natural_sorted(stimuli)
                                          for subj in roster_of(roster, stim)], columns=['participant', 'stimulus'])
        df_tot = full.merge(df_tot, on=['participant', 'stimulus'], how='left')
        zero = df_tot['looked'].isna()
        df_tot.loc[zero, ['n_visits', 'n_fixations', 'dwell_s']] = 0
        df_tot['first_visit_s'] = pd.to_numeric(df_tot['first_visit_s'], errors='coerce')
        if df_episodes is not None and len(df_episodes):
            df_tot.loc[zero, ['n_episodes', 'n_revisits', 'later_episodes_s']] = 0
        df_tot['looked'] = df_tot['looked'].eq(True)
    for col in ['n_visits', 'n_fixations']:
        df_tot[col] = df_tot[col].astype(int)
    df_tot['share_of_mapped'] = df_tot['dwell_s'] / df_tot.groupby('participant')['dwell_s'].transform('sum').replace(0., np.nan)
    df_tot['rank'] = df_tot.groupby('participant')['dwell_s'].rank(method='min', ascending=False).where(df_tot['dwell_s'] > 0)
    return df_tot.reset_index(drop=True)


def area_visit_table(fixes, names=None):
    """Visits of areas instead of snapshots: one row per participant, area and run of consecutive fixations inside.

    `fixes` maps stimulus -> FixationData (every snapshot of the room); `names` restricts the areas, as one list for
    all stimuli or a dict stimulus -> list (default: every area of every dataset). The table has the columns of visit_table() with the area as `stimulus` and the run as
    `trial`, so episodes(), stimulus_totals(), stimulus_sequence() and session_summary() work on areas too. Start and
    end times come from t_abs where the datasets carry it (see attach_intervals), else NaN. A fixation inside two
    overlapping areas counts for both."""
    ls = []
    for stim, fix in fixes.items():
        area_names = names.get(stim) if isinstance(names, dict) else names
        area_names = list(fix.areas_of_interest) if area_names is None else area_names
        area_names = [n for n in area_names if n in fix.areas_of_interest]
        if not area_names:
            continue
        subj = fix.subj_index.to_numpy()
        segment = fix.segments()
        dur = fix.fix_dur.to_numpy(dtype=float)
        to_s = 1000. if fix.dur_unit == 'ms' else 1.
        t_abs = pd.to_numeric(fix.df['t_abs'], errors='coerce').to_numpy(dtype=float) if 't_abs' in fix.df.columns \
            else np.full(len(fix.df), np.nan)
        for name in area_names:
            inside = np.asarray(fix.aoi_mask(name), dtype=bool)
            if not inside.any():
                continue
            new_run = inside & ~(np.r_[False, inside[:-1]] & np.r_[False, segment[1:] == segment[:-1]]
                                 & np.r_[False, subj[1:] == subj[:-1]])
            run_id = np.cumsum(new_run)
            df_ = pd.DataFrame({'participant': subj[inside], 'run': run_id[inside], 'dur': dur[inside],
                                't_abs': t_abs[inside], 'end': t_abs[inside] + dur[inside]})
            df_runs = df_.groupby(['participant', 'run'], sort=False).agg(
                n_fixations=('dur', 'size'), dwell=('dur', 'sum'), t_start=('t_abs', 'min'), t_end=('end', 'max')).reset_index()
            df_runs['stimulus'] = name
            df_runs['snapshot'] = str(stim)
            ls.append(df_runs)
    if not ls:
        return pd.DataFrame(columns=['participant', 'stimulus', 'trial', 'snapshot', 'n_fixations', 'dwell_s', 't_start_s',
                                     't_end_s', 'order'])
    df_visits = pd.concat(ls, ignore_index=True)
    df_visits['trial'] = df_visits.groupby(['participant', 'stimulus']).cumcount() + 1
    to_s = 1000. if np.nanmedian(df_visits['dwell'] / df_visits['n_fixations']) > 5 else 1.
    df_visits['dwell_s'] = df_visits['dwell'] / to_s
    df_visits['t_start_s'] = df_visits['t_start'] / 1000.
    df_visits['t_end_s'] = df_visits['t_end'] / 1000.
    df_visits = df_visits.drop(columns=['run', 'dwell', 't_start', 't_end'])
    df_visits['order'] = df_visits.groupby('participant')['t_start_s'].rank(method='first')
    df_visits = df_visits.sort_values(['participant', 't_start_s', 'stimulus', 'trial'], na_position='last')
    return df_visits[['participant', 'stimulus', 'trial', 'snapshot', 'n_fixations', 'dwell_s', 't_start_s', 't_end_s',
                      'order']].reset_index(drop=True)


def aoi_totals_over_stimuli(fixes, names=None, roster=None, reference=None):
    """The AOI table of every stimulus in one: participant x stimulus x area, with shares and ranks over the whole room.

    share_of_areas relates an area's dwell to the participant's dwell over all listed areas of all stimuli,
    share_of_mapped to all their fixations on any stimulus; rank 1 is the participant's longest-looked area. With a
    `roster` (a list, or a dict stimulus -> participants) every participant gets a row per area, zeros where they
    never looked (looked = False)."""
    from creapy.stats.descriptives import add_zero_rows
    ls = []
    mapped = {}
    for stim, fix in fixes.items():
        area_names = names.get(stim) if isinstance(names, dict) else names
        area_names = list(fix.areas_of_interest) if area_names is None else area_names
        area_names = [n for n in area_names if n in fix.areas_of_interest]
        total = fix.fix_dur.groupby(fix.subj_index.to_numpy()).sum()
        for subj, value in total.items():
            mapped[subj] = mapped.get(subj, 0.) + float(value)
        if not area_names:
            continue
        df_ = fix.aoi_metrics(names=area_names, reference=reference if reference in area_names else None)
        if roster is not None:
            df_ = add_zero_rows(df_, roster_of(roster, stim), ['n_fixations', 'n_visits', 'revisits', 'dwell_time'], per='aoi')
            df_['hit'] = df_['hit'].eq(True)
        df_.insert(1, 'stimulus', str(stim))
        ls.append(df_)
    if not ls:
        return pd.DataFrame(columns=['participant', 'stimulus', 'aoi'])
    df_all = pd.concat(ls, ignore_index=True)
    by_subj = df_all.groupby('participant')['dwell_time'].transform('sum')
    df_all['share_of_areas'] = df_all['dwell_time'] / by_subj.replace(0., np.nan)
    df_all['share_of_mapped'] = df_all['dwell_time'] / df_all['participant'].map(mapped).replace(0., np.nan)
    df_all['rank'] = df_all.groupby('participant')['dwell_time'].rank(method='min', ascending=False).where(df_all['dwell_time'] > 0)
    order = {s: i for i, s in enumerate(natural_sorted(df_all['participant'].astype(object).unique()))}
    df_all['_o'] = df_all['participant'].astype(object).map(order)
    return df_all.sort_values(['_o', 'stimulus', 'aoi'], kind='stable').drop(columns='_o').reset_index(drop=True)


def roster_of(roster, stim):
    """The participants a zero row is owed for `stim`: the list itself, or the entry of a dict stimulus -> list."""
    if isinstance(roster, dict):
        return list(roster.get(str(stim), roster.get(stim, [])))
    return list(roster)


def unit_summary(df_totals, unit_col='stimulus', dwell_col='dwell_s'):
    """One row per stimulus (or area): how many participants looked, median and mean dwell, visits and revisits.

    Takes stimulus_totals() or aoi_totals_over_stimuli() output (one row per participant and unit, zero rows
    included when they were requested). dwell_* over everyone, dwell_*_looked over those who looked."""
    keys = [unit_col] if unit_col == 'stimulus' or 'stimulus' not in df_totals.columns else ['stimulus', unit_col]
    ls = []
    for unit, df_ in df_totals.groupby(keys, sort=False):
        looked = df_[df_[dwell_col] > 0]
        row = dict(zip(keys, unit if isinstance(unit, tuple) else (unit,)))
        row.update({'n_participants': int(len(df_)), 'n_looked': int(len(looked)),
                    'share_looked': float(len(looked) / len(df_)) if len(df_) else np.nan,
                    'dwell_median': float(df_[dwell_col].median()), 'dwell_mean': float(df_[dwell_col].mean()),
                    'dwell_sum': float(df_[dwell_col].sum()),
                    'dwell_median_looked': float(looked[dwell_col].median()) if len(looked) else np.nan,
                    'dwell_mean_looked': float(looked[dwell_col].mean()) if len(looked) else np.nan})
        for col in ('n_visits', 'n_episodes', 'n_revisits', 'n_fixations'):
            if col in df_.columns and df_[col].notna().any():
                row[f'{col}_mean'] = float(df_[col].mean())
        if 'n_revisits' in df_.columns and df_['n_revisits'].notna().any():
            row['share_revisited'] = float((df_['n_revisits'] > 0).mean())
        if 'rank' in df_.columns:
            row['n_rank_1'] = int((df_['rank'] == 1).sum())
        if 'time_to_first_fixation' in df_.columns:
            row['time_to_first_fixation_median'] = float(df_['time_to_first_fixation'].median())
        ls.append(row)
    df_sum = pd.DataFrame.from_records(ls)
    if len(df_sum):
        total = df_sum['dwell_sum'].sum()
        df_sum['share_of_total_dwell'] = df_sum['dwell_sum'] / total if total > 0 else np.nan
    return df_sum


def stimulus_sequence(df_episodes, sep=' > '):
    """Per participant: the stimuli in the order of their episodes, as one string, plus counts."""
    ls = []
    for subj, df_ in df_episodes.sort_values('episode_no').groupby('participant', sort=False):
        ls.append({'participant': subj, 'sequence': sep.join(df_['stimulus'].astype(str)),
                   'n_episodes': int(len(df_)), 'n_stimuli': int(df_['stimulus'].nunique()),
                   'n_revisits': int(df_['revisit'].sum())})
    return pd.DataFrame.from_records(ls)


def session_summary(df_visits, df_episodes=None, df_events=None, roster=None):
    """Per participant: span on the recording clock from first to last mapped fixation, mapped time, stimuli, visits, revisits.

    span_s is the time between the first and the last fixation mapped on any stimulus of this dataset, mapped_s the
    union of the visit spans inside it (so unmapped_s is the time spent looking elsewhere, including walking).
    Logged events (participant, event, t_abs_ms from load_prolab_intervals) add one column per event name with
    its time in seconds, and event_span_s from the earliest to the latest event."""
    ls = []
    df_v = df_visits.dropna(subset=['t_start_s']) if has_clock(df_visits) else df_visits.iloc[0:0]
    for subj, df_ in df_visits.groupby('participant', sort=False):
        row = {'participant': subj, 'n_stimuli': int(df_['stimulus'].nunique()), 'n_visits': int(len(df_)),
               'n_fixations': int(df_['n_fixations'].sum()), 'dwell_s': float(df_['dwell_s'].sum())}
        df_c = df_v[df_v['participant'] == subj]
        if len(df_c):
            start, end = df_c['t_start_s'].to_numpy(dtype=float), df_c['t_end_s'].to_numpy(dtype=float)
            row.update({'first_s': float(start.min()), 'last_s': float(end.max()),
                        'span_s': float(end.max() - start.min()), 'mapped_s': float(merged_span(start, end))})
            row['unmapped_s'] = row['span_s'] - row['mapped_s']
        ls.append(row)
    df_sum = pd.DataFrame.from_records(ls)
    if df_episodes is not None and len(df_episodes):
        rev = df_episodes.groupby('participant')['revisit'].sum()
        df_sum['n_revisits'] = df_sum['participant'].map(rev).fillna(0).astype(int)
    if df_events is not None and len(df_events):
        wide = df_events.pivot_table(index='participant', columns='event', values='t_abs_ms', aggfunc='min') / 1000.
        wide.columns = [f"event_{c}_s" for c in wide.columns]
        wide['event_span_s'] = (wide.max(axis=1) - wide.min(axis=1)).where(wide.notna().sum(axis=1) >= 2)
        df_sum = df_sum.merge(wide.reset_index(), on='participant', how='left')
    if roster is not None:
        missing = [s for s in roster if s not in set(df_sum['participant'])]
        if missing:
            df_zero = pd.DataFrame({'participant': missing, 'n_stimuli': 0, 'n_visits': 0, 'n_fixations': 0, 'dwell_s': 0.})
            df_sum = pd.concat([df_sum, df_zero], ignore_index=True)
    order = {s: i for i, s in enumerate(natural_sorted(df_sum['participant'].unique()))}
    return df_sum.sort_values('participant', key=lambda s: s.map(order)).reset_index(drop=True)


def merged_span(start, end):
    """Total length covered by the union of the intervals [start, end)."""
    idx = np.argsort(start)
    total, cur_s, cur_e = 0., None, None
    for s, e in zip(start[idx], end[idx]):
        if cur_e is None or s > cur_e:
            if cur_e is not None:
                total += cur_e - cur_s
            cur_s, cur_e = s, e
        else:
            cur_e = max(cur_e, e)
    if cur_e is not None:
        total += cur_e - cur_s
    return total


def stimulus_palette(stimuli):
    """Dict stimulus -> RGBA (tab20 cycle)."""
    palette = plt.get_cmap('tab20')
    return {stim: palette(i % 20) for i, stim in enumerate(stimuli)}


def show_visit_timeline(ax, df_visits, subjects=None, stimuli=None, colors=None, relative=True, df_events=None,
                        row_height=0.8, highlight=None):
    """Timeline: one row per participant, every visit a bar on the recording clock, coloured by stimulus.

    relative=True starts every participant at their first mapped fixation. Logged events are drawn as ticks.
    `highlight` names one stimulus whose bars are drawn opaque while the others fade."""
    assert has_clock(df_visits), "the timeline needs the recording clock (t_start_s)"
    df_ = df_visits.dropna(subset=['t_start_s']).copy()
    if subjects is None:
        subjects = natural_sorted(df_['participant'].unique())
    if stimuli is None:
        stimuli = natural_sorted(df_['stimulus'].unique())
    if colors is None:
        colors = stimulus_palette(stimuli)
    df_ = df_[df_['participant'].isin(subjects)]
    offset = df_.groupby('participant')['t_start_s'].transform('min') if relative else 0.
    if df_events is not None and len(df_events) and relative:
        first = df_.groupby('participant')['t_start_s'].min()
        df_events = df_events.assign(t_s=df_events['t_abs_ms'] / 1000. - df_events['participant'].map(first))
    elif df_events is not None and len(df_events):
        df_events = df_events.assign(t_s=df_events['t_abs_ms'] / 1000.)
    row_of = {subj: i for i, subj in enumerate(subjects)}
    rows = df_['participant'].map(row_of).to_numpy(dtype=float)
    x0 = (df_['t_start_s'] - offset).to_numpy(dtype=float)
    x1 = (df_['t_end_s'] - offset).to_numpy(dtype=float)
    y0, y1 = rows - row_height / 2, rows + row_height / 2
    verts = np.stack([np.column_stack([x0, y0]), np.column_stack([x1, y0]),
                      np.column_stack([x1, y1]), np.column_stack([x0, y1])], axis=1)
    rgba = np.array([colors.get(s, (0.5, 0.5, 0.5, 1.)) for s in df_['stimulus']], dtype=float)
    if highlight is not None:
        rgba[df_['stimulus'].to_numpy() != highlight, 3] = 0.25
    ax.add_collection(PolyCollection(verts, facecolors=rgba, edgecolors='none'))
    if df_events is not None and len(df_events):
        df_e = df_events[df_events['participant'].isin(row_of)]
        ax.scatter(df_e['t_s'], df_e['participant'].map(row_of), marker='|', s=60, color='white', zorder=3, lw=1.)
    x_max = float(np.nanmax(x1)) if len(x1) else 1.
    if df_events is not None and len(df_events) and len(df_events[df_events['participant'].isin(row_of)]):
        x_max = max(x_max, float(df_events[df_events['participant'].isin(row_of)]['t_s'].max()))
    ax.set_xlim(min(0., float(np.nanmin(x0)) if len(x0) else 0.), x_max * 1.02)
    if len(subjects) <= 40:
        ax.set_yticks(range(len(subjects)))
        ax.set_yticklabels([str(s) for s in subjects], fontsize=7 if len(subjects) > 30 else 9)
    else:
        step = 10 if len(subjects) <= 200 else 25
        ax.set_yticks(range(0, len(subjects), step))
        ax.set_yticklabels([str(subjects[i]) for i in range(0, len(subjects), step)], fontsize=7)
        ax.set_ylabel(f"participants ({len(subjects)})")
    ax.set_ylim(len(subjects) - 0.4, -0.6)
    ax.set_xlabel("Time since the first mapped fixation (s)" if relative else "Recording time (s)")
    handles = [Patch(color=colors[s], label=s) for s in stimuli]
    if df_events is not None and len(df_events):
        handles.append(plt.Line2D([], [], marker='|', color='white', ls='none', label='logged event'))
    ax.legend(handles=handles, loc='upper left', bbox_to_anchor=(1.01, 1.), fontsize=7, frameon=False)
    return df_


if __name__ == '__main__':
    pass
