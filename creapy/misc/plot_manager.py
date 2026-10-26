import matplotlib.pyplot as plt
import numpy as np
from tqdm import tqdm
from creapy.gaze.fixation import FixationData


plt.rcParams['font.family'] = 'Arial Narrow'


class FixationDatasetPlotManager:
    """
    One FixationData per stimulus from a fixation table, for quick overview plots in a notebook.
    `datasets` maps the stimulus value (the image path) to its FixationData.
    """

    def __init__(self, df, stim_col, x_col, y_col, t_col, subj_col, duration_col):
        self.datasets = {}
        for path_to_stim, df_stim in tqdm(list(df.groupby(stim_col)), desc='Initialization'):
            dm = FixationData(df_stim, path_to_stim, fix_x_col=x_col, fix_y_col=y_col,
                                               fix_t_col=t_col, subj_index_col=subj_col, fix_dur_col=duration_col)
            self.datasets[path_to_stim] = dm

    def plot(self, which='heatmaps', layout='auto', **kwargs):
        """
        Show every stimulus at once. `which`: 'heatmaps' (fixation KDE) or 'duration' (fixation-duration curve
        over time). `layout`: 'single' (one figure per stimulus, stimulus image beside it), 'auto' (square grid),
        an int (that many columns) or 'overlay' (all duration curves in one axes, duration only). kwargs go to
        make_heatmap / make_v_curve_by_time. Figures are shown with plt.show() and closed afterwards.
        """
        assert which in ['heatmaps', 'duration']

        if isinstance(layout, str):
            assert layout in ['single', 'auto', 'overlay']
            if layout == 'overlay':
                assert which == 'duration'
        else:
            assert isinstance(layout, int)

        cmap = plt.get_cmap('tab10')

        if layout == 'single':
            for path_to_stim, dm in self.datasets.items():
                fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(10, 5))
                if which == 'heatmaps':
                    dm.plot_setup(ax0)
                    dm.make_heatmap(ax1, from_level=0, **kwargs)
                elif which == 'duration':
                    dm.make_v_curve_by_time(ax0=ax0, ax1=ax1, color=cmap(0), **kwargs)
                ax1.set_title(path_to_stim)
                fig.tight_layout()
                plt.show()
                plt.close()
        elif layout == 'overlay':
            fig, ax = plt.subplots(1, 1, figsize=(10, 5))
            for i, (path_to_stim, dm) in tqdm(list(enumerate(self.datasets.items())), desc=f'Generating {which} ...'):
                dm.make_v_curve_by_time(ax0=None, ax1=ax, color=cmap(i), **kwargs)
            plt.show()
            plt.close()
        else:
            if layout == 'auto':
                n_col = int(np.ceil(np.sqrt(len(self.datasets))))
                n_row = n_col
            else:
                n_col = int(layout)
                n_row = int(np.ceil(len(self.datasets) / n_col))
            fig, _ = plt.subplots(n_row, n_col, figsize=(5 * n_col, 5 * n_row),
                                  sharey='all' if (which == 'duration' and layout != 'single') else False)
            ax_idx = -1
            for ax_idx, (path_to_stim, dm) in tqdm(list(enumerate(self.datasets.items())),
                                                   desc=f'Generating {which} ...'):
                ax = fig.axes[ax_idx]
                if which == 'heatmaps':
                    dm.make_heatmap(ax, **kwargs)
                elif which == 'duration':
                    dm.make_v_curve_by_time(ax0=None, ax1=ax, color=cmap(0), **kwargs)
                ax.set_title(path_to_stim)
            for ax in fig.axes[ax_idx + 1:]:
                ax.remove()
            fig.tight_layout()
            plt.show()
            plt.close()