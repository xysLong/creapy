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
    """Forward (done, total, text) to a progress callback; a callback that returns False asks for an abort."""
    if progress(done, total, text) is False:
        raise InterruptedError("Computation cancelled.")


class SaccadeData(StimulusGaze):
    """Saccades of all participants on one stimulus image, each a line from (x0, y0) to (x1, y1)."""

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
        self.sac_lines = shapely.linestrings(np.dstack([
            [self.sac_x0, self.sac_y0],
            [self.sac_x1, self.sac_y1]
        ]).transpose(1, 2, 0))

        self.sac_amp = self.v

        self.angles_360 = SaccadeData.__compute_angles(self.sac_lines)
        self.angles_180 = np.mod(self.angles_360, 180)

        self._onset = np.column_stack([np.asarray(self.sac_x0, dtype=float),
                                       np.asarray(self.sac_y0, dtype=float)])
        self._offset = np.column_stack([np.asarray(self.sac_x1, dtype=float),
                                        np.asarray(self.sac_y1, dtype=float)])
        self._points = np.column_stack([self.xi.ravel(), self.yi.ravel()])
        self._field_cache: dict = {}

        self._heatmap_cache: dict = {}

        self._subject_field_cache: dict = {}

        self._similarity_cache: dict = {}

        self._profile_cache: dict = {}

    def subset(self, subjects=None, t_range=None):
        """A new SaccadeData with only the selected participants and/or time window."""
        mask = self.subset_rows(subjects=subjects, t_range=t_range)
        assert mask.any(), "The selection leaves no saccades."
        df_ = self.df[mask].copy()
        df_[self.t_col] = self.t[mask].to_numpy()
        return SaccadeData(df_, self.path_to_stim, img=self.img, scale=1., t_min=self.t_min, t_max=self.t_max,
                           time_unit='s', **self.mapping)

    def participant_stats(self):
        """One row per participant."""
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
        """Draw every saccade as an arrow over the stimulus in ax (one quiver call)."""
        self.plot_setup(ax, stimulus_alpha=stimulus_alpha, bw=grayscale)

        x0 = np.asarray(self.sac_x0)
        x1 = np.asarray(self.sac_x1)
        y0 = np.asarray(self.sac_y0)
        y1 = np.asarray(self.sac_y1)

        u = x1 - x0
        v = y1 - y0

        if ooi is not None:
            diff = np.abs(((self.angles_180 - ooi + 90) % 180) - 90)
            angular_similarity = 1 - (diff / 90.)
            alpha = self.__nonlinearity(angular_similarity) * alpha

        colors = np.ones((len(u), 4))
        colors[:, 0], colors[:, 1], colors[:, 2] = color
        colors[:, 3] = alpha

        ax.autoscale(False)

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
            minlength=0,
        )


    def make_heatmap(self, ax, alpha, sigma, cmap='coolwarm', ooi=90, quantile=0.8, degree=2,
                     stimulus_alpha=1, grayscale=False):
        """HeatMatch orientation heatmap (Long et al. 2026) over the stimulus in ax."""
        self.plot_setup(ax, stimulus_alpha=stimulus_alpha, bw=grayscale)
        self._get_heatmap(sigma).draw(ax, ooi=(90 - ooi) % 180, base_opacity=alpha,
                                       opacity_density_weight=0.8,
                                       cmap=cmap, degree=degree, quantile=quantile)

    def _get_heatmap(self, sigma):
        if sigma not in self._heatmap_cache:
            self.get_circular_weighted_stats(sigma)
            self._heatmap_cache[sigma] = Heatmap(self._field_cache[sigma], self.width, self.height)
        return self._heatmap_cache[sigma]


    def __nonlinearity(self, xx, quantile=0.8, degree=2, eps=1e-12):
        center = np.quantile(xx, quantile)
        xx = np.clip(xx, eps, 1 - eps)
        xx = 1 / (1 + (center * (1 - xx) / (1 - center) / xx) ** degree)
        return xx


    def get_circular_weighted_stats(self, sigma):
        """The orientation field behind the saccade heatmap, computed by heatmatch with kernel width sigma."""
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

        dx = coords[:, 1, 0] - coords[:, 0, 0]
        dy = coords[:, 1, 1] - coords[:, 0, 1]

        angles_rad = np.arctan2(-dy, dx)
        angles_deg = np.degrees(angles_rad)

        angles_deg = np.mod(angles_deg, 360)
        return angles_deg

    def make_rose_plot(self, bins=36, title=None, ax=None, rays=True, num=False, hull=True, hull_args=None,
                       cmap='GnBu', center_symmetric=False, subjects=None):
        """Rose diagram of saccade directions in `bins` bins over 360 degrees, every participant weighted equally."""
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
        """Pairwise HeatMatch similarity (Long et al. 2026) between all participants, self-pairs included."""
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
        """Sliding-window HeatMatch similarity: pairwise s_loc/s_dir per time window."""
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
        """Compute the orientation field for `sigma` (pixels) into the cache without drawing."""
        self._get_heatmap(sigma)
