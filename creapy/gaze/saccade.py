import itertools
import matplotlib.pyplot as plt
import shapely
import pandas as pd
import numpy as np
from tqdm import tqdm
from heatmatch import make_orientation_field, Heatmap, compute_similarity

from creapy.gaze.base import StimulusGaze
from creapy.similarity.heatmatch_result import HeatMatchSimilarityResult, HeatMatchSimilarityProfile


def report_progress(progress, done, total, text):
    """Forward (done, total, text) to a progress callback; a callback that returns False asks for an abort, which is
    raised as InterruptedError. Shared by the long loops below.
    """
    if progress(done, total, text) is False:
        raise InterruptedError("Computation cancelled.")


class SaccadeData(StimulusGaze):
    """Saccades of all participants on one stimulus image, each a line from (x0, y0) to (x1, y1) in pixels of the image
    array with y down (normalized_xy=True for Tobii's 0-1 positions). Column names come as parameters (sac_*_col,
    subj_index_col, optional trial_col). angles_360 holds the direction of each saccade in degrees as seen on screen
    (0 right, 90 up), angles_180 the orientation folded to [0, 180). Orientation fields and similarities are cached.
    """

    def __init__(self, df_stim, path_to_stim,
                 sac_x0_col, sac_y0_col, sac_x1_col, sac_y1_col, sac_t_col, sac_amp_col,
                 subj_index_col,
                 t_min=0, t_max=None, interpolation_grid=(200, 200), interpolation_step=0.01, sigma=5,
                 trial_col=None, img=None, scale=1., normalized_xy=False, time_unit=None,
                 **kwargs):
        df_stim = df_stim.copy()
        for col in [sac_x0_col, sac_y0_col, sac_x1_col, sac_y1_col]:
            df_stim[col] = pd.to_numeric(df_stim[col], errors='coerce')
        df_stim = df_stim.dropna(subset=[sac_x0_col, sac_y0_col, sac_x1_col, sac_y1_col])
        super().__init__(df_stim=df_stim,
                         path_to_stim=path_to_stim,
                         subj_index_col=subj_index_col,
                         t_col=sac_t_col,
                         v_col=sac_amp_col,
                         t_min=t_min,
                         t_max=t_max,
                         interpolation_grid=interpolation_grid,
                         interpolation_step=interpolation_step,
                         sigma=sigma,
                         trial_col=trial_col,
                         img=img, scale=scale, time_unit=time_unit)
        # bring the coordinates onto the (possibly downscaled) image array, as FixationData does
        if normalized_xy:
            for col, size in [(sac_x0_col, self.width), (sac_x1_col, self.width), (sac_y0_col, self.height), (sac_y1_col, self.height)]:
                self.df[col] = self.df[col] * size
        elif self.scale != 1.:
            for col in [sac_x0_col, sac_y0_col, sac_x1_col, sac_y1_col]:
                self.df[col] = self.df[col] * self.scale
        self.mapping = {'sac_x0_col': sac_x0_col, 'sac_y0_col': sac_y0_col, 'sac_x1_col': sac_x1_col,
                        'sac_y1_col': sac_y1_col, 'sac_t_col': sac_t_col, 'sac_amp_col': sac_amp_col,
                        'subj_index_col': subj_index_col, 'trial_col': self.trial_col}

        self.sac_x0 = self.df[sac_x0_col].astype(float)
        self.sac_y0 = self.df[sac_y0_col].astype(float)
        self.sac_x1 = self.df[sac_x1_col].astype(float)
        self.sac_y1 = self.df[sac_y1_col].astype(float)
        # print(self.df[[sac_x0_col, sac_y0_col, sac_x1_col, sac_y1_col]].head(10).to_string())
        self.sac_lines = shapely.linestrings(np.dstack([
            [self.sac_x0, self.sac_y0],
            [self.sac_x1, self.sac_y1]
        ]).transpose(1, 2, 0))
        # print(self.sac_lines)

        self.sac_amp = self.v

        # For rose plots:
        self.angles_360 = SaccadeData.__compute_angles(self.sac_lines)
        self.angles_180 = np.mod(self.angles_360, 180)

        # For heatmap generation
        self._onset = np.column_stack([np.asarray(self.sac_x0, dtype=float),
                                       np.asarray(self.sac_y0, dtype=float)])
        self._offset = np.column_stack([np.asarray(self.sac_x1, dtype=float),
                                        np.asarray(self.sac_y1, dtype=float)])
        self._points = np.column_stack([self.xi.ravel(), self.yi.ravel()])
        self._field_cache: dict = {}  # sigma -> OrientationField

        self._heatmap_cache: dict = {}  # sigma -> Heatmap

        self._subject_field_cache: dict = {}  # sigma -> {subj -> OrientationField}

        self._similarity_cache: dict = {}  # (sigma, density_coherence_tradeoff) -> HeatMatchSimilarityResult

        self._profile_cache: dict = {}  # (window, step, sigma, tradeoff, min_saccades) -> HeatMatchSimilarityProfile

    def subset(self, subjects=None, t_range=None):
        """A new SaccadeData with only the selected participants (iterable of ids) and/or time window t_range=(t0, t1)
        in seconds. Orientation fields are recomputed lazily. Asserts that at least one saccade remains.
        """
        mask = self.subset_rows(subjects=subjects, t_range=t_range)
        assert mask.any(), "The selection leaves no saccades."
        df_ = self.df[mask].copy()
        df_[self.t_col] = self.t[mask].to_numpy()  # already in seconds, relative to the trial start
        return SaccadeData(df_, self.path_to_stim, img=self.img, scale=1., t_min=self.t_min, t_max=self.t_max,
                           time_unit='s', **self.mapping)  # df_ already holds array pixels and seconds

    def participant_stats(self):
        """One row per participant. Columns: participant, n_saccades, mean_saccade_amplitude and
        median_saccade_amplitude (table unit, usually px or degrees), saccade_rate_per_s, horizontal_share (fraction of
        saccades within 45 degrees of horizontal). Sorted in natural participant order.
        """
        ls = []
        for subj, df_subj in self.df.groupby(self.subj_index_col, sort=False):
            amp = self.sac_amp[df_subj.index]
            ls.append({'participant': subj,
                       'n_saccades': int(len(df_subj)),
                       'mean_saccade_amplitude': float(amp.mean()),
                       'median_saccade_amplitude': float(amp.median()),
                       'saccade_rate_per_s': float(len(df_subj) / max(self.t[df_subj.index].max() - self.t[df_subj.index].min(), 1e-9)),
                       'horizontal_share': float(np.mean(np.minimum(self.angles_180[df_subj.index.to_numpy()],
                                                                     180 - self.angles_180[df_subj.index.to_numpy()]) < 45))})
        df_stats = pd.DataFrame.from_records(ls)
        df_stats['participant'] = pd.Categorical(df_stats['participant'], categories=self.subjects, ordered=True)
        return df_stats.sort_values('participant').reset_index(drop=True)

    def visualize_scanpaths(self, ax, color=(1, 1, 0), alpha=1., width=1, ooi=None, stimulus_alpha=1., grayscale=False):
        """Draw every saccade as an arrow over the stimulus in ax (one quiver call). color is an RGB tuple, width scales
        the arrow thickness. ooi, an orientation of interest in degrees (0 horizontal, 90 vertical), fades saccades of
        other orientations: alpha is multiplied by a sigmoid of the angular similarity. Nothing is returned.
        """
        self.plot_setup(ax, stimulus_alpha=stimulus_alpha, bw=grayscale)

        x0 = np.asarray(self.sac_x0)
        x1 = np.asarray(self.sac_x1)
        y0 = np.asarray(self.sac_y0)
        y1 = np.asarray(self.sac_y1)

        # Direction vectors for quiver
        u = x1 - x0
        v = y1 - y0

        if ooi is not None:
            diff = np.abs(((self.angles_180 - ooi + 90) % 180) - 90)
            angular_similarity = 1 - (diff / 90.)
            alpha = self.__nonlinearity(angular_similarity) * alpha

        # Use alpha from weights by making an RGBA array
        # base color = yellow = (1, 1, 0), then add alpha from weights
        colors = np.ones((len(u), 4))
        colors[:, 0], colors[:, 1], colors[:, 2] = color
        colors[:, 3] = alpha

        # Turn off autoscaling updates while adding lots of artists
        ax.autoscale(False)

        # Single fast call to draw all arrows
        ax.quiver(
            x0.ravel(), y0.ravel(),
            u.ravel(), v.ravel(),
            angles="xy",
            scale_units="xy",
            scale=1,
            pivot="tail",
            color=colors,
            width=0.0005 * width,
            headwidth=1.2 * width,
            headlength=1.6 * width,
            headaxislength=1.4 * width,
            minlength=0,  # don’t drop short arrows
        )

        # for i in np.random.choice(range(len(u)), 5):
        #     ax.scatter(self.sac_x0[i], self.sac_y0[i], s=10, color='red')
        #     ax.plot([self.sac_x0[i], self.sac_x1[i]], [self.sac_y0[i], self.sac_y1[i]], color='black')
        #     ax.scatter(self.sac_x1[i], self.sac_y1[i], s=10, color='blue')
        #     ax.text(self.sac_x1[i], self.sac_y1[i], self.angles_180[i])

    def make_heatmap(self, ax, alpha, sigma, cmap='coolwarm', ooi=90, quantile=0.8, degree=2,
                     stimulus_alpha=1, grayscale=False):
        """HeatMatch orientation heatmap (Long et al. 2026) over the stimulus in ax. sigma is the kernel width in pixels
        of the image array; ooi is the orientation painted warm, in degrees as seen on screen (90 = vertical), the cool
        end of cmap goes to the perpendicular one; alpha is the base opacity, quantile and degree shape how quickly low
        density fades out. Slow on big datasets; the field is cached per sigma (see prepare_heatmap).
        """
        self.plot_setup(ax, stimulus_alpha=stimulus_alpha, bw=grayscale)
        # ooi here is the visual (y-up) orientation to paint warm, like the GUI dial
        # and visualize_scanpaths. heatmatch anchors its ooi at the cool end and
        # measures angles in image (y-down) coordinates: (90 - ooi) converts both.
        self._get_heatmap(sigma).draw(ax, ooi=(90 - ooi) % 180, base_opacity=alpha,
                                       opacity_density_weight=0.8,
                                       cmap=cmap, degree=degree, quantile=quantile)

    def _get_heatmap(self, sigma):
        if sigma not in self._heatmap_cache:
            self.get_circular_weighted_stats(sigma)  # populates _field_cache
            self._heatmap_cache[sigma] = Heatmap(self._field_cache[sigma], self.width, self.height)
        return self._heatmap_cache[sigma]


    def __nonlinearity(self, xx, quantile=0.8, degree=2, eps=1e-12):
        center = np.quantile(xx, quantile)
        xx = np.clip(xx, eps, 1 - eps)
        xx = 1 / (1 + (center * (1 - xx) / (1 - center) / xx) ** degree)
        return xx


    def get_circular_weighted_stats(self, sigma):
        """The orientation field behind the saccade heatmap, computed by heatmatch with kernel width sigma in pixels and
        cached per sigma. Returns three flat arrays over the interpolation grid (reshape with self.xi.shape): mean
        orientation in degrees [0, 180) in image (y-down) coordinates, 0 where nothing is in reach; coherence R in
        [0, 1]; density rho (sums to 1).
        """
        if sigma not in self._field_cache:
            self._field_cache[sigma] = make_orientation_field(
                self._points, self._onset, self._offset,
                sigma=float(sigma), grid_shape=self.xi.shape
            )
        field = self._field_cache[sigma]
        angles_180 = np.where(np.isnan(field.omega_mean), 0.0, np.degrees(field.omega_mean))
        return angles_180, field.R, field.rho

    @staticmethod
    def __compute_angles(sac_lines):
        coords = shapely.get_coordinates(sac_lines).reshape(-1, 2, 2)

        # Compute delta x and y
        dx = coords[:, 1, 0] - coords[:, 0, 0]
        dy = coords[:, 1, 1] - coords[:, 0, 1]

        # Compute angle in radians, convert to degrees
        angles_rad = np.arctan2(-dy, dx) # flip y to get y-up angles
        angles_deg = np.degrees(angles_rad)

        # Normalize to [0, 360)
        angles_deg = np.mod(angles_deg, 360)
        return angles_deg

    def make_rose_plot(self, bins=36, title=None, ax=None, rays=True, num=False, hull=True, hull_args=None,
                       cmap='GnBu', center_symmetric=False, subjects=None):
        """Rose diagram of saccade directions in `bins` bins over 360 degrees, every participant weighted equally, bar
        height = share of saccades (sums to 1); rays, num and hull toggle bars, percent labels and outline. ax must be a
        polar axes when given, otherwise a figure is made and shown. center_symmetric=True folds directions onto
        orientations. Returns (xx, yy): bin centres in degrees (0 right, 90 up) and the share per bin.
        """
        cmap = plt.get_cmap(cmap)
        xx, yy = self.__circular_histogram(bins, center_symmetric=center_symmetric, subjects=subjects)
        x_angles_rad = np.radians(xx)
        show = ax is None
        if ax is None:
            fig, ax = plt.subplots(subplot_kw={'projection': 'polar'})
        if rays:
            y_min, y_max = min(yy), max(yy)
            color = [cmap((y - y_min) / (y_max - y_min)) for y in yy]
            ax.bar(x_angles_rad, yy, width=2 * np.pi / bins, bottom=0.0, color=color, zorder=100)
        if num:
            for x, y in zip(x_angles_rad, yy):
                ax.text(x, y, f"{round(y * 100)}%", ha="center", va="center", zorder=1000)
        if hull:
            if hull_args is None:
                hull_args = {}
            ax.plot(np.append(x_angles_rad, [x_angles_rad[0]]), np.append(yy, [yy[0]]), zorder=200,
                    **hull_args)
        ax.set_xticks(np.radians([0, 45, 90, 135, 180, 225, 270, 315]))
        ax.set_xticklabels(["Right", "", "Top", "", "Left", "", "Bottom", ""])
        ax.set_yticklabels([])
        if title:
            ax.set_title(title, weight="bold", loc="left")
        if show:
            plt.show()
        return xx, yy

    def __circular_histogram(self, bins, center_symmetric=False, subjects=None):
        mask = self.subset_rows(subjects=subjects)
        weights_ = np.asarray(self.weights_simple, dtype=float)[mask]
        weights_ = weights_ / weights_.sum() * mask.sum() / len(mask) if mask.sum() else weights_
        if center_symmetric:
            angles_ = self.angles_180[mask].copy()
            assert max(angles_) < 180
            angles_ = np.concatenate((angles_, angles_ + 180))
            weights = np.concatenate((weights_, weights_))
        else:
            angles_ = self.angles_360[mask].copy()
            weights = weights_
        bin_width = 360 / bins
        half_bin_width = bin_width / 2
        angles_[angles_ >= 360 - half_bin_width] -= 360
        yy_, xx_ = np.histogram(angles_, bins=bins, range=(-half_bin_width, 360 - half_bin_width),
                                weights=weights, density=True)
        xx = (xx_[:-1] + xx_[1:]) / 2
        yy = yy_ * bin_width
        return xx, yy

    def compute_heatmatch_similarity(self, sigma=50, density_coherence_tradeoff=0.5, verbose=True, progress=None):
        """Pairwise HeatMatch similarity (Long et al. 2026) between all participants, self-pairs included. sigma is the
        kernel width in pixels, density_coherence_tradeoff in [0, 1] weights the directional score by density (1) or
        coherence (0). Returns a HeatMatchSimilarityResult over s_loc/s_dir, cached per (sigma, tradeoff).
        progress(done, total, text) is an optional callback; returning False aborts with InterruptedError (GUI cancel).
        """
        key = (sigma, density_coherence_tradeoff)
        if key not in self._similarity_cache:
            fields = self._get_subject_fields(sigma, verbose=verbose, progress=progress)
            combos = list(itertools.combinations_with_replacement(fields, 2))
            ls = []
            for i, (subj_a, subj_b) in enumerate(tqdm(combos, desc="Computing pairwise similarities", disable=not verbose)):
                if progress is not None and i % 50 == 0:
                    report_progress(progress, i, len(combos), "pairwise similarities")
                sim = compute_similarity(fields[subj_a], fields[subj_b],
                                         density_coherence_tradeoff=density_coherence_tradeoff)
                ls.append({'subject_a': subj_a, 'subject_b': subj_b, 's_loc': sim.s_loc, 's_dir': sim.s_dir})
            self._similarity_cache[key] = HeatMatchSimilarityResult(pd.DataFrame.from_records(ls))
        return self._similarity_cache[key]

    def compute_heatmatch_similarity_profile(self, window=None, step=None, sigma=50,
                                             density_coherence_tradeoff=0.5, min_saccades=3, verbose=True,
                                             progress=None):
        """Sliding-window HeatMatch similarity: pairwise s_loc/s_dir per time window, i.e. viewer synchrony over time.
        window and step in seconds (defaults: a third of the viewing time, half a window); participants with fewer than
        min_saccades saccades in a window are left out of it. Returns a HeatMatchSimilarityProfile with columns
        t_center, subject_a, subject_b, s_loc, s_dir, cached per parameter set; progress as in
        compute_heatmatch_similarity.
        """
        if window is None:
            window = (self.t_max - self.t_min) / 3
        if step is None:
            step = window / 2
        key = (window, step, sigma, density_coherence_tradeoff, min_saccades)
        if key not in self._profile_cache:
            t_starts = np.arange(self.t_min, self.t_max - window + step / 2, step)
            assert len(t_starts) > 0, "The window is larger than the viewing time!"
            subjects = list(self.subjects)
            subj_masks = {subj: (self.subj_index == subj).to_numpy() for subj in subjects}
            ls = []
            for w_idx, t0 in enumerate(tqdm(t_starts, desc="Sliding-window similarity", disable=not verbose)):
                if progress is not None:
                    report_progress(progress, w_idx, len(t_starts), "time windows")
                in_window = ((self.t >= t0) & (self.t < t0 + window)).to_numpy()
                fields = {}
                for subj in subjects:
                    mask = in_window & subj_masks[subj]
                    if mask.sum() >= min_saccades:
                        fields[subj] = make_orientation_field(self._points, self._onset[mask], self._offset[mask],
                                                              sigma=float(sigma), grid_shape=self.xi.shape)
                for subj_a, subj_b in itertools.combinations(fields, 2):
                    sim = compute_similarity(fields[subj_a], fields[subj_b],
                                             density_coherence_tradeoff=density_coherence_tradeoff)
                    ls.append({'t_center': t0 + window / 2, 'subject_a': subj_a, 'subject_b': subj_b,
                               's_loc': sim.s_loc, 's_dir': sim.s_dir})
            if not ls:
                raise ValueError("No pair of participants has enough saccades in any time window "
                                 f"(min_saccades={min_saccades}); use fewer windows or more participants.")
            self._profile_cache[key] = HeatMatchSimilarityProfile(pd.DataFrame.from_records(ls), window=window)
        return self._profile_cache[key]

    def _get_subject_fields(self, sigma, verbose=True, progress=None):
        if sigma not in self._subject_field_cache:
            fields = {}
            for i, subj in enumerate(tqdm(self.subjects, desc="Computing orientation fields",
                                          disable=not verbose)):
                if progress is not None:
                    report_progress(progress, i, len(self.subjects), "orientation fields")
                mask = (self.subj_index == subj).to_numpy()
                fields[subj] = make_orientation_field(self._points, self._onset[mask], self._offset[mask],
                                                      sigma=float(sigma), grid_shape=self.xi.shape)
            self._subject_field_cache[sigma] = fields
        return self._subject_field_cache[sigma]

    def prepare_heatmap(self, sigma):
        """Compute the orientation field for `sigma` (pixels) into the cache without drawing, callable from a worker
        thread; make_heatmap with the same sigma is then quick.
        """
        self._get_heatmap(sigma)

    # Legacy grid-based saccade similarity (compute_grid_based_saccade_similarity,
    # visualize_saccade_dominance_in_grid) retired 2026-09-04: superseded by
    # compute_heatmatch_similarity above (HeatMatch is canonical for saccade similarity).
