import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from creapy.aoi.aoi import AOI
from creapy.misc.utils import load_stimulus_image, seconds_from_table_time, natural_sorted


class StimulusGaze:
    """Shared base of FixationData and SaccadeData: one stimulus image plus the gaze events of all participants on it.
    Takes the event table, the image path, the participant column and a time and a value column (fixation duration
    or saccade amplitude). Times are brought to seconds (time_unit 's', 'ms' or 'us'; guessed from the magnitudes
    when None) and, for recording-clock timestamps, counted from each participant's first event (see self.t).
    """

    def __init__(self, df_stim, path_to_stim, subj_index_col, t_col, v_col,
                 t_min=0, t_max=None, interpolation_grid=(100, 100), interpolation_step=0.01, sigma=5,
                 trial_col=None, img=None, scale=1., time_unit=None):

        # Essential data. Rows with a missing time or value are dropped (EyeLink writes '.', Tobii leaves
        # blanks) and the rest is sorted by time within each viewing, so the table may arrive in any order.
        df = df_stim.copy()
        df[t_col] = pd.to_numeric(df[t_col], errors='coerce')
        df[v_col] = pd.to_numeric(df[v_col], errors='coerce')
        keep = df[t_col].notna() & df[v_col].notna()
        self.n_dropped = int((~keep).sum())
        keys = [subj_index_col] + ([trial_col] if trial_col is not None and trial_col in df.columns else [])
        self.df = df[keep].sort_values(keys + [t_col], kind='stable').reset_index(drop=True)
        assert len(self.df) > 0, "No usable rows: every row lacks a time or a value."
        self.subj_index_col = subj_index_col
        self.t_col = t_col
        self.v_col = v_col
        self.trial_col = keys[1] if len(keys) > 1 else None
        self.subj_index = self.df[subj_index_col]
        self.subjects = natural_sorted(self.subj_index.unique())
        self.v = self.df[v_col]  # Can be Fixation Duration or Saccade Amplitude

        # EyeLink reports give times in ms, Tobii in ms or µs, but the whole temporal pipeline
        # (interpolation_step=0.01, sigma=5, the 5 s dashed curve tail) assumes seconds.
        if time_unit in ('s', 'ms', 'us'):
            factor = {'s': 1., 'ms': 1e3, 'us': 1e6}[time_unit]
            self.t, self.time_unit = self.df[t_col] / factor, time_unit
        else:
            self.t, self.time_unit = seconds_from_table_time(self.df[t_col])
        self.t = pd.Series(np.asarray(self.t, dtype=float), index=self.df.index)
        # Viewing time per participant counted from their own first event, so trials recorded at different
        # recording clocks (Tobii) share one time axis
        self.t_rel = self.t - self.t.groupby(self.subj_index.to_numpy()).transform('min')
        if self.t.min() > 60.:
            # recording-global clocks (Tobii, raw EyeLink timestamps): use the per-participant time instead
            self.t = self.t_rel

        # Load image (downscaled if huge; `scale` maps the table's pixel coordinates onto the array)
        self.path_to_stim = path_to_stim
        if img is not None:
            self.img, self.scale = img, scale
        else:
            self.img, self.scale = load_stimulus_image(path_to_stim)
        height, width = self.img.shape[:2]
        self.height = height
        self.width = width

        # Unified time scale
        if t_max is None:
            t_max = float(self.t.max())
        self.t_min = t_min
        self.t_max = t_max

        # For temporal curve:
        # Weighted such that each subject gets a total weight of 1.
        self.weights_simple = 1 / self.df.groupby(subj_index_col)[subj_index_col].transform('size')

        # For heatmap generation
        nx, ny = interpolation_grid
        xi = np.linspace(0, self.width, nx)
        yi = np.linspace(0, self.height, ny)
        xi, yi = np.meshgrid(xi, yi)
        self.xi = xi
        self.yi = yi

        # AOIs
        self.areas_of_interest = {}  # name -> AOI object
        # Duration / amplitude curve over time, computed on first use (a subset of 157 participants used to
        # pay ~1 s here before anything was drawn)
        self.cache_v_curve = {}
        self.interpolation_step = interpolation_step
        self.sigma = sigma

    def n_subjects(self):
        """Number of distinct participants in the table."""
        return len(self.subjects)

    def subset_rows(self, subjects=None, t_range=None):
        """Boolean row mask over self.df for a participant selection (any iterable of ids) and/or a time window
        t_range=(t0, t1) in seconds on the dataset's time axis self.t. Both bounds are inclusive; None means no filter.
        """
        mask = np.ones(len(self.df), dtype=bool)
        if subjects is not None:
            mask &= self.subj_index.isin(list(subjects)).to_numpy()
        if t_range is not None:
            t0, t1 = t_range
            mask &= (self.t.to_numpy() >= t0) & (self.t.to_numpy() <= t1)
        return mask

    def plot_setup(self, ax, include_stimulus=True, bw=False, stimulus_alpha=1.):
        """Draw the stimulus into ax as the background of a gaze plot: image pixel coordinates, y pointing down, no
        ticks. bw=True shows it in grayscale, include_stimulus=False a black canvas of the same size, stimulus_alpha
        fades it.
        """
        if include_stimulus:
            if bw:
                ax.imshow(np.mean(self.img[..., :3], axis=-1), cmap='gray', extent=[0, self.width, self.height, 0],
                          alpha=stimulus_alpha, vmin=0, vmax=255)
            else:
                ax.imshow(self.img, extent=[0, self.width, self.height, 0], alpha=stimulus_alpha)
        else:
            ax.imshow(np.zeros_like(self.img), extent=[0, self.width, self.height, 0])
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlim([0, self.width])
        ax.set_ylim([self.height, 0])

    def __compute_v_curve(self, interpolation_step, sigma):
        if (interpolation_step, sigma) not in self.cache_v_curve:
            t_new = np.arange(self.t_min, self.t_max + interpolation_step, interpolation_step)
            m, s = StimulusGaze.gaussian_smooth_irregular(t_new, self.t, self.v,
                                                          weights_subj=self.weights_simple,
                                                          sigma=sigma)
            self.cache_v_curve[(interpolation_step, sigma)] = (t_new, m, s)
        return self.cache_v_curve[(interpolation_step, sigma)]

    def make_v_curve_by_time(self, ax0, ax1, interpolation_step=0.01, sigma=5, n_std=0.05, t_valid=None,
                             color=None, label=None):
        """Plot the value (fixation duration or saccade amplitude) over viewing time into ax1: a Gaussian-smoothed mean
        (sigma and interpolation_step in seconds) with every participant weighted equally, plus a band of n_std standard
        deviations when 0 < n_std <= 1. The curve is dashed after t_valid (default: the last 5 s, where few participants
        still contribute). ax0, if not None, gets the stimulus image via plot_setup.
        """
        t_new, m, s = self.__compute_v_curve(interpolation_step, sigma)
        if t_valid is None:
            t_valid = max(self.t_min, self.t_max - 5.)
        if ax0 is not None:
            self.plot_setup(ax0)
        ax1.plot(t_new[t_new <= t_valid], m[t_new <= t_valid], color=color, label=label)
        ax1.plot(t_new[t_new > t_valid], m[t_new > t_valid], ls='dashed', color=color)
        if 0. < n_std <= 1.:
            ax1.fill_between(t_new, m - n_std * s, m + n_std * s, alpha=0.1, color=color)

    def set_top_down_aoi(self, name, geom):
        """Register a hand-drawn area of interest under `name`: geom is a shapely polygon in image array pixels
        (y down), e.g. AOI.rectangle(...).geom. An existing AOI of the same name is replaced.
        """
        self.areas_of_interest[name] = AOI(name=name, geom=geom)

    def remove_aoi(self, name):
        """Drop the AOI called `name`; unknown names are ignored."""
        self.areas_of_interest.pop(name, None)

    def show_all_aoi(self, ax=None):
        """Draw every registered AOI over the stimulus, one tab10 colour each. Without ax a new figure is created and
        shown with plt.show().
        """
        show = ax is None
        if ax is None:
            fig, ax = plt.subplots(1, 1, figsize=(5, 5))
        self.plot_setup(ax)  # type: ignore
        for i, (name, aoi) in enumerate(self.areas_of_interest.items()):
            aoi.show(ax, color=plt.get_cmap('tab10')(i % 10))
        if show:
            ax.figure.tight_layout()
            plt.show()

    @staticmethod
    def gaussian_smooth_irregular(t_new, t_old, v_old, weights_subj, sigma, chunk_size=512):
        """Gaussian-kernel smoothing of irregularly sampled values v_old at times t_old onto the grid t_new (sigma in
        the unit of t). weights_subj weights each sample (e.g. 1/n per participant so every viewer counts equally).
        Returns (m, s): weighted mean and weighted standard deviation per t_new point, NaN where no sample is in reach.
        """
        # Vectorized over chunks of t_new (one (chunk, n_samples) kernel matrix at a time,
        # so memory stays bounded); ~10x faster than the per-point loop it replaced.
        t_old = np.asarray(t_old, dtype=float)
        v_old = np.asarray(v_old, dtype=float)
        weights_subj = np.asarray(weights_subj, dtype=float)
        m = np.empty_like(t_new, dtype=float)
        s = np.empty_like(t_new, dtype=float)

        for start in range(0, len(t_new), chunk_size):
            tt = t_new[start:start + chunk_size, None]
            total_weights = np.exp(-0.5 * ((t_old[None, :] - tt) / sigma) ** 2) * weights_subj[None, :]
            weight_sums = total_weights.sum(axis=1, keepdims=True)
            with np.errstate(divide='ignore', invalid='ignore'):
                total_weights = np.where(weight_sums < 1e-12, np.nan, total_weights / weight_sums)
            mm = (total_weights * v_old[None, :]).sum(axis=1)
            ss = np.sqrt((total_weights * (v_old[None, :] - mm[:, None]) ** 2).sum(axis=1))
            m[start:start + chunk_size] = mm
            s[start:start + chunk_size] = ss

        return m, s
