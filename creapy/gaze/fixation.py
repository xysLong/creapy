import itertools
import matplotlib.patches as patches
import matplotlib.ticker as ticker
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import scipy as sp
import shapely
from creapy.aoi.aoi import AOI
from creapy.similarity.grid_fixation import FixationGrid
from creapy.gaze.base import StimulusGaze
from creapy.misc.utils import natural_sorted
from creapy.misc.contours import contour_levels, filled_contour_paths

plt.rcParams['font.family'] = ['Arial Narrow', 'Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif']


class FixationData(StimulusGaze):
    """Fixations of all participants on one stimulus image. Column names come as parameters (fix_x_col, fix_y_col,
    fix_t_col, fix_dur_col, subj_index_col, optional trial_col/pupil_col); coordinates end up in pixels of the image
    array with y down (normalized_xy=True for Tobii's 0-1 positions), durations stay in the table's unit (self.dur_unit,
    'ms' or 's', detected). Heatmaps weight fixations by duration and every participant equally; results are cached.
    """

    def __init__(self, df_stim, path_to_stim,
                 fix_x_col, fix_y_col, fix_t_col, fix_dur_col,
                 subj_index_col,
                 interpolation_grid=(100, 100), bw_method=0.1, num_levels=20,
                 t_min=0, t_max=None, interpolation_step=0.01, sigma=5,
                 trial_col=None, pupil_col=None, img=None, scale=1., normalized_xy=False, time_unit=None,
                 **kwargs):
        df_stim = df_stim.copy()
        for col in [fix_x_col, fix_y_col]:
            df_stim[col] = pd.to_numeric(df_stim[col], errors='coerce')
        df_stim = df_stim[df_stim[fix_x_col].notna() & df_stim[fix_y_col].notna()]
        super().__init__(df_stim=df_stim,
                         path_to_stim=path_to_stim,
                         subj_index_col=subj_index_col,
                         t_col=fix_t_col,
                         v_col=fix_dur_col,
                         t_min=t_min,
                         t_max=t_max,
                         interpolation_grid=interpolation_grid,
                         interpolation_step=interpolation_step,
                         sigma=sigma,
                         trial_col=trial_col,
                         img=img, scale=scale, time_unit=time_unit)
        self.mapping = {'fix_x_col': fix_x_col, 'fix_y_col': fix_y_col, 'fix_t_col': fix_t_col,
                        'fix_dur_col': fix_dur_col, 'subj_index_col': subj_index_col,
                        'trial_col': self.trial_col, 'pupil_col': pupil_col}
        self.pupil_col = pupil_col if pupil_col is not None and pupil_col in self.df.columns else None

        # Coordinates: Tobii metrics exports give 0–1 positions on the medium, tables give original-image pixels;
        # both are brought onto the (possibly downscaled) image array once, here. self.df keeps those values,
        # so subsets, conversions and exports all speak array pixels.
        if normalized_xy:
            self.df[fix_x_col] = self.df[fix_x_col] * self.width
            self.df[fix_y_col] = self.df[fix_y_col] * self.height
        elif self.scale != 1.:
            self.df[fix_x_col] = self.df[fix_x_col] * self.scale
            self.df[fix_y_col] = self.df[fix_y_col] * self.scale
        self.fix_x = self.df[fix_x_col].astype(float)
        self.fix_y = self.df[fix_y_col].astype(float)
        self.fix_xy = np.vstack([self.fix_x, self.fix_y])
        self.fix_points = shapely.points(self.fix_x, self.fix_y)
        self.fix_dur = self.v
        # Durations arrive in ms (EyeLink/Tobii reports) or s (preprocessed tables): a median above 5 means ms
        self.dur_unit = 'ms' if float(self.fix_dur.median()) > 5 else 's'
        outside = (self.fix_x < 0) | (self.fix_x > self.width) | (self.fix_y < 0) | (self.fix_y > self.height)
        self.n_outside = int(outside.sum())  # fixations off the stimulus image (kept, but worth reporting)

        # For heatmaps:
        # Weighted such that each subject gets a total weight of 1,
        # AND within that, fixations are weighted by their duration.
        self.weights_fd_adjusted = self.fix_dur / self.df.groupby(subj_index_col)[fix_dur_col].transform('sum')

        # Heatmap (KDE + contours) and AOI curves are computed on first use: the constructor used to run the
        # default KDE eagerly, which made every participant/group/time subset cost seconds on large datasets
        self.cache_heatmap_zi = {}  # bw_method -> zi
        self.cache_heatmap_contour = {}  # (bw_method, num_levels, vmax) -> contour paths
        self.cache_scanpath_similarity = {}  # (method, sorted kwargs) -> PairwiseSimilarityResult
        self.cache_aoi_percentage_curve = {}

    def subset(self, subjects=None, t_range=None):
        """A new FixationData with only the selected participants (iterable of ids) and/or time window t_range=(t0, t1)
        in seconds; AOIs are carried over. Cheap: the image is shared and the heatmap recomputed on demand.
        Asserts that at least one fixation remains.
        """
        mask = self.subset_rows(subjects=subjects, t_range=t_range)
        assert mask.any(), "The selection leaves no fixations."
        df_ = self.df[mask].copy()
        df_[self.t_col] = self.t[mask].to_numpy()  # already in seconds, relative to the trial start
        # df_ already holds array pixels, so neither the downscale factor nor the normalisation may be applied again
        sub = FixationData(df_, self.path_to_stim, img=self.img, scale=1., t_min=self.t_min, t_max=self.t_max,
                           time_unit='s', **self.mapping)
        sub.areas_of_interest = dict(self.areas_of_interest)
        return sub

    def __compute_heatmap_zi(self, bw_method):
        if bw_method not in self.cache_heatmap_zi:
            if self.fix_xy.shape[1] < 3 or np.linalg.matrix_rank(np.cov(self.fix_xy)) < 2:
                # a KDE needs a few distinct points; a single fixation gets a tiny Gaussian blob instead
                zi = np.zeros(self.xi.shape)
                for x, y, w in zip(self.fix_x, self.fix_y, self.weights_fd_adjusted):
                    zi += w * np.exp(-0.5 * (((self.xi - x) ** 2 + (self.yi - y) ** 2) / (0.05 * self.width) ** 2))
                self.cache_heatmap_zi[bw_method] = zi
            else:
                kernel_density_estimate = sp.stats.gaussian_kde(self.fix_xy, bw_method=bw_method,
                                                                weights=self.weights_fd_adjusted)
                self.cache_heatmap_zi[bw_method] = kernel_density_estimate(
                    np.vstack([self.xi.ravel(), self.yi.ravel()])).reshape(self.xi.shape)
        return self.cache_heatmap_zi[bw_method]

    def heatmap_max(self, bw_method=0.1):
        """Peak density of this dataset's heatmap for the given bw_method, i.e. the `vmax` to pass to make_heatmap of
        OTHER datasets (stimuli, groups, time windows) so that their colours mean the same thing.
        """
        return float(self.__compute_heatmap_zi(bw_method).max())

    def prepare_heatmap(self, bw_method=0.1, num_levels=20, vmax=None):
        """Run the expensive part of make_heatmap (KDE and contouring) into the cache without touching matplotlib, so
        it can be called from a worker thread; make_heatmap with the same bw_method, num_levels and vmax is then
        instant.
        """
        self.__compute_heatmap_contour(bw_method=bw_method, num_levels=num_levels, vmax=vmax)

    def __compute_heatmap_contour(self, bw_method, num_levels, vmax=None):
        # vmax=None: levels span this dataset's own density range (matplotlib's default, every heatmap is
        # normalised to its own maximum). vmax given: levels run from 0 to vmax, densities above saturate,
        # so several heatmaps share one colour scale.
        key = (bw_method, num_levels, vmax)
        if key not in self.cache_heatmap_contour:
            zi = self.__compute_heatmap_zi(bw_method)
            if vmax is None:
                levels = contour_levels(zi.min(), zi.max(), num_levels)
            else:
                assert vmax > 0
                levels = np.linspace(0, vmax, num_levels + 1)
                zi = np.minimum(zi, vmax * (1 - 1e-9))
            # contourpy instead of ax.contourf(...).get_paths(): identical polygons, no figure, thread-safe
            self.cache_heatmap_contour[key] = filled_contour_paths(self.xi, self.yi, zi, levels)
        return self.cache_heatmap_contour[key]

    def make_heatmap(self, ax, bw_method=0.1, num_levels=20, from_level=1, cmap='coolwarm', alpha=0.75,
                     scatter_color=(1, 1, 1), scatter_size=1, scatter_alpha=0.5, stimulus_alpha=1., grayscale=False,
                     vmax=None):
        """Duration-weighted fixation heatmap over the stimulus in ax: a Gaussian KDE (bw_method = scipy's bandwidth
        factor) cut into num_levels filled contours, levels below from_level left transparent, every participant with
        equal total weight. vmax (see heatmap_max) puts several heatmaps on one colour scale; without it colours are
        normalised to this dataset's own peak. Dots mark the fixations, sized by duration; scatter_size=0 hides them.
        """
        contour_paths = self.__compute_heatmap_contour(bw_method=bw_method, num_levels=num_levels, vmax=vmax)
        cmap = plt.get_cmap(cmap)
        self.plot_setup(ax, stimulus_alpha=stimulus_alpha, bw=grayscale)
        for i, path in enumerate(contour_paths):
            if i >= from_level:
                ax.add_patch(patches.PathPatch(path, facecolor=cmap(i / num_levels), alpha=alpha, edgecolor='none'))
        if scatter_alpha > 0 and scatter_size > 0:
            # marker area grows with the fixation duration in SECONDS (a 300 ms fixation at size 16 ≈ 5 pt²),
            # whatever unit the table uses
            dur_s = self.fix_dur / (1000. if self.dur_unit == 'ms' else 1.)
            ax.scatter(self.fix_x, self.fix_y, s=scatter_size * dur_s,
                       facecolor=scatter_color, edgecolor='none',
                       marker='o', alpha=scatter_alpha)

    def visualize_scanpath(self, ax, subjects=None, numbered=True, color=None, alpha=0.8, size=1.,
                           line_width=1.5, stimulus_alpha=1., grayscale=False, max_numbers=150):
        """The textbook scanpath in ax: fixation circles sized by duration, connected in viewing order. One participant
        gets one colour and fixation numbers (only first and last above max_numbers fixations); several participants
        get one tab10 colour each and no numbers. subjects defaults to all. Returns the list of participants drawn.
        """
        self.plot_setup(ax, stimulus_alpha=stimulus_alpha, bw=grayscale)
        if subjects is None:
            subjects = self.subjects
        subjects = [s for s in natural_sorted(subjects) if s in set(self.subjects)]
        palette = plt.get_cmap('tab10')
        many = len(subjects) > 1
        for i, subj in enumerate(subjects):
            mask = (self.subj_index == subj).to_numpy()
            xx = self.fix_x[mask].to_numpy()
            yy = self.fix_y[mask].to_numpy()
            dur = self.fix_dur[mask].to_numpy()
            c = palette(i % 10) if (color is None or many) else color
            dur_s = dur / (1000. if self.dur_unit == 'ms' else 1.)
            ax.plot(xx, yy, '-', color=c, alpha=alpha * 0.8, lw=line_width, zorder=2)
            # marker area proportional to the fixation duration: 300 ms -> ~60 pt² at size 1
            ax.scatter(xx, yy, s=size * (200 * dur_s + 8), facecolor=c,
                       edgecolor='white', linewidth=0.5, alpha=alpha, zorder=3)
            if numbered and not many and len(xx) <= max_numbers:
                fontsize = 7 if len(xx) <= 60 else 5
                for k, (x, y) in enumerate(zip(xx, yy), start=1):
                    ax.text(x, y, str(k), ha='center', va='center', fontsize=fontsize, color='black', zorder=4)
            elif numbered and not many:
                # too many fixations to number them all: mark the first and last instead
                ax.text(xx[0], yy[0], '1', ha='center', va='center', fontsize=8, color='black', zorder=4)
                ax.text(xx[-1], yy[-1], str(len(xx)), ha='center', va='center', fontsize=8, color='black', zorder=4)
        return subjects

    def set_bottom_up_aoi(self, bw_method=0.1, num_levels=20, from_level=1):
        """Data-driven AOI: the hot spots of the heatmap, i.e. the union of the contour levels from from_level upwards
        (same bw_method/num_levels as make_heatmap). Registers it under a name like '0.1_1/20' and returns that name.
        """
        contour_paths = self.__compute_heatmap_contour(bw_method=bw_method, num_levels=num_levels)
        name = f"{bw_method}_{from_level}/{num_levels}"
        self.areas_of_interest[name] = AOI(name=name, paths=contour_paths[from_level:])
        return name

    def __compute_aoi_percentage_curve(self, interpolation_step, sigma):
        # TODO: AOI caching is less straightforward
        if (interpolation_step, sigma) not in self.cache_aoi_percentage_curve:
            t_new = np.arange(self.t_min, self.t_max + interpolation_step, interpolation_step)
            name_to_ms = {}
            for name, aoi in self.areas_of_interest.items():
                are_in_aoi = aoi.contains(self.fix_points)
                name_to_ms[name] = self.gaussian_smooth_irregular(t_new, self.t, are_in_aoi,
                                                                  weights_subj=self.weights_fd_adjusted, sigma=sigma)
            self.cache_aoi_percentage_curve[(interpolation_step, sigma)] = (t_new, name_to_ms)
        else:
            t_new, name_to_ms = self.cache_aoi_percentage_curve[(interpolation_step, sigma)]
            for name, aoi in self.areas_of_interest.items():
                if name not in name_to_ms:
                    are_in_aoi = aoi.contains(self.fix_points)
                    name_to_ms[name] = self.gaussian_smooth_irregular(t_new, self.t, are_in_aoi,
                                                                      weights_subj=self.weights_fd_adjusted,
                                                                      sigma=sigma)
            # AOIs that were removed meanwhile
            for name in list(name_to_ms):
                if name not in self.areas_of_interest:
                    del name_to_ms[name]
            self.cache_aoi_percentage_curve[(interpolation_step, sigma)] = (t_new, name_to_ms)
        return self.cache_aoi_percentage_curve[(interpolation_step, sigma)]

    def make_aoi_percentage_curve(self, ax0, ax1, interpolation_step=0.01, sigma=5, n_std=0.05,
                                  color=None, names=None):
        """Plot into ax1 how the share of fixation time inside each AOI evolves over viewing time: Gaussian-smoothed
        (sigma and interpolation_step in seconds), fixations weighted by duration and every participant equally, with a
        band of n_std standard deviations when 0 < n_std <= 1. One curve per AOI (restrict with `names`), y axis in
        percent; ax0, if not None, gets the stimulus image. AOIs added or removed since the last call are picked up.
        """
        t_new, aoi_name_to_ms = self.__compute_aoi_percentage_curve(interpolation_step, sigma)
        if ax0 is not None:
            self.plot_setup(ax0)
        palette = plt.get_cmap('tab10')
        for i, (name, (m, s)) in enumerate(aoi_name_to_ms.items()):
            if names is not None and name not in names:
                continue
            c = color if (color is not None and len(aoi_name_to_ms) == 1) else palette(i % 10)
            ax1.plot(t_new, m, color=c, label=name)
            if 0. < n_std <= 1.:
                ax1.fill_between(t_new, m - n_std * s, m + n_std * s, alpha=0.1, color=c)
        ax1.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1, decimals=0))
        if len(aoi_name_to_ms) > 1:
            ax1.legend()

    def aoi_metrics(self, names=None):
        """The classic AOI table, one row per participant x AOI (all AOIs, or the given `names`). Columns: participant,
        aoi, n_fixations, n_visits (runs of consecutive fixations inside), revisits, dwell_time (sum of durations, table
        unit), dwell_share (of the participant's total), mean_fixation_duration, time_to_first_fixation (s, from the
        participant's first fixation), first_fixation_rank, aoi_area_share. Non-lookers get zeros and NaN latencies.
        """
        if names is None:
            names = list(self.areas_of_interest)
        total_dur = self.df.groupby(self.subj_index_col)[self.v_col].sum()
        order = self.df.groupby(self.subj_index_col).cumcount() + 1  # fixation rank within the participant
        ls = []
        for name in names:
            aoi = self.areas_of_interest[name]
            inside = aoi.contains(self.fix_points)
            df_ = pd.DataFrame({'subj': self.subj_index.to_numpy(), 'inside': inside,
                                'dur': self.fix_dur.to_numpy(), 't': self.t.to_numpy(), 'rank': order.to_numpy()})
            for subj in self.subjects:
                df_subj = df_[df_['subj'] == subj]
                hits = df_subj[df_subj['inside']]
                # a visit = a run of consecutive fixations inside the AOI (Pro Lab's "Visit"); revisits = returns
                inside_ = df_subj['inside'].to_numpy()
                n_visits = int(np.sum(inside_[1:] & ~inside_[:-1]) + (inside_[0] if len(inside_) else 0))
                ls.append({'participant': subj, 'aoi': name,
                           'n_fixations': int(len(hits)),
                           'n_visits': n_visits,
                           'revisits': max(n_visits - 1, 0),
                           'dwell_time': float(hits['dur'].sum()),
                           'dwell_share': float(hits['dur'].sum() / total_dur[subj]) if total_dur[subj] > 0 else np.nan,
                           'mean_fixation_duration': float(hits['dur'].mean()) if len(hits) else np.nan,
                           'time_to_first_fixation': float(hits['t'].min() - df_subj['t'].min()) if len(hits) else np.nan,
                           'first_fixation_rank': int(hits['rank'].min()) if len(hits) else np.nan,
                           'aoi_area_share': aoi.area() / (self.width * self.height)})
        return pd.DataFrame.from_records(ls)

    def participant_stats(self):
        """One row per participant with the usual descriptives. Columns: participant, n_fixations, viewing_time_s,
        mean_fixation_duration, median_fixation_duration, total_fixation_duration (table unit), scanpath_length_px,
        mean_x, mean_y, spread_px (image array pixels) and mean_pupil when a pupil column was mapped.
        Sorted in natural participant order.
        """
        ls = []
        for subj, df_subj in self.df.groupby(self.subj_index_col, sort=False):
            t = self.t[df_subj.index]
            dur = self.fix_dur[df_subj.index]
            xx = self.fix_x[df_subj.index].to_numpy()
            yy = self.fix_y[df_subj.index].to_numpy()
            row = {'participant': subj,
                   'n_fixations': int(len(df_subj)),
                   'viewing_time_s': float(t.max() - t.min() + dur.iloc[-1] / (1000. if self.dur_unit == 'ms' else 1.)),
                   'mean_fixation_duration': float(dur.mean()),
                   'median_fixation_duration': float(dur.median()),
                   'total_fixation_duration': float(dur.sum()),
                   'scanpath_length_px': float(np.sum(np.hypot(np.diff(xx), np.diff(yy)))),
                   'mean_x': float(np.mean(xx)), 'mean_y': float(np.mean(yy)),
                   'spread_px': float(np.sqrt(np.var(xx) + np.var(yy)))}
            if self.pupil_col is not None:
                row['mean_pupil'] = float(pd.to_numeric(df_subj[self.pupil_col], errors='coerce').mean())
            ls.append(row)
        df_stats = pd.DataFrame.from_records(ls)
        df_stats['participant'] = pd.Categorical(df_stats['participant'], categories=self.subjects, ordered=True)
        return df_stats.sort_values('participant').reset_index(drop=True)

    def compute_scanpath_similarity(self, method='multimatch', verbose=True, progress=None, **kwargs):
        """Pairwise scanpath similarity between all participants: method 'multimatch' (five scores), 'scanmatch' or
        'cross_recurrence'; extra kwargs go to the respective algorithm. Returns a PairwiseSimilarityResult (matrix,
        boxplot by group, permutation test, viewer map), cached per method and kwargs. progress(done, total, text) is
        an optional callback; returning False from it aborts with InterruptedError.
        """
        from creapy.similarity.scanpath import scanpath_similarity_table
        from creapy.similarity.heatmatch_result import PairwiseSimilarityResult
        from creapy.stats.recurrence import cross_recurrence_table
        key = (method, tuple(sorted(kwargs.items())))
        if key not in self.cache_scanpath_similarity:
            if method == 'cross_recurrence':
                df_sim = cross_recurrence_table(self, verbose=verbose, progress=progress, **kwargs)
            else:
                df_sim = scanpath_similarity_table(self, method=method, verbose=verbose, progress=progress, **kwargs)
            self.cache_scanpath_similarity[key] = PairwiseSimilarityResult(df_sim)
        return self.cache_scanpath_similarity[key]

    def compute_grid_based_fixation_similarity(self, grid_sizes=(7,), include_self=False):
        """Pairwise fixation similarity on an n x n grid over the image, duration-weighted and with equal weight per
        participant: a dict grid size (cells per side) -> PairwiseSimilarityResult, or just the result when a single
        grid size is given. include_self=True also includes each participant's comparison with themselves.
        """
        df_matchable = pd.DataFrame(
            {'subject': self.subj_index,
             'point': self.fix_points,
             'weight': self.weights_fd_adjusted}
        )
        results = {}
        for grid_size in grid_sizes:
            grid = FixationGrid(self.height, self.width, grid_size)
            results[grid_size] = grid.compute_pairwise_similarities(df_matchable, include_self)
        if len(grid_sizes) == 1:
            return results[grid_sizes[0]]
        return results
