import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np


def make_cyclic_colormap(base_cmap='coolwarm', n_points=256):
    """
    A colormap that runs through `base_cmap` and back again, so its start and end colour coincide - for
    orientations, where 0° and 180° are the same. Returns a ListedColormap with 2 * n_points - 2 colours.
    """
    # eea92e
    # 625792
    # base_cmap = sns.diverging_palette(220, 20, as_cmap=True)
    # base_cmap = sns.color_palette("vlag", as_cmap=True)
    base_cmap = plt.get_cmap(base_cmap)
    colors_forward = base_cmap(np.linspace(0, 1, n_points))
    colors_backward = base_cmap(np.linspace(1, 0, n_points))
    colors_cyclic = np.vstack((colors_forward[:-1], colors_backward[:-1]))
    cyclic_cmap = ListedColormap(colors_cyclic, name=f"{base_cmap}_cyclic")
    return cyclic_cmap